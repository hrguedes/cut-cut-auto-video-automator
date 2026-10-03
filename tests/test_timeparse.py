import pytest

from cut_and_cut.core.timeparse import TimeParseError, format_clock, parse_duration, parse_position


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("90", 90.0),
        ("90.5", 90.5),
        ("  90  ", 90.0),
        ("01:30", 90.0),
        ("1:30", 90.0),
        ("00:01:30", 90.0),
        ("0:01:30", 90.0),
        ("01:30.5", 90.5),
        ("1:00:00", 3600.0),
        ("90:00", 5400.0),
    ],
)
def test_parse_duration_accepts_seconds_and_clock(text: str, expected: float) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    "text",
    ["", "   ", "0", "0.0", "00:00", "00:00:00", "-1", "abc", "1:2:3:4", "01:60", "00:01:60", "1:60:00"],
)
def test_parse_duration_rejects_invalid(text: str) -> None:
    with pytest.raises(TimeParseError):
        parse_duration(text)


def test_parse_position_allows_zero() -> None:
    assert parse_position("0") == 0
    assert parse_position("00:00:00") == 0
    assert parse_position("00:00:45") == 45


def test_format_clock() -> None:
    assert format_clock(90) == "00:01:30"
    assert format_clock(3600) == "01:00:00"
    assert format_clock(59.6) == "00:01:00"
