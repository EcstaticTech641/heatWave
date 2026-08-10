import os
import pytest
import re
from pathlib import Path
from src.parser.extractor import (
    parse_pdf_via_spatial_engine,
    detect_source_format,
)
from src.parser.formats.ncaa.ncaa_parser import (
    parse_event_header_extended,
    NCAACollegeParser,
)
from src.models.schemas import Event, Swimmer, Entry, RelayEntry

pytestmark = pytest.mark.skipif(
    os.getenv("HEATWAVE_NCAA", "0") != "1",
    reason="NCAA parser disabled (set HEATWAVE_NCAA=1 to enable)"
)

def test_parse_event_header_extended():
    # 1. Standard swim event
    header_swim = "Event 41 Men 100 Yard Freestyle"
    res = parse_event_header_extended(header_swim)
    assert res is not None
    assert res["number"] == 41
    assert res["event_label"] == "41"
    assert res["gender"] == "Men"
    assert res["distance"] == 100
    assert res["stroke"] == "Freestyle"
    assert not res["is_exhibition"]
    assert not res["is_relay"]
    assert not res["is_diving"]

    # 2. Relay event
    header_relay = "Event 1 Women 200 Yard Medley Relay"
    res = parse_event_header_extended(header_relay)
    assert res is not None
    assert res["number"] == 1
    assert res["is_relay"]
    assert not res["is_diving"]

    # 3. Diving event
    header_dive = "Event 30 Women 3 mtr Diving NCAA D2"
    res = parse_event_header_extended(header_dive)
    assert res is not None
    assert res["number"] == 30
    assert res["event_label"] == "30"
    assert res["gender"] == "Women"
    assert res["distance"] == 0
    assert res["stroke"] == "3m Diving"
    assert res["name"] == "3 mtr Diving"
    assert not res["is_exhibition"]
    assert not res["is_relay"]
    assert res["is_diving"]

    # 4. Exhibition event (alphanumeric event ID)
    header_ex = "Event 41X Men 100 Yard Freestyle"
    res = parse_event_header_extended(header_ex)
    assert res is not None
    assert res["number"] == 41
    assert res["event_label"] == "41X"
    assert res["is_exhibition"]

    # 5. 3m Diving stroke label
    header_3m = "Event 40 Men 3 mtr Diving NCAA D2 460 dd 15.0"
    res = parse_event_header_extended(header_3m)
    assert res is not None
    assert res["stroke"] == "3m Diving"

    # 6. 1m Diving stroke label
    header_1m = "Event 41 Women 1 mtr Diving NCAA D2"
    res = parse_event_header_extended(header_1m)
    assert res is not None
    assert res["stroke"] == "1m Diving"


def test_ncaa_college_parser_individual_and_exhibition():
    raw_text = """
Event 41 Men 100 Yard Freestyle
Yr Name School Seed Time
1 Smith, John FR CMU 44.50
2 Doe, Jane SO CSM X45.12
3 Miller, Bob GS UCCS XNT
    """
    parser = NCAACollegeParser()
    events = parser.parse(raw_text)
    assert len(events) == 1
    event = events[0]
    assert event.number == 41
    assert len(event.entries) == 3
    
    assert event.entries[0].place == 1
    assert event.entries[0].swimmer.name == "Smith, John"
    assert event.entries[0].swimmer.year == "FR"
    assert event.entries[0].swimmer.team_code == "CMU"
    assert event.entries[0].seed_time == "44.50"

    assert event.entries[1].place == 2
    assert event.entries[1].swimmer.year == "SO"
    assert event.entries[1].seed_time == "X45.12"

    assert event.entries[2].place == 3
    assert event.entries[2].swimmer.year == "GS"
    assert event.entries[2].seed_time == "XNT"


def test_ncaa_college_parser_diving():
    raw_text = """
Event 30 Women 3 mtr Diving NCAA D2
Name Yr School Score
1 Smith, Sarah SR CSM 460.00
2 Doe, Alice GS CMU 412.50
3 Miller, Mary JR WCU NP
    """
    parser = NCAACollegeParser()
    events = parser.parse(raw_text)
    assert len(events) == 1
    event = events[0]
    assert event.number == 30
    assert event.name == "3 mtr Diving"
    assert len(event.entries) == 3
    
    assert event.entries[0].place == 1
    assert event.entries[0].swimmer.name == "Smith, Sarah"
    assert event.entries[0].swimmer.year == "SR"
    assert event.entries[0].seed_time == "460.00"

    assert event.entries[2].place == 3
    assert event.entries[2].swimmer.name == "Miller, Mary"
    assert event.entries[2].seed_time == "NP"


def test_ncaa_college_parser_relay():
    raw_text = """
Event 1 Women 200 Yard Medley Relay
Team Relay Seed Time
1 Colorado Mesa-CO A 1:40.12
2 Mines-CO B 1:43.45
3 Western Colorado-CO A X1:45.00
    """
    parser = NCAACollegeParser()
    events = parser.parse(raw_text)
    assert len(events) == 1
    event = events[0]
    assert event.number == 1
    assert len(event.entries) == 3
    
    assert event.entries[0].place == 1
    assert event.entries[0].team_name == "Colorado Mesa-CO A"
    assert event.entries[0].seed_time == "1:40.12"

    assert event.entries[2].place == 3
    assert event.entries[2].team_name == "Western Colorado-CO A"
    assert event.entries[2].seed_time == "X1:45.00"


def test_integration_rmac_pdf(monkeypatch):
    monkeypatch.setenv("HEATWAVE_NCAA", "1")
    pdf_path = "data/samples/2024_rmac_swd_psych.pdf"
    if not Path(pdf_path).exists():
        pytest.skip(f"RMAC sample PDF not found at {pdf_path}")

    # Use the full spatial layout pipeline
    events, _val = parse_pdf_via_spatial_engine(pdf_path)
    assert len(events) > 0

    # Verify event uniqueness & types
    event_ids = [e.event_label for e in events]
    assert "41" in event_ids
    assert "41X" in event_ids

    e_41 = next(e for e in events if e.event_label == "41")
    e_41x = next(e for e in events if e.event_label == "41X")

    assert not e_41.is_exhibition
    assert e_41x.is_exhibition
    assert e_41.number == 41
    assert e_41x.number == 41

    # Verify diving
    e_dives = [e for e in events if "Diving" in e.stroke]
    assert len(e_dives) > 0
    for ed in e_dives:
        assert all(isinstance(entry, Entry) for entry in ed.entries)
        # Check diving score parsed as raw string, not MM:SS
        for entry in ed.entries:
            assert re.match(r"^[Xx]?(?:\d+\.\d{2}|NP|NT)$", entry.seed_time)

    # Verify relays
    e_relays = [e for e in events if "Relay" in e.stroke]
    assert len(e_relays) > 0
    for er in e_relays:
        assert all(isinstance(entry, RelayEntry) for entry in er.entries)
