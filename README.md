# heatWave

**heatWave** transforms USA Swimming psych sheets (entry lists) into professionally formatted heat sheets for meet operations — eliminating hours of manual work by automating extraction, parsing, seeding, and PDF generation.

---

## Quick Start (For Coaches)

### Option 1: Download heatWave.exe (Recommended)

1. **Download** the latest release here `https://github.com/EcstaticTech641/heatWave/releases` (portable or setup.exe)
2. **Double-click** `heatWave.exe` to launch
3. **A native desktop window opens** — no browser needed, no Python required!
4. **Use the app** — upload your psych sheet and generate heat sheets in seconds

> **Works on Windows 10/11 with zero setup.**

### Option 2: Run from Source (For Developers)

```bash
# Clone the repo and install dependencies
pip install -r requirements.txt

# Launch the desktop app
python run_desktop.py
```

The app opens in a native `pywebview` desktop window powered by Streamlit.

---

## Five-Step Workflow

1. **Upload** your psych sheet PDF (drag & drop)
2. **Preview** parsed events to verify accuracy
3. **Customize** meet name, date, and pool lanes
4. **Generate** heat sheets (click button, ~5 seconds)
5. **Download** as PDFs — full meet or individual events

---

## What It Does

### Input
- USA Swimming psych sheet PDF (standard text-based format)
- Typically 80–150 KB

### Processing
1. **Extract** text from PDF (handles two-column layouts)
2. **Parse** events and swimmer entries
3. **Seed** heats using official USA Swimming rules
4. **Generate** professional PDF heat sheets

### Output
- **Full Meet PDF** — all events in one document (for meet director)
- **Individual Event PDFs** — one per event (for timers/officials)
- Both print-ready and coach-friendly formatted

### Example
```
Input:  State Swimming 10-Under Championship psych sheet
        78.3 KB, 28 events, 702 swimmers

Processing: < 5 seconds

Output:
  Full_Meet_Heatsheets.pdf  (83.7 KB, 29 pages)
  Event_01_Heatsheet.pdf    (2.9 KB)
  Event_02_Heatsheet.pdf    (2.7 KB)
  ... and 26 more individual event PDFs
```

---

## Features

### Core
- Drag-and-drop PDF upload interface
- Live event preview with filters and search
- Custom meet settings (title, date, lanes)
- USA Swimming-compliant heat seeding
- Professional PDF generation
- Individual and full-meet PDF downloads
- **100% offline** — no internet required, no data ever uploaded

### Supported
- Relay and individual events
- 4–10 lane pools (configurable)
- NT (no time) entries
- Multi-word names and team codes
- Standard seed time formats (`MM:SS.XX`)
- Batch processing (28+ events at once)

---

## Project Architecture

### Directory Structure
```
heatWave/
├── src/
│   ├── models/
│   │   └── schemas.py           # Data models (Pydantic)
│   ├── parser/
│   │   └── extractor.py         # PDF → Events
│   ├── seeding/
│   │   └── seeder.py            # Events → Heat assignments
│   ├── core/
│   │   └── pdf_generator.py     # Heat sheets → PDFs
│   └── ui/
│       ├── streamlit_app.py     # Streamlit UI
│       └── templates/           # UI templates / assets
├── tests/                       # Unit and integration tests
├── assets/
│   └── icon.ico                 # App icon
├── data/
│   ├── samples/                 # Example psych sheets
│   └── output/                  # Generated heat sheets
├── run_desktop.py               # Desktop launcher (Streamlit + pywebview)
├── build_heatwave.py            # Python build script
├── heatWave.spec                # PyInstaller spec file
├── installer.iss                # Inno Setup installer script
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

### Technology Stack
| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Desktop Window | pywebview |
| UI Framework | Streamlit |
| PDF Extraction | pdfplumber, PyMuPDF |
| Data Validation | Pydantic |
| PDF Generation | ReportLab |
| Packaging | PyInstaller + Inno Setup |
| Testing | pytest |

---

## For Developers

### Core Components

#### 1. Parser (`src/parser/extractor.py`)
```python
from src.parser.extractor import extract_text_from_pdf, parse_events_from_text

text   = extract_text_from_pdf("psych_sheet.pdf")
events = parse_events_from_text(text)  # → List[Event]
```

#### 2. Seeder (`src/seeding/seeder.py`)
```python
from src.seeding.seeder import seed_event

heat_sheet = seed_event(event, lanes=8)  # → HeatSheet
```

#### 3. PDF Generator (`src/core/pdf_generator.py`)
```python
from src.core.pdf_generator import generate_full_meet_pdf

generate_full_meet_pdf(
    heat_sheets,
    "output.pdf",
    meet_title="My Meet",
    meet_date="01/15/2025"
)
```

#### 4. Desktop Launcher (`run_desktop.py`)
Starts Streamlit in a background thread and wraps it in a native `pywebview` window. Credentials are auto-created to skip Streamlit's first-run email prompt.

```bash
python run_desktop.py
```

### Full Pipeline Example
```python
from src.parser.extractor import extract_text_from_pdf, parse_events_from_text
from src.seeding.seeder import seed_event
from src.core.pdf_generator import generate_full_meet_pdf

text        = extract_text_from_pdf("psych_sheet.pdf")
events      = parse_events_from_text(text)
heat_sheets = [seed_event(e, lanes=8) for e in events]

generate_full_meet_pdf(
    heat_sheets,
    "output/heat_sheets.pdf",
    meet_title="My Meet",
    meet_date="01/15/2025"
)
```

### Running Tests
```bash
pytest                          # Run all tests
pytest tests/test_parsing.py    # Parser only
pytest tests/test_seeding.py    # Seeder only
pytest tests/test_integration.py # Full pipeline
```

---

## Building & Distribution

### Prerequisites
- Python 3.11+
- `pip install -r requirements.txt`
- `pip install pyinstaller`
- [Inno Setup](https://jrsoftware.org/isinfo.php) (for installer, optional)

### Build the Standalone Executable
```bash
# Option 1: Python build script (recommended)
python build_heatwave.py

# Option 2: Manual PyInstaller
pyinstaller --clean heatWave.spec
```

Output: `dist/heatWave/heatWave.exe` (~22 MB launcher + bundled dependencies)

### Build the Windows Installer (Optional)
With [Inno Setup](https://jrsoftware.org/isinfo.php) installed:
```
Open installer.iss in Inno Setup → Build → Compile
```
Output: `dist/heatWave_v1.0_setup.exe`

### Distribute to Coaches
**Portable (no install needed):**
1. Zip the entire `dist/heatWave/` folder
2. Share via email, Google Drive, Dropbox, or USB
3. Coaches extract and double-click `heatWave.exe`

**Installer:**
1. Share `heatWave_v1.0_setup.exe`
2. Coaches run the installer — creates Start Menu + optional Desktop shortcut
3. Launch from Start Menu or Desktop

---

## USA Swimming Seeding Rules

The app implements official USA Swimming preliminary seeding:

**Heat Assignment:**
- Swimmers sorted by seed time (slowest → fastest)
- Heats filled sequentially (fastest swimmers in last heat)

**Lane Placement (Center-Out):**
```
8-lane pool:  Lane 4 → 5 → 3 → 6 → 2 → 7 → 1 → 8
```

---

## Configuration

### Meet Settings (in app UI)
| Setting | Description |
|---|---|
| Meet Title | Name printed on every heat sheet |
| Meet Date | Format: `MM/DD/YYYY` |
| Pool Lanes | Number of lanes (4–10, typically 8) |

### App Window (in `run_desktop.py`)
```python
webview.create_window(
    'heatWave — Heat Sheet Generator',
    'http://localhost:8501',
    width=1100,
    height=780,
    min_size=(800, 600)
)
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Error processing PDF" | Verify it's a standard USA Swimming text-based psych sheet |
| "No events found" | Check the PDF isn't a scanned image (OCR not yet supported) |
| "Missing swimmers" | Confirm the swimmers appear in the source psych sheet |
| App window doesn't open | Ensure `pywebview` is installed: `pip install pywebview` |
| Slow first launch | Normal — Streamlit's first boot takes ~3–5 seconds |

---

## Dependencies

```
pdfplumber       PDF text extraction
PyMuPDF          PDF parsing (fitz)
pydantic         Data validation
reportlab        PDF generation
streamlit        UI framework
pywebview        Native desktop window
pytest           Testing
```

---

## Privacy & Security

- **100% Offline** — no internet connection required
- **No Data Storage** — PDFs generated in memory, not saved to disk
- **Local Processing** — all computation on your machine
- **Safe for Sensitive Data** — meet data never leaves your computer

---

## Performance

| Operation | Speed |
|---|---|
| PDF text extraction | 55K characters in < 1 second |
| Event seeding (702 entries) | < 2 seconds |
| Full-meet PDF generation | < 3 seconds |
| Total end-to-end | < 5 seconds |

---

## What's Next

### Completed in v1.0
- PDF text extraction
- Event parsing (28+ events, 700+ entries)
- USA Swimming heat seeding algorithm
- Professional PDF generation
- Streamlit UI with drag-and-drop upload
- Native desktop window (pywebview)
- Portable `.exe` and Windows installer

### Future Enhancements
- [ ] OCR support for scanned PDFs
- [ ] Manual entry editing interface
- [ ] Scratch / no-show handling
- [ ] Export to Hy-Tek / Meet Maestro formats
- [ ] Advanced seeding options (circle seeding, time trials)
- [ ] macOS / Linux support

---

## Quick Reference

| Task | Command |
|---|---|
| Launch desktop app | `python run_desktop.py` |
| Run all tests | `pytest` |
| Build executable | `python build_heatwave.py` |

---

## License & Credits

**Project:** heatWave  
**Version:** 1.1.3  
**Last Updated:** June 2026  
**License:** See [LICENSE](LICENSE)

Made for USA Swimming coaches and meet directors.
