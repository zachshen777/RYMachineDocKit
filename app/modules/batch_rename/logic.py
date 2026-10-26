"""批量重命名核心逻辑：扫描、规则引擎、冲突检测、执行与撤销。"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime

UNDO_FILE = ".rename_undo.json"
INVALID_CHARS = set('\\/:*?"<>|')


@dataclass
class RenameItem:
    path: str
    name: str          # 当前名（含扩展名；目录无扩展概念但保留原文）
    is_dir: bool
    mtime: float = 0.0
    new_name: str = ""
    status: str = ""   # ok / conflict / skip


@dataclass
class Rule:
    type: str          # replace / add / number / case / date
    params: dict = field(default_factory=dict)


def scan(source: str, include_files=True, include_dirs=True, recursive=False) -> list[RenameItem]:
    """扫描 source 下的直接子项（recursive 时含子层）。"""
    items: list[RenameItem] = []
    if recursive:
        for root, dirs, files in os.walk(source):
            for d in dirs:
                if include_dirs:
                    full = os.path.join(root, d)
                    items.append(RenameItem(full, d, True, os.path.getmtime(full)))
            for f in files:
                if include_files:
                    full = os.path.join(root, f)
                    items.append(RenameItem(full, f, False, os.path.getmtime(full)))
        # 深度优先自底向上重命名更安全：先改深层，避免父目录改名后路径失效
        items.sort(key=lambda it: it.path.count(os.sep), reverse=True)
    else:
        try:
            entries = os.listdir(source)
        except OSError as e:
            raise ValueError(f"无法读取目录：{e}")
        for name in sorted(entries):
            full = os.path.join(source, name)
            if os.path.isdir(full):
                if include_dirs:
                    items.append(RenameItem(full, name, True, os.path.getmtime(full)))
            else:
                if include_files:
                    items.append(RenameItem(full, name, False, os.path.getmtime(full)))
    return items


def _split(name: str) -> tuple[str, str]:
    if "." in name[1:]:
        stem, ext = os.path.splitext(name)
        return stem, ext
    return name, ""


def apply_rule(name: str, rule: Rule, seq: int, mtime: float, is_dir: bool) -> str:
    stem, ext = ("", "") if is_dir else _split(name)
    whole_stem = stem if not is_dir else name
    t = rule.type
    p = rule.params
    if t == "replace":
        find = p.get("find", "")
        rep = p.get("replace", "")
        use_regex = p.get("regex", False)
        target = p.get("target", "name")  # name / stem / ext
        if use_regex:
            def rx(s):
                try:
                    return re.sub(find, rep, s)
                except re.error:
                    return s
            if target == "ext":
                ext = rx(ext)
            elif target == "stem":
                whole_stem = rx(whole_stem)
            else:
                whole_stem = rx(whole_stem)
                ext = rx(ext)
        else:
            if target == "ext":
                ext = ext.replace(find, rep)
            elif target == "stem":
                whole_stem = whole_stem.replace(find, rep)
            else:
                whole_stem = whole_stem.replace(find, rep)
                ext = ext.replace(find, rep)
    elif t == "add":
        prefix = p.get("prefix", "")
        suffix = p.get("suffix", "")
        whole_stem = prefix + whole_stem + suffix
    elif t == "number":
        pad = int(p.get("pad", 3))
        start = int(p.get("start", 1))
        sep = p.get("sep", "_")
        pos = p.get("pos", "suffix")  # prefix / suffix
        num = str(start + seq).zfill(pad)
        if pos == "prefix":
            whole_stem = num + sep + whole_stem
        else:
            whole_stem = whole_stem + sep + num
    elif t == "case":
        mode = p.get("mode", "upper")
        target = p.get("target", "stem")
        if target == "ext":
            ext = ext.upper() if mode == "upper" else ext.lower()
        else:
            whole_stem = whole_stem.upper() if mode == "upper" else whole_stem.lower()
    elif t == "date":
        fmt = p.get("fmt", "%Y%m%d")
        pos = p.get("pos", "suffix")
        sep = p.get("sep", "_")
        stamp = datetime.fromtimestamp(mtime).strftime(fmt)
        if pos == "prefix":
            whole_stem = stamp + sep + whole_stem
        else:
            whole_stem = whole_stem + sep + stamp
    return (whole_stem + ext) if not is_dir else whole_stem


def preview(items: list[RenameItem], rules: list[Rule]) -> list[RenameItem]:
    """按规则序列计算新名，并做批内冲突检测。"""
    seq = 0
    seen: dict[str, int] = {}
    for it in items:
        new = it.name
        for r in rules:
            new = apply_rule(new, r, seq, it.mtime, it.is_dir)
        new = "".join(("_" if ch in INVALID_CHARS else ch) for ch in new) or it.name
        it.new_name = new
        if new == it.name:
            it.status = "skip"
        elif new in seen:
            it.status = "conflict"
        else:
            seen[new] = 1
            it.status = "ok"
        seq += 1
    return items


def execute(items: list[RenameItem], undo_dir: str | None = None) -> tuple[int, list[str]]:
    """执行重命名，返回 (成功数, 错误列表)。记录撤销文件。"""
    done: list[tuple[str, str]] = []
    errors: list[str] = []
    for it in items:
        if it.status in ("skip", "conflict") or not it.new_name or it.new_name == it.name:
            continue
        dest = os.path.join(os.path.dirname(it.path), it.new_name)
        if os.path.exists(dest):
            errors.append(f"目标已存在，跳过：{it.new_name}")
            continue
        try:
            os.rename(it.path, dest)
            done.append((dest, it.path))
        except OSError as e:
            errors.append(f"{it.name} → {it.new_name}：{e}")
    if done and undo_dir is not None:
        undo_path = os.path.join(undo_dir, UNDO_FILE)
        history = []
        if os.path.exists(undo_path):
            try:
                with open(undo_path, encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:  # noqa: BLE001
                history = []
        history.append({"time": datetime.now().isoformat(timespec="seconds"),
                        "ops": [{"now": a, "old": b} for a, b in done]})
        with open(undo_path, "w", encoding="utf-8") as f:
            json.dump(history[-20:], f, ensure_ascii=False, indent=1)
    return len(done), errors


def undo_last(undo_dir: str) -> tuple[int, str]:
    undo_path = os.path.join(undo_dir, UNDO_FILE)
    if not os.path.exists(undo_path):
        return 0, "没有可撤销的重命名记录"
    with open(undo_path, encoding="utf-8") as f:
        history = json.load(f)
    if not history:
        return 0, "没有可撤销的重命名记录"
    last = history.pop()
    n = 0
    for op in last["ops"]:
        if os.path.exists(op["now"]):
            try:
                os.rename(op["now"], op["old"])
                n += 1
            except OSError:
                pass
    with open(undo_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=1)
    return n, f"已撤销 {n} 项"
