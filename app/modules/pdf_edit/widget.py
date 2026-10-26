"""PDF 编辑页面：预览渲染 + 橡皮筋框选 + 编辑项列表 + 批量应用。"""
from __future__ import annotations

import os

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QPushButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget, QColorDialog, QFormLayout, QFileDialog,
)

from ...ui import common, theme
from . import logic


class PreviewCanvas(QWidget):
    """显示当前页渲染图，支持橡皮筋框选，并绘制已添加的编辑框。"""

    rectSelected = Signal(float, float, float, float)  # rx, ry, rw, rh

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._edits: list[logic.EditSpec] = []
        self._origin: QPoint | None = None
        self._current: QRect | None = None
        self.setMouseTracking(False)
        self.setMinimumSize(300, 300)
        self.setCursor(Qt.CrossCursor)

    def set_pixmap_bytes(self, png: bytes):
        img = QImage.fromData(png)
        self._pixmap = QPixmap.fromImage(img)
        self.setFixedSize(self._pixmap.size())
        self.update()

    def set_edits(self, edits: list[logic.EditSpec]):
        self._edits = edits
        self.update()

    def paintEvent(self, ev):  # noqa: N802
        p = QPainter(self)
        if self._pixmap:
            p.drawPixmap(0, 0, self._pixmap)
        pen = QPen(QColor(theme.PRIMARY), 2, Qt.DashLine)
        p.setPen(pen)
        font = QFont()
        font.setPointSize(9)
        p.setFont(font)
        w, h = self.width(), self.height()
        for i, e in enumerate(self._edits, 1):
            r = QRect(int(e.rx * w), int(e.ry * h), int(e.rw * w), int(e.rh * h))
            p.drawRect(r)
            p.fillRect(r.adjusted(0, 0, 0, 14).intersected(self.rect()), QColor(59, 130, 246, 40))
            p.drawText(r.adjusted(4, 2, 0, 0), Qt.AlignTop | Qt.AlignLeft, str(i))
        if self._current:
            p.setPen(QPen(QColor(theme.SUCCESS), 2, Qt.DashLine))
            p.drawRect(self._current)
        p.end()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._origin = ev.position().toPoint()
            self._current = QRect(self._origin, self._origin)

    def mouseMoveEvent(self, ev):
        if self._origin:
            self._current = QRect(self._origin, ev.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton or not self._current:
            return
        r = self._current
        self._current = None
        self._origin = None
        w, h = self.width(), self.height()
        if r.width() < 8 or r.height() < 8:
            self.update()
            return
        self.rectSelected.emit(r.x() / w, r.y() / h, r.width() / w, r.height() / h)


class TextDialog(QDialog):
    """框选完成后填写新文本与样式。"""

    def __init__(self, parent, rect_h_pt: float):
        super().__init__(parent)
        self.setWindowTitle("框选区域内容")
        self.setMinimumWidth(360)
        form = QFormLayout(self)
        form.setSpacing(10)
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("留空 = 仅遮罩清除原文，不写新文字")
        form.addRow("新文本", self.text_edit)
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(0, 96)
        self.size_spin.setDecimals(1)
        self.size_spin.setSpecialValueText("自动")
        self.size_spin.setValue(0)
        self.size_spin.setSingleStep(0.5)
        auto = round(rect_h_pt * logic.FONT_RATIO, 1)
        self.size_spin.setToolTip(f"0 表示自动（约 {auto}pt）")
        form.addRow("字号 (pt)", self.size_spin)
        self.align_combo = QComboBox()
        self.align_combo.addItems(["居中", "左对齐"])
        form.addRow("对齐", self.align_combo)
        self.mask_btn = QPushButton("白色")
        self.mask_btn.clicked.connect(lambda: self._pick_color(self.mask_btn, "#ffffff"))
        self.text_btn = QPushButton("黑色")
        self.text_btn.clicked.connect(lambda: self._pick_color(self.text_btn, "#000000"))
        row = QHBoxLayout()
        row.addWidget(QLabel("遮罩色"))
        row.addWidget(self.mask_btn)
        row.addSpacing(8)
        row.addWidget(QLabel("文字色"))
        row.addWidget(self.text_btn)
        row.addStretch(1)
        form.addRow(row)
        ok = QPushButton("确定")
        ok.setObjectName("primaryBtn")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        brow = QHBoxLayout()
        brow.addStretch(1)
        brow.addWidget(ok)
        brow.addWidget(cancel)
        form.addRow(brow)
        self.text_edit.setFocus()
        self._mask_color, self._text_color = "#ffffff", "#000000"

    def _pick_color(self, btn: QPushButton, current: str):
        c = QColorDialog.getColor(QColor(btn.text()), self)
        if c.isValid():
            btn.setText(c.name())

    def values(self) -> tuple[str, float | None, str, str, str]:
        size = self.size_spin.value() if self.size_spin.value() > 0 else None
        align = "center" if self.align_combo.currentIndex() == 0 else "left"
        return (self.text_edit.text().strip(), size, align,
                self.mask_btn.text(), self.text_btn.text())


class PdfEditPage(QWidget):
    def __init__(self):
        super().__init__()
        self.pdf_path = ""
        self.page_count = 0
        self.cur_page = 1
        self.edits: list[logic.EditSpec] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        root.addWidget(common.page_header(
            "PDF 编辑",
            "打开 PDF 后在预览图上拖拽框选区域（一次框选可应用到多页同一位置），遮罩原文并重写新文字，另存为「-已编辑」文件。"))

        top, tv = common.card()
        row = QHBoxLayout(top)
        self.open_btn = QPushButton("打开 PDF")
        self.open_btn.setObjectName("primaryBtn")
        self.open_btn.clicked.connect(self._open)
        self.file_label = QLabel("未打开文件")
        self.file_label.setObjectName("hint")
        self.page_label = QLabel("")
        row.addWidget(self.open_btn)
        row.addWidget(self.file_label, 1)
        row.addWidget(self.page_label)
        tv.addWidget(row)
        root.addWidget(top)

        body = QHBoxLayout()
        body.setSpacing(12)

        # 左侧：预览 + 翻页 + 应用
        left, lv = common.card()
        nav = QHBoxLayout()
        self.prev_btn = QPushButton("◀ 上一页")
        self.next_btn = QPushButton("下一页 ▶")
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 1)
        self.prev_btn.clicked.connect(lambda: self._goto(self.page_spin.value() - 1))
        self.next_btn.clicked.connect(lambda: self._goto(self.page_spin.value() + 1))
        self.page_spin.valueChanged.connect(self._goto)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.page_spin)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        nav.addWidget(QLabel("应用到"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["仅当前页", "全部页面", "页码范围"])
        self.scope_edit = QLineEdit()
        self.scope_edit.setPlaceholderText("如 1,3,5-8")
        self.scope_edit.setFixedWidth(110)
        nav.addWidget(self.scope_combo)
        nav.addWidget(self.scope_edit)
        lv.addLayout(nav)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.canvas = PreviewCanvas()
        self.scroll.setWidget(self.canvas)
        lv.addWidget(self.scroll, 1)

        apply_row = QHBoxLayout()
        self.apply_btn = QPushButton("执行编辑并另存")
        self.apply_btn.setObjectName("primaryBtn")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply)
        self.status = QLabel("拖拽框选 → 填写内容 → 执行编辑")
        self.status.setObjectName("hint")
        apply_row.addWidget(self.apply_btn)
        apply_row.addStretch(1)
        apply_row.addWidget(self.status)
        lv.addLayout(apply_row)
        body.addWidget(left, 1)

        # 右侧：编辑项列表
        right, rv = common.card("编辑项（框选区域）")
        self.edit_list = QListWidget()
        self.edit_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.edit_list.customContextMenuRequested.connect(self._edit_menu)
        rv.addWidget(self.edit_list, 1)
        self.clear_btn = QPushButton("清空全部")
        self.clear_btn.setObjectName("dangerBtn")
        self.clear_btn.clicked.connect(self._clear_edits)
        rv.addWidget(self.clear_btn)
        hint = QLabel("提示：编辑按比例记录，应用「全部页面」时会在每页同一相对位置生效。")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        rv.addWidget(hint)
        body.addWidget(right, 0)
        right.setFixedWidth(280)

        root.addLayout(body, 1)

        self.canvas.rectSelected.connect(self._on_rect)
        self.scope_combo.currentIndexChanged.connect(
            lambda i: self.scope_edit.setEnabled(i == 2))
        self.scope_edit.setEnabled(False)

    # ---------------- 打开 / 翻页 ----------------
    def _open(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开 PDF", "", "PDF 文件 (*.pdf)")
        if not path:
            return
        self.pdf_path = path
        self.page_count = len(logic.page_infos(path))
        self.page_spin.setRange(1, self.page_count)
        self.page_spin.setValue(1)
        self.cur_page = 1
        self.edits.clear()
        self._refresh_list()
        self.file_label.setText(os.path.basename(path))
        self.apply_btn.setEnabled(True)
        self._render()

    def _goto(self, page: int):
        if not self.pdf_path:
            return
        page = max(1, min(self.page_count, page))
        if page != self.cur_page or not self._pixmap_loaded():
            self.cur_page = page
            self.page_spin.blockSignals(True)
            self.page_spin.setValue(page)
            self.page_spin.blockSignals(False)
            self._render()

    def _pixmap_loaded(self) -> bool:
        return self.canvas._pixmap is not None

    def _render(self):
        png = logic.render_page_png(self.pdf_path, self.cur_page)
        self.canvas.set_pixmap_bytes(png)
        self.canvas.set_edits(self.edits)
        self.page_label.setText(f"第 {self.cur_page} / {self.page_count} 页")

    # ---------------- 框选 ----------------
    def _on_rect(self, rx, ry, rw, rh):
        infos = logic.page_infos(self.pdf_path)
        info = infos[self.cur_page - 1]
        dlg = TextDialog(self, rh * info["height"])
        if dlg.exec() != QDialog.Accepted:
            self.canvas.set_edits(self.edits)
            return
        text, size, align, mask, tcolor = dlg.values()
        self.edits.append(logic.EditSpec(rx, ry, rw, rh, text, size, align, mask, tcolor))
        self._refresh_list()
        self.canvas.set_edits(self.edits)

    def _refresh_list(self):
        self.edit_list.clear()
        for i, e in enumerate(self.edits, 1):
            brief = e.text if e.text else "（仅遮罩）"
            QListWidgetItem(f"{i}. {brief}", self.edit_list)
        self.status.setText(f"共 {len(self.edits)} 个编辑项")

    def _edit_menu(self, pos):
        item = self.edit_list.itemAt(pos)
        if not item:
            return
        idx = self.edit_list.row(item)
        menu = QMenu(self)
        menu.addAction("删除此项", lambda: self._del_edit(idx))
        menu.exec(self.edit_list.mapToGlobal(pos))

    def _del_edit(self, idx: int):
        del self.edits[idx]
        self._refresh_list()
        self.canvas.set_edits(self.edits)

    def _clear_edits(self):
        if not self.edits:
            return
        if common.confirm(self, "清空", "确定清空全部编辑项？"):
            self.edits.clear()
            self._refresh_list()
            self.canvas.set_edits(self.edits)

    # ---------------- 应用 ----------------
    def _apply(self):
        if not self.pdf_path or not self.edits:
            common.error(self, "请先打开 PDF 并框选至少一个区域")
            return
        scope = ["current", "all", "range"][self.scope_combo.currentIndex()]
        spec = {"current": str(self.cur_page), "all": "all",
                "range": self.scope_edit.text() or "all"}[scope]
        out, n = logic.apply_edits(self.pdf_path, self.edits, spec)
        self.status.setText(f"已生成：{os.path.basename(out)}（{n} 页）")
        if common.confirm(self, "完成", f"已生成 {os.path.basename(out)}（处理 {n} 页）。\n\n是否打开所在文件夹？"):
            os.startfile(os.path.dirname(out))
