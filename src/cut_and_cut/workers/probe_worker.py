from pathlib import Path

from PySide6.QtCore import QObject, Signal

from cut_and_cut.core.ffmpeg import ProbeError, parse_probe_json, probe_command
from cut_and_cut.workers.process_runner import ProcessRunner


class ProbeWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runner = ProcessRunner(self)
        self._runner.finished.connect(self._on_finished)
        self._runner.failed_to_start.connect(self._on_start_failed)
        self._token = 0
        self._running_token = 0
        self._request: tuple[int, Path, Path] | None = None
        self._source: Path | None = None
        self._busy = False

    def probe(self, ffprobe: Path, source: Path) -> None:
        self._token += 1
        self._request = (self._token, ffprobe, source)
        if self._busy:
            self._runner.kill()
            return
        self._begin()

    def shutdown(self) -> None:
        self._token += 1
        self._request = None
        self._runner.kill_and_wait(2000)

    def _begin(self) -> None:
        if self._request is None or self._busy:
            return
        token, ffprobe, source = self._request
        self._busy = True
        self._running_token = token
        self._source = source
        self._runner.start(probe_command(ffprobe, source))

    def _on_finished(self, code: int, _normal: bool) -> None:
        self._busy = False
        token = self._running_token
        source = self._source
        stdout = self._runner.stdout_text()
        stderr = self._runner.stderr_text()
        if token == self._token and source is not None:
            self._emit_result(code, stdout, stderr, source)
        if self._request is not None and self._request[0] != token:
            self._begin()

    def _on_start_failed(self, message: str) -> None:
        self._busy = False
        token = self._running_token
        if token == self._token:
            self.failed.emit(message or "Não foi possível iniciar o ffprobe.")
        if self._request is not None and self._request[0] != token:
            self._begin()

    def _emit_result(self, code: int, stdout: str, stderr: str, source: Path) -> None:
        if code != 0:
            self.failed.emit(_tail(stderr) or "Não foi possível ler o vídeo.")
            return
        try:
            info = parse_probe_json(stdout, source)
        except ProbeError as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(info)


def _tail(text: str, limit: int = 8) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-limit:])
