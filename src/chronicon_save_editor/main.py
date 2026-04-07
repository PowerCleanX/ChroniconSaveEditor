from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from chronicon_save_editor.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Chronicon Save Editor")
    app.setOrganizationName("Open Source")

    window = MainWindow()
    window.resize(1320, 860)
    window.show()
    return app.exec()
