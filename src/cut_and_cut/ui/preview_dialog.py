from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from cut_and_cut.core.timeparse import format_clock


class PreviewDialog(QDialog):
    """Play a finished file, or a slice of the source before it is exported."""

    def __init__(
        self,
        path: Path,
        title: str,
        *,
        start_s: float = 0.0,
        end_s: float | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(860, 560)
        self._start_ms = max(0, int(start_s * 1000))
        self._end_ms = None if end_s is None else max(self._start_ms, int(end_s * 1000))
        self._ended = False
        self._seeked = False

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(1.0)
        self._player.setAudioOutput(self._audio)
        self._video = QVideoWidget()
        self._video.setMinimumHeight(360)
        self._video.setStyleSheet("background: black;")
        self._player.setVideoOutput(self._video)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.positionChanged.connect(self._on_position)
        self._player.playbackStateChanged.connect(self._on_state)
        self._player.errorOccurred.connect(self._on_error)

        if end_s is None:
            detail = path.name
        else:
            detail = f"{format_clock(start_s)} – {format_clock(end_s)}"
        self._detail = QLabel(detail)
        self._message = QLabel("")
        self._message.setWordWrap(True)
        self._message.setObjectName("errorLabel")

        self._play = QPushButton("Pausar")
        self._play.clicked.connect(self._toggle)
        close = QPushButton("Fechar")
        close.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(self._play)
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(self._video, 1)
        layout.addWidget(self._detail)
        layout.addWidget(self._message)
        layout.addLayout(buttons)

        self._player.setSource(QUrl.fromLocalFile(str(path)))

    def done(self, result: int) -> None:
        self._player.stop()
        self._player.setSource(QUrl())
        super().done(result)

    def _on_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._message.setText("Não foi possível abrir o vídeo.")
            self._play.setEnabled(False)
            return
        if status == QMediaPlayer.MediaStatus.LoadedMedia and not self._seeked:
            self._seeked = True
            if self._start_ms:
                self._player.setPosition(self._start_ms)
            self._player.play()

    def _on_position(self, position: int) -> None:
        if self._end_ms is None or self._ended:
            return
        if position >= self._end_ms:
            self._ended = True
            self._player.pause()

    def _on_state(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._play.setText("Pausar" if playing else "Reproduzir")

    def _on_error(self, error: QMediaPlayer.Error, message: str) -> None:
        if error == QMediaPlayer.Error.NoError:
            return
        self._message.setText(message or "Não foi possível reproduzir o vídeo.")

    def _toggle(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            return
        if self._ended or (self._end_ms is not None and self._player.position() >= self._end_ms):
            self._ended = False
            self._player.setPosition(self._start_ms)
        self._player.play()
