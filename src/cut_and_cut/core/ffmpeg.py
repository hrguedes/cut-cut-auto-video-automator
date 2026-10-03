import json
from dataclasses import dataclass
from pathlib import Path

from cut_and_cut.core.models import CutMode, MediaInfo
from cut_and_cut.core.timeparse import parse_progress_timestamp


class ProbeError(ValueError):
    """ffprobe output could not be turned into media info."""


@dataclass(frozen=True)
class ProgressSnapshot:
    out_time_s: float | None = None
    ended: bool = False


def probe_command(ffprobe: Path, source: Path) -> list[str]:
    return [
        str(ffprobe),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(source),
    ]


def export_command(
    ffmpeg: Path,
    source: Path,
    output: Path,
    start_s: float,
    duration_s: float,
    mode: CutMode,
    *,
    has_audio: bool,
) -> list[str]:
    """Build an argv list. Callers must not join it into a shell string."""
    args = [
        str(ffmpeg),
        "-y",
        "-ss",
        _seconds(start_s),
        "-i",
        str(source),
        "-t",
        _seconds(duration_s),
    ]
    if mode is CutMode.PRECISE:
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
        if has_audio:
            args += ["-c:a", "aac", "-b:a", "192k"]
        else:
            args += ["-an"]
        args += ["-movflags", "+faststart", "-avoid_negative_ts", "make_zero"]
    else:
        # Copy cuts land on keyframes. make_zero avoids a negative start timestamp.
        args += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
    args += ["-progress", "pipe:1", "-nostats", str(output)]
    return args


def thumbnail_command(ffmpeg: Path, source: Path, start_s: float, output: Path) -> list[str]:
    return [
        str(ffmpeg),
        "-y",
        "-ss",
        _seconds(start_s),
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-vf",
        "scale=320:-1",
        str(output),
    ]


def output_extension(mode: CutMode, source: Path) -> str:
    if mode is CutMode.PRECISE:
        return ".mp4"
    return source.suffix.lower() or ".mp4"


def parse_probe_json(payload: str, source: Path) -> MediaInfo:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ProbeError("A resposta do ffprobe não é um JSON válido.") from exc
    if not isinstance(data, dict):
        raise ProbeError("A resposta do ffprobe não é um JSON válido.")

    streams = data.get("streams")
    if not isinstance(streams, list):
        streams = []
    video = next((stream for stream in streams if _codec_type(stream) == "video"), None)
    if not isinstance(video, dict):
        raise ProbeError("O arquivo não tem faixa de vídeo.")
    audio = next((stream for stream in streams if _codec_type(stream) == "audio"), None)
    audio_codec = None
    if isinstance(audio, dict):
        name = audio.get("codec_name")
        audio_codec = str(name) if name else None

    container = source.suffix.lstrip(".").lower() or "desconhecido"
    return MediaInfo(
        path=source,
        duration_s=_duration(data, video),
        width=_as_int(video.get("width")),
        height=_as_int(video.get("height")),
        video_codec=str(video.get("codec_name") or "desconhecido"),
        audio_codec=audio_codec,
        container=container,
    )


def parse_progress_line(line: str) -> ProgressSnapshot | None:
    """Read one `key=value` line from `ffmpeg -progress pipe:1`.

    `out_time` is used on purpose. `out_time_ms` is microseconds in some
    FFmpeg versions and milliseconds in others.
    """
    text = line.strip()
    if "=" not in text:
        return None
    key, value = text.split("=", 1)
    if key == "out_time":
        return ProgressSnapshot(out_time_s=parse_progress_timestamp(value))
    if key == "progress" and value == "end":
        return ProgressSnapshot(ended=True)
    return None


def _seconds(value: float) -> str:
    return f"{value:.3f}"


def _codec_type(stream: object) -> str | None:
    if not isinstance(stream, dict):
        return None
    value = stream.get("codec_type")
    return str(value) if value is not None else None


def _duration(data: dict, video: dict) -> float:
    fmt = data.get("format")
    raw = fmt.get("duration") if isinstance(fmt, dict) else None
    if raw in (None, "", "N/A"):
        raw = video.get("duration")
    try:
        duration = float(raw)
    except (TypeError, ValueError) as exc:
        raise ProbeError("Não foi possível ler a duração do vídeo.") from exc
    if duration <= 0:
        raise ProbeError("Não foi possível ler a duração do vídeo.")
    return duration


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
