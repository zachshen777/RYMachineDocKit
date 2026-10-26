"""文件归类核心逻辑（移植自套料助手 FileClassifyService 的归类口径）。

归类规则：
- 仅 PDF 参与识别：文件名形如 CHB2059HW01CM01.pdf → 项目编号=CHB2059（第一层），
  仓号字母 M/F/Q/T…（第二层）；兼容无分段号/无 H 的写法与「字母+数字」兜底。
- 同一目标目录内重名 → 按修改时间保留最新一份，其余移入 项目/_重名/（加 _1、_2 后缀）。
- 无法识别的 PDF → 项目/_未识别/（项目都取不到时进 _未识别/）。
- 非 PDF → 其他文件/ 下保留原层级。
来源支持文件夹或 zip 压缩包；执行时复制生成结果目录（可选同时打 zip 包），不动原文件。
"""
from __future__ import annotations

import os
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime

DUP_DIR = "_重名"
UNKNOWN_DIR = "_未识别"
OTHER_DIR = "其他文件"

STRUCTURED = re.compile(r"^([A-Za-z]+\d+)(H?)([A-Z]\d+[CP])?([A-Z])(\d+)(.*)$")
LOOSE_PROJECT = re.compile(r"^([A-Za-z]+\d+)")
LOOSE_TYPE = re.compile(r"([A-Za-z])(\d+)(?:-[A-Za-z0-9\u4e00-\u9fa5]+)*$")

JUNK_DIRS = {"__MACOSX"}


@dataclass
class PlanItem:
    source: str        # 来源内相对路径（/ 分隔）
    target: str        # 目标相对路径
    project: str | None
    ftype: str | None
    size: int
    mtime: float
    is_dup: bool = False


@dataclass
class Plan:
    items: list[PlanItem] = field(default_factory=list)
    unrecognized: list[str] = field(default_factory=list)
    projects: set = field(default_factory=set)
    type_counts: dict = field(default_factory=dict)
    pdf_count: int = 0
    other_count: int = 0
    dup_count: int = 0
    is_zip: bool = False


def _is_junk(path: str) -> bool:
    return any(part in JUNK_DIRS for part in path.split("/")) or os.path.basename(path).startswith("._")


def _parse_name(base: str):
    """解析 PDF 文件名（不含扩展名）→ (project, type) 或 (None, None)。"""
    m = STRUCTURED.match(base)
    if m:
        return m.group(1), m.group(4)
    p = LOOSE_PROJECT.match(base)
    if p:
        t = LOOSE_TYPE.search(base)
        return p.group(1), (t.group(1) if t else None)
    return None, None


def _common_root_depth(names: list[str]) -> int:
    """所有条目共享的第一层目录数（压缩包常自带一层工程号目录，剥掉）。"""
    parts = [n.split("/") for n in names]
    if not parts:
        return 0
    depth = 0
    first = parts[0]
    while depth < len(first) - 1:
        seg = first[depth]
        if all(len(p) > depth + 1 and p[depth] == seg for p in parts):
            depth += 1
        else:
            break
    return depth


def analyze_zip(zip_path: str) -> Plan:
    plan = Plan(is_zip=True)
    with zipfile.ZipFile(zip_path) as zf:
        entries = [(i.filename.replace("\\", "/"), i.file_size, i.date_time) for i in zf.infolist()
                   if not i.is_dir() and not _is_junk(i.filename)]
    if not entries:
        raise ValueError("压缩包里没有可识别的文件（可能只是空目录）")
    depth = _common_root_depth([n for n, _s, _t in entries])
    _build_plan(plan, entries,
                rel=lambda n, d=depth: "/".join(n.split("/")[d:]),
                mtime=lambda t: datetime(*t).timestamp())
    return plan


def analyze_dir(dir_path: str) -> Plan:
    entries = []
    for root, _dirs, files in os.walk(dir_path):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, dir_path).replace("\\", "/")
            if _is_junk(rel):
                continue
            entries.append((rel, os.path.getsize(full), os.path.getmtime(full)))
    if not entries:
        raise ValueError("文件夹里没有可识别的文件")
    depth = _common_root_depth([n for n, _s, _t in entries])
    plan = Plan()
    _build_plan(plan, entries,
                rel=lambda n, d=depth: "/".join(n.split("/")[d:]),
                mtime=lambda t: t)
    return plan


def _build_plan(plan: Plan, entries, rel, mtime):
    items = []
    for name, size, t in entries:
        r = rel(name)
        if not r:
            r = os.path.basename(name)
        mt = mtime(t)
        if not r.lower().endswith(".pdf"):
            plan.other_count += 1
            items.append(PlanItem(name, f"{OTHER_DIR}/{r}", None, None, size, mt))
            continue
        plan.pdf_count += 1
        base = os.path.basename(r)
        stem = os.path.splitext(base)[0]
        project, ftype = _parse_name(stem)
        if project is None:
            items.append(PlanItem(name, f"{UNKNOWN_DIR}/{base}", None, None, size, mt))
            plan.unrecognized.append(r)
            continue
        if ftype is None:
            items.append(PlanItem(name, f"{project}/{UNKNOWN_DIR}/{base}", project, None, size, mt))
            plan.unrecognized.append(r)
            continue
        plan.projects.add(project)
        plan.type_counts[ftype] = plan.type_counts.get(ftype, 0) + 1
        items.append(PlanItem(name, f"{project}/{ftype}/{base}", project, ftype, size, mt))
    # 同目标目录重名 → 新的保留，其余进 _重名
    by_target: dict[str, list[PlanItem]] = {}
    for it in items:
        if it.project:
            by_target.setdefault(it.target, []).append(it)
    for group in by_target.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda it: (-it.mtime, it.source))
        for k, it in enumerate(group[1:], 1):
            stem, ext = os.path.splitext(it.target)
            it.target = f"{stem}_{k}{ext}"
            it.is_dup = True
            plan.dup_count += 1
    plan.items.extend(items)


# ==================== 执行 ====================

def execute(plan: Plan, source: str, out_dir: str | None = None,
            make_zip: bool = False, move: bool = False,
            worker=None) -> tuple[str, int]:
    """执行归类。zip 来源解压抽取；文件夹来源复制/移动。返回 (输出路径, 文件数)。"""
    if plan.is_zip:
        out_root = out_dir or os.path.join(
            os.path.dirname(source), os.path.splitext(os.path.basename(source))[0] + "-归类结果")
        os.makedirs(out_root, exist_ok=True)
        count = 0
        with zipfile.ZipFile(source) as zf:
            for i, it in enumerate(plan.items, 1):
                if worker:
                    worker.progress.emit(int(i / len(plan.items) * 100), f"归类 {it.target}")
                dest = os.path.join(out_root, it.target.replace("/", os.sep))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(it.source) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_root = out_dir or os.path.join(os.path.dirname(source), f"{os.path.basename(source)}-归类结果-{stamp}")
        os.makedirs(out_root, exist_ok=True)
        count = 0
        base = os.path.abspath(source)
        for i, it in enumerate(plan.items, 1):
            if worker:
                worker.progress.emit(int(i / len(plan.items) * 100), f"归类 {it.target}")
            src = os.path.join(base, it.source.replace("/", os.sep))
            if not os.path.exists(src):
                # 根目录剥过层时，尝试直接按相对路径找
                src = os.path.join(base, os.path.basename(it.source))
            dest = os.path.join(out_root, it.target.replace("/", os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if move:
                shutil.move(src, dest)
            else:
                shutil.copy2(src, dest)
            count += 1

    if make_zip:
        zip_path = out_root + ".zip"
        if os.path.exists(zip_path):
            os.remove(zip_path)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(out_root):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, out_root)
                    zf.write(full, rel)
    return out_root, count
