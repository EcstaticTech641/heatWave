"""
Test suite for event and entry parsing logic.
"""
from src.parser.extractor import (
    extract_text_from_pdf,
    parse_event_header,
    parse_individual_entry,
    parse_relay_entry,
    parse_seed_time,
    parse_events_from_text,
)


def test_seed_time_parsing():
    """Test seed time validation and normalization."""
    print("Testing seed time parsing...")
    
    assert parse_seed_time("2:13.43") == "2:13.43"
    assert parse_seed_time("NT") == "NT"
    assert parse_seed_time("2:13") == "2:13.00"
    assert parse_seed_time("  1:23.45  ") == "1:23.45"
    assert parse_seed_time("nt") == "NT"
    
    print("✓ Seed time parsing tests passed")


def test_event_header_parsing():
    """Test event header line parsing."""
    print("Testing event header parsing...")
    
    # Test relay event
    line1 = "Event 1 Girls 10 & Under 200 Yard Freestyle Relay"
    result = parse_event_header(line1)
    assert result is not None
    assert result[0] == 1  # event number
    assert result[1] == "Girls"  # gender
    assert result[3] == 200  # distance
    assert "Freestyle" in result[4]  # stroke
    
    # Test individual event
    line2 = "Event 4 Boys 10 & Under 200 Yard IM"
    result = parse_event_header(line2)
    assert result is not None
    assert result[0] == 4
    assert result[1] == "Boys"
    
    print("✓ Event header parsing tests passed")


def test_individual_entry_parsing():
    """Test individual swimmer entry parsing."""
    print("Testing individual entry parsing...")
    
    # Format: place name age team seed_time
    line1 = "1 Meek, Keaston 10 Bartlesville Spl-OK 2:42.05"
    result = parse_individual_entry(line1)
    assert result is not None
    place, name, age, team, seed = result
    assert place == 1
    assert "Keaston" in name
    assert age == 10
    assert "Bartlesville" in team
    assert seed == "2:42.05"
    
    # Test with longer names
    line2 = "26 Sunarto, Lily 10 Life Time Fitnes-OK 4:23.38L"
    result = parse_individual_entry(line2)
    assert result is not None
    place, name, age, team, seed = result
    assert place == 26
    assert "Lily" in name
    assert age == 10
    
    print("✓ Individual entry parsing tests passed")


def test_relay_entry_parsing():
    """Test relay entry parsing."""
    print("Testing relay entry parsing...")
    
    # Format: place team_name seed_time
    line1 = "1 King Marlin Swim-OK A 2:13.43"
    result = parse_relay_entry(line1)
    assert result is not None
    place, team, seed = result
    assert place == 1
    assert "King Marlin" in team
    assert seed == "2:13.43"
    
    # Test another format
    line2 = "5 Jenks Trojan Swi-OK B 2:30.93"
    result = parse_relay_entry(line2)
    assert result is not None
    place, team, seed = result
    assert place == 5
    
    print("✓ Relay entry parsing tests passed")


def test_full_extraction_and_parsing():
    """Test full PDF extraction and event parsing."""
    print("\nTesting full PDF extraction and parsing...")
    
    pdf_path = "data/samples/1769543968773-7a7qa8q6s.pdf"
    
    # Extract text
    text = extract_text_from_pdf(pdf_path)
    assert len(text) > 100
    print(f"✓ Extracted {len(text)} characters from PDF")
    
    # Parse events
    events = parse_events_from_text(text)
    assert len(events) > 0
    print(f"✓ Parsed {len(events)} events from text")
    
    # Check first event details
    if events:
        event = events[0]
        print(f"\nFirst event details:")
        print(f"  Event {event.number}: {event.name}")
        print(f"  Gender: {event.gender}")
        print(f"  Distance: {event.distance} yards")
        print(f"  Stroke: {event.stroke}")
        print(f"  Entries: {len(event.entries)}")
        
        if event.entries:
            first_entry = event.entries[0]
            if hasattr(first_entry, 'swimmer'):
                print(f"  First entry: {first_entry.swimmer.name} - {first_entry.seed_time}")
            else:
                print(f"  First entry: {first_entry.team_name} - {first_entry.seed_time}")
    
    # Display summary
    print(f"\nParsing Summary:")
    for event in events[:5]:  # Show first 5 events
        entry_type = "Individual" if events[0].entries and hasattr(events[0].entries[0], 'swimmer') else "Relay"
        print(f"  Event {event.number}: {event.gender} {event.distance}Y {event.stroke} ({len(event.entries)} entries)")
    
    print("\n✓ Full extraction and parsing tests passed")


if __name__ == "__main__":
    test_seed_time_parsing()
    test_event_header_parsing()
    test_individual_entry_parsing()
    test_relay_entry_parsing()
    test_full_extraction_and_parsing()
    print("\n" + "="*50)
    print("All tests passed! ✓")
    print("="*50)
