"""
Module: test_parser_baseline.py
Purpose: Establish baseline parser performance and document expected failures for TeamUnify.
Inputs: Sample psych sheet text files.
Outputs: Test reports and logging of parsing results.
Dependencies: pytest, src.parser.extractor
Architecture role: Baseline regression and failure tracking tests.
"""
from pathlib import Path
from src.parser.extractor import parse_events_from_text


def test_hytek_baseline_success():
    """Verify the baseline parser successfully parses standard Hy-Tek format."""
    sample_path = Path("data/test_suite/hytek_sample.txt")
    assert sample_path.exists(), "Hy-Tek sample file is missing"
    
    text = sample_path.read_text(encoding="utf-8")
    events = parse_events_from_text(text)
    
    # Standard Hy-Tek should parse, but because the baseline parser requires a colon in the seed time
    # (e.g. 2:42.05 but not 28.45), it will fail to parse entries with times under 1 minute.
    # Therefore, it only successfully parses the NT entry.
    assert len(events) == 2, f"Expected 2 events, got {len(events)}"
    
    # Event 1 Checks
    e1 = events[0]
    assert e1.number == 1
    assert e1.gender == "Girls"
    assert len(e1.entries) == 3  # 1 NT entry succeeds, 2 under-minute entries fallback as low confidence
    
    # Low-confidence fallback entries
    assert e1.entries[0].low_confidence is True
    assert e1.entries[0].swimmer.name == "Smith, Emily S"
    assert e1.entries[0].seed_time == "28.45"
    
    # Successful NT entry
    assert e1.entries[2].low_confidence is False
    assert e1.entries[2].swimmer.name == "Jones, Sarah"
    assert e1.entries[2].seed_time == "NT"

    
    # Event 12 Checks
    e2 = events[1]
    assert e2.number == 12
    assert e2.gender == "Boys"
    assert len(e2.entries) == 1
    assert e2.entries[0].swimmer.name == "Meek, Keaston"
    assert e2.entries[0].seed_time == "2:42.05"



def test_teamunify_baseline_success():
    """Verify that the parser successfully parses TeamUnify format using the new engine."""
    sample_path = Path("data/test_suite/teamunify_sample.txt")
    assert sample_path.exists(), "TeamUnify sample file is missing"
    
    text = sample_path.read_text(encoding="utf-8")
    events = parse_events_from_text(text)
    
    # We should parse exactly 2 events
    assert len(events) == 2, f"Expected 2 parsed events, got {len(events)}"
    
    # Event 1 Checks
    e1 = events[0]
    assert e1.number == 1
    assert e1.name == "10 & Under 50Y Freestyle"
    assert e1.gender == "Girls"
    assert e1.distance == 50
    assert e1.stroke == "Freestyle"
    assert len(e1.entries) == 3
    
    # Entry 1
    entry1 = e1.entries[0]
    assert entry1.place == 1
    assert entry1.swimmer.name == "Smith, Emily S"
    assert entry1.swimmer.age == 10
    assert entry1.swimmer.team_code == "MAC"
    assert entry1.seed_time == "28.45"  # group 5 matched "28.45"
    
    # Entry 3
    entry3 = e1.entries[2]
    assert entry3.place == 3
    assert entry3.swimmer.name == "Jones, Sarah"
    assert entry3.swimmer.age == 9
    assert entry3.swimmer.team_code == "YOTA"
    assert entry3.seed_time == "NT"
    
    # Event 3 Checks
    e2 = events[1]
    assert e2.number == 3
    assert e2.name == "15 & Over 200Y Individual Medley"
    assert e2.gender == "Women"
    assert e2.distance == 200
    assert e2.stroke == "Individual Medley"
    assert len(e2.entries) == 1

