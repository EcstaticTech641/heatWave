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


def validate_parsed_events(events: List[Event], pdf_producer: str | None = None) -> ValidationResult:
    """Runs automated validation and sanity checks on extracted Event objects.

    Args:
        events: List of Event objects parsed from psych sheet.
        pdf_producer: Optional PDF Creator/Producer metadata string.

    Returns:
        ValidationResult object containing is_valid status, warnings, errors,
        confidence_score (0.0 to 1.0), and pdf_producer.
    """
    warnings: List[str] = []
    errors: List[str] = []
    confidence_score = 1.0
    is_valid = True

    # ------------------------------------------------------------------------
    # Check 0: PDF Producer Metadata Check
    # ------------------------------------------------------------------------
    if pdf_producer:
        producer_upper = pdf_producer.upper()
        if not ("HY-TEK" in producer_upper or "MEET MANAGER" in producer_upper):
            warnings.append("Unrecognized PDF producer string. Verify output layout.")

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
    # Check 2: Large Entry Count Thresholds (Soft warnings only)
    # ------------------------------------------------------------------------
    large_entry_count = False
    for e in events:
        entry_count = len(e.entries)
        if entry_count > 250:
            large_entry_count = True
            warnings.append(
                f"Large entry count ({entry_count}) in Event {e.number} — verify layout."
            )
        elif entry_count > 80:
            large_entry_count = True
            warnings.append(
                f"Large entry count ({entry_count}) in Event {e.number} — verify this is correct."
            )

    if large_entry_count:
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
            # Must match Last, First pattern — allow Unicode letters for accented names
            # (e.g. Andrés, Müller, O'Brien). Digits in name are still rejected.
            if (
                re.match(r"^[\w\s'\-\.]+\,\s*[\w\s'\-\.]+", name, re.UNICODE)
                and not re.search(r"\d", name)
            ):
                passing_names += 1

        pass_rate = passing_names / len(athlete_names)
        # All Check 3 outcomes are soft confidence penalties only.
        # is_valid=False is reserved for structural failures (Checks 1 & 2).
        if pass_rate < 0.50:
            confidence_score -= 0.20
            warnings.append(
                f"Low athlete name integrity: only {pass_rate:.1%} of athlete names match "
                f"expected 'Last, First' format. Possible column drift or non-standard formatting."
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
    from src.parser.extractor import normalize_seed_time
    all_times: List[str] = []
    for e in events:
        for entry in e.entries:
            all_times.append(entry.seed_time)

    if all_times:
        valid_format_count = 0
        for t in all_times:
            ts = normalize_seed_time(t)
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
        pdf_producer=pdf_producer,
    )
