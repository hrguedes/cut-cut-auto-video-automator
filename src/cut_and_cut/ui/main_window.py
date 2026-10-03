from pathlib import Path

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
)

from cut_and_cut.core.models import MediaInfo, PlanResult, ProjectConfig
from cut_and_cut.ui.config_page import ConfigPage
from cut_and_cut.ui.export_page import ExportPage
from cut_and_cut.ui.ffmpeg_dialog import FfmpegSetupDialog
from cut_and_cut.ui.home_page import HomePage
from cut_and_cut.ui.review_page import ReviewPage
from cut_and_cut.user_settings import remember_destination, save_binaries

_STYLE = """
QLabel#pageTitle { font-size: 22px; font-weight: 600; }
QLabel#pageStep { color: palette(mid); }
QLabel#homeTitle { font-size: 36px; font-weight: 700; }
QLabel#homeAuthor { font-size: 18px; }
QLabel#homeInfo { color: palette(mid); }
QLabel#errorLabel { color: #a12626; }
QLabel#warningLabel {
    background: #f3e2b8;
    color: #5c4314;
    border-radius: 6px;
    padding: 8px;
}
QFrame#clipCard {
    border: 1px solid palette(mid);
    border-radius: 8px;
}
QLabel#thumbLabel {
    background: palette(alternate-base);
    border-radius: 4px;
}
QLabel#shortBadge {
    background: #f3e2b8;
    color: #5c4314;
    border-radius: 4px;
    padding: 2px 8px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self, ffmpeg: Path, ffprobe: Path) -> None:
        super().__init__()
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self._config_data: ProjectConfig | None = None
        self._media: MediaInfo | None = None

        self.setWindowTitle("Cut Cut")
        self.setMinimumSize(780, 640)
        self.resize(880, 720)
        self.setStyleSheet(_STYLE)

        self._home = HomePage()
        self._config = ConfigPage(ffprobe)
        self._review = ReviewPage()
        self._export = ExportPage()
        self._home.start_requested.connect(self._show_config)
        self._config.submitted.connect(self._on_configured)
        self._review.back_requested.connect(self._show_config)
        self._review.export_requested.connect(self._start_export)
        self._export.review_requested.connect(self._back_to_review)
        self._export.redo_requested.connect(self._start_export)
        self._export.new_project_requested.connect(self._new_project)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._home)
        self._stack.addWidget(self._config)
        self._stack.addWidget(self._review)
        self._stack.addWidget(self._export)
        self.setCentralWidget(self._stack)

        tools = self.menuBar().addMenu("Ferramentas")
        locate = tools.addAction("Localizar FFmpeg…")
        locate.triggered.connect(self._locate_ffmpeg)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._config.shutdown()
        self._review.shutdown()
        self._export.shutdown()
        event.accept()

    def _on_configured(self, config: object, media: object, plan: object) -> None:
        if not isinstance(config, ProjectConfig) or not isinstance(media, MediaInfo):
            return
        if not isinstance(plan, PlanResult):
            return
        self._config_data = config
        self._media = media
        remember_destination(config.destination)
        self._review.show_plan(
            source=config.source,
            destination=config.destination,
            project_name=config.name,
            mode=config.mode,
            plan=plan,
            ffmpeg=self._ffmpeg,
            media_duration_s=media.duration_s,
        )
        self._stack.setCurrentWidget(self._review)

    def _show_config(self) -> None:
        self._review.pause_thumbnails()
        self._stack.setCurrentWidget(self._config)

    def _back_to_review(self) -> None:
        self._review.resume_thumbnails()
        self._stack.setCurrentWidget(self._review)

    def _new_project(self) -> None:
        self._review.clear()
        self._config.reset()
        self._config_data = None
        self._media = None
        self._stack.setCurrentWidget(self._config)

    def _start_export(self) -> None:
        config = self._config_data
        media = self._media
        if config is None or media is None:
            return
        items = self._review.export_items()
        if not items:
            return
        existing = [item.output for item in items if item.output.exists()]
        if existing and not self._confirm_overwrite(existing):
            return
        self._review.pause_thumbnails()
        self._export.begin(
            self._ffmpeg,
            config.source,
            config.mode,
            media.has_audio,
            items,
        )
        self._stack.setCurrentWidget(self._export)

    def _confirm_overwrite(self, existing: list[Path]) -> bool:
        preview = "\n".join(path.name for path in existing[:8])
        if len(existing) > 8:
            preview += f"\n… e mais {len(existing) - 8}"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Substituir arquivos")
        box.setText("Já existem arquivos com esses nomes. Deseja substituí-los?")
        box.setInformativeText(preview)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        yes = box.button(QMessageBox.StandardButton.Yes)
        no = box.button(QMessageBox.StandardButton.No)
        if yes is not None:
            yes.setText("Substituir")
        if no is not None:
            no.setText("Cancelar")
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _locate_ffmpeg(self, _checked: bool = False) -> None:
        dialog = FfmpegSetupDialog(self, missing=False)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._ffmpeg, self._ffprobe = dialog.binaries()
        save_binaries(self._ffmpeg, self._ffprobe)
        self._config.set_ffprobe(self._ffprobe)
