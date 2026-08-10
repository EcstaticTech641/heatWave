#!/usr/bin/env python
"""
Utility script to generate canonical golden JSON fixtures for heatWave regression testing.

Usage:
    python scripts/generate_fixtures.py            # Dry run: compares output vs existing fixtures
    python scripts/generate_fixtures.py --confirm  # Overwrites expected fixture JSON files
"""
import sys
import os
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.parser.extractor import parse_pdf_via_spatial_engine
from src.seeding.seeder import seed_event


def build_fixture_dict(pdf_path: Path) -> dict | None:
    """Processes a sample PDF and returns the canonical fixture dictionary structure."""
    print(f"Processing PDF: {pdf_path.name} ...")
    events, validation = parse_pdf_via_spatial_engine(str(pdf_path))

    if not validation.is_valid or validation.confidence_score < 0.85:
        print(f"❌ Aborting fixture generation for {pdf_path.name}: "
              f"is_valid={validation.is_valid}, score={validation.confidence_score}")
        if validation.errors:
            print("   Errors:", validation.errors)
        if validation.warnings:
            print("   Warnings:", validation.warnings)
        return None

    total_events = len(events)
    total_entries = sum(len(e.entries) for e in events)

    event_summaries = []
    seeding_summaries = []

    for event in events:
        is_relay = event.entries and not hasattr(event.entries[0], "swimmer")
        event_summaries.append({
            "event_number": event.number,
            "event_name": event.name,
            "gender": event.gender,
            "distance": event.distance,
            "stroke": event.stroke,
            "entry_count": len(event.entries),
        })

        heat_sheet = seed_event(event, lanes=8)
        heats_dict = {}
        for assignment in heat_sheet.assignments:
            h_num = assignment.heat
            if h_num not in heats_dict:
                heats_dict[h_num] = {}
            lane_str = str(assignment.lane)

            if is_relay:
                name_val = getattr(assignment.entry, "team_name", "Unknown Relay")
            else:
                name_val = assignment.entry.swimmer.name if hasattr(assignment.entry, "swimmer") and assignment.entry.swimmer else "Unknown Athlete"
            heats_dict[h_num][lane_str] = name_val

        formatted_heats = [
            {
                "heat_number": h_num,
                "lanes": heats_dict[h_num],
            }
            for h_num in sorted(heats_dict.keys())
        ]

        seeding_summaries.append({
            "event_number": event.number,
            "total_heats": heat_sheet.heats,
            "heats": formatted_heats,
        })

    fixture_data = {
        "fixture_version": "1.0",
        "source_file": pdf_path.name,
        "generated_by": "heatWave v1.1.4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation_summary": {
            "is_valid": validation.is_valid,
            "confidence_score": validation.confidence_score,
        },
        "total_events": total_events,
        "total_entries": total_entries,
        "events": event_summaries,
        "seeding": seeding_summaries,
    }

    return fixture_data


def main():
    parser = argparse.ArgumentParser(description="Generate golden test fixtures for heatWave.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Overwrite existing fixture JSON files in tests/fixtures/expected/",
    )
    args = parser.parse_args()

    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures"
    pdf_dir = fixtures_dir / "psych_sheets"
    expected_dir = fixtures_dir / "expected"

    if not pdf_dir.exists():
        print(f"Error: PDF fixture directory not found at {pdf_dir}")
        sys.exit(1)

    expected_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"Error: No PDF files found in {pdf_dir}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} sample PDF(s) in {pdf_dir}")
    print(f"Mode: {'CONFIRM (Overwriting target files)' if args.confirm else 'DRY RUN (Diff check only)'}\n")

    changes_detected = False

    for pdf_file in pdf_files:
        fixture_data = build_fixture_dict(pdf_file)
        if not fixture_data:
            sys.exit(1)

        expected_filename = f"{pdf_file.stem}_expected.json"
        target_path = expected_dir / expected_filename

        new_json_str = json.dumps(fixture_data, indent=2)

        if target_path.exists():
            existing_data = json.loads(target_path.read_text(encoding="utf-8"))
            compare_data = dict(fixture_data)
            compare_existing = dict(existing_data)
            compare_data.pop("generated_at", None)
            compare_existing.pop("generated_at", None)

            if compare_data == compare_existing:
                print(f"  [OK] {expected_filename} matches existing baseline.")
                continue
            else:
                print(f"  [DIFF] {expected_filename} HAS DIFFS from existing baseline.")
                changes_detected = True
        else:
            print(f"  [NEW] {expected_filename}")
            changes_detected = True

        if args.confirm:
            target_path.write_text(new_json_str, encoding="utf-8")
            print(f"  [WRITE] Wrote {target_path}")

    print("\n" + "=" * 60)
    if not args.confirm:
        if changes_detected:
            print("Dry run complete. Diffs/new fixtures detected.")
            print("Run 'python scripts/generate_fixtures.py --confirm' to freeze fixtures.")
        else:
            print("Dry run complete. All generated fixtures match existing target files.")
    else:
        print("Fixtures successfully frozen and updated!")


if __name__ == "__main__":
    main()
