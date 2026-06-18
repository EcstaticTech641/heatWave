import pdfplumber
import pytest
import os
from src.parser.extractor import extract_spatial_words_to_lines

# ---------------------------------------------------------------------------
# Legacy script-style baseline — left intact for backward compatibility
# ---------------------------------------------------------------------------

def test_extract():
    pdf_path = "data/samples/1769543968773-7a7qa8q6s.pdf"
    
    print("--- pdfplumber column cropping text ---")
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        width = first_page.width
        height = first_page.height
        
        left_bbox = (0, 0, width / 2, height)
        right_bbox = (width / 2, 0, width, height)
        
        left_col = first_page.crop(left_bbox)
        right_col = first_page.crop(right_bbox)
        
        left_text = left_col.extract_text()
        right_text = right_col.extract_text()
        
        print("--- LEFT COLUMN ---")
        print(left_text[:500])
        print("...")
        print("--- RIGHT COLUMN ---")
        print(right_text[:500])
        print("...")

if __name__ == "__main__":
    test_extract()


# ---------------------------------------------------------------------------
# Phase 6.1 — Assertion-driven unit test
# ---------------------------------------------------------------------------

_SAMPLE_PDF = "data/samples/1769543968773-7a7qa8q6s.pdf"


@pytest.mark.skipif(
    not os.path.exists(_SAMPLE_PDF),
    reason=f"Sample PDF not present at {_SAMPLE_PDF}",
)
def test_extract_spatial_words_to_lines():
    """extract_spatial_words_to_lines must return a non-empty list of lines,
    each of which is a list of pdfplumber word-token dicts with the expected keys."""
    result = extract_spatial_words_to_lines(_SAMPLE_PDF, page_num=0)

    # Must return something
    assert isinstance(result, list), "Result must be a list"
    assert len(result) > 0, "Result must be non-empty for a content-bearing page"

    # Every element must be a non-empty list
    for line_idx, line in enumerate(result):
        assert isinstance(line, list), f"Line {line_idx} must be a list"
        assert len(line) > 0, f"Line {line_idx} must not be empty"

        for token in line:
            # Each token must be a dict with the required spatial keys
            assert isinstance(token, dict), f"Token in line {line_idx} must be a dict"
            for key in ("text", "x0", "x1", "top", "bottom"):
                assert key in token, (
                    f"Token in line {line_idx} missing key '{key}': {token}"
                )
            # text must be a non-empty string
            assert isinstance(token["text"], str) and token["text"].strip(), (
                f"Token 'text' in line {line_idx} must be a non-empty string"
            )
            # Coordinate values must be numeric and make geometric sense
            assert token["x0"] <= token["x1"], (
                f"x0 must be <= x1 in line {line_idx}: {token}"
            )
            assert token["top"] <= token["bottom"], (
                f"top must be <= bottom in line {line_idx}: {token}"
            )

    # Lines must be in top-to-bottom order
    tops = [line[0]["top"] for line in result]
    assert tops == sorted(tops), "Lines must be sorted top-to-bottom"

