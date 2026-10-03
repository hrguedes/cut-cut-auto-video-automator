import os
import shutil
import sys
from pathlib import Path


def find_beside_executable() -> tuple[Path, Path] | None:
    """Look for ffmpeg and ffprobe in the same folder as the running executable."""
    return find_in_folder(Path(sys.executable).resolve().parent)


def find_in_folder(folder: Path) -> tuple[Path, Path] | None:
    for ffmpeg_name, ffprobe_name in _binary_names():
        ffmpeg = folder / ffmpeg_name
        ffprobe = folder / ffprobe_name
        if is_usable(ffmpeg) and is_usable(ffprobe):
            return ffmpeg, ffprobe
    return None


def find_on_path() -> tuple[Path, Path] | None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        return None
    return Path(ffmpeg), Path(ffprobe)


def is_usable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _binary_names() -> tuple[tuple[str, str], ...]:
    if sys.platform == "win32":
        return (("ffmpeg.exe", "ffprobe.exe"), ("ffmpeg", "ffprobe"))
    return (("ffmpeg", "ffprobe"), ("ffmpeg.exe", "ffprobe.exe"))


def ffprobe_beside(ffmpeg: Path) -> Path | None:
    names = ["ffprobe.exe", "ffprobe"] if ffmpeg.suffix.lower() == ".exe" else ["ffprobe", "ffprobe.exe"]
    for name in names:
        candidate = ffmpeg.with_name(name)
        if candidate.is_file():
            return candidate
    return None
