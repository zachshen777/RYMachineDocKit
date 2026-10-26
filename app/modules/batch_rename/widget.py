"""批量重命名页面：扫描 + 规则列表 + 预览 + 执行 / 撤销。"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...ui import common
from ...ui import theme
from . import logic

RULE_NAMES = {
    "replace": "查找替换",
    "add": "添加前后缀",
    "number": "添加序号",
    "case": "大小写",
    "date": "插入日期",
}


class BatchRenamePage(QWidget):
    def __init__(self):
        super().__init__()
        self._items: list[logic.RenameItem] = []
        self._rules: list[logic.Rule] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        root.addWidget(common.page_header(
            "批量重命名",
            "选择文件夹后按规则批量重命名文件 / 文件夹：查找替换（支持正则）、前后缀、序号、大小写、按修改时间插入日期；预览确认后执行，支持一键撤销最近一次。"))

        # 来源
        src_card, sv = common.card("来源")
        row = QHBoxLayout()
        self.src_edit = None
        from PySide6.QtWidgets import QLineEdit
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("选择要处理的文件夹")
        b = QPushButton("浏览…")
        b.clicked.connect(self._pick)
        self.scan_btn = QPushButton("扫描")
        self.scan_btn.setObjectName("primaryBtn")
        self.scan_btn.clicked.connect(self._scan)
        row.addWidget(self.src_edit, 1)
        row.addWidget(b)
        row.addWidget(self.scan_btn)
        sv.addLayout(row)
        opts = QHBoxLayout()
        self.files_cb = QCheckBox("文件")
        self.files_cb.setChecked(True)
        self.dirs_cb = QCheckBox("文件夹")
        self.dirs_cb.setChecked(True)
        self.rec_cb = QCheckBox("包含子文件夹（先深层后浅层）")
        opts.addWidget(self.files_cb)
        opts.addWidget(self.dirs_cb)
        opts.addWidget(self.rec_cb)
        opts.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("hint")
        opts.addWidget(self.count_label)
        sv.addLayout(opts)
        root.addWidget(src_card)

        # 规则
        rule_card, rv = common.card("规则（自上而下依次生效）")
        self.rule_list = QListWidget()
        self.rule_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.rule_list.customContextMenuRequested.connect(self._rule_menu)
        self.rule_list.setFixedHeight(110)
        rv.addWidget(self.rule_list)
        add_row = QHBoxLayout()
        self.rule_type = QComboBox()
        for k, v in RULE_NAMES.items():
            self.rule_type.addItem(v, k)
        add_btn = QPushButton("＋ 添加规则")
        add_btn.clicked.connect(self._add_rule)
        undo_btn = QPushButton("撤销最近一次")
        undo_btn.setObjectName("dangerBtn")
        undo_btn.clicked.connect(self._undo)
        add_row.addWidget(self.rule_type)
        add_row.addWidget(add_btn)
        add_row.addStretch(1)
        add_row.addWidget(undo_btn)
        rv.addLayout(add_row)
        root.addWidget(rule_card)

        # 预览
        prev_card, pv = common.card("预览")
        btn_row = QHBoxLayout()
        self.rename_btn = QPushButton("执行重命名")
        self.rename_btn.setObjectName("primaryBtn")
        self.rename_btn.setEnabled(False)
        self.rename_btn.clicked.connect(self._apply)
        self.status = QLabel("扫描后自动预览")
        self.status.setObjectName("hint")
        btn_row.addWidget(self.rename_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.status)
        pv.addLayout(btn_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["原名称", "新名称"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 380)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        pv.addWidget(self.table, 1)
        root.addWidget(prev_card, 1)

    # ---------------- 交互 ----------------
    def _pick(self):
        p = QFileDialog.getExistingDirectory(self, "选择文件夹", self.src_edit.text() or "")
        if p:
            self.src_edit.setText(p)

    def _scan(self):
        src = self.src_edit.text().strip()
        if not src or not os.path.isdir(src):
            common.error(self, "请先选择存在的文件夹")
            return
        if not (self.files_cb.isChecked() or self.dirs_cb.isChecked()):
            common.error(self, "至少勾选「文件」或「文件夹」一项")
            return
        try:
            self._items = logic.scan(src, self.files_cb.isChecked(),
                                     self.dirs_cb.isChecked(), self.rec_cb.isChecked())
        except ValueError as e:
            common.error(self, str(e))
            return
        self.count_label.setText(f"共 {len(self._items)} 项")
        self._refresh_preview()

    def _add_rule(self):
        t = self.rule_type.currentData()
        r = logic.Rule(t, {})
        if not self._edit_rule(r, add=True):
            return
        self._rules.append(r)
        self._refresh_rules()
        self._refresh_preview()

    def _edit_rule(self, rule: logic.Rule, add: bool) -> bool:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout
        dlg = QDialog(self)
        dlg.setWindowTitle(("添加规则：" if add else "编辑规则：") + RULE_NAMES[rule.type])
        dlg.setMinimumWidth(380)
        form = QFormLayout(dlg)
        form.setSpacing(10)
        p = rule.params

        def line(key, placeholder=""):
            e = QLineEdit(p.get(key, ""))
            e.setPlaceholderText(placeholder)
            form.addRow({"find": "查找内容", "replace": "替换为", "prefix": "前缀",
                         "suffix": "后缀", "sep": "连接符", "fmt": "日期格式（如 %Y%m%d）"}.get(key, key), e)
            return e

        widgets: dict = {}
        if rule.type == "replace":
            widgets["find"] = line("find", "要查找的文字")
            widgets["replace"] = line("replace", "替换为（留空 = 删除）")
            tgt = QComboBox()
            tgt.addItems(["整个文件名", "仅主名", "仅扩展名"])
            tgt.setCurrentIndex(p.get("target_i", 0))
            form.addRow("作用范围", tgt)
            rgx = QCheckBox("使用正则表达式")
            rgx.setChecked(p.get("regex", False))
            form.addRow("", rgx)
            widgets["_target"] = tgt
            widgets["_regex"] = rgx
        elif rule.type == "add":
            widgets["prefix"] = line("prefix")
            widgets["suffix"] = line("suffix")
        elif rule.type == "number":
            pos = QComboBox()
            pos.addItems(["后缀（名称_001）", "前缀（001_名称）"])
            pos.setCurrentIndex(1 if p.get("pos") == "prefix" else 0)
            start = QSpinBox()
            start.setRange(0, 99999)
            start.setValue(int(p.get("start", 1)))
            pad = QSpinBox()
            pad.setRange(1, 8)
            pad.setValue(int(p.get("pad", 3)))
            widgets["sep"] = line("sep", "_")
            form.addRow("位置", pos)
            form.addRow("起始编号", start)
            form.addRow("编号位数", pad)
            widgets["_pos"] = pos
            widgets["_start"] = start
            widgets["_pad"] = pad
        elif rule.type == "case":
            mode = QComboBox()
            mode.addItems(["全部大写", "全部小写"])
            mode.setCurrentIndex(1 if p.get("mode") == "lower" else 0)
            form.addRow("转换", mode)
            widgets["_mode"] = mode
        elif rule.type == "date":
            widgets["fmt"] = line("fmt", "%Y%m%d / %Y-%m-%d 等")
            pos = QComboBox()
            pos.addItems(["后缀", "前缀"])
            pos.setCurrentIndex(1 if p.get("pos") == "prefix" else 0)
            widgets["sep"] = line("sep", "_")
            form.addRow("位置", pos)
            widgets["_pos"] = pos
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec() != QDialog.Accepted:
            return False
        for k, w in widgets.items():
            if k.startswith("_"):
                continue
            rule.params[k] = w.text()
        if rule.type == "replace":
            rule.params["target"] = ["name", "stem", "ext"][widgets["_target"].currentIndex()]
            rule.params["target_i"] = widgets["_target"].currentIndex()
            rule.params["regex"] = widgets["_regex"].isChecked()
        elif rule.type == "number":
            rule.params["pos"] = "prefix" if widgets["_pos"].currentIndex() == 1 else "suffix"
            rule.params["start"] = widgets["_start"].value()
            rule.params["pad"] = widgets["_pad"].value()
        elif rule.type == "case":
            rule.params["mode"] = "lower" if widgets["_mode"].currentIndex() == 1 else "upper"
        elif rule.type == "date":
            rule.params["pos"] = "prefix" if widgets["_pos"].currentIndex() == 1 else "suffix"
        return True

    def _refresh_rules(self):
        self.rule_list.clear()
        for i, r in enumerate(self._rules, 1):
            brief = ""
            p = r.params
            if r.type == "replace":
                brief = f"「{p.get('find','')}」→「{p.get('replace','')}」"
            elif r.type == "add":
                brief = f"前「{p.get('prefix','')}」 后「{p.get('suffix','')}」"
            elif r.type == "number":
                brief = f"{p.get('pos','suffix')} 从 {p.get('start',1)} 起 {p.get('pad',3)} 位"
            elif r.type == "case":
                brief = "转大写" if p.get("mode") == "upper" else "转小写"
            elif r.type == "date":
                brief = f"{p.get('pos','suffix')} {p.get('fmt','%Y%m%d')}"
            QListWidgetItem(f"{i}. {RULE_NAMES[r.type]}　{brief}", self.rule_list)

    def _rule_menu(self, pos):
        item = self.rule_list.itemAt(pos)
        if not item:
            return
        idx = self.rule_list.row(item)
        menu = QMenu(self)
        menu.addAction("编辑", lambda: self._edit_rule_at(idx))
        menu.addAction("上移", lambda: self._move_rule(idx, -1))
        menu.addAction("下移", lambda: self._move_rule(idx, 1))
        menu.addSeparator()
        menu.addAction("删除", lambda: self._del_rule(idx))
        menu.exec(self.rule_list.mapToGlobal(pos))

    def _edit_rule_at(self, idx):
        if self._edit_rule(self._rules[idx], add=False):
            self._refresh_rules()
            self._refresh_preview()

    def _move_rule(self, idx, d):
        j = idx + d
        if 0 <= j < len(self._rules):
            self._rules[idx], self._rules[j] = self._rules[j], self._rules[idx]
            self._refresh_rules()
            self._refresh_preview()

    def _del_rule(self, idx):
        del self._rules[idx]
        self._refresh_rules()
        self._refresh_preview()

    # ---------------- 预览 / 执行 ----------------
    def _refresh_preview(self):
        logic.preview(self._items, self._rules)
        self.table.setRowCount(0)
        n_change = 0
        for it in self._items:
            i = self.table.rowCount()
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(it.name))
            self.table.setItem(i, 1, QTableWidgetItem(it.new_name))
            color = None
            if it.status == "ok":
                color = theme.SUCCESS
                n_change += 1
            elif it.status == "conflict":
                color = theme.DANGER
            elif it.status == "skip":
                color = theme.TEXT_SUB
            if color:
                self.table.item(i, 1).setForeground(color)
        self.rename_btn.setEnabled(n_change > 0)
        self.status.setText(f"{len(self._items)} 项中 {n_change} 项将重命名（红色为批内重名冲突）")

    def _apply(self):
        changes = [it for it in self._items if it.status == "ok" and it.new_name != it.name]
        if not changes:
            return
        if not common.confirm(self, "执行确认", f"将对 {len(changes)} 项执行重命名，确定继续？"):
            return
        undo_dir = self.src_edit.text().strip()
        n, errors = logic.execute(self._items, undo_dir)
        if errors:
            common.info(self, "\n".join(errors[:10]), title=f"完成 {n} 项，{len(errors)} 项出错")
        else:
            common.info(self, f"重命名完成，共 {n} 项。", title="完成")
        self._scan()

    def _undo(self):
        undo_dir = self.src_edit.text().strip()
        if not undo_dir or not os.path.isdir(undo_dir):
            common.error(self, "请先选择文件夹")
            return
        n, msg = logic.undo_last(undo_dir)
        common.info(self, msg, title="撤销")
        self._scan()
