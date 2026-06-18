"""
Module: test_parsing_variants.py
Purpose: Test variant matching and signature detection for Hy-Tek and TeamUnify layouts.
Inputs: Synthetic and real-world raw text line samples.
Outputs: Assertion results.
Dependencies: pytest, src.parser.extractor
Architecture role: Unit tests for testing layout detection and regex micro-matchers.
"""
import re
from src.parser.extractor import (
    detect_source_format,
    HYTEK_EVENT_RE,
    HYTEK_ATHLETE_RE,
    TEAMUNIFY_EVENT_RE,
    TEAMUNIFY_ATHLETE_RE,
)


def test_signature_detector():
    """Verify that detect_source_format correctly identifies the layout source."""
    # Test Hy-Tek branding detection
    assert detect_source_format("Welcome to the meet\nHy-Tek's Meet Manager 8.0") == "hytek"
    assert detect_source_format("HY-TEK's Meet Manager - 12:00 PM") == "hytek"
    
    # Test TeamUnify/TouchPad branding detection
    assert detect_source_format("Powered by TeamUnify database") == "teamunify"
    assert detect_source_format("TouchPad Meet Management Software") == "teamunify"
    
    # Test heuristic fallbacks
    assert detect_source_format("#1 Girls 10 & Under 50 Free\n1 Smith, Emily S 10 MAC") == "teamunify"
    assert detect_source_format("Event 1 Girls 50 Fly\n#2 Boys 50 Free") == "teamunify"
    
    # Test generic fallback
    assert detect_source_format("Some random swimming document text") == "generic"


def test_hytek_regex_matchers():
    """Test the Hy-Tek micro-matchers on valid Hy-Tek lines."""
    # Event headers
    event_line_1 = "Event 1  Girls 10 & Under 50 Yard Freestyle"
    event_line_2 = "Event 12  Boys 11-12 100 Yard Butterfly"
    
    assert re.search(HYTEK_EVENT_RE, event_line_1) is not None
    assert re.search(HYTEK_EVENT_RE, event_line_2) is not None
    
    # Athlete rows
    athlete_line_1 = "1 Smith, Emily S           10 MAC-NC      28.45"
    athlete_line_2 = "2 De La Cruz, Maria        10 TYDE-NC     29.10"
    athlete_line_3 = "3 Jones, Sarah               9 YOTA-NC     31.05  NT"
    
    assert re.match(HYTEK_ATHLETE_RE, athlete_line_1.strip()) is not None
    assert re.match(HYTEK_ATHLETE_RE, athlete_line_2.strip()) is not None
    
    # Note: athlete_line_3 has "NT" after a seed time or multiple fields. 
    # The regex checks for \s+(\d{1,2}:\d{2}\.\d{2}|\d{2}\.\d{2}|NT). 
    # Let's verify how it handles NT.
    assert re.search(HYTEK_ATHLETE_RE, athlete_line_3) is not None


def test_teamunify_regex_matchers():
    """Test TeamUnify micro-matchers on TeamUnify specific lines."""
    # Event headers
    event_line_1 = "#1 Girls 10 & Under 50 Free"
    event_line_2 = "Event 3  Women 15 & Over 200 IM"
    
    assert re.match(TEAMUNIFY_EVENT_RE, event_line_1) is not None
    assert re.match(TEAMUNIFY_EVENT_RE, event_line_2) is not None
    
    # Athlete rows
    athlete_line_1 = "1  Smith, Emily S        10  MAC         28.45Y"
    athlete_line_2 = "2  De La Cruz, Maria     10  TYDE        29.10L"
    athlete_line_3 = "3  Jones, Sarah           9  YOTA          NT"
    
    assert re.match(TEAMUNIFY_ATHLETE_RE, athlete_line_1.strip()) is not None
    assert re.match(TEAMUNIFY_ATHLETE_RE, athlete_line_2.strip()) is not None
    assert re.match(TEAMUNIFY_ATHLETE_RE, athlete_line_3.strip()) is not None
