import os
import json
import pytest
from pathlib import Path
from src.parser.extractor import parse_pdf_via_spatial_engine
from src.seeding.seeder import seed_event

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PDF_DIR = FIXTURES_DIR / "psych_sheets"
EXPECTED_DIR = FIXTURES_DIR / "expected"


def _get_fixture_pairs():
    """Helper to discover matching (pdf_path, json_path) fixture pairs."""
    if not PDF_DIR.exists() or not EXPECTED_DIR.exists():
        return []
    pairs = []
    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        expected_json_path = EXPECTED_DIR / f"{pdf_path.stem}_expected.json"
        if expected_json_path.exists():
            pairs.append((pdf_path, expected_json_path))
    return pairs


FIXTURE_PAIRS = _get_fixture_pairs()


@pytest.mark.skipif(
    len(FIXTURE_PAIRS) == 0,
    reason=(
        "Golden regression fixtures not found. "
        "Place psych sheet PDFs in tests/fixtures/psych_sheets/ "
        "and run: python scripts/generate_fixtures.py --confirm"
    ),
)
@pytest.mark.parametrize("pdf_path, expected_json_path", FIXTURE_PAIRS, ids=[p[0].name for p in FIXTURE_PAIRS])
def test_golden_regression(pdf_path: Path, expected_json_path: Path):
    """End-to-end golden regression test validating extraction, validation scores,
    event details, heat seeding, and cross-event swimmer name integrity."""
    expected = json.loads(expected_json_path.read_text(encoding="utf-8"))

    # Execute runtime pipeline
    events, validation = parse_pdf_via_spatial_engine(str(pdf_path))

    # Assertion 1: Validation Pass
    assert validation.is_valid is True, f"Validation failed for {pdf_path.name}: {validation.errors}"
    assert validation.confidence_score >= 0.85, (
        f"Validation confidence score ({validation.confidence_score}) below 0.85 threshold for {pdf_path.name}"
    )

    # Assertion 2: Event & Entry Totals
    total_entries = sum(len(e.entries) for e in events)
    assert len(events) == expected["total_events"], (
        f"Event count mismatch for {pdf_path.name}: expected {expected['total_events']}, got {len(events)}"
    )
    assert total_entries == expected["total_entries"], (
        f"Total entry count mismatch for {pdf_path.name}: expected {expected['total_entries']}, got {total_entries}"
    )

    # Build maps for expected event details and seeding
    expected_events_map = {e["event_number"]: e for e in expected["events"]}
    expected_seeding_map = {s["event_number"]: s for s in expected["seeding"]}

    # Assertion 3 & 4 & 5: Per-event Identity, Seeding, and Name Set Integrity
    for event in events:
        e_num = event.number
        assert e_num in expected_events_map, f"Unexpected event number {e_num} parsed from {pdf_path.name}"
        exp_event = expected_events_map[e_num]

        # Assertion 3: Event Identity & Attributes
        assert event.name == exp_event["event_name"], f"Event {e_num} name mismatch"
        assert event.gender == exp_event["gender"], f"Event {e_num} gender mismatch"
        assert event.distance == exp_event["distance"], f"Event {e_num} distance mismatch"
        assert event.stroke == exp_event["stroke"], f"Event {e_num} stroke mismatch"
        assert len(event.entries) == exp_event["entry_count"], f"Event {e_num} entry count mismatch"

        # Execute Seeder
        heat_sheet = seed_event(event, lanes=8)
        assert e_num in expected_seeding_map, f"Missing seeding expectation for event {e_num}"
        exp_seeding = expected_seeding_map[e_num]

        # Assertion 4: Seeding Integrity (Total Heats & Heat/Lane Assignments)
        assert heat_sheet.heats == exp_seeding["total_heats"], (
            f"Event {e_num} total heats mismatch: expected {exp_seeding['total_heats']}, got {heat_sheet.heats}"
        )

        # Reconstruct runtime heats mapping
        is_relay = event.entries and not hasattr(event.entries[0], "swimmer")
        runtime_heats_dict = {}
        runtime_swimmer_names = set()

        for assignment in heat_sheet.assignments:
            h_num = assignment.heat
            if h_num not in runtime_heats_dict:
                runtime_heats_dict[h_num] = {}
            lane_str = str(assignment.lane)

            if is_relay:
                name_val = getattr(assignment.entry, "team_name", "Unknown Relay")
            else:
                name_val = assignment.entry.swimmer.name if hasattr(assignment.entry, "swimmer") and assignment.entry.swimmer else "Unknown Athlete"

            runtime_heats_dict[h_num][lane_str] = name_val
            runtime_swimmer_names.add(name_val)

        # Normalize fixture heats list to dictionary keyed by heat number
        exp_heats_dict = {h["heat_number"]: h["lanes"] for h in exp_seeding["heats"]}

        assert sorted(runtime_heats_dict.keys()) == sorted(exp_heats_dict.keys()), (
            f"Event {e_num} heat numbers mismatch"
        )

        for h_num, runtime_lanes in runtime_heats_dict.items():
            exp_lanes = exp_heats_dict[h_num]
            assert runtime_lanes == exp_lanes, (
                f"Event {e_num} Heat {h_num} lane assignments mismatch.\n"
                f"Expected: {exp_lanes}\nGot: {runtime_lanes}"
            )

        # Assertion 5: Cross-Event Contamination Guard (Swimmer/Team Name Set Equality)
        exp_swimmer_names = {
            name
            for h in exp_seeding["heats"]
            for name in h["lanes"].values()
        }
        assert runtime_swimmer_names == exp_swimmer_names, (
            f"Event {e_num} swimmer name set mismatch (possible cross-event contamination).\n"
            f"Diff: {runtime_swimmer_names.symmetric_difference(exp_swimmer_names)}"
        )
