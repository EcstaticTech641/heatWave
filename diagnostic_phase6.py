"""
Diagnostic script for Phase 6 failures.
Run from project root: .venv\Scripts\python.exe diagnostic_phase6.py
"""
import sys
sys.path.insert(0, ".")

from src.parser.extractor import (
    extract_spatial_words_to_lines,
    detect_column_boundaries,
    reconstruct_text_by_columns,
    parse_pdf_via_spatial_engine,
    extract_text_from_pdf,
    parse_events_from_text,
    FALLBACK_2_COLUMN, FALLBACK_3_COLUMN,
    PAGE_WIDTH, NOISE_FLOOR, GUTTER_WIDTH_THRESHOLD,
)
import pdfplumber

PDF_2COL = "data/samples/1769543968773-7a7qa8q6s.pdf"
PDF_3COL = "data/samples/psych-sheet-3col.pdf"


def analyse_page(pdf_path, page_num=0, label=""):
    print(f"\n{'='*70}")
    print(f"  {label}  |  page {page_num}")
    print(f"{'='*70}")
    lines = extract_spatial_words_to_lines(pdf_path, page_num)
    print(f"  Lines detected: {len(lines)}")

    # Build raw density histogram
    density = [0] * PAGE_WIDTH
    for line in lines:
        for word in line:
            left  = max(0, int(word["x0"]))
            right = min(PAGE_WIDTH - 1, int(word["x1"]))
            for x in range(left, right + 1):
                density[x] += 1

    # Find ALL gutters
    gutters = []
    in_gutter = False
    g_start = 0
    for x in range(PAGE_WIDTH):
        if density[x] <= NOISE_FLOOR:
            if not in_gutter:
                in_gutter = True
                g_start = x
        else:
            if in_gutter:
                g_end = x - 1
                w = g_end - g_start + 1
                if w >= GUTTER_WIDTH_THRESHOLD:
                    gutters.append((g_start, g_end, w))
                in_gutter = False
    if in_gutter:
        g_end = PAGE_WIDTH - 1
        w = g_end - g_start + 1
        if w >= GUTTER_WIDTH_THRESHOLD:
            gutters.append((g_start, g_end, w))

    print(f"  Gutters (>={GUTTER_WIDTH_THRESHOLD}px, density<={NOISE_FLOOR}): {len(gutters)}")
    for g in gutters:
        mx = max(density[g[0]:g[1]+1])
        print(f"    x={g[0]:3d}-{g[1]:3d}  width={g[2]:3d}px  max_density={mx}")

    # detect_column_boundaries result
    boundaries = detect_column_boundaries(lines)
    print(f"  Detected boundaries: {boundaries}")
    print(f"    is FALLBACK_2_COLUMN? {boundaries is FALLBACK_2_COLUMN}")

    # Reconstruction sample
    text = reconstruct_text_by_columns(lines, boundaries)
    print(f"  Reconstructed text: {len(text)} chars")
    print(f"  First 300 chars:\n---\n{text[:300]}\n---")
    return boundaries


# ── 2-column sheet ───────────────────────────────────────────────────────────
print("\n\n" + "="*70)
print("  2-COL SHEET DIAGNOSIS")
with pdfplumber.open(PDF_2COL) as pdf:
    n = len(pdf.pages)
print(f"  Total pages: {n}")
for pg in range(min(2, n)):
    analyse_page(PDF_2COL, pg, f"2COL p{pg}")

# ── 3-column sheet ───────────────────────────────────────────────────────────
print("\n\n" + "="*70)
print("  3-COL SHEET DIAGNOSIS")
with pdfplumber.open(PDF_3COL) as pdf:
    n = len(pdf.pages)
print(f"  Total pages: {n}")
for pg in range(min(2, n)):
    analyse_page(PDF_3COL, pg, f"3COL p{pg}")

# ── Legacy pipeline on 3-col ─────────────────────────────────────────────────
print("\n\n" + "="*70)
print("  3-COL: LEGACY PIPELINE")
legacy_text = extract_text_from_pdf(PDF_3COL)
print(f"  Text length: {len(legacy_text)}")
print(f"  First 600 chars:\n---\n{legacy_text[:600]}\n---")
legacy_events, _val1 = parse_events_from_text(legacy_text)
print(f"  Events found: {len(legacy_events)}")

# ── Spatial engine full run on 3-col ─────────────────────────────────────────
print("\n\n" + "="*70)
print("  3-COL: SPATIAL ENGINE FULL RUN")
spatial_events, _val2 = parse_pdf_via_spatial_engine(PDF_3COL)
print(f"  Events found: {len(spatial_events)}")
print(f"  auto_layout_failed: {any(e.auto_layout_failed for e in spatial_events) if spatial_events else 'N/A'}")
