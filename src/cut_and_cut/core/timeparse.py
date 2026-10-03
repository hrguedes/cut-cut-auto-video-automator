import re

_BARE_SECONDS = re.compile(r"^\d+(?:\.\d+)?$")
_CLOCK_PART = re.compile(r"^\d+$")
_SECONDS_PART = re.compile(r"^\d+(?:\.\d+)?$")


class TimeParseError(ValueError):
    """The text is not a duration this app accepts."""


def parse_duration(text: str) -> float:
    """Parse seconds ("90", "90.5"), mm:ss ("01:30") or hh:mm:ss ("00:01:30")."""
    raw = text.strip()
    if not raw:
        raise TimeParseError(_HINT)

    if ":" not in raw:
        if not _BARE_SECONDS.fullmatch(raw):
            raise TimeParseError(_HINT)
        seconds = float(raw)
    else:
        seconds = _parse_clock(raw)

    if seconds <= 0:
        raise TimeParseError("A duração precisa ser maior que zero.")
    return seconds


def parse_position(text: str) -> float:
    """Parse a timeline position. Zero is allowed. Same spellings as parse_duration."""
    raw = text.strip()
    if not raw or "_" in raw:
        raise TimeParseError(_POSITION_HINT)

    if ":" not in raw:
        if not _BARE_SECONDS.fullmatch(raw):
            raise TimeParseError(_POSITION_HINT)
        seconds = float(raw)
    else:
        seconds = _parse_clock(raw)

    if seconds < 0:
        raise TimeParseError("O tempo não pode ser negativo.")
    return seconds


def format_clock(seconds: float) -> str:
    """Format a duration as hh:mm:ss, rounding to the nearest second."""
    if seconds < 0:
        raise TimeParseError("A duração não pode ser negativa.")
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_progress_timestamp(value: str) -> float:
    """Parse an FFmpeg out_time value such as 00:01:30.500000."""
    raw = value.strip()
    if ":" not in raw:
        try:
            return float(raw)
        except ValueError as exc:
            raise TimeParseError(_HINT) from exc
    parts = raw.split(":")
    if len(parts) != 3:
        raise TimeParseError(_HINT)
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        secs = float(parts[2])
    except ValueError as exc:
        raise TimeParseError(_HINT) from exc
    if hours < 0 or minutes < 0 or secs < 0:
        raise TimeParseError(_HINT)
    return hours * 3600 + minutes * 60 + secs


_HINT = "Use segundos (90), mm:ss (01:30) ou hh:mm:ss (00:01:30)."
_POSITION_HINT = "Informe o tempo no formato 00:00:00."


def _parse_clock(raw: str) -> float:
    parts = raw.split(":")
    if len(parts) == 2:
        minutes_text, seconds_text = parts
        hours = 0
        if not _CLOCK_PART.fullmatch(minutes_text):
            raise TimeParseError(_HINT)
        minutes = int(minutes_text)
    elif len(parts) == 3:
        hours_text, minutes_text, seconds_text = parts
        if not _CLOCK_PART.fullmatch(hours_text) or not _CLOCK_PART.fullmatch(minutes_text):
            raise TimeParseError(_HINT)
        hours = int(hours_text)
        minutes = int(minutes_text)
        if minutes >= 60:
            raise TimeParseError("Os minutos precisam ser menores que 60.")
    else:
        raise TimeParseError(_HINT)

    if not _SECONDS_PART.fullmatch(seconds_text):
        raise TimeParseError(_HINT)
    seconds = float(seconds_text)
    if seconds >= 60:
        raise TimeParseError("Os segundos precisam ser menores que 60.")
    return hours * 3600 + minutes * 60 + seconds
