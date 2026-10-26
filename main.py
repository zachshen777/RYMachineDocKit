"""程序入口：python main.py"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app import __app_name__
from app.ui import theme
from app.ui.main_window import MainWindow, resource_path


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.app_qss())
    icon = QIcon(resource_path("logo.png"))
    app.setWindowIcon(icon)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
