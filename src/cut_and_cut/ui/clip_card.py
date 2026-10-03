from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from cut_and_cut.core.models import ClipPlan
from cut_and_cut.core.timeparse import TimeParseError, format_clock, parse_position

_THUMB_WIDTH = 320
_THUMB_HEIGHT = 180


class ClipCard(QFrame):
    inclusion_changed = Signal()
    preview_requested = Signal()
    range_changed = Signal()

    def __init__(self, clip: ClipPlan, media_duration_s: float, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.clip = clip
        self._media_duration_s = media_duration_s
        self._has_thumbnail = False
        self._range_valid = True
        self._thumbnail_start = clip.start_s
        self._original_range = (clip.start_s, clip.end_s)
        self.setObjectName("clipCard")

        self._thumb = QLabel("Gerando miniatura…")
        self._thumb.setObjectName("thumbLabel")
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setFixedSize(_THUMB_WIDTH, _THUMB_HEIGHT)
        self._thumb.setWordWrap(True)

        self._start = _clock_field(clip.start_s, "Início do corte. Exemplo: 00:00:30.")
        self._end = _clock_field(clip.end_s, "Fim do corte. Exemplo: 00:01:00.")
        self._start.editingFinished.connect(self._commit_range)
        self._end.editingFinished.connect(self._commit_range)

        self._duration = QLabel(f"Duração {format_clock(clip.duration_s)}")
        self._range_error = QLabel("")
        self._range_error.setObjectName("errorLabel")
        self._range_error.setWordWrap(True)
        self._range_error.setVisible(False)
        self._badge = QLabel("mais curto")
        self._badge.setObjectName("shortBadge")
        self._badge.setVisible(clip.shorter)

        self._include = QCheckBox("Incluir")
        self._include.setChecked(clip.included)
        self._include.toggled.connect(self._on_include)

        self._title = QLineEdit(clip.title)
        self._title.setPlaceholderText("Título do corte")
        self._title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._preview = QPushButton("Visualizar")
        self._preview.clicked.connect(lambda _checked=False: self.preview_requested.emit())

        header = QHBoxLayout()
        header.addStretch(1)
        header.addWidget(self._include)

        times = QHBoxLayout()
        times.addWidget(QLabel("Início"))
        times.addWidget(self._start)
        times.addSpacing(12)
        times.addWidget(QLabel("Fim"))
        times.addWidget(self._end)
        times.addStretch(1)

        details = QVBoxLayout()
        details.addLayout(header)
        details.addLayout(times)
        details.addWidget(self._duration)
        details.addWidget(self._range_error)
        details.addWidget(self._badge)
        details.addWidget(QLabel("Título"))
        details.addWidget(self._title)
        details.addWidget(self._preview, 0, Qt.AlignmentFlag.AlignLeft)
        details.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)
        layout.addWidget(self._thumb)
        layout.addLayout(details, 1)

    @property
    def has_thumbnail(self) -> bool:
        return self._has_thumbnail

    @property
    def range_valid(self) -> bool:
        return self._range_valid

    def consume_thumbnail_refresh(self) -> bool:
        if not self._range_valid or abs(self.clip.start_s - self._thumbnail_start) < 0.05:
            return False
        self._thumbnail_start = self.clip.start_s
        return True

    def mark_thumbnail_pending(self) -> None:
        self._thumb.setPixmap(QPixmap())
        self._thumb.setText("Gerando miniatura…")
        self._has_thumbnail = False

    def current_title(self) -> str:
        text = self._title.text().strip()
        return text or f"Corte {self.clip.index:02d}"

    def set_thumbnail(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.mark_thumbnail_failed()
            return
        scaled = pixmap.scaled(
            _THUMB_WIDTH,
            _THUMB_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumb.setPixmap(scaled)
        self._has_thumbnail = True

    def mark_thumbnail_failed(self) -> None:
        self._thumb.setPixmap(QPixmap())
        self._thumb.setText("Sem miniatura")
        self._has_thumbnail = False

    def _on_include(self, checked: bool) -> None:
        self.clip.included = checked
        self.inclusion_changed.emit()

    def _commit_range(self) -> None:
        if not self._start.hasAcceptableInput() or not self._end.hasAcceptableInput():
            self._reject("Informe início e fim no formato 00:00:00.")
            return
        try:
            start = _position_from_field(self._start, self.clip.start_s)
            end = _position_from_field(self._end, self.clip.end_s)
        except TimeParseError as exc:
            self._reject(str(exc))
            return
        if start >= self._media_duration_s:
            self._reject("O início precisa estar dentro do vídeo.")
            return
        if end > self._media_duration_s + 0.001:
            self._reject(f"O fim não pode passar de {format_clock(self._media_duration_s)}.")
            return
        if end <= start:
            self._reject("O fim precisa ser depois do início.")
            return

        self.clip.start_s = start
        self.clip.end_s = end
        self.clip.duration_s = end - start
        self._range_valid = True
        self._range_error.hide()
        self._preview.setEnabled(True)
        self._duration.setText(f"Duração {format_clock(self.clip.duration_s)}")
        self._badge.setVisible(self.clip.shorter and (start, end) == self._original_range)
        self.range_changed.emit()

    def _reject(self, message: str) -> None:
        self._range_valid = False
        self._range_error.setText(message)
        self._range_error.show()
        self._preview.setEnabled(False)
        self.range_changed.emit()


def _clock_field(seconds: float, tip: str) -> QLineEdit:
    field = QLineEdit()
    field.setInputMask("99:99:99;_")
    field.setText(format_clock(seconds))
    field.setToolTip(tip)
    field.setFixedWidth(96)
    field.setCursorPosition(0)
    return field


def _position_from_field(field: QLineEdit, current: float) -> float:
    if field.text() == format_clock(current):
        return current
    return parse_position(field.text())
