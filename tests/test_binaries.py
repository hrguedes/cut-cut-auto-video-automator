from pathlib import Path

from cut_and_cut.binaries import ffprobe_beside, find_in_folder


def test_ffprobe_beside_the_ffmpeg_binary(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg"
    ffprobe = tmp_path / "ffprobe"
    ffmpeg.write_text("", encoding="utf-8")
    ffprobe.write_text("", encoding="utf-8")
    assert ffprobe_beside(ffmpeg) == ffprobe


def test_find_in_folder_prefers_windows_executables(tmp_path: Path) -> None:
    _executable(tmp_path / "ffmpeg.exe")
    _executable(tmp_path / "ffprobe.exe")
    found = find_in_folder(tmp_path)
    assert found == (tmp_path / "ffmpeg.exe", tmp_path / "ffprobe.exe")


def test_find_in_folder_requires_both_binaries(tmp_path: Path) -> None:
    _executable(tmp_path / "ffmpeg.exe")
    assert find_in_folder(tmp_path) is None


def test_ffprobe_beside_windows_exe(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    ffmpeg.write_text("", encoding="utf-8")
    ffprobe.write_text("", encoding="utf-8")
    assert ffprobe_beside(ffmpeg) == ffprobe


def _executable(path: Path) -> None:
    path.write_text("", encoding="utf-8")
    path.chmod(0o755)
