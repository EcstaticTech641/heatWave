# Swim Psych-to-Heat Converter

## Project Overview
**Project Name:** `heatWave`  
**Short Description:** A tool that reads a USA Swimming psych sheet PDF (entry rankings) and automatically produces a formatted heat sheet (meet program) with properly seeded heats and lane assignments.

**Goal**  
Eliminate the manual work coaches currently do when a psych sheet arrives before the heat sheet. The app will:
- Extract all text reliably (native PDF text or OCR fallback).
- Parse events, individual entries, and relays.
- Apply standard USA Swimming prelim seeding rules.
- Output a clean, printable heat sheet (PDF) that mirrors the style coaches are used to seeing.

## Project Intentions
1. **Primary Intention**  
   Save coaches hours at every meet by turning the psych sheet into a usable heat sheet in < 30 seconds.

2. **Core Value**  
   - 100% offline capable (coaches are often in venues with poor Wi-Fi).  
   - Accurate handling of the two-column layout common in psych sheets.  
   - Correct gender separation (odd event numbers = girls, even = boys).  
   - Proper relay parsing (team name + optional individual names).  
   - Standard USA Swimming seeding (fastest-to-slowest heat order, center-lane preference, 8-lane default with configurability).

3. **Long-term Intentions (post-MVP)**  
   - Export in Hy-Tek / TeamUnify / Meet Maestro compatible formats.  
   - Scratch / no-show editing UI.  
   - Team roster integration for automatic name/team lookup.

## Scope (MVP – Minimum Viable Product)
### In Scope
- PDF upload (single or multi-page psych sheets).
- Text extraction (native PDF text preferred, OCR fallback for scanned/image PDFs).
- Layout-aware parsing that respects two-column format (left column finishes before right column continues).
- Structured data model for:
  - Events (number, name, gender, distance, stroke).
  - Entries (place, swimmer name, age, team code, seed time).
  - Relays (team name, seed time, optional 4 swimmers).
- Heat seeding algorithm following current USA Swimming rules (prelims, 8 lanes, circle/seeded heat assignment).
- Simple web or desktop UI: drag-and-drop PDF → preview parsed data → “Generate Heat Sheet” → downloadable PDF.
- Basic error reporting (e.g., “Could not parse Event 5 – please check PDF”).

### Out of Scope (MVP)
- Full meet management system (no live timing, no results entry).
- Automatic import into 3rd-party software (Hy-Tek, etc.).
- Mobile-only version.
- Advanced editing (add/remove swimmers inside the app).
- Non-USA Swimming formats or international rules.

## Limitations & Assumptions
- **PDF Variability** – Psych sheets from different meet software (Hy-Tek, Meet Maestro, etc.) have slightly different layouts. MVP will target the most common formats; users may need to supply 2–3 sample PDFs during development for tuning.
- **OCR Accuracy** – Scanned psych sheets may require manual correction on rare ambiguous names/times. We will provide a “review & edit” table for the MVP.
- **Seeding Rules** – We will implement the current USA Swimming Technical Rules (preliminary seeding). Any meet-specific deviations will need manual adjustment.
- **Two-Column Layout** – The parser will detect and re-flow columns correctly; extreme custom layouts may fail.
- **Assumptions**:
  - Standard 8-lane pool (configurable).
  - Seed times are in MM:SS.XX or NT format.
  - No duplicate entries or scratches in the input psych sheet.
  - Coach has a modern computer (Python runtime is easy to install).

## Current Requirements (as stated by user)
1. **Text Detection / OCR Method** – Highest priority starting point.
2. **Data Storage** – Structured model for events and entries.
3. **Processing Algorithm** – Parsing + USA Swimming seeding logic.
4. **Front-end Development** – User-friendly interface.
5. **Tech Preference** – Node.js / JavaScript / Python (or any high-level language).  
   → **Recommendation**: **Python is the best choice**.  
   Java or C++ are **not** better for this project.

### Why Python (not Java or C++)?
- Python has mature, battle-tested libraries for exactly this workflow (`pdfplumber`, `PyMuPDF`, `pytesseract`, `pdf2image`).
- Rapid prototyping of parsing rules and seeding algorithm.
- Excellent data handling (Pydantic models, pandas for quick debugging).
- Easy desktop or web UI (Streamlit for MVP in hours, or FastAPI + React).
- C++ would be massive overkill (no benefit in speed or size).  
- Java works but is more verbose and slower to iterate on parsing logic.

## Recommended Technology Stack (MVP)

| Layer              | Technology                          | Reason |
|--------------------|-------------------------------------|--------|
| **PDF/Text Extraction** | `PyMuPDF (fitz)` + `pdfplumber`    | Best layout awareness for two-column pages |
| **OCR Fallback**   | `pdf2image` + `pytesseract`        | Handles scanned PDFs reliably |
| **Data Model**     | Pydantic dataclasses / JSON schema | Type-safe, easy validation |
| **Parsing Logic**  | Rule-based + regex (with optional spaCy) | Fast and deterministic |
| **Seeding Engine** | Pure Python functions              | Implements official USA Swimming rules |
| **Backend**        | FastAPI (or Flask)                 | Simple REST API, easy to run locally |
| **Frontend**       | Streamlit (MVP) or React + Vite    | Streamlit = fastest possible UI |
| **PDF Output**     | `WeasyPrint` or `ReportLab`        | Clean, professional heat-sheet PDFs |
| **Desktop Option** | PyInstaller or Streamlit + native wrapper | One-click executable for coaches |
| **Storage**        | In-memory + optional JSON/SQLite   | No database needed for MVP |
| **Language**       | Python 3.11+                       | High-level, exactly what you asked for |

**Alternative Pure-JS Stack** (if you strongly prefer Node.js):  
`pdf.js` + `pdf-lib` + `Tesseract.js` – possible but OCR and column detection are noticeably weaker and slower.

## Project Phases (Suggested Roadmap)
1. **Phase 0 (1–2 days)** – Create repo, gather 3–5 real (anonymized) psych sheet PDFs.
2. **Phase 1 (Text Extraction)** – Prove we can pull clean text while respecting two-column flow.
3. **Phase 2 (Parsing)** – Build event/entry/relay data model and parser.
4. **Phase 3 (Seeding)** – Implement heat & lane assignment logic.
5. **Phase 4 (UI & Output)** – Streamlit UI + PDF generation.
6. **Phase 5 (Polish)** – Error handling, manual review table, packaging.

## Acceptance Criteria (MVP)
- Upload a typical psych sheet → successfully parses every event and every entry.
- Correctly identifies relays vs. individuals.
- Produces a heat sheet PDF that a coach could print and hand to timers.
- Runs completely offline.
- Handles both text-based and scanned PDFs.

---

**Next Immediate Step**  
Share 1–2 sample psych sheet PDFs (you can redact names if you want) and I can start prototyping the text extraction code right away.

This `project.md` file is ready to be dropped into a GitHub repo. Let me know if you want to adjust scope, add features, or start coding the first phase!