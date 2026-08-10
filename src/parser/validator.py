import re
from typing import List
from src.models.schemas import Event, ValidationResult


def _parse_time_to_seconds(time_str: str) -> float | None:
    """Helper to convert a seed time string to seconds float."""
    time_str = time_str.strip().upper()
    if time_str == "NT":
        return None
    if re.match(r"^\d{1,2}:\d{2}\.\d{2}$", time_str):
        parts = time_str.split(":")
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60.0 + seconds
    if re.match(r"^\d{1,2}\.\d{2}$", time_str):
        return float(time_str)
    return None


def validate_parsed_events(events: List[Event]) -> ValidationResult:
    """Runs automated validation and sanity checks on extracted Event objects.

    Args:
        events: List of Event objects parsed from psych sheet.

    Returns:
        ValidationResult object containing is_valid status, warnings, errors,
        and confidence_score (0.0 to 1.0).
    """
    warnings: List[str] = []
    errors: List[str] = []
    confidence_score = 1.0
    is_valid = True

    # ------------------------------------------------------------------------
    # Check 1: Non-Empty Meet
    # ------------------------------------------------------------------------
    total_events = len(events)
    total_entries = sum(len(e.entries) for e in events)

    if total_events == 0 or total_entries == 0:
        errors.append("No events or swimmer entries were extracted from document.")
        return ValidationResult(
            is_valid=False,
            warnings=warnings,
            errors=errors,
            confidence_score=0.0,
        )

    # ------------------------------------------------------------------------
    # Check 2: Merged Column Detection (Entry Count Thresholds)
    # ------------------------------------------------------------------------
    hard_merged_cols = False
    soft_merged_cols = False
    for e in events:
        entry_count = len(e.entries)
        if entry_count > 120:
            hard_merged_cols = True
            errors.append(
                f"Event {e.number} has {entry_count} entries (exceeds max threshold 120). Likely merged columns."
            )
        elif entry_count > 80:
            soft_merged_cols = True
            warnings.append(
                f"Large entry count ({entry_count}) in Event {e.number} — verify this is correct."
            )

    if hard_merged_cols:
        is_valid = False
        confidence_score -= 0.30
    elif soft_merged_cols:
        confidence_score -= 0.05

    # ------------------------------------------------------------------------
    # Check 3: Name Integrity
    # ------------------------------------------------------------------------
    athlete_names: List[str] = []
    for e in events:
        for entry in e.entries:
            if hasattr(entry, "swimmer") and getattr(entry, "swimmer") is not None:
                athlete_names.append(entry.swimmer.name)

    if athlete_names:
        passing_names = 0
        for name in athlete_names:
            # Must match Last, First pattern (at least 1 char each) and contain no digits
            if re.match(r"^[A-Za-z\s'\-\.]+\,\s*[A-Za-z\s'\-\.]+", name) and not re.search(r"\d", name):
                passing_names += 1

        pass_rate = passing_names / len(athlete_names)
        if pass_rate < 0.50:
            is_valid = False
            confidence_score -= 0.30
            errors.append(
                f"Name integrity check failed: only {pass_rate:.1%} of athlete names match expected format."
            )
        elif pass_rate < 0.90:
            confidence_score -= 0.10
            warnings.append(
                f"Low athlete name integrity: {pass_rate:.1%} of athlete names match expected format."
            )
        elif pass_rate < 1.00:
            confidence_score -= 0.02

    # ------------------------------------------------------------------------
    # Check 4a: Seed Time Format Check
    # ------------------------------------------------------------------------
    all_times: List[str] = []
    for e in events:
        for entry in e.entries:
            all_times.append(entry.seed_time)

    if all_times:
        valid_format_count = 0
        for t in all_times:
            ts = t.strip().upper()
            if (
                ts == "NT"
                or re.match(r"^\d{1,2}:\d{2}\.\d{2}$", ts)
                or re.match(r"^\d{1,2}\.\d{2}$", ts)
            ):
                valid_format_count += 1

        fail_count = len(all_times) - valid_format_count
        fail_rate = fail_count / len(all_times)

        if fail_rate > 0.10:
            is_valid = False
            confidence_score -= 0.25
            errors.append(
                f"Seed time format check failed: {fail_rate:.1%} of seed times have invalid formatting."
            )
        elif fail_rate > 0:
            confidence_score -= 0.05
            warnings.append(
                f"Seed time formatting issues: {fail_rate:.1%} of seed times have non-standard format."
            )

    # ------------------------------------------------------------------------
    # Check 4b: Seed Time Plausibility Check (Soft warnings)
    # ------------------------------------------------------------------------
    implausible_count = 0
    for e in events:
        for entry in e.entries:
            time_str = entry.seed_time.strip().upper()
            if time_str == "NT":
                continue
            sec = _parse_time_to_seconds(time_str)
            if sec is not None:
                if sec > 1800.0:  # > 30:00.00
                    implausible_count += 1
                    warnings.append(
                        f"Unusually long seed time ({entry.seed_time}) in Event {e.number} — verify."
                    )
                elif sec < 10.0:  # < 10.00 seconds
                    implausible_count += 1
                    warnings.append(
                        f"Unusually short seed time ({entry.seed_time}) in Event {e.number} — verify."
                    )

    if implausible_count > 0:
        penalty = min(0.10, implausible_count * 0.01)
        confidence_score -= penalty

    # ------------------------------------------------------------------------
    # Clamp score and finalize is_valid
    # ------------------------------------------------------------------------
    confidence_score = max(0.0, min(1.0, round(confidence_score, 4)))
    if errors:
        is_valid = False

    return ValidationResult(
        is_valid=is_valid,
        warnings=warnings,
        errors=errors,
        confidence_score=confidence_score,
    )
