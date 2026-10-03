import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from cut_and_cut import __version__

_PHOTO_WIDTH = 280
_PHOTO_HEIGHT = 360


class HomePage(QWidget):
    start_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        title = QLabel("Cut Cut")
        title.setObjectName("homeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        author = QLabel("Feito por Hugo Guedes")
        author.setObjectName("homeAuthor")
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)

        info = QLabel(
            f"Versão {__version__}\nCorta um vídeo em partes de duração fixa."
        )
        info.setObjectName("homeInfo")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)

        self._photo = QLabel()
        self._photo.setObjectName("homePhoto")
        self._photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(author_photo()))
        if pixmap.isNull():
            self._photo.setText("Foto indisponível")
        else:
            self._photo.setPixmap(
                pixmap.scaled(
                    _PHOTO_WIDTH,
                    _PHOTO_HEIGHT,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        start = QPushButton("Começar")
        start.clicked.connect(self.start_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(author)
        layout.addWidget(info)
        layout.addSpacing(8)
        layout.addWidget(self._photo, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(8)
        layout.addWidget(start, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)


def author_photo() -> Path:
    packaged = Path(__file__).resolve().parent.parent / "assets" / "author.jpg"
    if packaged.is_file():
        return packaged
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        bundled = meipass / "assets" / "author.jpg"
        if bundled.is_file():
            return bundled
        beside = Path(sys.executable).resolve().parent / "author.jpg"
        if beside.is_file():
            return beside
    return packaged
