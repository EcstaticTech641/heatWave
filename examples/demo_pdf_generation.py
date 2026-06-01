"""
Test PDF heat sheet generation with real meet data.
"""
from pathlib import Path
from src.parser.extractor import extract_text_from_pdf, parse_events_from_text
from src.seeding.seeder import seed_event
from src.core.pdf_generator import generate_heat_sheet_pdf, generate_full_meet_pdf


def main():
    print("=" * 100)
    print("PDF HEAT SHEET GENERATION TEST")
    print("=" * 100)
    
    # Extract and parse events
    pdf_path = "data/samples/1769543968773-7a7qa8q6s.pdf"
    print(f"\nExtracting events from: {pdf_path}")
    
    text = extract_text_from_pdf(pdf_path)
    events = parse_events_from_text(text)
    print(f"Parsed {len(events)} events")
    
    # Seed all events
    print("\nSeeding events...")
    heat_sheets = []
    for event in events:
        if event.entries:
            heat_sheet = seed_event(event, lanes=8)
            heat_sheets.append(heat_sheet)
    
    print(f"Seeded {len(heat_sheets)} events")
    
    # Generate individual PDFs for a few events
    output_dir = Path("data/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate first event PDF
    if heat_sheets:
        print(f"\n--- Generating Single Event PDF ---")
        first_sheet = heat_sheets[0]
        event = first_sheet.event
        
        output_pdf = output_dir / f"Event_{event.number:02d}_Heatsheet.pdf"
        print(f"Generating: {output_pdf.name}")
        
        pdf_path = generate_heat_sheet_pdf(
            first_sheet,
            str(output_pdf),
            meet_title="Oklahoma Swimming - 10-Under Champions",
            meet_date="07/18/2025 - 07/20/2025"
        )
        
        print(f"✓ PDF generated: {pdf_path}")
        print(f"  Event: {event.number} - {event.gender} {event.distance}Y {event.stroke}")
        print(f"  Heats: {first_sheet.heats}")
        print(f"  Entries: {len(first_sheet.assignments)}")
    
    # Generate full meet PDF
    print(f"\n--- Generating Full Meet PDF ---")
    full_meet_pdf = output_dir / "Full_Meet_Heatsheets.pdf"
    print(f"Generating: {full_meet_pdf.name}")
    print(f"Including {len(heat_sheets)} events...")
    
    pdf_path = generate_full_meet_pdf(
        heat_sheets,
        str(full_meet_pdf),
        meet_title="Oklahoma Swimming - 10-Under Champions",
        meet_date="07/18/2025 - 07/20/2025"
    )
    
    print(f"✓ Full meet PDF generated: {pdf_path}")
    print(f"  Total size: {pdf_path.stat().st_size / 1024:.1f} KB")
    
    # Generate a few more individual event PDFs
    print(f"\n--- Generating Sample Event PDFs ---")
    sample_indices = [0, 2, 4]  # First, third, fifth events
    
    for i in sample_indices:
        if i < len(heat_sheets):
            sheet = heat_sheets[i]
            event = sheet.event
            
            output_pdf = output_dir / f"Event_{event.number:02d}_Heatsheet.pdf"
            
            pdf_path = generate_heat_sheet_pdf(
                sheet,
                str(output_pdf),
                meet_title="Oklahoma Swimming - 10-Under Champions",
                meet_date="07/18/2025 - 07/20/2025"
            )
            
            print(f"✓ Generated: Event {event.number} ({event.gender} {event.distance}Y {event.stroke})")
    
    print(f"\n" + "=" * 100)
    print("PDF GENERATION COMPLETE")
    print("=" * 100)
    print(f"\nOutput files saved to: {output_dir.absolute()}")
    print(f"\nGenerated Files:")
    for pdf_file in sorted(output_dir.glob("*.pdf")):
        size_kb = pdf_file.stat().st_size / 1024
        print(f"  - {pdf_file.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
