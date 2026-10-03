from pathlib import Path

from PySide6.QtCore import QSettings

from cut_and_cut.binaries import find_beside_executable, find_on_path, is_usable


def settings() -> QSettings:
    return QSettings("CutAndCut", "CutAndCut")


def load_binaries() -> tuple[Path, Path] | None:
    bundled = find_beside_executable()
    if bundled is not None:
        return bundled
    stored = settings()
    ffmpeg = str(stored.value("ffmpeg_path", "") or "")
    ffprobe = str(stored.value("ffprobe_path", "") or "")
    if ffmpeg and ffprobe:
        ffmpeg_path = Path(ffmpeg)
        ffprobe_path = Path(ffprobe)
        if is_usable(ffmpeg_path) and is_usable(ffprobe_path):
            return ffmpeg_path, ffprobe_path
    return find_on_path()


def save_binaries(ffmpeg: Path, ffprobe: Path) -> None:
    stored = settings()
    stored.setValue("ffmpeg_path", str(ffmpeg))
    stored.setValue("ffprobe_path", str(ffprobe))


def last_destination() -> str:
    return str(settings().value("last_destination", "") or "")


def remember_destination(path: Path) -> None:
    settings().setValue("last_destination", str(path))
