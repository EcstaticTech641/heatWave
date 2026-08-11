import abc
import os
import re
from typing import List, Tuple
import pdfplumber
from ..models.schemas import Event, Entry, RelayEntry, Swimmer, ValidationResult
from .validator import validate_parsed_events

# Regular Expressions for parsing variants
HYTEK_EVENT_RE = r"Event\s+(\d+)\s+(Girls|Boys|Men|Women|Mixed)\s+(.+?)\s+(\d+)\s+(Yard|Meter)\s+(Freestyle|Backstroke|Breaststroke|Butterfly|Individual Medley|Medley Relay|Free Relay)"
HYTEK_ATHLETE_RE = r"^\s*(\d+)\s+([A-Za-z\s,\.]+)\s+(\d{1,2})\s+([A-Z0-9\-]+)\s+(\d{1,2}:\d{2}\.\d{2}|\d{2}\.\d{2}|NT)"

TEAMUNIFY_EVENT_RE = r"(?:Event|#)\s*(\d+)\s+(Girls|Boys|Men|Women|Mixed)\s+(.+?)\s+(\d+)\s+(Free|Back|Breast|Fly|IM|Medley|FR)"
TEAMUNIFY_ATHLETE_RE = r"^\s*(\d+)\s+([A-Za-z\s,\.]+)\s+(\d{1,2})\s+([A-Z0-9\-]+)\s+(\d{1,2}:\d{2}\.\d{2}|\d{2}\.\d{2}|NT)([YLS]|$)"




# ---------------------------------------------------------------------------
# Spatial Layout Engine — constants
# ---------------------------------------------------------------------------
FALLBACK_1_COLUMN: List[Tuple[float, float]] = [(36.0, 576.0)]
FALLBACK_2_COLUMN: List[Tuple[float, float]] = [(36.0, 296.0), (316.0, 576.0)]
FALLBACK_3_COLUMN: List[Tuple[float, float]] = [(36.0, 200.0), (216.0, 396.0), (412.0, 576.0)]
MIN_LINES_FOR_HISTOGRAM = 5
GUTTER_WIDTH_THRESHOLD = 12
MIN_COLUMN_WIDTH = 40
NOISE_FLOOR = 2
PAGE_WIDTH = 612

# Map column_override integer → fallback boundary list
_COLUMN_OVERRIDE_MAP = {
    1: FALLBACK_1_COLUMN,
    2: FALLBACK_2_COLUMN,
    3: FALLBACK_3_COLUMN,
}


# ---------------------------------------------------------------------------
# Phase 6.1 — Spatial Coordinate Extraction
# ---------------------------------------------------------------------------

def extract_spatial_words_to_lines(pdf_path: str, page_num: int) -> List[List[dict]]:
    """Extract word tokens from a single PDF page and group them into horizontal lines.

    Opens the page with pdfplumber, retrieves precise word bounding boxes via
    ``extract_words``, then clusters tokens that share the same ``top`` coordinate
    (within ±2 px) into ordered horizontal lines.

    Args:
        pdf_path: Absolute path to the PDF file.
        page_num: Zero-based page index.

    Returns:
        List[List[dict]] — one inner list per line, sorted top-to-bottom.
        Each dict is a pdfplumber word token with at minimum:
        ``text``, ``x0``, ``x1``, ``top``, ``bottom``.
    """
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num]
        words = page.extract_words(x_tolerance=3, y_tolerance=3)

    if not words:
        return []

    # --- group words into horizontal lines by top coordinate (±2 px tolerance) ---
    # Sort words top-to-bottom first so each anchor is the topmost unused word
    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    used: List[bool] = [False] * len(sorted_words)
    lines: List[List[dict]] = []

    for i, anchor in enumerate(sorted_words):
        if used[i]:
            continue
        current_line: List[dict] = [anchor]
        used[i] = True
        anchor_top = anchor["top"]

        for j in range(i + 1, len(sorted_words)):
            if used[j]:
                continue
            if abs(sorted_words[j]["top"] - anchor_top) <= 2:
                current_line.append(sorted_words[j])
                used[j] = True

        # Sort the line left-to-right by x0
        current_line.sort(key=lambda w: w["x0"])
        lines.append(current_line)

    # Lines are already in top-to-bottom order (iterated over sorted_words)
    return lines


# ---------------------------------------------------------------------------
# Phase 6.2 — Dynamic Histogram Column Discovery
# ---------------------------------------------------------------------------

def detect_column_boundaries(
    spatial_lines: List[List[dict]],
    previous_page_boundaries: List[Tuple[float, float]] | None = None,
) -> List[Tuple[float, float]]:
    """Discover column boundary tuples from the x-density of word tokens on a page.

    Builds a PAGE_WIDTH-element integer histogram where every index spanned by a
    word's x-footprint is incremented.  Runs of consecutive low-density indices
    that are wide enough become structural gutters; the gaps between gutters
    define column boundaries.

    Args:
        spatial_lines: Output of :func:`extract_spatial_words_to_lines`.
        previous_page_boundaries: Boundary list from the previous page, used as
            a fallback when this page is too sparse to histogram reliably.

    Returns:
        List[Tuple[float, float]] — one ``(left_x, right_x)`` tuple per column,
        ordered left-to-right.  Falls back to ``previous_page_boundaries`` or
        ``FALLBACK_2_COLUMN`` when detection fails.
    """
    fallback = previous_page_boundaries if previous_page_boundaries is not None else FALLBACK_2_COLUMN

    # Sparse-page guard
    if len(spatial_lines) < MIN_LINES_FOR_HISTOGRAM:
        return fallback

    # --- Build x-density histogram ---
    density = [0] * PAGE_WIDTH
    for line in spatial_lines:
        for word in line:
            left = max(0, int(word["x0"]))
            right = min(PAGE_WIDTH - 1, int(word["x1"]))
            for x in range(left, right + 1):
                density[x] += 1

    # Use a page-relative noise floor so dense 3-column pages (where every x
    # gets at least a few hits) can still have their tight inter-column gutters
    # detected.  At least 4 % of lines must cover an x-position for it to be
    # considered "active" content; anything below that is gutter-eligible.
    adaptive_floor = max(NOISE_FLOOR, int(len(spatial_lines) * 0.04))

    # --- Scan for gutters: consecutive low-density spans >= GUTTER_WIDTH_THRESHOLD ---
    gutters: List[Tuple[int, int]] = []   # (gutter_start, gutter_end) inclusive
    in_gutter = False
    gutter_start = 0

    for x in range(PAGE_WIDTH):
        if density[x] <= adaptive_floor:
            if not in_gutter:
                in_gutter = True
                gutter_start = x
        else:
            if in_gutter:
                gutter_end = x - 1
                width = gutter_end - gutter_start + 1
                if width >= GUTTER_WIDTH_THRESHOLD:
                    gutters.append((gutter_start, gutter_end))
                in_gutter = False

    # Catch a gutter that runs to the page edge
    if in_gutter:
        gutter_end = PAGE_WIDTH - 1
        width = gutter_end - gutter_start + 1
        if width >= GUTTER_WIDTH_THRESHOLD:
            gutters.append((gutter_start, gutter_end))

    # --- Derive columns from gaps between gutters ---
    # Collect column ranges: spans of non-gutter x that lie between gutters
    column_boundaries: List[Tuple[float, float]] = []

    if not gutters:
        # No gutters found → treat the whole page as a single column
        column_boundaries = [(36.0, float(PAGE_WIDTH - 36))]
    else:
        segments: List[Tuple[int, int]] = []

        # Before first gutter
        if gutters[0][0] > 0:
            segments.append((0, gutters[0][0] - 1))

        # Between gutters
        for i in range(len(gutters) - 1):
            seg_left = gutters[i][1] + 1
            seg_right = gutters[i + 1][0] - 1
            if seg_right >= seg_left:
                segments.append((seg_left, seg_right))

        # After last gutter
        if gutters[-1][1] < PAGE_WIDTH - 1:
            segments.append((gutters[-1][1] + 1, PAGE_WIDTH - 1))

        # Filter out segments too narrow to be real columns
        column_boundaries = [
            (float(s[0]), float(s[1]))
            for s in segments
            if (s[1] - s[0] + 1) >= MIN_COLUMN_WIDTH
        ]

    # --- Guard rails: reject implausible results ---
    if not column_boundaries or len(column_boundaries) > 3:
        return fallback

    return column_boundaries


# ---------------------------------------------------------------------------
# Phase 6.3 — Column Slicing & Text Reconstruction
# ---------------------------------------------------------------------------

def reconstruct_text_by_columns(
    spatial_lines: List[List[dict]],
    boundaries: List[Tuple[float, float]],
) -> str:
    """Bin each word token into its column and reconstruct reading-order text.

    Words are sorted into columns based on which boundary range contains their
    ``x0`` coordinate.  Columns are emitted left-to-right; lines within each
    column are joined with newlines.

    Args:
        spatial_lines: Output of :func:`extract_spatial_words_to_lines`.
        boundaries: Column ``(left_x, right_x)`` tuples from
            :func:`detect_column_boundaries`.

    Returns:
        Single string with all columns concatenated in reading order,
        separated by newline pairs.
    """
    # Initialise one bucket per column (list of text lines)
    columns: List[List[str]] = [[] for _ in boundaries]

    for line in spatial_lines:
        # Bin each word into its column
        col_words: List[List[str]] = [[] for _ in boundaries]
        for word in line:
            placed = False
            for col_idx, (col_left, col_right) in enumerate(boundaries):
                if col_left <= word["x0"] <= col_right:
                    col_words[col_idx].append(word["text"])
                    placed = True
                    break
            if not placed:
                # Word falls outside all defined columns — assign to nearest column
                best = min(
                    range(len(boundaries)),
                    key=lambda i: min(
                        abs(word["x0"] - boundaries[i][0]),
                        abs(word["x0"] - boundaries[i][1]),
                    ),
                )
                col_words[best].append(word["text"])

        # Append each column's line text into its bucket
        for col_idx, words_in_col in enumerate(col_words):
            if words_in_col:
                columns[col_idx].append(" ".join(words_in_col))

    # Emit columns in order, joined by newlines
    return "\n\n".join("\n".join(col_lines) for col_lines in columns if col_lines)


def parse_pdf_via_spatial_engine(
    pdf_path: str,
    column_override: int | None = None,
) -> tuple[List[Event], ValidationResult]:
    """Full spatial-layout pipeline: extract → detect columns → reconstruct → parse.

    Processes each page of the PDF individually through the spatial engine,
    carrying the previous page's column boundaries forward as a fallback for
    sparse trailing pages.  The reconstructed text is then fed into the existing
    :class:`ParserFactory` routing — no changes to downstream parser logic.

    Args:
        pdf_path: Path to the psych-sheet PDF.
        column_override: If 1, 2, or 3, skip histogram detection entirely and
            force the corresponding ``FALLBACK_N_COLUMN`` constant.

    Returns:
        Tuple of (List[Event], ValidationResult).
    """
    all_page_texts: List[str] = []
    previous_boundaries: List[Tuple[float, float]] | None = None
    layout_confidence_low = False

    pdf_producer: str | None = None
    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        if pdf.metadata:
            pdf_producer = pdf.metadata.get("Producer") or pdf.metadata.get("producer") or None

    for page_num in range(num_pages):
        spatial_lines = extract_spatial_words_to_lines(pdf_path, page_num)

        # --- Determine column boundaries ---
        if column_override is not None:
            boundaries = _COLUMN_OVERRIDE_MAP.get(column_override, FALLBACK_2_COLUMN)
        else:
            if len(spatial_lines) < MIN_LINES_FOR_HISTOGRAM:
                # Sparse page: use previous page's map (partial-page protection)
                layout_confidence_low = True
                boundaries = previous_boundaries if previous_boundaries is not None else FALLBACK_2_COLUMN
            else:
                boundaries = detect_column_boundaries(spatial_lines, previous_boundaries)

        previous_boundaries = boundaries

        # --- Reconstruct page text in reading order ---
        page_text = reconstruct_text_by_columns(spatial_lines, boundaries)
        if page_text:
            all_page_texts.append(page_text)

    combined_text = "\n".join(all_page_texts)

    # --- Fix 2: split any lines where two event headers were merged by the
    # spatial engine (both headers sit at the same Y on a two-column page) ---
    combined_text = _split_merged_event_headers(combined_text)

    # --- Route through existing parser factory (unchanged logic) ---
    parser = ParserFactory.get_parser(combined_text)
    events = parser.parse(combined_text)

    # auto_layout_failed: True only when the pipeline produced zero events
    # without a manual column override being provided.  A graceful fallback
    # to a default boundary map (FALLBACK_2_COLUMN) does NOT constitute
    # failure — only complete parse failure triggers the UI safety net.
    auto_layout_failed = (len(events) == 0) and (column_override is None)

    # --- Propagate layout flags onto every returned Event ---
    for event in events:
        event.layout_confidence_low = layout_confidence_low
        event.auto_layout_failed = auto_layout_failed

    validation = validate_parsed_events(events, pdf_producer=pdf_producer)
    return events, validation



def _split_merged_event_headers(text: str) -> str:
    """Post-processing pass: split lines where two event headers were merged
    by the spatial column reconstructor.

    On two-column pages the left and right event headers often share the same
    top Y-coordinate, so :func:`reconstruct_text_by_columns` joins them into
    a single line (e.g. ``'Event 1 Women 1000 Yard Freestyle Event 2 Men 1000
    Yard Freestyle'``).  When the parser sees this, it treats the second header
    token as part of the first event's noise block, resets
    ``parsing_entries = False`` mid-roster, and drops all subsequent entries.

    The fix searches each reconstructed line for a second ``Event \\d+`` token
    and, if found, emits the two halves as separate lines.
    """
    result = []
    for line in text.splitlines():
        # Look for a second Event header embedded in the same line
        m = re.search(r'^(.*?Event\s+\d+[^\n]*?)(Event\s+\d+.*)$', line)
        if m and m.group(1).strip() != m.group(0).strip():
            result.append(m.group(1).strip())
            result.append(m.group(2).strip())
        else:
            result.append(line)
    return '\n'.join(result)


def detect_source_format(raw_text: str) -> str:
    """Detects if the psych sheet is from Hy-Tek, TeamUnify, or NCAA/Championship style.

    Args:
        raw_text: The raw text content of the psych sheet.

    Returns:
        The source format string: 'ncaa', 'hytek', 'teamunify', or 'generic'.
    """
    # NCAA/Collegiate parsing engine disabled for v1.1.4 (USA Swimming age-group primary)
    # Set HEATWAVE_NCAA=1 to re-enable during testing.
    if os.getenv("HEATWAVE_NCAA", "0") == "1":
        if re.search(r"\bYr\b.*\bName\b.*\bSchool\b|\bName\b.*\bYr\b.*\bSchool\b|\bTeam\b.*\bRelay\b.*\bSeed\b", raw_text):
            return "ncaa"

    # Look for software branding signatures
    if "Hy-Tek's Meet Manager" in raw_text or "HY-TEK's" in raw_text:
        # Some Hy-Tek-generated sheets use '#N' event headers (TeamUnify rendering
        # style) even though the branding says HY-TEK's.  Detect this by checking
        # for the '#' prefix before an event number in the first few thousand chars.
        sample = raw_text[:3000]
        if re.search(r'#\s*\d+\s+(Girls|Boys|Men|Women|Mixed)', sample):
            return "teamunify"
        return "hytek"
    if "TeamUnify" in raw_text or "TouchPad" in raw_text:
        return "teamunify"
    
    # Heuristic fallback checking pattern structures
    if "Event" in raw_text and ("Yard" in raw_text or "Freestyle" in raw_text or "Backstroke" in raw_text or "Butterfly" in raw_text):
        return "hytek"
    if "#" in raw_text and ("Free" in raw_text or "Fly" in raw_text):
        return "teamunify"

        
    return "generic"




HEADER_FOOTER_PATTERNS = [
    r"HY-TEK's MEET MANAGER.*Page \d+",                 # Page footer
    r"\bPage\s+\d+\s*$",                                # Standalone Page N
    r"^\d{4}\b.*?\bPsych Sheet\b",                      # Meet title header
    r"^\d{4}\b.*?\b\d{1,2}/\d{1,2}/\d{4}\b",            # Meet date header (e.g. 2025 OKS... 7/18/2025)
    r"^\s*Psych Sheet\s*$",                             # Psych Sheet title
    r"^Event\s+\d+[\s\.]*\([^)]*\)",                    # Event continuation header: Event 9 ...(Girls 10 & Under 100 Yard IM)
    r"^Event\s+\d+[\s\.]+\.\.\.",                       # Event continuation pattern: Event 9 ...
    r"\(Continued\)",                                   # (Continued) text anywhere
    r"^\s*Name\s+Age\s+Team\s+Seed Time",               # Column header
    r"^\s*Team\s+Relay\s+Seed",                         # Relay column header
    r"^\s*Licensed To:.*",                              # Licensing header
    r".*For Office Use Only.*",                         # Administrative header
]


def is_header_or_footer_line(line: str) -> bool:
    """Returns True if line is a psych sheet page header, footer, or continuation banner."""
    cleaned = line.strip()
    if not cleaned:
        return True
    for pattern in HEADER_FOOTER_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return True
    return False


def parse_event_header(line: str) -> Tuple[int, str, str, int, str] | None:
    """
    Parse event header line: "Event 1 Girls 10 & Under 200 Yard Freestyle"
    
    Returns:
        Tuple of (event_number, gender, event_name, distance, stroke) or None if not matched.
    """
    cleaned = line.strip()
    # Reject continuation headers like "Event 9 ...(Girls 10 & Under 100 Yard IM)"
    if "..." in cleaned or "(continued)" in cleaned.lower():
        return None

    # Pattern: Event N Gender AgeGroup DistanceYards Stroke...
    pattern = r"Event\s+(\d+)\s+(Girls|Boys|Women|Men)\s+(.+?)\s+(\d+)\s+Yard\s+(.+?)(?:\s+Relay)?$"
    
    match = re.match(pattern, cleaned)
    if match:
        event_num = int(match.group(1))
        gender = match.group(2)
        age_group = normalize_age_group(match.group(3))
        distance = int(match.group(4))
        stroke = match.group(5)
        
        # Construct full event name
        event_name = f"{age_group} {distance}Y {stroke}"
        
        return (event_num, gender, event_name, distance, stroke)

    return None


def normalize_seed_time(time_str: str) -> str:
    """Normalizes seed times by removing course/standard prefixes/suffixes and enforcing standard format.

    Args:
        time_str: The raw seed time string.

    Returns:
        The normalized seed time string.
    """
    cleaned = time_str.strip().upper()
    if not cleaned or cleaned in ["NT", "NO TIME", "N.T."]:
        return "NT"
    
    # Strip course/standard prefixes and suffixes: Y, L, S, B, A, X
    cleaned = re.sub(r"^[A-Za-z\s]+", "", cleaned)
    cleaned = re.sub(r"[A-Za-z\s]+$", "", cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        return "NT"

    # Handle partial formats (e.g. MM:SS -> MM:SS.00)
    if re.match(r"^\d+:\d{2}$", cleaned):
        cleaned = cleaned + ".00"
        
    return cleaned


def normalize_age_group(age_str: str) -> str:
    """Normalizes age group strings to a standardized representation.

    Args:
        age_str: The raw age group string.

    Returns:
        The normalized age group string.
    """
    cleaned = age_str.strip()
    # E.g. "10 & Under" / "10&U" -> "10 & Under"
    cleaned = re.sub(r'(\d+)\s*&\s*[Uu](nd)?e?r?', r'\1 & Under', cleaned)
    # E.g. "15 & Over" / "15&O" -> "15 & Over"
    cleaned = re.sub(r'(\d+)\s*&\s*[Oo](v)?e?r?', r'\1 & Over', cleaned)
    return cleaned


def parse_seed_time(time_str: str) -> str:
    """
    Parse and validate seed time formats (MM:SS.XX or NT).
    
    Returns:
        Normalized seed time string.
    """
    return normalize_seed_time(time_str)



def parse_individual_entry(line: str) -> Tuple[int, str, int, str, str] | None:
    """
    Parse individual swimmer entry: "1 Doe, John 10 Team A-OK 2:42.05"
    
    Returns:
        Tuple of (place, swimmer_name, age, team_code, seed_time) or None if not matched.
    """
    parts = line.split()
    if len(parts) < 3:
        return None
    
    try:
        place = int(parts[0])
    except ValueError:
        return None
    
    # Check if last token is standalone course letter (e.g. "27.45 L" or "27.45 Y")
    has_course = False
    if (
        len(parts) >= 6
        and parts[-1].upper() in ["Y", "L", "S", "B", "A", "X"]
        and re.search(r"\d", parts[-2])
    ):
        seed_time_raw = parts[-2]
        has_course = True
    else:
        seed_time_raw = parts[-1]

    seed_time = parse_seed_time(seed_time_raw)
    
    is_valid_time = bool(
        re.match(r"^\d+:\d{2}\.\d{2}$", seed_time)
        or re.match(r"^\d{1,2}\.\d{2}$", seed_time)
        or seed_time == "NT"
    )

    if is_valid_time:
        if has_course:
            parts_for_name = parts[:-2]
        else:
            parts_for_name = parts[:-1]
    else:
        # No seed time token found at end of line; default to NT
        seed_time = "NT"
        parts_for_name = parts

    # Find age: scan from end backwards looking for 1-2 digit number
    age = None
    age_idx = -1
    
    for i in range(len(parts_for_name) - 1, 0, -1):
        if re.match(r"^\d{1,2}$", parts_for_name[i]):
            try:
                age = int(parts_for_name[i])
                age_idx = i
                break
            except ValueError:
                continue
    
    if age_idx >= 2:
        name = " ".join(parts_for_name[1:age_idx])
        team_parts = parts_for_name[age_idx + 1:]
        if not team_parts:
            # Incomplete line cut off at page/column boundary (e.g. "2 Tyszko, Cade P 14")
            return None
        team_code = " ".join(team_parts)
    else:
        if len(parts_for_name) < 4:
            return None
        team_code = parts_for_name[-1]
        name = " ".join(parts_for_name[1:-1])
        age = None

    if not name:
        return None
    
    return (place, name, age, team_code, seed_time)


def parse_relay_entry(line: str) -> Tuple[int, str, str] | None:
    """
    Parse relay entry: "1 Team A-OK A 2:13.43"
    
    Returns:
        Tuple of (place, team_name, seed_time) or None if not matched.
    """
    parts = line.split()
    
    if len(parts) < 3:
        return None
    
    try:
        place = int(parts[0])
    except ValueError:
        return None
    
    # Find seed time (last part, should be MM:SS.XX or NT)
    seed_time_str = parts[-1]
    if not (
        re.match(r"^\d+:\d{2}", seed_time_str)          # MM:SS.XX
        or re.match(r"^\d{1,2}\.\d{2}$", seed_time_str) # SS.XX (sub-minute)
        or seed_time_str.upper() == "NT"
    ):
        return None
    
    # Team everything in between place and seed time
    team_name = " ".join(parts[1:-1])
    seed_time = parse_seed_time(seed_time_str)
    
    return (place, team_name, seed_time)


class BasePsychSheetParser(abc.ABC):
    """Abstract base class establishing a uniform contract for all psych sheet parsers."""

    @abc.abstractmethod
    def parse(self, raw_text: str) -> List[Event]:
        """Parses raw text string from a PDF into a structured list of Event objects."""
        pass


class HyTekParser(BasePsychSheetParser):
    """Strategy for handling standard, strictly formatted Hy-Tek psych sheets."""

    def parse(self, raw_text: str) -> List[Event]:
        lines = raw_text.split("\n")
        events: List[Event] = []
        
        current_event: Event | None = None
        is_relay_event = False
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            # Skip page headers, footers, continuation banners, and column headers
            if is_header_or_footer_line(line):
                continue

            # Check for event header
            event_info = parse_event_header(line)
            if event_info:
                # Save previous event if it exists
                if current_event:
                    events.append(current_event)
                
                event_num, gender, event_name, distance, stroke = event_info
                is_relay_event = "Relay" in line
                
                current_event = Event(
                    number=event_num,
                    name=event_name,
                    gender=gender,
                    distance=distance,
                    stroke=stroke,
                    entries=[]
                )
                continue

            # Parse entries
            if current_event:
                if is_relay_event:
                    entry_data = parse_relay_entry(line)
                    if entry_data:
                        place, team_name, seed_time = entry_data
                        relay_entry = RelayEntry(
                            place=place,
                            team_name=team_name,
                            seed_time=seed_time
                        )
                        current_event.entries.append(relay_entry)
                else:
                    entry_data = parse_individual_entry(line)
                    if entry_data:
                        place, name, age, team_code, seed_time = entry_data
                        swimmer = Swimmer(name=name, age=age, team_code=team_code)
                        entry = Entry(place=place, swimmer=swimmer, seed_time=seed_time)
                        current_event.entries.append(entry)

        # Don't forget the last event
        if current_event:
            events.append(current_event)
        
        return events


class TeamUnifyParser(BasePsychSheetParser):
    """Strategy for parsing TeamUnify psych sheets with irregular padding and suffixes."""

    def parse(self, raw_text: str) -> List[Event]:
        events: List[Event] = []
        current_event = None
        
        # Split text cleanly into lines
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        
        for line in lines:
            # 1. Check if line matches an Event Header
            event_match = re.search(TEAMUNIFY_EVENT_RE, line)
            if event_match:
                # If we were already tracking an event, save it before starting a new one
                if current_event:
                    events.append(current_event)
                
                event_num = int(event_match.group(1))
                gender = event_match.group(2)
                age_group = normalize_age_group(event_match.group(3))
                distance = int(event_match.group(4))
                stroke = event_match.group(5)
                
                # Normalize TeamUnify shorthand stroke tokens to your core standard values
                stroke_map = {
                    "Free": "Freestyle",
                    "Back": "Backstroke",
                    "Breast": "Breaststroke",
                    "Fly": "Butterfly",
                    "IM": "Individual Medley",
                    "Medley": "Medley Relay",
                    "FR": "Free Relay"
                }
                normalized_stroke = stroke_map.get(stroke, stroke)
                
                event_name = f"{age_group} {distance}Y {normalized_stroke}"
                
                # Initialize your existing Event model structure
                current_event = Event(
                    number=event_num,
                    name=event_name,
                    gender=gender,
                    distance=distance,
                    stroke=normalized_stroke,
                    entries=[]
                )
                continue
            
            # 2. Check if we are inside an event block and match an Athlete Entry row
            if current_event:
                athlete_match = re.search(TEAMUNIFY_ATHLETE_RE, line)
                if athlete_match:
                    # Extract raw fields matching regex groups
                    seed_no = int(athlete_match.group(1))
                    full_name = athlete_match.group(2).strip()
                    age = int(athlete_match.group(3))
                    team_code = athlete_match.group(4).strip()
                    raw_time = normalize_seed_time(athlete_match.group(5))
                    
                    swimmer = Swimmer(name=full_name, age=age, team_code=team_code)
                    entry = Entry(place=seed_no, swimmer=swimmer, seed_time=raw_time)
                    current_event.entries.append(entry)

        # Append the final event block left in the loop buffer
        if current_event:
            events.append(current_event)
            
        return events


        
        # Append the final event block left in the loop buffer
        if current_event:
            events.append(current_event)
            
        return events





class GenericParser(BasePsychSheetParser):
    """Fallback strategy using heuristic token scanning when software format is ambiguous."""

    def parse(self, raw_text: str) -> List[Event]:
        return []
class ParserFactory:
    """Dynamically routes processing workloads to the correct parser engine."""

    @staticmethod
    def get_parser(raw_text: str) -> BasePsychSheetParser:
        source_format = detect_source_format(raw_text)
        
        # NCAA/Collegiate parsing engine disabled for v1.1.4 unless explicitly enabled
        if os.getenv("HEATWAVE_NCAA", "0") == "1" and source_format == "ncaa":
            from .formats.ncaa.ncaa_parser import NCAACollegeParser
            return NCAACollegeParser()
        elif source_format == "hytek":
            return HyTekParser()
        elif source_format == "teamunify":
            return TeamUnifyParser()
        else:
            return GenericParser()


def parse_events_from_text(text: str) -> tuple[List[Event], ValidationResult]:
    """Top-level functional interface used by the Streamlit application pipeline."""
    parser = ParserFactory.get_parser(text)
    events = parser.parse(text)
    validation = validate_parsed_events(events)
    return events, validation

