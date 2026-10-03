from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from cut_and_cut.core.models import CutMode, MediaInfo, PlanError, PlanResult, ProjectConfig
from cut_and_cut.core.planner import plan_clips
from cut_and_cut.core.timeparse import TimeParseError, format_clock, parse_duration
from cut_and_cut.user_settings import last_destination, remember_destination
from cut_and_cut.workers.probe_worker import ProbeWorker

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
_VIDEO_FILTER = "Vídeos (*.mp4 *.mov *.mkv *.avi *.webm)"


class ConfigPage(QWidget):
    submitted = Signal(object, object, object)

    def __init__(self, ffprobe: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ffprobe = ffprobe
        self._media: MediaInfo | None = None
        self._probe_state = "idle"
        self._probe_error = ""
        self._inflight: Path | None = None

        self._probe = ProbeWorker(self)
        self._probe.succeeded.connect(self._on_probe)
        self._probe.failed.connect(self._on_probe_failed)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Aula 01")

        self._destination = QLineEdit(last_destination())
        self._destination.setPlaceholderText("Pasta onde o projeto será criado")
        destination_button = QPushButton("Escolher…")
        destination_button.clicked.connect(self._browse_destination)

        self._source = QLineEdit()
        self._source.setPlaceholderText("Arquivo de vídeo")
        source_button = QPushButton("Escolher…")
        source_button.clicked.connect(self._browse_source)
        self._source.textChanged.connect(self._sync_source)

        self._duration = QLineEdit()
        self._duration.setInputMask("99:99:99;_")
        self._duration.setToolTip("Formato horas:minutos:segundos. Exemplo: 00:01:30.")
        self._duration.setCursorPosition(0)
        self._count = QLineEdit()
        self._count.setPlaceholderText("vazio usa todos os cortes que couberem")

        self._precise = QRadioButton("Preciso")
        self._fast = QRadioButton("Rápido")
        self._precise.setChecked(True)
        mode_group = QButtonGroup(self)
        mode_group.addButton(self._precise)
        mode_group.addButton(self._fast)
        mode_box = QWidget()
        mode_layout = QHBoxLayout(mode_box)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.addWidget(self._precise)
        mode_layout.addWidget(self._fast)
        mode_layout.addStretch(1)

        self._fast_hint = QLabel(
            "No modo rápido os cortes caem em keyframes e podem ficar imprecisos."
        )
        self._fast_hint.setObjectName("warningLabel")
        self._fast_hint.setWordWrap(True)
        self._fast_hint.setVisible(False)
        self._fast.toggled.connect(self._fast_hint.setVisible)

        self._info = QLabel("")
        self._info.setWordWrap(True)
        self._error = QLabel("")
        self._error.setObjectName("errorLabel")
        self._error.setWordWrap(True)

        continue_button = QPushButton("Continuar")
        continue_button.clicked.connect(self._on_continue)

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("Nome do projeto", self._name)
        form.addRow("Pasta de destino", _with_button(self._destination, destination_button))
        form.addRow("Vídeo de origem", _with_button(self._source, source_button))
        form.addRow("Duração de cada corte", self._duration)
        form.addRow("Quantidade de cortes (opcional)", self._count)
        form.addRow("Modo de corte", mode_box)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(continue_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(_heading("Configuração", "Etapa 1 de 3"))
        layout.addLayout(form)
        layout.addWidget(self._fast_hint)
        layout.addWidget(self._info)
        layout.addWidget(self._error)
        layout.addStretch(1)
        layout.addLayout(buttons)

    def set_ffprobe(self, ffprobe: Path) -> None:
        self._ffprobe = ffprobe

    def reset(self) -> None:
        self._name.clear()
        self._source.clear()
        self._duration.clear()
        self._count.clear()
        self._precise.setChecked(True)
        self._error.setText("")
        self._info.setText("")
        self._media = None
        self._probe_state = "idle"
        self._probe_error = ""
        self._inflight = None

    def shutdown(self) -> None:
        self._probe.shutdown()

    def _browse_destination(self) -> None:
        current = self._destination.text().strip() or last_destination() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Escolher pasta de destino", current)
        if chosen:
            self._destination.setText(chosen)
            remember_destination(Path(chosen))

    def _browse_source(self) -> None:
        current = self._source.text().strip()
        if current:
            start = str(Path(current).parent)
        else:
            start = self._destination.text().strip() or str(Path.home())
        chosen, _selected = QFileDialog.getOpenFileName(
            self,
            "Escolher vídeo",
            start,
            _VIDEO_FILTER,
        )
        if chosen:
            self._source.setText(chosen)

    def _sync_source(self) -> None:
        path = Path(self._source.text().strip())
        if self._media is not None and self._media.path == path:
            self._probe_state = "ready"
            self._inflight = path
            self._info.setText(describe_media(self._media))
            return
        self._media = None
        if path.suffix.lower() not in VIDEO_EXTENSIONS or not path.is_file():
            self._probe_state = "idle"
            self._inflight = None
            self._info.setText("")
            return
        if self._probe_state == "loading" and self._inflight == path:
            return
        self._probe_state = "loading"
        self._probe_error = ""
        self._inflight = path
        self._info.setText("Lendo o vídeo…")
        self._error.setText("")
        self._probe.probe(self._ffprobe, path)

    def _on_probe(self, info: object) -> None:
        if not isinstance(info, MediaInfo):
            return
        if Path(self._source.text().strip()) != info.path:
            return
        self._media = info
        self._probe_state = "ready"
        self._info.setText(describe_media(info))

    def _on_probe_failed(self, message: str) -> None:
        if self._inflight is None or Path(self._source.text().strip()) != self._inflight:
            return
        self._media = None
        self._probe_state = "failed"
        self._probe_error = message
        self._info.setText("")
        self._error.setText(message)

    def _on_continue(self) -> None:
        try:
            config, media, plan = self._build()
        except ValueError as exc:
            self._error.setText(str(exc))
            return
        self._error.setText("")
        self.submitted.emit(config, media, plan)

    def _build(self) -> tuple[ProjectConfig, MediaInfo, PlanResult]:
        name = self._name.text().strip()
        if not name:
            raise ValueError("Informe o nome do projeto.")

        destination = Path(self._destination.text().strip())
        if not destination.is_dir():
            raise ValueError("Escolha uma pasta de destino.")

        source = Path(self._source.text().strip())
        if source.suffix.lower() not in VIDEO_EXTENSIONS or not source.is_file():
            raise ValueError("Escolha um vídeo de origem (mp4, mov, mkv, avi ou webm).")

        if self._probe_state == "loading":
            raise ValueError("Aguarde a leitura do vídeo.")
        media = self._media
        if media is None or media.path != source:
            raise ValueError(self._probe_error or "Não foi possível ler o vídeo.")

        if not self._duration.hasAcceptableInput():
            raise ValueError("Informe a duração no formato 00:01:30.")
        try:
            segment = parse_duration(self._duration.text())
        except TimeParseError as exc:
            raise ValueError(str(exc)) from exc

        count = _parse_count(self._count.text())
        mode = CutMode.FAST if self._fast.isChecked() else CutMode.PRECISE
        try:
            plan = plan_clips(media.duration_s, segment, count)
        except PlanError as exc:
            raise ValueError(str(exc)) from exc

        config = ProjectConfig(
            name=name,
            destination=destination,
            source=source,
            segment_duration_s=segment,
            count=count,
            mode=mode,
        )
        return config, media, plan


def describe_media(info: MediaInfo) -> str:
    audio = info.audio_codec if info.audio_codec else "sem áudio"
    return (
        f"Duração {format_clock(info.duration_s)} · "
        f"{info.width}×{info.height} · "
        f"vídeo {info.video_codec} · áudio {audio}"
    )


def _parse_count(text: str) -> int | None:
    raw = text.strip()
    if not raw:
        return None
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError("A quantidade de cortes precisa ser um número inteiro maior que zero.")
    return int(raw)


def _with_button(field: QLineEdit, button: QPushButton) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(field, 1)
    layout.addWidget(button)
    return row


def _heading(title: str, step: str) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    heading = QLabel(title)
    heading.setObjectName("pageTitle")
    step_label = QLabel(step)
    step_label.setObjectName("pageStep")
    layout.addWidget(heading)
    layout.addWidget(step_label)
    return box
