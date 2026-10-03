import sys

from PySide6.QtWidgets import QApplication, QDialog

from cut_and_cut.ui.ffmpeg_dialog import FfmpegSetupDialog
from cut_and_cut.ui.main_window import MainWindow
from cut_and_cut.user_settings import load_binaries, save_binaries


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("CutAndCut")
    app.setApplicationName("CutAndCut")
    app.setApplicationDisplayName("Cut Cut")

    binaries = load_binaries()
    if binaries is None:
        dialog = FfmpegSetupDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return 1
        binaries = dialog.binaries()
        save_binaries(*binaries)

    window = MainWindow(*binaries)
    window.show()
    return app.exec()
