import pytest
from src.models.schemas import Event, Entry, Swimmer, RelayEntry
from src.parser.validator import validate_parsed_events


def _create_mock_entry(place: int, name: str, seed_time: str, team: str = "TEST-CO") -> Entry:
    """Helper to construct individual athlete Entry objects."""
    return Entry(
        place=place,
        swimmer=Swimmer(name=name, age=12, team_code=team),
        seed_time=seed_time,
    )


def test_empty_event_list():
    """Test 1: Empty event list or 0 total entries returns is_valid = False and score 0.0."""
    result = validate_parsed_events([])
    assert result.is_valid is False
    assert result.confidence_score == 0.0
    assert len(result.errors) > 0

    empty_event = Event(
        number=1,
        name="Empty Event",
        gender="Girls",
        distance=50,
        stroke="Freestyle",
        entries=[],
    )
    result_empty_entries = validate_parsed_events([empty_event])
    assert result_empty_entries.is_valid is False
    assert result_empty_entries.confidence_score == 0.0
    assert len(result_empty_entries.errors) > 0


def test_merged_column_detection():
    """Test 2: Entry count thresholds (>80 soft warning, >120 hard error)."""
    # Soft warning: 90 entries (>80, <=120)
    entries_90 = [
        _create_mock_entry(i, "Swimmer, Athlete", "25.50")
        for i in range(1, 91)
    ]
    event_90 = Event(
        number=1,
        name="Large 50 Free",
        gender="Girls",
        distance=50,
        stroke="Freestyle",
        entries=entries_90,
    )
    result_soft = validate_parsed_events([event_90])
    assert result_soft.is_valid is True
    assert result_soft.confidence_score >= 0.95
    assert any("Large entry count" in w for w in result_soft.warnings)

    # Large event (125 entries) soft warning
    entries_125 = [
        _create_mock_entry(i, "Swimmer, Athlete", "25.50")
        for i in range(1, 126)
    ]
    event_125 = Event(
        number=2,
        name="Huge 50 Free",
        gender="Boys",
        distance=50,
        stroke="Freestyle",
        entries=entries_125,
    )
    result_hard = validate_parsed_events([event_125])
    assert result_hard.is_valid is True
    assert result_hard.confidence_score >= 0.90
    assert any("Large entry count" in w for w in result_hard.warnings)


def test_invalid_seed_time_format():
    """Test 3: Invalid time string formats lower confidence score."""
    # 5 entries, 3 with malformed time strings (>10% fail rate)
    bad_entries = [
        _create_mock_entry(1, "Jones, Alice", "INVALID_1"),
        _create_mock_entry(2, "Smith, Bob", "INVALID_2"),
        _create_mock_entry(3, "Taylor, Charlie", "99999"),
        _create_mock_entry(4, "Davis, Diana", "1:05.50"),
        _create_mock_entry(5, "Evans, Evan", "NT"),
    ]
    event = Event(
        number=1,
        name="100 Backstroke",
        gender="Girls",
        distance=100,
        stroke="Backstroke",
        entries=bad_entries,
    )
    result = validate_parsed_events([event])
    assert result.is_valid is False
    assert result.confidence_score <= 0.75
    assert any("Seed time format check failed" in e for e in result.errors)


def test_valid_usa_swimming_mock_data():
    """Test 4: Valid USA Swimming mock event data returns is_valid = True and score >= 0.90."""
    valid_entries = [
        _create_mock_entry(1, "Miller, Hannah", "1:02.15"),
        _create_mock_entry(2, "Wilson, James", "1:05.80"),
        _create_mock_entry(3, "Anderson, Chloe", "29.10"),
        _create_mock_entry(4, "Thomas, Ryan", "NT"),
    ]
    event = Event(
        number=1,
        name="100 Yard Butterfly",
        gender="Girls",
        distance=100,
        stroke="Butterfly",
        entries=valid_entries,
    )
    result = validate_parsed_events([event])
    assert result.is_valid is True
    assert result.confidence_score >= 0.90
    assert len(result.errors) == 0


def test_confidence_score_scale_discrimination():
    """Test 5: Confidence score properly discriminates between clean data and minor issues."""
    # Clean list: 30 entries all matching expected format
    clean_entries = [
        _create_mock_entry(i, "Swimmer, Athlete", "1:05.00")
        for i in range(1, 31)
    ]
    clean_event = Event(
        number=1,
        name="100 Free",
        gender="Girls",
        distance=100,
        stroke="Freestyle",
        entries=clean_entries,
    )
    clean_result = validate_parsed_events([clean_event])
    assert clean_result.is_valid is True
    assert clean_result.confidence_score >= 0.90

    # Minor issues list: 30 entries, 4 with non-matching name format (86.7% pass rate -> warning penalty -0.10)
    # and 1 unusually long seed time (>30 min -> penalty -0.01)
    minor_entries = [
        _create_mock_entry(i, "Swimmer, Athlete" if i > 4 else "BadNameOnly", "1:05.00" if i != 30 else "35:00.00")
        for i in range(1, 31)
    ]
    minor_event = Event(
        number=2,
        name="100 Free Minor Issues",
        gender="Boys",
        distance=100,
        stroke="Freestyle",
        entries=minor_entries,
    )
    minor_result = validate_parsed_events([minor_event])

    assert minor_result.is_valid is True
    assert 0.70 <= minor_result.confidence_score < 0.90
    assert clean_result.confidence_score > minor_result.confidence_score


def test_accented_names_pass_check3():
    """Names with accented characters (ñ, é, ü) must not be penalised."""
    accented_entries = [
        _create_mock_entry(1, "Andrés, Miguel", "1:02.15"),
        _create_mock_entry(2, "Müller, Sophie", "1:05.80"),
        _create_mock_entry(3, "García, Lucía", "1:08.00"),
        _create_mock_entry(4, "O'Brien, Siobhán", "1:10.45"),
        _create_mock_entry(5, "López, María", "1:12.00"),
    ]
    event = Event(number=1, name="100 Free", gender="Girls", distance=100, stroke="Freestyle", entries=accented_entries)
    result = validate_parsed_events([event])
    assert result.is_valid is True, f"Accented names failed: {result.errors}"
    assert result.confidence_score == 1.0


def test_check3_never_sets_is_valid_false():
    """Check 3 (name integrity) must NEVER set is_valid=False, even at 0% pass rate."""
    bad_name_entries = [
        _create_mock_entry(i, "NoCommaName", "1:05.00")
        for i in range(1, 11)
    ]
    event = Event(number=1, name="100 Free", gender="Girls", distance=100, stroke="Freestyle", entries=bad_name_entries)
    result = validate_parsed_events([event])
    assert result.is_valid is True
    assert result.confidence_score < 1.0
    assert len(result.errors) == 0
    assert any("name integrity" in w.lower() for w in result.warnings)


def test_pdf_producer_metadata_check():
    """Unrecognized PDF producer string must trigger a soft Yellow warning."""
    entries = [_create_mock_entry(1, "Smith, Alice", "1:05.00")]
    event = Event(number=1, name="100 Free", gender="Girls", distance=100, stroke="Freestyle", entries=entries)

    # Hy-Tek producer -> no warning
    res_hytek = validate_parsed_events([event], pdf_producer="HY-TEK's Meet Manager 8.0")
    assert not any("Unrecognized PDF producer" in w for w in res_hytek.warnings)

    # Unknown producer -> soft warning
    res_unknown = validate_parsed_events([event], pdf_producer="Unknown PDF Generator 1.0")
    assert any("Unrecognized PDF producer" in w for w in res_unknown.warnings)
    assert res_unknown.confidence_score == 1.0
