from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from cut_and_cut.binaries import ffprobe_beside, is_usable

_MESSAGE = (
    "O FFmpeg não foi encontrado.\n\n"
    "Instale o FFmpeg e deixe os comandos ffmpeg e ffprobe no PATH, "
    "ou escolha o executável do ffmpeg. O ffprobe precisa estar na mesma pasta.\n\n"
    "macOS: brew install ffmpeg\n"
    "Windows: winget install --id Gyan.FFmpeg -e"
)


class FfmpegSetupDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, missing: bool = True) -> None:
        super().__init__(parent)
        self.setWindowTitle("FFmpeg não encontrado" if missing else "Localizar FFmpeg")
        self._ffmpeg: Path | None = None
        self._ffprobe: Path | None = None

        message = _MESSAGE if missing else (
            "Escolha o executável do ffmpeg. O ffprobe precisa estar na mesma pasta."
        )
        text = QLabel(message)
        text.setWordWrap(True)
        buttons = QDialogButtonBox()
        locate = buttons.addButton("Localizar ffmpeg…", QDialogButtonBox.ButtonRole.ActionRole)
        cancel = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("Cancelar")
        locate.clicked.connect(self._locate)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addWidget(buttons)
        self.resize(480, 220)

    def binaries(self) -> tuple[Path, Path]:
        if self._ffmpeg is None or self._ffprobe is None:
            raise RuntimeError("FFmpeg ainda não foi escolhido.")
        return self._ffmpeg, self._ffprobe

    def _locate(self) -> None:
        start = str(self._ffmpeg.parent) if self._ffmpeg is not None else ""
        chosen, _selected = QFileDialog.getOpenFileName(
            self,
            "Escolher o executável do ffmpeg",
            start,
            "Executável (ffmpeg ffmpeg.exe *);;Todos os arquivos (*)",
        )
        if not chosen:
            return
        ffmpeg = Path(chosen)
        if not is_usable(ffmpeg):
            QMessageBox.warning(
                self,
                "FFmpeg",
                "Esse arquivo não pode ser executado. Escolha o ffmpeg.",
            )
            return
        ffprobe = ffprobe_beside(ffmpeg)
        if ffprobe is None or not is_usable(ffprobe):
            QMessageBox.warning(
                self,
                "FFmpeg",
                "O ffprobe não está na mesma pasta do ffmpeg.",
            )
            return
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self.accept()
