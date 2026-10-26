"""PDF 提取页面。"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel,
    QPlainTextEdit, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...ui import common
from ...ui import theme
from . import logic


class PdfExtractPage(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._rows: list[logic.ExtractRow] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        root.addWidget(common.page_header(
            "PDF 提取",
            "输入关键字（每行一个），在 PDF 文本层定位关键字后向右或向下取值；支持单个文件或整个文件夹批量提取，结果可导出 Excel。"))

        # ---- 输入设置 ----
        cfg, cv = common.card("提取设置")
        root.addWidget(cfg)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("来源"))
        self.src_edit = _combo_edit()
        btn_file = QPushButton("选文件")
        btn_dir = QPushButton("选文件夹")
        btn_file.clicked.connect(self._pick_file)
        btn_dir.clicked.connect(self._pick_dir)
        row1.addWidget(self.src_edit, 1)
        row1.addWidget(btn_file)
        row1.addWidget(btn_dir)
        cv.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("取值方向"))
        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["向右取值", "向下取值"])
        row2.addWidget(self.dir_combo)
        row2.addSpacing(12)
        row2.addWidget(QLabel("搜索容差 (pt)"))
        self.tol_spin = QDoubleSpinBox()
        self.tol_spin.setRange(1, 60)
        self.tol_spin.setValue(6)
        row2.addWidget(self.tol_spin)
        self.recursive_cb = QCheckBox("包含子文件夹")
        self.recursive_cb.setChecked(True)
        row2.addWidget(self.recursive_cb)
        row2.addStretch(1)
        cv.addLayout(row2)

        kw_hint = QLabel("关键字（每行一个，支持多个）")
        kw_hint.setObjectName("hint")
        cv.addWidget(kw_hint)
        self.kw_edit = QPlainTextEdit()
        self.kw_edit.setPlaceholderText("例如：\n使用订单\n钢板订单\n程序名\n规格\n材质")
        self.kw_edit.setFixedHeight(110)
        cv.addWidget(self.kw_edit)

        # ---- 操作 + 结果 ----
        act_row = QHBoxLayout()
        self.run_btn = QPushButton("开始提取")
        self.run_btn.setObjectName("primaryBtn")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self._run)
        self.export_btn = QPushButton("导出 Excel")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(260)
        self.progress.setValue(0)
        self.status = QLabel("就绪")
        self.status.setObjectName("hint")
        act_row.addWidget(self.run_btn)
        act_row.addWidget(self.export_btn)
        act_row.addStretch(1)
        act_row.addWidget(self.status)
        act_row.addWidget(self.progress)
        root.addLayout(act_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["文件名", "页码", "关键字", "提取值"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 60)
        self.table.setColumnWidth(2, 160)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, 1)

    # ---------------- 交互 ----------------
    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 文件", "", "PDF 文件 (*.pdf)")
        if path:
            self.src_edit.setText(path)

    def _pick_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            self.src_edit.setText(path)

    def _run(self):
        src = self.src_edit.text().strip()
        if not src or not os.path.exists(src):
            common.error(self, "请先选择存在的 PDF 文件或文件夹")
            return
        keywords = [k.strip() for k in self.kw_edit.toPlainText().splitlines() if k.strip()]
        if not keywords:
            common.error(self, "请至少输入一个关键字")
            return
        self._set_busy(True)
        self.progress.setValue(0)
        self.status.setText("提取中…")
        direction = "right" if self.dir_combo.currentIndex() == 0 else "below"
        self._worker = common.Worker(
            logic.run_extract, [src], keywords, direction,
            self.tol_spin.value(), self.recursive_cb.isChecked(), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str):
        self.progress.setValue(pct)
        self.status.setText(msg)

    def _on_done(self, result: logic.ExtractResult):
        self._set_busy(False)
        self.progress.setValue(100)
        self._rows = result.rows
        self.table.setRowCount(0)
        for r in result.rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(r.file))
            self.table.setItem(i, 1, QTableWidgetItem(str(r.page)))
            self.table.setItem(i, 2, QTableWidgetItem(r.keyword))
            self.table.setItem(i, 3, QTableWidgetItem(r.value))
        msg = f"完成：{result.file_count} 个文件 / {result.page_count} 页，提取 {len(result.rows)} 条"
        if result.skipped:
            msg += f"，跳过 {len(result.skipped)} 个"
        self.status.setText(msg)
        self.export_btn.setEnabled(bool(self._rows))
        if result.skipped:
            common.info(self, "以下文件提取失败：\n" + "\n".join(result.skipped[:10]), title="部分文件被跳过")

    def _on_failed(self, msg: str):
        self._set_busy(False)
        self.status.setText("失败")
        common.error(self, msg)

    def _export(self):
        if not self._rows:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出 Excel", "提取结果.xlsx", "Excel 文件 (*.xlsx)")
        if not path:
            return
        logic.export_xlsx(self._rows, path)
        self.status.setText(f"已导出：{path}")

    def _set_busy(self, busy: bool):
        self.run_btn.setEnabled(not busy)
        self.run_btn.setText("提取中…" if busy else "开始提取")


def _combo_edit() -> "QLineEditLike":
    # 简单占位：直接用 QLineEdit
    from PySide6.QtWidgets import QLineEdit
    e = QLineEdit()
    e.setPlaceholderText("选择 PDF 文件或包含 PDF 的文件夹")
    return e
