import pdfplumber
import pytest
import os
from src.parser.extractor import extract_spatial_words_to_lines

# ---------------------------------------------------------------------------
# Legacy script-style baseline — left intact for backward compatibility
# ---------------------------------------------------------------------------

def test_extract():
    pdf_path = "data/samples/1769543968773-7a7qa8q6s.pdf"
    
    print("--- pdfplumber column cropping text ---")
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        width = first_page.width
        height = first_page.height
        
        left_bbox = (0, 0, width / 2, height)
        right_bbox = (width / 2, 0, width, height)
        
        left_col = first_page.crop(left_bbox)
        right_col = first_page.crop(right_bbox)
        
        left_text = left_col.extract_text()
        right_text = right_col.extract_text()
        
        print("--- LEFT COLUMN ---")
        print(left_text[:500])
        print("...")
        print("--- RIGHT COLUMN ---")
        print(right_text[:500])
        print("...")

if __name__ == "__main__":
    test_extract()


# ---------------------------------------------------------------------------
# Phase 6.1 — Assertion-driven unit test
# ---------------------------------------------------------------------------

_SAMPLE_PDF = "data/samples/1769543968773-7a7qa8q6s.pdf"


@pytest.mark.skipif(
    not os.path.exists(_SAMPLE_PDF),
    reason=f"Sample PDF not present at {_SAMPLE_PDF}",
)
def test_extract_spatial_words_to_lines():
    """extract_spatial_words_to_lines must return a non-empty list of lines,
    each of which is a list of pdfplumber word-token dicts with the expected keys."""
    result = extract_spatial_words_to_lines(_SAMPLE_PDF, page_num=0)

    # Must return something
    assert isinstance(result, list), "Result must be a list"
    assert len(result) > 0, "Result must be non-empty for a content-bearing page"

    # Every element must be a non-empty list
    for line_idx, line in enumerate(result):
        assert isinstance(line, list), f"Line {line_idx} must be a list"
        assert len(line) > 0, f"Line {line_idx} must not be empty"

        for token in line:
            # Each token must be a dict with the required spatial keys
            assert isinstance(token, dict), f"Token in line {line_idx} must be a dict"
            for key in ("text", "x0", "x1", "top", "bottom"):
                assert key in token, (
                    f"Token in line {line_idx} missing key '{key}': {token}"
                )
            # text must be a non-empty string
            assert isinstance(token["text"], str) and token["text"].strip(), (
                f"Token 'text' in line {line_idx} must be a non-empty string"
            )
            # Coordinate values must be numeric and make geometric sense
            assert token["x0"] <= token["x1"], (
                f"x0 must be <= x1 in line {line_idx}: {token}"
            )
            assert token["top"] <= token["bottom"], (
                f"top must be <= bottom in line {line_idx}: {token}"
            )

    # Lines must be in top-to-bottom order
    tops = [line[0]["top"] for line in result]
    assert tops == sorted(tops), "Lines must be sorted top-to-bottom"


def test_page_continuation_and_footer_stripping():
    """Verify that HyTek continuation headers, page footers, and column headers are stripped
    and do not corrupt swimmer entries across page handovers."""
    from src.parser.extractor import HyTekParser

    raw_text = """Event 9 Girls 10 & Under 100 Yard IM
20 Doe, Jane 9 Team A-OK 1:43.63
21 Smith, John 10 Team B-OK 1:46.56
22 Johnson, Mary 10 Team A-OK 1:48.74
23 Brown, David 9 Team A-OK 1:50.55
24 Miller, Alex 8 Team A-OK 1:50.84

State Swimming - For Office Use Only License HY-TEK's MEET MANAGER 8.0 - 7:52 AM 7/16/2025 Page 3
2025 State 10-Under Championship - 7/18/2025 to 7/20/2025
Psych Sheet
Event 9 ...(Girls 10 & Under 100 Yard IM)
Name Age Team Seed Time

25 Taylor, Sam 9 Team C-OK 1:51.02
26 Anderson, Chris 9 Team D-OK 1:51.91
27 Thomas, Pat 10 Team D-OK 1:53.11
28 Jackson, Taylor 9 Team E-OK 1:53.61
29 White, Morgan 10 Team F-OK 1:53.80
30 Harris, Jordan 10 Team B-OK 1:54.85
"""

    parser = HyTekParser()
    events = parser.parse(raw_text)

    assert len(events) == 1, f"Expected 1 event, got {len(events)}"
    event = events[0]
    assert event.number == 9
    assert len(event.entries) == 11, f"Expected 11 entries, got {len(event.entries)}"

    # Check entry 25 details
    entry25 = next(e for e in event.entries if e.place == 25)
    assert entry25.swimmer.name == "Taylor, Sam"
    assert entry25.swimmer.age == 9
    assert entry25.swimmer.team_code == "Team C-OK"
    assert entry25.seed_time == "1:51.02"

    # Ensure no dummy header entries were generated (e.g. place 2025)
    places = [e.place for e in event.entries]
    assert max(places) == 30
    assert 2025 not in places


def test_large_event_extraction():
    """Verify that a large event with 120+ entries parses cleanly without column bleeding or entry loss."""
    from src.parser.extractor import HyTekParser

    header = "Event 5 Girls 11-12 50 Yard Freestyle\n"
    # Build 125 anonymized entry lines
    lines = [
        f"{i} Swimmer, Athlete{i} {11 + (i % 2)} Team A-OK {25.00 + (i * 0.10):.2f}"
        for i in range(1, 126)
    ]
    raw_text = header + "\n".join(lines)

    parser = HyTekParser()
    events = parser.parse(raw_text)

    assert len(events) == 1
    event = events[0]
    assert event.number == 5
    assert len(event.entries) == 125
    assert event.entries[0].place == 1
    assert event.entries[0].swimmer.name == "Swimmer, Athlete1"
    assert event.entries[124].place == 125
    assert event.entries[124].swimmer.name == "Swimmer, Athlete125"


def test_time_suffix_normalization():
    """Verify seed time normalization handles Y, L, S, B, A, X suffixes and course prefixes."""
    from src.parser.extractor import normalize_seed_time, parse_individual_entry

    assert normalize_seed_time("27.45Y") == "27.45"
    assert normalize_seed_time("27.45 L") == "27.45"
    assert normalize_seed_time("A 27.45") == "27.45"
    assert normalize_seed_time("B 1:02.15 Y") == "1:02.15"

    # Test via parse_individual_entry
    res1 = parse_individual_entry("1 Doe, John 10 Team A-OK 27.45Y")
    assert res1 is not None
    assert res1[4] == "27.45"

    res2 = parse_individual_entry("2 Smith, Jane 10 Team B-OK 27.45 L")
    assert res2 is not None
    assert res2[4] == "27.45"

