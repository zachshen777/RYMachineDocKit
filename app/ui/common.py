"""通用 UI 组件：卡片、选路径行、后台线程、消息条。"""
from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from . import theme


def card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    """创建一张圆角卡片，返回 (卡片, 内容布局)。"""
    f = QFrame()
    f.setObjectName("card")
    v = QVBoxLayout(f)
    v.setContentsMargins(16, 14, 16, 14)
    v.setSpacing(10)
    if title:
        t = QLabel(title)
        t.setObjectName("cardTitle")
        v.addWidget(t)
    return f, v


def page_header(title: str, desc: str = "") -> QWidget:
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 4)
    v.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    v.addWidget(t)
    if desc:
        d = QLabel(desc)
        d.setObjectName("pageDesc")
        d.setWordWrap(True)
        v.addWidget(d)
    return w


def browse_row(placeholder: str = "", dir_mode: bool = False, name_filters: list[str] | None = None):
    """「输入框 + 浏览按钮」一行。返回 (widget, line_edit)。

    dir_mode=True 选目录，否则选文件（name_filters 如 ["PDF 文件 (*.pdf)"]）。
    """
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    btn = QPushButton("浏览…")

    def _browse():
        if dir_mode:
            path = QFileDialog.getExistingDirectory(w, "选择文件夹", edit.text() or "")
        else:
            path, _ = QFileDialog.getOpenFileName(
                w, "选择文件", edit.text() or "", ";;".join(name_filters or ["所有文件 (*.*)"]))
        if path:
            edit.setText(path)

    btn.clicked.connect(_browse)
    h.addWidget(edit, 1)
    h.addWidget(btn)
    return w, edit


class Worker(QThread):
    """后台任务线程：fn(*args, **kwargs) 在子线程执行。

    进度通过 progress.emit(int, str) 上报；结果/异常分别走 done / failed。
    """

    progress = Signal(int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, parent=None, **kwargs):
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):  # noqa: D102
        try:
            self.done.emit(self._fn(self, *self._args, **self._kwargs))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            msg = str(e) or e.__class__.__name__
            self.failed.emit(msg)


def confirm(parent, title: str, text: str) -> bool:
    return QMessageBox.question(parent, title, text,
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes


def info(parent, text: str, title: str = "提示"):
    QMessageBox.information(parent, title, text)


def error(parent, text: str, title: str = "出错了"):
    QMessageBox.critical(parent, title, text)
