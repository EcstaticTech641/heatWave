# heatWave
> **Psych sheets in. Heat sheets out. In under 5 seconds.**

**heatWave** converts USA Swimming psych sheet PDFs into print-ready heat sheets — automating extraction, prelim seeding, timeline estimation, and PDF generation that usually takes meet directors hours by hand.

---

## What It Does

heatWave processes psych sheet PDFs from meet management software, runs an automated spatial layout engine to parse events and athlete entries, and seeds all heats according to standard USA Swimming center-out lane rules. It provides a real-time validation banner with confidence scoring, an interactive event preview dashboard, and generates publication-ready meet PDFs with optional wall-clock timeline estimates.

---

## Quick Start (For Coaches & Meet Directors)

1. **Download:** Get `heatWave.exe` from the latest release.
2. **Launch:** Double-click `heatWave.exe` — your default web browser opens automatically with the local desktop UI.
3. **Upload:** Drag & drop your USA Swimming psych sheet PDF.
4. **Generate:** Review the validation health score, adjust session settings, and click **Generate Heat Sheets** to download your PDFs.

---

## 5-Step Coach Workflow

```text
  ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
  │ 1. UPLOAD │ ──► │ 2. REVIEW │ ──► │ 3. ADJUST │ ──► │ 4. SEED   │ ──► │ 5. EXPORT │
  │ PDF file  │     │ Validation│     │ Sessions  │     │ Heats     │     │ Print PDF │
  └───────────┘     └───────────┘     └───────────┘     └───────────┘     └───────────┘
```

1. **Upload PDF:** Drag & drop any Hy-Tek or TeamUnify psych sheet PDF.
2. **Review Validation Health:** Inspect the green/yellow/red parsing banner and entry counts.
3. **Adjust Settings:** Configure pool lane count (e.g. 6 or 8 lanes), session start times, and heat gap intervals.
4. **Seed Heats:** Automatically apply USA Swimming prelim seeding rules (slowest-to-fastest heats, center-out lane placement).
5. **Export & Print:** Download complete meet heat sheets or single-event PDFs.

---

## Supported Formats

- ✅ **Standard USA Swimming age-group psych sheets** (Hy-Tek / TeamUnify 1- and 2-column text PDFs)
- ❌ **Scanned / image-based PDFs** *(no OCR engine enabled in v1.1.4)*
- ❌ **NCAA / collegiate championship sheets** *(experimental engine isolated behind `HEATWAVE_NCAA=1`)*
- ❌ **Custom or non-standard header formats** *(headers omitting standard distance or stroke labels)*

See [DEFECTS.md](DEFECTS.md) for detailed format boundaries, defect logs, and known limitations.

---

## For Developers

### Setup & Local Development
```bash
# Clone the repository
git clone https://github.com/EcstaticTech/heatWave.git
cd heatWave

# Set up virtual environment
python -m venv .venv
.venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt

# Launch desktop app in development mode
python run_desktop.py
```

### Running Tests
```bash
# Run full automated test suite
python -m pytest

# Run golden regression tests only
python -m pytest tests/test_golden_regression.py
```

### Building Standalone Executable
```bash
# Package standalone Windows executable
python build_heatwave.py
```
Output executable is created at `dist/heatWave/heatWave.exe`.

---

## Architecture Overview

```text
heatWave/
├── assets/                          # Application icons and visual assets
├── dist/                            # Packaged PyInstaller executable bundle
├── docs/                            # Guides and technical documentation
├── scripts/                         # Fixture generation and automation utilities
│   └── generate_fixtures.py        # Snapshot generator for golden regression tests
├── src/
│   ├── core/                        # PDF generator & timeline estimation engines
│   │   ├── pdf_generator.py
│   │   └── timeline.py
│   ├── models/                      # Pydantic schemas (Event, Entry, HeatSheet, ValidationResult)
│   │   └── schemas.py
│   ├── parser/                      # Psych sheet parsing engine & spatial reconstructor
│   │   ├── extractor.py
│   │   ├── validator.py            # Data validation & health scoring engine
│   │   └── formats/                # Parser format subpackages
│   │       └── ncaa/               # Inactive experimental NCAA parser (HEATWAVE_NCAA=1)
│   ├── seeding/                     # USA Swimming prelim seeding engine
│   │   └── seeder.py
│   └── ui/                          # Streamlit UI dashboard & seeding guards
│       └── streamlit_app.py
├── tests/                           # Unit, integration, & golden regression test suites
│   ├── fixtures/                   # Golden test fixture PDFs & JSON baselines
│   └── test_golden_regression.py
├── DEFECTS.md                       # Format boundaries and defect log
├── heatWave.spec                    # PyInstaller build specification
├── pyproject.toml                   # Project metadata & build settings
├── requirements.txt                 # Python dependencies
└── run_desktop.py                   # Desktop pywebview launcher
```

---

## Disclaimer & Privacy

- **100% Offline & Private**: Zero data collected, stored, or uploaded. All processing runs locally on your host machine.
- **Unofficial Utility**: Independent personal project; not affiliated with, sponsored by, or endorsed by USA Swimming, NCAA, Hy-Tek, or TeamUnify.
- **Full Notice**: For complete details on privacy, non-affiliation, and rules compliance, see [PRIVACY_AND_DISCLAIMERS.md](docs/PRIVACY_AND_DISCLAIMERS.md).

---

## License & Credits

**Project:** heatWave  
**Version:** 1.3.2  
**Last Updated:** August 2026  
**License:** See [LICENSE](LICENSE)  

Made for USA Swimming coaches and meet directors.
