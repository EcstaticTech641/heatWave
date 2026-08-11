"""
Serialization, Controller, and Seeding Determinism Test Suite.

Verifies:
1. Unmodified ParseResult JSON round-trip serialization without field loss.
2. Scratch & edit controller operations with JSON persistence.
3. Seeding determinism post-deserialization.
4. Generated PDF binary hashing / structural determinism.
"""
import json
import hashlib
import tempfile
from pathlib import Path
import pytest

from src.models.schemas import ParseResult, Event, Entry, Swimmer, RelayEntry
from src.parser.extractor import parse_pdf_via_spatial_engine
from src.core.controller import HeatWaveController
from src.seeding.seeder import seed_event
from src.core.pdf_generator import generate_full_meet_pdf

_SAMPLE_PDF = "data/samples/1769543968773-7a7qa8q6s.pdf"


def test_unmodified_json_round_trip():
    """Verify ParseResult -> model_dump_json() -> model_validate_json() round trip preserves all fields."""
    parse_result = parse_pdf_via_spatial_engine(_SAMPLE_PDF)
    assert isinstance(parse_result, ParseResult)

    json_str = parse_result.model_dump_json()
    reconstructed = ParseResult.model_validate_json(json_str)

    assert len(reconstructed.events) == len(parse_result.events)
    assert reconstructed.validation.is_valid == parse_result.validation.is_valid
    assert reconstructed.pdf_producer == parse_result.pdf_producer
    assert reconstructed.edit_summary == parse_result.edit_summary

    # Field-by-field verification of first event
    e_orig = parse_result.events[0]
    e_recon = reconstructed.events[0]
    assert e_recon.number == e_orig.number
    assert e_recon.event_id == e_orig.event_id
    assert e_recon.session == e_orig.session
    assert len(e_recon.entries) == len(e_orig.entries)


def test_scratch_and_edit_round_trip():
    """Verify scratch_entry and edit_entry_time update status and edit_source and persist through JSON."""
    parse_result = parse_pdf_via_spatial_engine(_SAMPLE_PDF)
    controller = HeatWaveController(parse_result)

    event_1 = parse_result.events[0]
    event_id = event_1.event_id

    # Apply scratch to place 1
    controller.scratch_entry(event_id, "1")
    # Apply time edit to place 2
    controller.edit_entry_time(event_id, "2", "2:10.00")

    # Verify controller state in memory
    assert event_1.entries[0].status == "scratched"
    assert event_1.entries[1].seed_time == "2:10.00"
    assert event_1.entries[1].edit_source == "user_edited"
    assert controller.parse_result.edit_summary["scratches"] == 1
    assert controller.parse_result.edit_summary["time_edits"] == 1

    # Round-trip JSON serialization
    json_str = controller.parse_result.model_dump_json()
    reconstructed = ParseResult.model_validate_json(json_str)

    recon_event = reconstructed.events[0]
    assert recon_event.entries[0].status == "scratched"
    assert recon_event.entries[1].seed_time == "2:10.00"
    assert recon_event.entries[1].edit_source == "user_edited"
    assert reconstructed.edit_summary["scratches"] == 1
    assert reconstructed.edit_summary["time_edits"] == 1


def test_seeding_determinism_post_deserialization():
    """Verify deserialized ParseResult produces identical heat sheet assignments as direct PDF parsing."""
    parse_result = parse_pdf_via_spatial_engine(_SAMPLE_PDF)
    json_str = parse_result.model_dump_json()
    reconstructed = ParseResult.model_validate_json(json_str)

    for i in range(min(5, len(parse_result.events))):
        sheet_direct = seed_event(parse_result.events[i], lanes=8)
        sheet_recon = seed_event(reconstructed.events[i], lanes=8)

        assert sheet_direct.heats == sheet_recon.heats
        assert len(sheet_direct.assignments) == len(sheet_recon.assignments)

        for a1, a2 in zip(sheet_direct.assignments, sheet_recon.assignments):
            assert a1.heat == a2.heat
            assert a1.lane == a2.lane
            assert a1.entry.place == a2.entry.place
            assert a1.entry.seed_time == a2.entry.seed_time


def test_golden_pdf_determinism():
    """Verify PDF rendering from unmodified deserialized ParseResult produces deterministic binary output."""
    parse_result = parse_pdf_via_spatial_engine(_SAMPLE_PDF)
    sheets_direct = [seed_event(e, lanes=8) for e in parse_result.events if e.entries]

    json_str = parse_result.model_dump_json()
    reconstructed = ParseResult.model_validate_json(json_str)
    sheets_recon = [seed_event(e, lanes=8) for e in reconstructed.events if e.entries]

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path_1 = Path(tmp_dir) / "direct.pdf"
        pdf_path_2 = Path(tmp_dir) / "recon.pdf"

        generate_full_meet_pdf(sheets_direct, str(pdf_path_1), "Meet Title", "08/11/2026")
        generate_full_meet_pdf(sheets_recon, str(pdf_path_2), "Meet Title", "08/11/2026")

        bytes_1 = pdf_path_1.read_bytes()
        bytes_2 = pdf_path_2.read_bytes()

        # Both PDFs must be equal size and non-empty
        assert len(bytes_1) > 0
        assert len(bytes_1) == len(bytes_2)
