import abc
import re
from typing import List, Tuple
import pdfplumber
from ..models.schemas import Event, Entry, RelayEntry, Swimmer

# Regular Expressions for parsing variants
HYTEK_EVENT_RE = r"Event\s+(\d+)\s+(Girls|Boys|Men|Women|Mixed)\s+(.+?)\s+(\d+)\s+(Yard|Meter)\s+(Freestyle|Backstroke|Breaststroke|Butterfly|Individual Medley|Medley Relay|Free Relay)"
HYTEK_ATHLETE_RE = r"^\s*(\d+)\s+([A-Za-z\s,\.]+)\s+(\d{1,2})\s+([A-Z0-9\-]+)\s+(\d{1,2}:\d{2}\.\d{2}|\d{2}\.\d{2}|NT)"

TEAMUNIFY_EVENT_RE = r"(?:Event|#)\s*(\d+)\s+(Girls|Boys|Men|Women|Mixed)\s+(.+?)\s+(\d+)\s+(Free|Back|Breast|Fly|IM|Medley|FR)"
TEAMUNIFY_ATHLETE_RE = r"^\s*(\d+)\s+([A-Za-z\s,\.]+)\s+(\d{1,2})\s+([A-Z0-9\-]+)\s+(\d{1,2}:\d{2}\.\d{2}|\d{2}\.\d{2}|NT)([YLS]|$)"



def detect_source_format(raw_text: str) -> str:
    """Detects if the psych sheet is from Hy-Tek or TeamUnify.

    Args:
        raw_text: The raw text content of the psych sheet.

    Returns:
        The source format string: 'hytek', 'teamunify', or 'generic'.
    """
    # Look for software branding signatures
    if "Hy-Tek's Meet Manager" in raw_text or "HY-TEK's" in raw_text:
        return "hytek"
    if "TeamUnify" in raw_text or "TouchPad" in raw_text:
        return "teamunify"
    
    # Heuristic fallback checking pattern structures
    if "Event" in raw_text and ("Yard" in raw_text or "Freestyle" in raw_text or "Backstroke" in raw_text or "Butterfly" in raw_text):
        return "hytek"
    if "#" in raw_text and ("Free" in raw_text or "Fly" in raw_text):
        return "teamunify"

        
    return "generic"



def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a Psych Sheet PDF.
    Handles the two-column layout parsing by extracting left and right columns separately.
    
    Returns:
        Full text with columns merged in reading order.
    """
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page_num, page in enumerate(pdf.pages):
            width = page.width
            height = page.height
            
            # Crop left and right columns
            left_bbox = (0, 0, width / 2, height)
            right_bbox = (width / 2, 0, width, height)
            
            left_col = page.crop(left_bbox)
            right_col = page.crop(right_bbox)
            
            left_text = left_col.extract_text() or ""
            right_text = right_col.extract_text() or ""
            
            # Merge columns intelligently (left then right)
            if page_num > 0:
                full_text += "\n"
            full_text += left_text + "\n" + right_text
        
        return full_text


def parse_event_header(line: str) -> Tuple[int, str, str, int, str] | None:
    """
    Parse event header line: "Event 1 Girls 10 & Under 200 Yard Freestyle"
    
    Returns:
        Tuple of (event_number, gender, event_name, distance, stroke) or None if not matched.
    """
    # Pattern: Event N Gender AgeGroup DistanceYards StrokeStroke...
    pattern = r"Event\s+(\d+)\s+(Girls|Boys|Women|Men)\s+(.+?)\s+(\d+)\s+Yard\s+(.+?)(?:\s+Relay)?$"
    
    match = re.match(pattern, line.strip())
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
    """Normalizes seed times by removing course suffixes and enforcing standard format.

    Args:
        time_str: The raw seed time string.

    Returns:
        The normalized seed time string.
    """
    cleaned = time_str.strip().upper()
    if not cleaned or cleaned in ["NT", "NO TIME", "N.T."]:
        return "NT"
    
    # Strip course suffixes: Y, L, S
    if cleaned[-1] in ["Y", "L", "S"]:
        cleaned = cleaned[:-1].strip()
    
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
    Parse individual swimmer entry: "1 Meek, Keaston 10 Bartlesville Spl-OK 2:42.05"
    
    Returns:
        Tuple of (place, swimmer_name, age, team_code, seed_time) or None if not matched.
    """
    # Pattern: place name age team seed_time
    parts = line.split()
    
    if len(parts) < 5:
        return None
    
    try:
        place = int(parts[0])
    except ValueError:
        return None
    
    # Work backwards: seed_time is last, age is a number that comes before team
    # Find seed_time (last part, should match time pattern)
    seed_time_str = parts[-1]
    if not (re.match(r"^\d+:\d{2}", seed_time_str) or seed_time_str.upper() == "NT"):
        return None
    
    seed_time = parse_seed_time(seed_time_str)
    
    # Find age: scan from end backwards (before seed_time) looking for age pattern
    # Age is typically 1-2 digits, and comes after name, before team
    age = None
    age_idx = -1
    
    for i in range(len(parts) - 2, 0, -1):  # Start before seed_time
        if re.match(r"^\d{1,2}$", parts[i]):  # 1-2 digit number
            try:
                age = int(parts[i])
                age_idx = i
                break
            except ValueError:
                continue
    
    if age_idx < 2:  # Need at least place and name before age
        return None
    
    # Name is everything between place and age
    name = " ".join(parts[1:age_idx])
    
    # Team code is everything between age and seed_time
    if age_idx + 1 >= len(parts) - 1:  # Make sure there's a team between age and seed_time
        return None
    
    team_code = " ".join(parts[age_idx + 1:-1])
    
    return (place, name, age, team_code, seed_time)


def parse_relay_entry(line: str) -> Tuple[int, str, str] | None:
    """
    Parse relay entry: "1 King Marlin Swim-OK A 2:13.43"
    
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
    if not (re.match(r"^\d+:\d{2}", seed_time_str) or seed_time_str.upper() == "NT"):
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
            
            # Skip header lines
            if any(skip in line for skip in ["Name Age Team", "Team Relay Seed", "Seed Time", "HY-TEK"]):
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
                        parts = line.split()
                        if parts and parts[0].isdigit():
                            place = int(parts[0])
                            team_name = " ".join(parts[1:-1]) if len(parts) > 2 else "Unknown Team"
                            seed_time = parts[-1] if len(parts) > 1 else "NT"
                            relay_entry = RelayEntry(
                                place=place,
                                team_name=team_name,
                                seed_time=seed_time,
                                low_confidence=True,
                                error_msg="Failed to parse relay entry format cleanly"
                            )
                            current_event.entries.append(relay_entry)
                else:
                    entry_data = parse_individual_entry(line)
                    if entry_data:
                        place, name, age, team_code, seed_time = entry_data
                        swimmer = Swimmer(name=name, age=age, team_code=team_code)
                        entry = Entry(place=place, swimmer=swimmer, seed_time=seed_time)
                        current_event.entries.append(entry)
                    else:
                        parts = line.split()
                        if parts and parts[0].isdigit():
                            place = int(parts[0])
                            name = " ".join(parts[1:-3]) if len(parts) > 4 else (" ".join(parts[1:-1]) if len(parts) > 2 else "Unknown Athlete")
                            age = None
                            team_code = "Unknown"
                            for p in parts[1:-1]:
                                if p.isdigit() and len(p) <= 2:
                                    age = int(p)
                                    break
                            # Try to extract a team code (if we found age, look after it)
                            age_idx = -1
                            for i, p in enumerate(parts):
                                if p.isdigit() and len(p) <= 2 and i > 0:
                                    age_idx = i
                                    break
                            if age_idx != -1 and age_idx + 1 < len(parts) - 1:
                                team_code = " ".join(parts[age_idx + 1:-1])
                            
                            seed_time = parts[-1] if len(parts) > 1 else "NT"
                            swimmer = Swimmer(name=name, age=age, team_code=team_code)
                            entry = Entry(
                                place=place,
                                swimmer=swimmer,
                                seed_time=seed_time,
                                low_confidence=True,
                                error_msg="Failed to parse individual entry format cleanly"
                            )
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
                else:
                    parts = line.split()
                    if parts and parts[0].isdigit():
                        place = int(parts[0])
                        name = " ".join(parts[1:-3]) if len(parts) > 4 else (" ".join(parts[1:-1]) if len(parts) > 2 else "Unknown Athlete")
                        age = None
                        team_code = "Unknown"
                        for p in parts[1:-1]:
                            if p.isdigit() and len(p) <= 2:
                                age = int(p)
                                break
                        # Try to extract team code
                        age_idx = -1
                        for i, p in enumerate(parts):
                            if p.isdigit() and len(p) <= 2 and i > 0:
                                age_idx = i
                                break
                        if age_idx != -1 and age_idx + 1 < len(parts) - 1:
                            team_code = " ".join(parts[age_idx + 1:-1])
                        
                        seed_time = parts[-1] if len(parts) > 1 else "NT"
                        swimmer = Swimmer(name=name, age=age, team_code=team_code)
                        entry = Entry(
                            place=place,
                            swimmer=swimmer,
                            seed_time=seed_time,
                            low_confidence=True,
                            error_msg="Failed to parse individual entry format cleanly"
                        )
                        current_event.entries.append(entry)


        
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
        
        if source_format == "hytek":
            return HyTekParser()
        elif source_format == "teamunify":
            return TeamUnifyParser()
        else:
            return GenericParser()


def parse_events_from_text(text: str) -> List[Event]:
    """Top-level functional interface used by the Streamlit application pipeline."""
    parser = ParserFactory.get_parser(text)
    return parser.parse(text)

