"""文件归类页面：解析 → 预览树 → 确认执行。"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QRadioButton, QTableWidget, QTableWidgetItem, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ...ui import common
from ...ui import theme
from . import logic


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


class FileClassifyPage(QWidget):
    def __init__(self):
        super().__init__()
        self._plan: logic.Plan | None = None
        self._source = ""
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        root.addWidget(common.page_header(
            "文件归类",
            "选择文件夹或 zip 压缩包，按套料图命名规则识别「项目编号 / 仓号字母」生成两级目录；重名进 _重名、识别不了进 _未识别、非 PDF 进 其他文件。预览确认后执行，不改动原文件（可选移动）。"))

        src_card, sv = common.card("来源")
        row = QHBoxLayout()
        self.src_edit = None
        from PySide6.QtWidgets import QLineEdit
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("选择包含套料图 PDF 的文件夹或 .zip 压缩包")
        b1 = QPushButton("选文件夹")
        b2 = QPushButton("选 zip")
        b1.clicked.connect(self._pick_dir)
        b2.clicked.connect(self._pick_zip)
        self.analyze_btn = QPushButton("解析")
        self.analyze_btn.setObjectName("primaryBtn")
        self.analyze_btn.clicked.connect(self._analyze)
        row.addWidget(self.src_edit, 1)
        row.addWidget(b1)
        row.addWidget(b2)
        row.addWidget(self.analyze_btn)
        sv.addLayout(row)
        root.addWidget(src_card)

        # 统计
        stat_card, stv = common.card("解析结果")
        self.stat_label = QLabel("尚未解析")
        self.stat_label.setObjectName("hint")
        stv.addWidget(self.stat_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["目标路径", "来源", "大小", "说明"])
        self.tree.setColumnWidth(0, 380)
        self.tree.setColumnWidth(1, 320)
        self.tree.setColumnWidth(2, 90)
        self.tree.setAlternatingRowColors(True)
        stv.addWidget(self.tree, 1)
        root.addWidget(stat_card, 1)

        # 执行设置
        exec_card, ev = common.card("执行")
        er = QHBoxLayout()
        self.mode_copy = QRadioButton("复制（保留原文件）")
        self.mode_copy.setChecked(True)
        self.mode_move = QRadioButton("移动")
        er.addWidget(self.mode_copy)
        er.addWidget(self.mode_move)
        er.addSpacing(16)
        self.zip_cb = QCheckBox("同时打包 zip")
        er.addWidget(self.zip_cb)
        er.addStretch(1)
        self.out_edit = None
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("输出目录（留空 = 源目录旁自动生成「-归类结果」）")
        bout = QPushButton("浏览…")
        bout.clicked.connect(self._pick_out)
        self.exec_btn = QPushButton("执行归类")
        self.exec_btn.setObjectName("primaryBtn")
        self.exec_btn.setEnabled(False)
        self.exec_btn.clicked.connect(self._execute)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(240)
        self.status = QLabel("")
        self.status.setObjectName("hint")
        er.addWidget(QLabel("输出"))
        er.addWidget(self.out_edit, 1)
        er.addWidget(bout)
        er.addSpacing(8)
        er.addWidget(self.exec_btn)
        er.addWidget(self.progress)
        ev.addLayout(er)
        srow = QHBoxLayout()
        srow.addStretch(1)
        srow.addWidget(self.status)
        ev.addLayout(srow)
        root.addWidget(exec_card)

    # ---------------- 交互 ----------------
    def _pick_dir(self):
        p = QFileDialog.getExistingDirectory(self, "选择文件夹", self.src_edit.text() or "")
        if p:
            self.src_edit.setText(p)

    def _pick_zip(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择 zip 压缩包", self.src_edit.text() or "",
                                           "压缩包 (*.zip)")
        if p:
            self.src_edit.setText(p)

    def _pick_out(self):
        p = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if p:
            self.out_edit.setText(p)

    def _analyze(self):
        src = self.src_edit.text().strip()
        if not src or not os.path.exists(src):
            common.error(self, "请先选择存在的文件夹或 zip 文件")
            return
        self._source = src
        try:
            if src.lower().endswith(".zip"):
                plan = logic.analyze_zip(src)
            else:
                plan = logic.analyze_dir(src)
        except (ValueError, OSError) as e:
            common.error(self, f"解析失败：{e}")
            return
        except Exception as e:  # noqa: BLE001
            common.error(self, f"解析失败：{e}")
            return
        self._plan = plan
        self._render_plan()
        self.exec_btn.setEnabled(True)

    def _render_plan(self):
        plan = self._plan
        self.tree.clear()
        nodes: dict[str, QTreeWidgetItem] = {}
        for it in sorted(plan.items, key=lambda x: x.target):
            parent = None
            parts = it.target.split("/")
            if len(parts) > 1:
                key = "/".join(parts[:-1])
                if key not in nodes:
                    nodes[key] = QTreeWidgetItem(self.tree, [key, "", "", ""])
                    nodes[key].setFirstColumnSpanned(True)
                parent = nodes[key]
            note = ""
            if it.is_dup:
                note = "重名（保留最新，此份顺延改名）"
            elif UNKNOWN_DIR in it.target:
                note = "未识别"
            elif it.target.startswith(OTHER_DIR):
                note = "非 PDF"
            row = QTreeWidgetItem(parent or self.tree, [parts[-1], it.source, _human(it.size), note])
            if note:
                row.setForeground(3, Qt.gray)
        self.tree.expandAll()

        type_txt = "、".join(f"{k}×{v}" for k, v in sorted(plan.type_counts.items())) or "无"
        self.stat_label.setText(
            f"PDF {plan.pdf_count} 个（{type_txt}）｜非 PDF {plan.other_count} 个｜"
            f"重名 {plan.dup_count} 个｜未识别 {len(plan.unrecognized)} 个｜项目数 {len(plan.projects)}")

    def _execute(self):
        if not self._plan:
            return
        out = self.out_edit.text().strip() or None
        if self.mode_move.isChecked() and not self._plan.is_zip and not common.confirm(
                self, "移动确认", "移动模式会把源文件从原位置移走！\n\n确定继续吗？"):
            return
        self.exec_btn.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText("执行中…")
        self._worker = common.Worker(
            logic.execute, self._plan, self._source, out,
            self.zip_cb.isChecked(), self.mode_move.isChecked(), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, pct, msg):
        self.progress.setValue(pct)
        self.status.setText(msg)

    def _on_done(self, result):
        out_root, count = result
        self.progress.setValue(100)
        self.status.setText(f"完成：{count} 个文件 → {out_root}")
        self.exec_btn.setEnabled(True)
        if common.confirm(self, "完成", f"归类完成，共 {count} 个文件。\n{out_root}\n\n是否打开输出目录？"):
            os.startfile(out_root)

    def _on_failed(self, msg):
        self.exec_btn.setEnabled(True)
        self.status.setText("失败")
        common.error(self, msg)
