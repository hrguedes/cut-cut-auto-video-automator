import ast
import json
from pathlib import Path

import pytest

from cut_and_cut.core.ffmpeg import (
    ProbeError,
    export_command,
    output_extension,
    parse_probe_json,
    parse_progress_line,
    probe_command,
    thumbnail_command,
)
from cut_and_cut.core.models import CutMode

FFMPEG = Path("/opt/ffmpeg/bin/ffmpeg")
FFPROBE = Path("/opt/ffmpeg/bin/ffprobe")


def test_core_does_not_import_pyside_or_subprocess() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "cut_and_cut" / "core"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                assert not module.startswith("PySide6")
                assert module != "subprocess"
                assert not module.startswith("subprocess.")


def test_probe_command_is_an_argv_list() -> None:
    source = Path("/Users/eu/Meus Vídeos/aula 01.mp4")
    args = probe_command(FFPROBE, source)
    assert args[0] == str(FFPROBE)
    assert args[1:7] == ["-v", "error", "-print_format", "json", "-show_format", "-show_streams"]
    assert args[-1] == str(source)
    assert isinstance(args, list)


def test_precise_export_reencodes_to_mp4(tmp_path: Path) -> None:
    source = tmp_path / "Meu Vídeo.mov"
    output = tmp_path / "Área" / "aula.mp4"
    args = export_command(
        FFMPEG, source, output, 60, 30, CutMode.PRECISE, has_audio=True
    )
    assert args.index("-ss") < args.index("-i")
    assert args[args.index("-ss") + 1] == "60.000"
    assert args[args.index("-i") + 1] == str(source)
    assert args[args.index("-t") + 1] == "30.000"
    assert args[args.index("-c:v") + 1] == "libx264"
    assert args[args.index("-preset") + 1] == "veryfast"
    assert args[args.index("-crf") + 1] == "20"
    assert args[args.index("-c:a") + 1] == "aac"
    assert args[args.index("-b:a") + 1] == "192k"
    assert args[args.index("-movflags") + 1] == "+faststart"
    assert args[args.index("-avoid_negative_ts") + 1] == "make_zero"
    assert args[-4:-1] == ["-progress", "pipe:1", "-nostats"]
    assert args[-1] == str(output)
    assert "-c" not in args


def test_precise_export_without_audio_skips_aac(tmp_path: Path) -> None:
    args = export_command(
        FFMPEG,
        tmp_path / "silent.mp4",
        tmp_path / "out.mp4",
        0,
        10,
        CutMode.PRECISE,
        has_audio=False,
    )
    assert "-an" in args
    assert "aac" not in args


def test_fast_export_copies_and_keeps_the_extension(tmp_path: Path) -> None:
    source = tmp_path / "vídeo.mkv"
    output = tmp_path / "corte.mkv"
    args = export_command(FFMPEG, source, output, 0, 15, CutMode.FAST, has_audio=True)
    assert args[args.index("-c") + 1] == "copy"
    assert "libx264" not in args
    assert args[-1] == str(output)
    assert output_extension(CutMode.FAST, source) == ".mkv"
    assert output_extension(CutMode.PRECISE, source) == ".mp4"


def test_thumbnail_command() -> None:
    source = Path("/tmp/Área/vídeo.mp4")
    output = Path("/tmp/thumb.jpg")
    args = thumbnail_command(FFMPEG, source, 12.5, output)
    assert args.index("-ss") < args.index("-i")
    assert args[args.index("-ss") + 1] == "12.500"
    assert args[args.index("-frames:v") + 1] == "1"
    assert args[args.index("-vf") + 1] == "scale=320:-1"
    assert args[-1] == str(output)


def test_parse_probe_json() -> None:
    payload = json.dumps(
        {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "600.040000"},
        }
    )
    info = parse_probe_json(payload, Path("aula.mp4"))
    assert info.duration_s == pytest.approx(600.04)
    assert (info.width, info.height) == (1920, 1080)
    assert info.video_codec == "h264"
    assert info.audio_codec == "aac"
    assert info.container == "mp4"
    assert info.has_audio is True


def test_parse_probe_without_audio_or_video() -> None:
    silent = json.dumps(
        {
            "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720, "duration": "12"}],
            "format": {},
        }
    )
    info = parse_probe_json(silent, Path("tela.webm"))
    assert info.audio_codec is None
    assert info.has_audio is False
    assert info.duration_s == 12
    with pytest.raises(ProbeError):
        parse_probe_json("{}", Path("x.mp4"))
    with pytest.raises(ProbeError):
        parse_probe_json("não json", Path("x.mp4"))


def test_parse_progress_uses_out_time() -> None:
    running = parse_progress_line("out_time=00:00:30.500000")
    assert running is not None
    assert running.out_time_s == pytest.approx(30.5)
    assert running.ended is False
    ended = parse_progress_line("progress=end")
    assert ended is not None
    assert ended.ended is True
    assert parse_progress_line("out_time_ms=30500000") is None
    assert parse_progress_line("frame=10") is None
