import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from cut_and_cut.core.ffmpeg import output_extension
from cut_and_cut.core.models import CutMode, PlanResult
from cut_and_cut.core.naming import build_output_path
from cut_and_cut.ui.clip_card import ClipCard
from cut_and_cut.ui.preview_dialog import PreviewDialog
from cut_and_cut.workers.export_worker import ExportItem
from cut_and_cut.workers.thumbnail_worker import ThumbnailWorker


class ReviewPage(QWidget):
    back_requested = Signal()
    export_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = Path()
        self._destination = Path()
        self._project_name = ""
        self._mode = CutMode.PRECISE
        self._ffmpeg: Path | None = None
        self._media_duration_s = 0.0
        self._thumb_versions: dict[int, int] = {}
        self._cards: list[ClipCard] = []
        self._by_index: dict[int, ClipCard] = {}
        self._temp = Path(tempfile.mkdtemp(prefix="cutandcut-"))

        self._thumbs = ThumbnailWorker(self)
        self._thumbs.ready.connect(self._on_thumbnail)
        self._thumbs.failed.connect(self._on_thumbnail_failed)

        self._warning = QLabel("")
        self._warning.setObjectName("warningLabel")
        self._warning.setWordWrap(True)
        self._warning.setVisible(False)

        self._fast_hint = QLabel(
            "No modo rápido os cortes caem em keyframes e podem ficar imprecisos."
        )
        self._fast_hint.setObjectName("warningLabel")
        self._fast_hint.setWordWrap(True)
        self._fast_hint.setVisible(False)

        self._edit_hint = QLabel(
            "Se o assunto não fechar no tempo, ajuste o início e o fim de cada corte."
        )
        self._edit_hint.setWordWrap(True)

        self._cards_host = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(12)
        self._cards_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._cards_host)

        self._back = QPushButton("Voltar")
        self._back.clicked.connect(self.back_requested.emit)
        self._generate = QPushButton("Gerar cortes")
        self._generate.clicked.connect(self.export_requested.emit)

        buttons = QHBoxLayout()
        buttons.addWidget(self._back)
        buttons.addStretch(1)
        buttons.addWidget(self._generate)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(_heading("Revisão", "Etapa 2 de 3"))
        layout.addWidget(self._warning)
        layout.addWidget(self._fast_hint)
        layout.addWidget(self._edit_hint)
        layout.addWidget(scroll, 1)
        layout.addLayout(buttons)

    def show_plan(
        self,
        *,
        source: Path,
        destination: Path,
        project_name: str,
        mode: CutMode,
        plan: PlanResult,
        ffmpeg: Path,
        media_duration_s: float,
    ) -> None:
        self._source = source
        self._destination = destination
        self._project_name = project_name
        self._mode = mode
        self._ffmpeg = ffmpeg
        self._media_duration_s = media_duration_s
        self._thumb_versions = {}
        self._warning.setVisible(bool(plan.warning))
        self._warning.setText(plan.warning or "")
        self._fast_hint.setVisible(mode is CutMode.FAST)
        self._rebuild(plan)
        self._thumbs.start(ffmpeg, self._jobs())

    def export_items(self) -> list[ExportItem]:
        extension = output_extension(self._mode, self._source)
        items: list[ExportItem] = []
        for card in self._cards:
            if not card.clip.included or not card.range_valid:
                continue
            title = card.current_title()
            card.clip.title = title
            items.append(
                ExportItem(
                    index=card.clip.index,
                    start_s=card.clip.start_s,
                    duration_s=card.clip.duration_s,
                    output=build_output_path(
                        self._destination,
                        self._project_name,
                        card.clip.index,
                        title,
                        extension,
                    ),
                    title=title,
                )
            )
        return items

    def clear(self) -> None:
        self.pause_thumbnails()
        self._warning.hide()
        self._fast_hint.hide()
        self._clear_cards()
        self._generate.setEnabled(False)

    def pause_thumbnails(self) -> None:
        self._thumbs.cancel()

    def resume_thumbnails(self) -> None:
        if self._ffmpeg is None:
            return
        pending = [job for job in self._jobs() if not self._by_index[job[0]].has_thumbnail]
        if pending:
            self._thumbs.start(self._ffmpeg, pending)

    def shutdown(self) -> None:
        self._thumbs.shutdown()
        shutil.rmtree(self._temp, ignore_errors=True)

    def _rebuild(self, plan: PlanResult) -> None:
        self._clear_cards()
        for clip in plan.clips:
            card = ClipCard(clip, self._media_duration_s)
            card.inclusion_changed.connect(self._sync_generate)
            card.range_changed.connect(lambda card=card: self._on_range_changed(card))
            card.preview_requested.connect(lambda card=card: self._preview(card))
            self._cards.append(card)
            self._by_index[clip.index] = card
            self._cards_layout.addWidget(card)
        self._cards_layout.addStretch(1)
        self._sync_generate()

    def _clear_cards(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards = []
        self._by_index = {}

    def _on_range_changed(self, card: ClipCard) -> None:
        self._sync_generate()
        if self._ffmpeg is None or not card.consume_thumbnail_refresh():
            return
        card.mark_thumbnail_pending()
        version = self._thumb_versions.get(card.clip.index, 0) + 1
        self._thumb_versions[card.clip.index] = version
        output = self._temp / f"{card.clip.index:02d}-{version}.jpg"
        self._thumbs.refresh(
            self._ffmpeg,
            (card.clip.index, self._source, card.clip.start_s, output),
        )

    def _preview(self, card: ClipCard) -> None:
        if not card.range_valid:
            return
        dialog = PreviewDialog(
            self._source,
            card.current_title(),
            start_s=card.clip.start_s,
            end_s=card.clip.end_s,
            parent=self.window(),
        )
        dialog.exec()

    def _jobs(self) -> list[tuple[int, Path, float, Path]]:
        return [
            (card.clip.index, self._source, card.clip.start_s, self._temp / f"{card.clip.index:02d}.jpg")
            for card in self._cards
        ]

    def _sync_generate(self) -> None:
        included = [card for card in self._cards if card.clip.included]
        self._generate.setEnabled(bool(included) and all(card.range_valid for card in included))

    def _on_thumbnail(self, index: int, path: str) -> None:
        card = self._by_index.get(index)
        if card is not None:
            card.set_thumbnail(path)

    def _on_thumbnail_failed(self, index: int) -> None:
        card = self._by_index.get(index)
        if card is not None:
            card.mark_thumbnail_failed()


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
