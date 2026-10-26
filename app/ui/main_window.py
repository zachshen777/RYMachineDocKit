"""主窗口：侧边栏导航 + 页面堆栈。"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from .. import __app_name__, __version__
from ..modules.batch_rename.widget import BatchRenamePage
from ..modules.file_classify.widget import FileClassifyPage
from ..modules.pdf_edit.widget import PdfEditPage
from ..modules.pdf_extract.widget import PdfExtractPage
from . import theme


def resource_path(rel: str) -> str:
    """兼容 PyInstaller 打包后的资源路径。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate = os.path.join(base, "resources", rel)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", rel)


NAV_ITEMS = [
    ("pdf_extract", "PDF 提取", "按关键字定位取值，批量提取并导出 Excel"),
    ("pdf_edit", "PDF 编辑", "框选区域遮罩原文并重写新文字"),
    ("file_classify", "文件归类", "按套料图命名规则自动归类 PDF / 压缩包"),
    ("batch_rename", "批量重命名", "文件夹 / 文件批量改名，规则化预览后执行"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.setWindowIcon(QIcon(resource_path("logo.png")))
        self.resize(1180, 760)
        self.setMinimumSize(980, 640)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet(f"background: {theme.BORDER};")
        layout.addWidget(divider)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.pages: dict[str, QWidget] = {}
        self._page_keys = []
        for key, name, desc in NAV_ITEMS:
            page = {
                "pdf_extract": PdfExtractPage,
                "pdf_edit": PdfEditPage,
                "file_classify": FileClassifyPage,
                "batch_rename": BatchRenamePage,
            }[key]()
            self.pages[key] = page
            self._page_keys.append(key)
            self.stack.addWidget(page)

        self._nav_group: QButtonGroup | None = None
        self._build_nav_buttons()
        self.switch_page("pdf_extract")

    # ---------------- 侧边栏 ----------------
    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(210)
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 18, 14, 14)
        v.setSpacing(4)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        logo = QLabel()
        pix = QPixmap(resource_path("logo.png"))
        if not pix.isNull():
            logo.setPixmap(pix.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setStyleSheet("background: transparent;")
        logo_row.addWidget(logo)
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        t = QLabel(__app_name__)
        t.setObjectName("appTitle")
        sub = QLabel("RYMachineDocKit")
        sub.setObjectName("appSub")
        title_col.addWidget(t)
        title_col.addWidget(sub)
        logo_row.addLayout(title_col, 1)
        v.addLayout(logo_row)

        v.addSpacing(14)
        tip = QLabel("工具箱")
        tip.setObjectName("appSub")
        v.addWidget(tip)
        v.addSpacing(4)

        self._nav_holder = QVBoxLayout()
        self._nav_holder.setSpacing(4)
        v.addLayout(self._nav_holder)

        v.addStretch(1)
        ver = QLabel(f"v{__version__}")
        ver.setObjectName("appSub")
        v.addWidget(ver)
        return side

    def _build_nav_buttons(self):
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        for i, (key, name, _desc) in enumerate(NAV_ITEMS):
            btn = QPushButton(f"  {name}")
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.switch_page(k))
            self._nav_group.addButton(btn, i)
            self._nav_holder.addWidget(btn)

    def switch_page(self, key: str):
        idx = self._page_keys.index(key)
        self._nav_group.button(idx).setChecked(True)
        self.stack.setCurrentIndex(idx)
        page = self.pages[key]
        if hasattr(page, "on_activated"):
            page.on_activated()
