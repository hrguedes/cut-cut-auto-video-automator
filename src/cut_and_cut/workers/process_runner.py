from PySide6.QtCore import QObject, QProcess, Signal

_MAX_STDERR = 64_000


class ProcessRunner(QObject):
    """Run one argv list. stdout is emitted line by line; nothing waits on the GUI."""

    line_ready = Signal(str)
    finished = Signal(int, bool)
    failed_to_start = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._stdout_pending = ""
        self._stdout_all = ""
        self._stderr_all = ""
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    def start(self, args: list[str]) -> None:
        self._stdout_pending = ""
        self._stdout_all = ""
        self._stderr_all = ""
        program, *rest = args
        self._process.start(program, rest)

    def kill(self) -> None:
        if self.is_running():
            self._process.kill()

    def kill_and_wait(self, timeout_ms: int) -> tuple[int, bool, bool]:
        """For application exit only, when a locked partial file must be removed."""
        if not self.is_running():
            return 0, True, False
        self._process.kill()
        finished = self._process.waitForFinished(timeout_ms)
        normal = finished and self._process.exitStatus() == QProcess.ExitStatus.NormalExit
        return int(self._process.exitCode()), bool(normal), True

    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def stdout_text(self) -> str:
        return self._stdout_all

    def stderr_text(self) -> str:
        return self._stderr_all

    def _on_stdout(self) -> None:
        chunk = self._decode(self._process.readAllStandardOutput())
        self._stdout_all += chunk
        self._stdout_pending += chunk
        while "\n" in self._stdout_pending:
            line, self._stdout_pending = self._stdout_pending.split("\n", 1)
            self.line_ready.emit(line.rstrip("\r"))

    def _on_stderr(self) -> None:
        chunk = self._decode(self._process.readAllStandardError())
        self._stderr_all = (self._stderr_all + chunk)[-_MAX_STDERR:]

    def _on_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        if self._stdout_pending:
            self.line_ready.emit(self._stdout_pending.rstrip("\r"))
            self._stdout_pending = ""
        normal = status == QProcess.ExitStatus.NormalExit
        self.finished.emit(int(code), normal)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            message = self._process.errorString() or "Não foi possível iniciar o processo."
            self.failed_to_start.emit(message)

    @staticmethod
    def _decode(data: object) -> str:
        return bytes(data).decode("utf-8", errors="replace")
