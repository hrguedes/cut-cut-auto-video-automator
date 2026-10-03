from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from cut_and_cut.core.ffmpeg import export_command, parse_progress_line
from cut_and_cut.core.models import CutMode
from cut_and_cut.workers.process_runner import ProcessRunner


@dataclass(frozen=True)
class ExportItem:
    index: int
    start_s: float
    duration_s: float
    output: Path
    title: str


class ExportWorker(QObject):
    file_started = Signal(int, int, str)
    file_progress = Signal(float)
    overall_progress = Signal(float)
    finished_ok = Signal(int)
    failed = Signal(str)
    cancelled = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runner = ProcessRunner(self)
        self._runner.line_ready.connect(self._on_line)
        self._runner.finished.connect(self._on_finished)
        self._runner.failed_to_start.connect(self._on_start_failed)
        self._items: list[ExportItem] = []
        self._cursor = 0
        self._current: ExportItem | None = None
        self._ffmpeg: Path | None = None
        self._source: Path | None = None
        self._mode = CutMode.PRECISE
        self._has_audio = True
        self._cancel = False
        self._settled = False

    def start(
        self,
        ffmpeg: Path,
        source: Path,
        mode: CutMode,
        has_audio: bool,
        items: list[ExportItem],
    ) -> None:
        self._items = list(items)
        self._cursor = 0
        self._current = None
        self._ffmpeg = ffmpeg
        self._source = source
        self._mode = mode
        self._has_audio = has_audio
        self._cancel = False
        self._settled = False
        if not items:
            self._settled = True
            self.finished_ok.emit(0)
            return
        try:
            items[0].output.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._settled = True
            self.failed.emit(f"Não foi possível criar a pasta de destino.\n{exc}")
            return
        self._run_current()

    def cancel(self) -> None:
        if self._settled:
            return
        self._cancel = True
        if self._runner.is_running():
            self._runner.kill()
            return
        self._settled = True
        self.cancelled.emit(self._cursor)

    def shutdown(self) -> None:
        """Kill a running export and delete its partial file. Used when the window closes."""
        output = None if self._current is None else self._current.output
        self._cancel = True
        code, normal, was_running = self._runner.kill_and_wait(3000)
        if was_running and output is not None and not (normal and code == 0):
            _delete(output)
        self._settled = True

    def _run_current(self) -> None:
        if self._ffmpeg is None or self._source is None:
            return
        item = self._items[self._cursor]
        self._current = item
        self.file_started.emit(self._cursor + 1, len(self._items), item.output.name)
        self.file_progress.emit(0.0)
        self._emit_overall(0.0)
        self._runner.start(
            export_command(
                self._ffmpeg,
                self._source,
                item.output,
                item.start_s,
                item.duration_s,
                self._mode,
                has_audio=self._has_audio,
            )
        )

    def _on_line(self, line: str) -> None:
        if self._cancel or self._current is None:
            return
        snapshot = parse_progress_line(line)
        if snapshot is None:
            return
        if snapshot.ended:
            fraction = 1.0
        elif snapshot.out_time_s is None or self._current.duration_s <= 0:
            return
        else:
            fraction = min(1.0, snapshot.out_time_s / self._current.duration_s)
        self.file_progress.emit(fraction)
        self._emit_overall(fraction)

    def _on_finished(self, code: int, normal: bool) -> None:
        if self._settled:
            return
        item = self._current
        success = normal and code == 0
        if not success:
            if item is not None:
                _delete(item.output)
            if self._cancel:
                self._settled = True
                self.cancelled.emit(self._cursor)
                return
            self._settled = True
            detail = _tail(self._runner.stderr_text())
            self.failed.emit(detail or "O FFmpeg falhou ao gerar o corte.")
            return

        self._cursor += 1
        self._current = None
        if self._cancel:
            self._settled = True
            self.cancelled.emit(self._cursor)
            return
        if self._cursor >= len(self._items):
            self._settled = True
            self.file_progress.emit(1.0)
            self.overall_progress.emit(1.0)
            self.finished_ok.emit(self._cursor)
            return
        self._run_current()

    def _on_start_failed(self, message: str) -> None:
        if self._settled:
            return
        if self._current is not None:
            _delete(self._current.output)
        self._settled = True
        if self._cancel:
            self.cancelled.emit(self._cursor)
            return
        self.failed.emit(message or "Não foi possível iniciar o FFmpeg.")

    def _emit_overall(self, fraction: float) -> None:
        total = len(self._items)
        if total == 0:
            return
        self.overall_progress.emit((self._cursor + fraction) / total)


def _delete(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _tail(text: str, limit: int = 8) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-limit:])
