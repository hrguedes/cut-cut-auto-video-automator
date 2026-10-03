import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from cut_and_cut.core.models import CutMode
from cut_and_cut.workers.export_worker import ExportItem, ExportWorker
from cut_and_cut.workers.process_runner import ProcessRunner


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_process_runner_reads_stdout(qapp: QApplication) -> None:
    echo = Path("/bin/echo")
    if not echo.is_file():
        pytest.skip("este teste usa /bin/echo")
    runner = ProcessRunner()
    lines: list[str] = []
    finished: list[tuple[int, bool]] = []
    runner.line_ready.connect(lines.append)
    runner.finished.connect(lambda code, normal: finished.append((code, normal)))
    runner.start([str(echo), "corte-ok"])
    _wait(qapp, lambda: bool(finished))
    assert lines == ["corte-ok"]
    assert finished == [(0, True)]


@pytest.mark.skipif(sys.platform == "win32", reason="o dublê usa um script com shebang")
def test_cancel_deletes_the_partial_file(qapp: QApplication, tmp_path: Path) -> None:
    ffmpeg = _fake_ffmpeg(
        tmp_path / "ffmpeg",
        """
import pathlib, sys, time
output = pathlib.Path(sys.argv[-1])
output.write_text("parcial", encoding="utf-8")
print("out_time=00:00:01.000000", flush=True)
print("progress=continue", flush=True)
time.sleep(30)
""",
    )
    output = tmp_path / "Área final" / "Ação.mp4"
    worker = ExportWorker()
    cancelled: list[int] = []
    progressed: list[float] = []
    worker.cancelled.connect(cancelled.append)
    worker.file_progress.connect(progressed.append)
    worker.start(
        ffmpeg,
        tmp_path / "vídeo aula.mp4",
        CutMode.PRECISE,
        True,
        [ExportItem(1, 0, 10, output, "Ação")],
    )
    _wait(qapp, output.exists)
    assert output.read_text(encoding="utf-8") == "parcial"
    worker.cancel()
    _wait(qapp, lambda: bool(cancelled))
    assert cancelled == [0]
    assert not output.exists()
    assert any(value > 0 for value in progressed)


@pytest.mark.skipif(sys.platform == "win32", reason="o dublê usa um script com shebang")
def test_failed_export_deletes_the_partial_file(qapp: QApplication, tmp_path: Path) -> None:
    ffmpeg = _fake_ffmpeg(
        tmp_path / "ffmpeg",
        """
import pathlib, sys
output = pathlib.Path(sys.argv[-1])
output.write_text("parcial", encoding="utf-8")
sys.exit(1)
""",
    )
    output = tmp_path / "projeto" / "corte.mp4"
    worker = ExportWorker()
    errors: list[str] = []
    worker.failed.connect(errors.append)
    worker.start(
        ffmpeg,
        tmp_path / "video.mp4",
        CutMode.FAST,
        False,
        [ExportItem(1, 0, 5, output, "Corte 01")],
    )
    _wait(qapp, lambda: bool(errors))
    assert not output.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="o dublê usa um script com shebang")
def test_successful_export_keeps_the_file(qapp: QApplication, tmp_path: Path) -> None:
    ffmpeg = _fake_ffmpeg(
        tmp_path / "ffmpeg",
        """
import pathlib, sys
output = pathlib.Path(sys.argv[-1])
output.write_text("pronto", encoding="utf-8")
print("progress=end", flush=True)
""",
    )
    first = tmp_path / "Meu Vídeo" / "Meu_Vídeo_01_Corte_01.mp4"
    second = tmp_path / "Meu Vídeo" / "Meu_Vídeo_02_Corte_02.mp4"
    worker = ExportWorker()
    done: list[int] = []
    worker.finished_ok.connect(done.append)
    worker.start(
        ffmpeg,
        tmp_path / "vídeo.mov",
        CutMode.PRECISE,
        True,
        [
            ExportItem(1, 0, 60, first, "Corte 01"),
            ExportItem(2, 60, 60, second, "Corte 02"),
        ],
    )
    _wait(qapp, lambda: bool(done))
    assert done == [2]
    assert first.read_text(encoding="utf-8") == "pronto"
    assert second.read_text(encoding="utf-8") == "pronto"


def _fake_ffmpeg(path: Path, body: str) -> Path:
    path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    path.chmod(0o755)
    return path


def _wait(qapp: QApplication, ready, timeout_s: float = 5) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        qapp.processEvents()
        if ready():
            return
        time.sleep(0.02)
    raise AssertionError("tempo esgotado esperando o processo")
