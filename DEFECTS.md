# heatWave Known Defects & Format Scope Boundaries

This document formalizes supported psych sheet format boundaries, documented limitations, and tracked defect logs for **heatWave** (v1.3.2).

---

## 1. Supported Format Boundaries

### Primary Supported Formats (USA Swimming Age-Group Meets)
- **Hy-Tek Meet Manager Psych Sheets:**
  - Standard single-column text PDFs
  - Standard two-column text PDFs (`Event N ...` headers and numbered entry lists)
- **TeamUnify Psych Sheets:**
  - Standard text-based psych sheet layouts (`#N` or `Event N` header patterns)

### Relay Event Parsing Boundary

- **Relay team entries are parsed and seeded** using Team Name, Relay Letter (A/B/C), and Entry Time.
- **Relay Leg Swimmers:** Individual relay leg athlete names are **not extracted** in v1.3.2. Multi-line relay leg blocks (listing individual swimmer splits) are parsed at the structural level only; the `RelayEntry.swimmers` field is reserved for a future release (post-v1.4.0).
- **Rationale:** Relay leg name formatting varies across Hy-Tek versions and multi-column layouts. Relay seeding is strictly time-based and does not require individual leg names.

---

## 2. Unsupported / Out-of-Scope Formats

| Format Category | Status | Rationale |
| :--- | :--- | :--- |
| **Scanned / Image-based PDFs** | ❌ Unsupported | OCR engine (e.g. Tesseract) is not included in v1.1.4. PDFs containing bitmap page images yield 0 extracted characters. |
| **NCAA / Collegiate Championship Sheets** | ⚠️ Inactive (Experimental) | Multi-column collegiate sheets with complex structural anchoring, diving scores, and year/school fields are isolated in `src/parser/formats/ncaa/` and gated behind `HEATWAVE_NCAA=1`. |
| **Custom / Non-Standard Headers** | ❌ Unsupported | Headers omitting standard event distance (yards/meters) or stroke labels cannot be parsed reliably. |

---

## 3. Known Defect Log

### B1 — NCAA Diving Entries Format
- **Description:** Diving entries use point totals (e.g. `245.50`) instead of seed times (`MM:SS.XX`).
- **Workaround:** Gated behind `HEATWAVE_NCAA=1` in experimental subpackage `src/parser/formats/ncaa/ncaa_parser.py`.

### B2 — Exhibition Flag Merging
- **Description:** Alphanumeric exhibition events (e.g. `Event 41X`) require event label normalization to avoid truncating non-numeric event suffixes.
- **Workaround:** Extended event label tracking preserves labels like `"41X"` for presentation.

### C1 — Relay Stroke Label Normalization
- **Description:** Certain legacy Hy-Tek relay headers format as `200 Yard Free Relay` vs `200 Yard Freestyle Relay`.
- **Workaround:** Normalizer maps `Free Relay` and `FR` to standard stroke strings.

### C2 — Desktop PyInstaller Cold-Start Race Condition (Fixed in v1.2.1)
- **Description:** Opening `heatWave.exe` rendered an Edge WebView2 "ERR_CONNECTION_REFUSED" or "Can't reach this page" error due to pywebview launching before Streamlit finished socket binding.
- **Fix:** Added explicit IPv4 `127.0.0.1` binding, server thread status monitoring, multi-path UI script resolution, and health-check error window fallback in `run_desktop.py`.

---

## 4. Codebase Audit Log (Retained Functions)

| Function / Symbol | Location | Status | Notes |
| :--- | :--- | :--- | :--- |
| `extract_text_from_pdf` | `src/parser/extractor.py` | Retained | Legacy text extraction pipeline fallback used by CLI scripts & tests. |
| `format_heat_sheet` | `src/seeding/seeder.py` | Retained | Plain-text terminal heat sheet formatter used by CLI tools & diagnostics. |
| `GenericParser` | `src/parser/extractor.py` | Retained | Safe default fallback returned by `ParserFactory` when format detection is ambiguous. |

---

## 5. Diagnostic Heuristics

- **Multi-Check Diagnostic Heuristic:**
  When 2+ validation checks fail concurrently on an event (e.g., High Entry Count + Time Format Errors + Name Integrity Drops), treat the failure as a Parser Extraction Defect (such as column bleeding) rather than validator over-sensitivity.
