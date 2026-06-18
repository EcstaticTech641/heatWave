"""
Module: test_normalization.py
Purpose: Test the seed time and age group normalizer functions with various raw inputs.
Inputs: Target strings representing different time and age group layouts.
Outputs: Assertion results.
Dependencies: pytest, src.parser.extractor
Architecture role: Unit tests for checking data normalization correctness.
"""
from src.parser.extractor import (
    normalize_seed_time,
    normalize_age_group,
)


def test_seed_time_normalization():
    """Verify that normalize_seed_time accurately sanitizes various time input formats."""
    # Under-minute formats
    assert normalize_seed_time("28.45") == "28.45"
    assert normalize_seed_time("54.21") == "54.21"
    
    # Standard format
    assert normalize_seed_time("1:02.11") == "1:02.11"
    
    # Suffix stripping (Y, L, S)
    assert normalize_seed_time("28.45Y") == "28.45"
    assert normalize_seed_time("29.10L") == "29.10"
    assert normalize_seed_time("31.05S") == "31.05"
    assert normalize_seed_time("1:02.11Y") == "1:02.11"
    
    # Partial times (no decimal)
    assert normalize_seed_time("2:13") == "2:13.00"
    
    # No-time variations
    assert normalize_seed_time("NT") == "NT"
    assert normalize_seed_time("No Time") == "NT"
    assert normalize_seed_time("n.t.") == "NT"
    assert normalize_seed_time("  NT  ") == "NT"


def test_age_group_normalization():
    """Verify that normalize_age_group standardizes different age group formats."""
    # Under age groups
    assert normalize_age_group("10 & Under") == "10 & Under"
    assert normalize_age_group("10&U") == "10 & Under"
    assert normalize_age_group("10 & U") == "10 & Under"
    assert normalize_age_group("10&Under") == "10 & Under"
    assert normalize_age_group("8 & Under") == "8 & Under"
    
    # Over age groups
    assert normalize_age_group("15 & Over") == "15 & Over"
    assert normalize_age_group("15&O") == "15 & Over"
    assert normalize_age_group("15 & O") == "15 & Over"
    assert normalize_age_group("15&Over") == "15 & Over"
    
    # Unchanged formats
    assert normalize_age_group("11-12") == "11-12"
    assert normalize_age_group("13-14") == "13-14"
