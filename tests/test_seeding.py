"""
Test suite for heat seeding algorithm.
"""
from src.seeding.seeder import (
    time_to_seconds,
    get_center_out_lanes,
    sort_entries_by_time,
    seed_event,
    format_heat_sheet,
)
from src.parser.extractor import extract_text_from_pdf, parse_events_from_text
from src.models.schemas import Entry, Swimmer


def test_time_to_seconds():
    """Test seed time to seconds conversion."""
    print("Testing time to seconds conversion...")
    
    assert time_to_seconds("1:23.45") == 83.45
    assert time_to_seconds("2:30.00") == 150.0
    assert time_to_seconds("0:45.50") == 45.50
    assert time_to_seconds("NT") == float('inf')
    assert time_to_seconds("nt") == float('inf')
    
    print("✓ Time conversion tests passed")


def test_center_out_lanes():
    """Test center-out lane pattern generation."""
    print("Testing center-out lane patterns...")
    
    # Test 8 lanes
    lanes_8 = get_center_out_lanes(8)
    assert lanes_8 == [4, 5, 3, 6, 2, 7, 1, 8], f"Expected [4, 5, 3, 6, 2, 7, 1, 8], got {lanes_8}"
    
    # Test 6 lanes
    lanes_6 = get_center_out_lanes(6)
    assert lanes_6 == [3, 4, 2, 5, 1, 6], f"Expected [3, 4, 2, 5, 1, 6], got {lanes_6}"
    
    # Test 4 lanes
    lanes_4 = get_center_out_lanes(4)
    assert len(lanes_4) == 4
    assert set(lanes_4) == {1, 2, 3, 4}
    
    print(f"✓ Center-out patterns correct (8-lane: {lanes_8})")


def test_entry_sorting():
    """Test that entries are sorted correctly by seed time."""
    print("Testing entry sorting...")
    
    swimmers = [
        Swimmer(name="Swimmer A", age=10, team_code="TEAM-A"),
        Swimmer(name="Swimmer B", age=10, team_code="TEAM-B"),
        Swimmer(name="Swimmer C", age=10, team_code="TEAM-C"),
    ]
    
    entries = [
        Entry(place=1, swimmer=swimmers[0], seed_time="2:30.00"),  # Slowest
        Entry(place=2, swimmer=swimmers[1], seed_time="2:15.00"),  # Middle
        Entry(place=3, swimmer=swimmers[2], seed_time="2:00.00"),  # Fastest
    ]
    
    sorted_entries = sort_entries_by_time(entries)
    
    # Should be sorted slowest to fastest
    assert sorted_entries[0].seed_time == "2:30.00"
    assert sorted_entries[1].seed_time == "2:15.00"
    assert sorted_entries[2].seed_time == "2:00.00"
    
    print("✓ Entry sorting tests passed")


def test_seeding_with_sample_entries():
    """Test seeding algorithm with a small manually created event."""
    print("\nTesting seeding algorithm...")
    
    swimmers = [Swimmer(name=f"Swimmer {i}", age=10, team_code=f"TEAM{i}") for i in range(1, 11)]
    
    entries = [
        Entry(place=i, swimmer=swimmers[i-1], seed_time=f"2:{59-i*2:02d}.00")
        for i in range(1, 11)
    ]
    
    from src.models.schemas import Event as EventModel
    event = EventModel(
        number=1,
        name="Test Event",
        gender="Boys",
        distance=200,
        stroke="Freestyle",
        entries=entries
    )
    
    # Seed for 8-lane pool
    heat_sheet = seed_event(event, lanes=8)
    
    # Verify
    assert heat_sheet.heats == 2, f"Expected 2 heats, got {heat_sheet.heats}"
    assert len(heat_sheet.assignments) == 10
    
    # Check heat distribution
    # Note: With new behavior, first heat has empty lanes (partial fill)
    heat_1_count = sum(1 for a in heat_sheet.assignments if a.heat == 1)
    heat_2_count = sum(1 for a in heat_sheet.assignments if a.heat == 2)
    
    assert heat_1_count == 2, f"Heat 1 should have 2 entries (slowest, with empty lanes), got {heat_1_count}"
    assert heat_2_count == 8, f"Heat 2 should have 8 entries (fastest), got {heat_2_count}"
    
    print(f"✓ Seeding algorithm tests passed")
    print(f"  - {heat_sheet.heats} heats created")
    print(f"  - Heat 1: {heat_1_count} slowest swimmers (with empty lanes)")
    print(f"  - Heat 2: {heat_2_count} fastest swimmers")
    
    # Test formatting
    formatted = format_heat_sheet(heat_sheet)
    assert "Event 1:" in formatted
    assert "Heat 1:" in formatted
    assert "Heat 2:" in formatted
    
    print("✓ Formatting tests passed")


def test_seeding_with_real_data():
    """Test seeding with real PDF data."""
    print("\nTesting seeding with real PDF data...")
    
    # Extract and parse events from sample PDF
    pdf_path = "data/samples/1769543968773-7a7qa8q6s.pdf"
    text = extract_text_from_pdf(pdf_path)
    events = parse_events_from_text(text)
    
    print(f"Parsed {len(events)} events from PDF")
    
    # Seed a few individual events
    individual_events = [e for e in events if e.entries and hasattr(e.entries[0], 'swimmer')]
    
    if individual_events:
        test_event = individual_events[0]
        print(f"\nTesting seeding for: Event {test_event.number} ({test_event.name})")
        print(f"  Entries: {len(test_event.entries)}")
        
        heat_sheet = seed_event(test_event, lanes=8)
        
        print(f"  Heats: {heat_sheet.heats}")
        print(f"  Assignments: {len(heat_sheet.assignments)}")
        
        # Verify all entries are assigned
        assert len(heat_sheet.assignments) == len(test_event.entries)
        
        # Verify all lanes are valid
        for assignment in heat_sheet.assignments:
            assert 1 <= assignment.lane <= 8
            assert 1 <= assignment.heat <= heat_sheet.heats
        
        # Print first heat
        print(f"\n  Heat 1 assignments:")
        for assignment in heat_sheet.assignments:
            if assignment.heat == 1:
                entry = assignment.entry
                if hasattr(entry, 'swimmer'):
                    print(f"    Lane {assignment.lane}: {entry.swimmer.name} - {entry.seed_time}")
        
        print("\n✓ Real data seeding tests passed")
    
    # Seed relay events
    relay_events = [e for e in events if e.entries and not hasattr(e.entries[0], 'swimmer')]
    
    if relay_events:
        test_event = relay_events[0]
        print(f"\nTesting relay seeding for: Event {test_event.number}")
        print(f"  Entries: {len(test_event.entries)}")
        
        heat_sheet = seed_event(test_event, lanes=8)
        
        print(f"  Heats: {heat_sheet.heats}")
        
        # Verify all entries are assigned
        assert len(heat_sheet.assignments) == len(test_event.entries)
        
        print("✓ Relay event seeding tests passed")


if __name__ == "__main__":
    test_time_to_seconds()
    test_center_out_lanes()
    test_entry_sorting()
    test_seeding_with_sample_entries()
    test_seeding_with_real_data()
    
    print("\n" + "="*50)
    print("All seeding tests passed! ✓")
    print("="*50)
