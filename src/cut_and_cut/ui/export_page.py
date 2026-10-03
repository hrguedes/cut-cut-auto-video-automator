from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from cut_and_cut.core.models import CutMode
from cut_and_cut.ui.preview_dialog import PreviewDialog
from cut_and_cut.workers.export_worker import ExportItem, ExportWorker


class ExportPage(QWidget):
    review_requested = Signal()
    redo_requested = Signal()
    new_project_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._folder = Path()
        self._running = False
        self._items: list[ExportItem] = []

        self._worker = ExportWorker(self)
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_progress.connect(self._on_file_progress)
        self._worker.overall_progress.connect(self._on_overall)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)

        self._status = QLabel("Pronto para gerar.")
        self._status.setWordWrap(True)
        self._file_label = QLabel("")
        self._file_label.setWordWrap(True)

        self._overall = _bar()
        self._file = _bar()

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setObjectName("pageStep")

        self._results_host = QWidget()
        self._results_layout = QVBoxLayout(self._results_host)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(8)
        self._results = QScrollArea()
        self._results.setWidgetResizable(True)
        self._results.setWidget(self._results_host)
        self._results.setVisible(False)

        self._cancel = QPushButton("Cancelar")
        self._cancel.clicked.connect(self._on_cancel)
        self._open = QPushButton("Abrir pasta")
        self._open.clicked.connect(self._open_folder)
        self._open.setVisible(False)
        self._back = QPushButton("Voltar à revisão")
        self._back.clicked.connect(self.review_requested.emit)
        self._back.setVisible(False)
        self._redo = QPushButton("Refazer")
        self._redo.clicked.connect(self._on_redo)
        self._redo.setVisible(False)
        self._new = QPushButton("Novo projeto")
        self._new.clicked.connect(self.new_project_requested.emit)
        self._new.setVisible(False)

        buttons = QHBoxLayout()
        buttons.addWidget(self._new)
        buttons.addWidget(self._back)
        buttons.addStretch(1)
        buttons.addWidget(self._open)
        buttons.addWidget(self._redo)
        buttons.addWidget(self._cancel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(_heading("Exportação", "Etapa 3 de 3"))
        layout.addWidget(self._status)
        layout.addWidget(QLabel("Progresso geral"))
        layout.addWidget(self._overall)
        layout.addWidget(QLabel("Arquivo atual"))
        layout.addWidget(self._file_label)
        layout.addWidget(self._file)
        layout.addWidget(self._summary)
        layout.addWidget(self._results, 1)
        layout.addLayout(buttons)

    def begin(
        self,
        ffmpeg: Path,
        source: Path,
        mode: CutMode,
        has_audio: bool,
        items: list[ExportItem],
    ) -> None:
        self._items = list(items)
        self._folder = items[0].output.parent if items else Path()
        self._running = True
        self._status.setText("Gerando cortes…")
        self._file_label.setText("Preparando…")
        self._summary.setText("")
        self._overall.setValue(0)
        self._file.setValue(0)
        self._clear_results()
        self._results.setVisible(False)
        self._cancel.setVisible(True)
        self._cancel.setEnabled(True)
        self._cancel.setText("Cancelar")
        self._open.setVisible(False)
        self._back.setVisible(False)
        self._redo.setVisible(False)
        self._new.setVisible(False)
        self._worker.start(ffmpeg, source, mode, has_audio, items)

    def shutdown(self) -> None:
        if self._running:
            self._worker.shutdown()
            self._running = False

    def _on_file_started(self, position: int, total: int, name: str) -> None:
        self._file_label.setText(f"Arquivo {position} de {total} — {name}")
        self._file.setValue(0)

    def _on_file_progress(self, fraction: float) -> None:
        self._file.setValue(_bar_value(fraction))

    def _on_overall(self, fraction: float) -> None:
        self._overall.setValue(_bar_value(fraction))

    def _on_finished(self, count: int) -> None:
        self._running = False
        self._overall.setValue(1000)
        self._file.setValue(1000)
        self._status.setText("Exportação concluída.")
        if count == 1:
            done = "1 arquivo gerado"
        else:
            done = f"{count} arquivos gerados"
        self._summary.setText(f"{done} em\n{self._folder}")
        self._show_done()

    def _on_cancelled(self, count: int) -> None:
        self._running = False
        self._status.setText("Exportação cancelada.")
        if count == 0:
            done = "Nenhum arquivo foi concluído."
        elif count == 1:
            done = "1 arquivo foi concluído."
        else:
            done = f"{count} arquivos foram concluídos."
        self._summary.setText(f"{done} O arquivo que estava sendo gerado foi apagado.")
        self._show_done()

    def _on_failed(self, message: str) -> None:
        self._running = False
        self._status.setText("A exportação falhou.")
        self._summary.setText(message)
        self._show_done()

    def _on_cancel(self) -> None:
        self._cancel.setEnabled(False)
        self._cancel.setText("Cancelando…")
        self._status.setText("Cancelando a exportação…")
        self._worker.cancel()

    def _on_redo(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Refazer cortes")
        box.setText("Apagar os cortes gerados e fazer de novo?")
        box.setInformativeText("Os arquivos desta exportação serão apagados e gerados outra vez.")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        yes = box.button(QMessageBox.StandardButton.Yes)
        no = box.button(QMessageBox.StandardButton.No)
        if yes is not None:
            yes.setText("Apagar e refazer")
        if no is not None:
            no.setText("Cancelar")
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        self._delete_outputs()
        self.redo_requested.emit()

    def _show_done(self) -> None:
        self._cancel.setVisible(False)
        self._open.setVisible(self._folder.is_dir())
        self._back.setVisible(True)
        self._redo.setVisible(True)
        self._new.setVisible(True)
        self._fill_results()

    def _fill_results(self) -> None:
        self._clear_results()
        for item in self._items:
            row = QWidget()
            row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(item.output.name)
            label.setWordWrap(True)
            button = QPushButton("Visualizar")
            button.setEnabled(item.output.is_file())
            button.clicked.connect(
                lambda _checked=False, path=item.output, title=item.title: self._preview(path, title)
            )
            row_layout.addWidget(label, 1)
            row_layout.addWidget(button)
            self._results_layout.addWidget(row)
        self._results_layout.addStretch(1)
        self._results.setVisible(bool(self._items))

    def _clear_results(self) -> None:
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _preview(self, path: Path, title: str) -> None:
        dialog = PreviewDialog(path, title, parent=self.window())
        dialog.exec()

    def _delete_outputs(self) -> None:
        for item in self._items:
            try:
                item.output.unlink(missing_ok=True)
            except OSError:
                pass

    def _open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._folder)))


def _bar() -> QProgressBar:
    bar = QProgressBar()
    bar.setRange(0, 1000)
    bar.setValue(0)
    bar.setTextVisible(True)
    bar.setFormat("%p%")
    return bar


def _bar_value(fraction: float) -> int:
    return int(max(0.0, min(1.0, fraction)) * 1000)


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
