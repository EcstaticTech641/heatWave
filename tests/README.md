# heatWave Test Suite & Golden Regression Guide

This directory contains automated unit, integration, and golden regression tests for **heatWave**.

---

## 1. Directory Structure

```text
tests/
├── fixtures/                          # Golden test fixtures (gitignored)
│   ├── psych_sheets/                 # Sample USA Swimming psych sheet PDFs
│   └── expected/                     # Canonical expected JSON snapshots
├── test_extract.py                    # Spatial line extraction unit tests
├── test_golden_regression.py         # End-to-end golden regression test suite
├── test_integration.py               # PDF-to-seeding pipeline integration tests
├── test_ncaa_parser.py               # NCAA parser tests (HEATWAVE_NCAA=1)
├── test_normalization.py             # Event/time normalization unit tests
├── test_parser_baseline.py           # Baseline text parser regression tests
├── test_parser_factory.py            # Parser routing factory unit tests
├── test_parsing.py                   # Psych sheet event extraction tests
├── test_parsing_variants.py          # Software variant parser tests (Hy-Tek / TeamUnify)
├── test_seeding.py                   # Seeding algorithm & center-out lane assignment tests
├── test_spatial_extraction.py        # Column detection & layout reconstruction tests
└── test_validation.py               # Data validation engine & sanity check tests
```

---

## 2. Running Tests

### Run Full Test Suite
```bash
python -m pytest
```

### Run Golden Regression Suite Only
```bash
python -m pytest tests/test_golden_regression.py
```

> [!NOTE]
> If local fixture PDFs are missing from `tests/fixtures/psych_sheets/`, `test_golden_regression.py` will gracefully skip with a helpful notification.

---

## 3. Golden Fixture Management

Golden regression tests enforce deterministic output for:
- Event and entry extraction counts
- Event names, strokes, genders, and distances
- Seed time formatting and layout confidence scores
- USA Swimming center-out heat and lane assignments
- Athlete/team name set integrity (cross-event contamination guard)

### Dry Run (Compare Current Code Output vs Existing Snapshots)
```bash
python scripts/generate_fixtures.py
```
This runs the current extraction and seeding pipeline against candidate PDFs in `tests/fixtures/psych_sheets/` and prints diff status without modifying files on disk.

### Freeze / Update Fixtures
When an intentional parsing or seeding algorithm improvement is made, update the golden JSON baselines:
```bash
python scripts/generate_fixtures.py --confirm
```

---

## 4. Workflow for Adding New Sample PDFs

1. Copy the candidate USA Swimming psych sheet PDF to `tests/fixtures/psych_sheets/`.
2. Verify candidate PDF health (`is_valid == True` and `confidence_score >= 0.85`).
3. Run `python scripts/generate_fixtures.py --confirm` to freeze matching target `.json` file in `tests/fixtures/expected/`.
4. Run `python -m pytest tests/test_golden_regression.py` to confirm 100% pass rate.
