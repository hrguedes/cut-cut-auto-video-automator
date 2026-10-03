from pathlib import Path

from PySide6.QtCore import QObject, Signal

from cut_and_cut.core.ffmpeg import thumbnail_command
from cut_and_cut.workers.process_runner import ProcessRunner

ThumbnailJob = tuple[int, Path, float, Path]


class ThumbnailWorker(QObject):
    """Generate thumbnails one at a time so the window stays responsive."""

    ready = Signal(int, str)
    failed = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runner = ProcessRunner(self)
        self._runner.finished.connect(self._on_finished)
        self._runner.failed_to_start.connect(self._on_start_failed)
        self._queue: list[ThumbnailJob] = []
        self._current: ThumbnailJob | None = None
        self._ffmpeg: Path | None = None
        self._generation = 0
        self._job_generation = 0
        self._busy = False

    def start(self, ffmpeg: Path, jobs: list[ThumbnailJob]) -> None:
        self._generation += 1
        self._ffmpeg = ffmpeg
        self._queue = list(jobs)
        self._current = None
        if self._runner.is_running():
            self._runner.kill()
            return
        self._busy = False
        self._pump()

    def refresh(self, ffmpeg: Path, job: ThumbnailJob) -> None:
        """Regenerate one thumbnail and keep the other pending jobs."""
        self._ffmpeg = ffmpeg
        index = job[0]
        self._queue = [item for item in self._queue if item[0] != index]
        self._queue.insert(0, job)
        if self._current is not None and self._current[0] == index and self._runner.is_running():
            self._generation += 1
            self._runner.kill()
            return
        self._pump()

    def cancel(self) -> None:
        self._generation += 1
        self._queue.clear()
        if self._runner.is_running():
            self._runner.kill()

    def shutdown(self) -> None:
        self._generation += 1
        self._queue.clear()
        self._runner.kill_and_wait(2000)

    def _pump(self) -> None:
        if self._busy or not self._queue or self._ffmpeg is None:
            return
        job = self._queue.pop(0)
        _index, source, start_s, output = job
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.failed.emit(job[0])
            self._pump()
            return
        self._busy = True
        self._current = job
        self._job_generation = self._generation
        self._runner.start(thumbnail_command(self._ffmpeg, source, start_s, output))

    def _on_finished(self, code: int, normal: bool) -> None:
        self._busy = False
        job = self._current
        generation = self._job_generation
        self._current = None
        if job is not None and generation == self._generation:
            index, _source, _start, output = job
            if normal and code == 0 and output.is_file():
                self.ready.emit(index, str(output))
            else:
                self.failed.emit(index)
        self._pump()

    def _on_start_failed(self, _message: str) -> None:
        self._busy = False
        job = self._current
        generation = self._job_generation
        self._current = None
        if generation != self._generation:
            self._pump()
            return
        if job is not None:
            self.failed.emit(job[0])
        while self._queue:
            self.failed.emit(self._queue.pop(0)[0])
