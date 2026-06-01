"""
Demonstration of the complete heat seeding pipeline.
Extracts events from PDF, seeds them, and displays formatted heat sheets.
"""
from src.parser.extractor import extract_text_from_pdf, parse_events_from_text
from src.seeding.seeder import seed_event, format_heat_sheet


def main():
    print("=" * 100)
    print("HEATWAVE - HEAT SEEDING DEMONSTRATION")
    print("=" * 100)
    
    # Extract and parse
    pdf_path = "data/samples/1769543968773-7a7qa8q6s.pdf"
    print(f"\nExtracting text from: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    
    print("Parsing events...")
    events = parse_events_from_text(text)
    print(f"Successfully parsed {len(events)} events\n")
    
    # Separate into relay and individual events
    relay_events = [e for e in events if e.entries and not hasattr(e.entries[0], 'swimmer')]
    individual_events = [e for e in events if e.entries and hasattr(e.entries[0], 'swimmer')]
    
    print(f"Found {len(relay_events)} relay events and {len(individual_events)} individual events\n")
    
    # Demonstrate relay seeding
    if relay_events:
        print("=" * 100)
        print("RELAY EVENT HEAT SEEDING")
        print("=" * 100)
        
        relay_event = relay_events[0]
        print(f"\nSeeding Event {relay_event.number}: {relay_event.gender} {relay_event.distance}Y {relay_event.stroke} Relay")
        print(f"Total Entries: {len(relay_event.entries)}\n")
        
        heat_sheet = seed_event(relay_event, lanes=8)
        
        # Display heat sheet
        print(format_heat_sheet(heat_sheet))
        
        # Summary stats
        print(f"\n{'─' * 100}")
        print(f"Summary:")
        print(f"  Total Heats: {heat_sheet.heats}")
        print(f"  Total Lanes per Heat: {heat_sheet.lanes}")
        print(f"  Total Entries: {len(heat_sheet.assignments)}")
        for heat_num in range(1, heat_sheet.heats + 1):
            count = sum(1 for a in heat_sheet.assignments if a.heat == heat_num)
            print(f"  Heat {heat_num}: {count} entries")
    
    # Demonstrate individual event seeding
    if individual_events:
        print("\n" + "=" * 100)
        print("INDIVIDUAL EVENT HEAT SEEDING")
        print("=" * 100)
        
        # Show the largest individual event
        individual_events.sort(key=lambda e: len(e.entries), reverse=True)
        individual_event = individual_events[0]
        
        print(f"\nSeeding Event {individual_event.number}: {individual_event.gender} {individual_event.distance}Y {individual_event.stroke}")
        print(f"Total Entries: {len(individual_event.entries)}\n")
        
        heat_sheet = seed_event(individual_event, lanes=8)
        
        # Display heat sheet
        print(format_heat_sheet(heat_sheet))
        
        # Summary stats
        print(f"\n{'─' * 100}")
        print(f"Summary:")
        print(f"  Total Heats: {heat_sheet.heats}")
        print(f"  Total Lanes per Heat: {heat_sheet.lanes}")
        print(f"  Total Entries: {len(heat_sheet.assignments)}")
        for heat_num in range(1, heat_sheet.heats + 1):
            count = sum(1 for a in heat_sheet.assignments if a.heat == heat_num)
            print(f"  Heat {heat_num}: {count} entries")
    
    print("\n" + "=" * 100)
    print("DEMONSTRATION COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()
