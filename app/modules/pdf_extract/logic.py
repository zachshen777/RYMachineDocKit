"""PDF 关键字提取核心逻辑（PyMuPDF 实现）。

口径与套料助手一致：定位关键字文本框后，向「右」取同一行最近的连续文字，
或向「下」取正下方最近的文字作为值。全部基于文本层，无 OCR 依赖。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ExtractRow:
    file: str
    page: int          # 1 起
    keyword: str
    value: str


@dataclass
class ExtractResult:
    rows: list[ExtractRow] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # 无法打开 / 无文本层的文件
    file_count: int = 0
    page_count: int = 0


def collect_pdfs(source: str, recursive: bool = True) -> list[str]:
    """source 可以是单个 pdf 或一个文件夹。"""
    if os.path.isfile(source):
        return [source]
    pdfs: list[str] = []
    if recursive:
        for root, _dirs, files in os.walk(source):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdfs.append(os.path.join(root, f))
    else:
        for f in os.listdir(source):
            p = os.path.join(source, f)
            if os.path.isfile(p) and f.lower().endswith(".pdf"):
                pdfs.append(p)
    return sorted(pdfs)


def _words_of(page) -> list[tuple[float, float, float, float, str]]:
    return [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]


def _pick_right(words, krect, tol: float) -> str:
    """同一行（垂直中心差 ≤ tol）关键字右侧最近的连续文字。"""
    ky = (krect.y0 + krect.y1) / 2
    cand = [w for w in words
            if w[2] > krect.x1 and abs((w[1] + w[3]) / 2 - ky) <= max(tol, (krect.y1 - krect.y0) / 2)]
    if not cand:
        return ""
    cand.sort(key=lambda w: w[0])
    # 从最近的一个开始，拼接间距不大的连续词
    x = cand[0][0]
    parts = [cand[0][4]]
    for w in cand[1:]:
        if w[0] - x <= max(12.0, (w[3] - w[1]) * 1.2):
            parts.append(w[4])
            x = w[2]
        else:
            break
    return "".join(parts) if _cjk(parts) else " ".join(parts)


def _cjk(parts: list[str]) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for p in parts for ch in p)


def _pick_below(words, krect, tol: float) -> str:
    """正下方（水平中心差 ≤ tol）最近的文字。"""
    kx = (krect.x0 + krect.x1) / 2
    cand = [w for w in words if w[1] >= krect.y1 - 1 and abs((w[0] + w[2]) / 2 - kx) <= tol]
    if not cand:
        return ""
    cand.sort(key=lambda w: w[1])
    y = cand[0][1]
    parts = [cand[0][4]]
    for w in cand[1:]:
        if w[1] - y <= (w[3] - w[1]) * 1.1 + 2:
            parts.append(w[4])
            y = w[3]
        else:
            break
    return "".join(parts) if _cjk(parts) else " ".join(parts)


def extract_pdf(path: str, keywords: list[str], direction: str = "right",
                tolerance: float = 6.0) -> tuple[list[ExtractRow], int, bool]:
    """返回 (行列表, 页数, 是否有文本层)。"""
    import fitz  # PyMuPDF

    rows: list[ExtractRow] = []
    base = os.path.basename(path)
    with fitz.open(path) as doc:
        has_text = False
        for pno, page in enumerate(doc, start=1):
            words = _words_of(page)
            if words:
                has_text = True
            for kw in keywords:
                if not kw:
                    continue
                for rect in page.search_for(kw, quads=False):
                    value = (_pick_right if direction == "right" else _pick_below)(words, rect, tolerance)
                    rows.append(ExtractRow(base, pno, kw, value))
        return rows, doc.page_count, has_text


def run_extract(worker, sources: list[str], keywords: list[str], direction: str,
                tolerance: float, recursive: bool = True) -> ExtractResult:
    """Worker 线程入口。"""
    result = ExtractResult()
    pdfs: list[str] = []
    for s in sources:
        pdfs.extend(collect_pdfs(s, recursive))
    if not pdfs:
        raise ValueError("没有找到 PDF 文件")
    total = len(pdfs)
    for i, p in enumerate(pdfs, 1):
        worker.progress.emit(int(i / total * 100), f"正在提取 {os.path.basename(p)}（{i}/{total}）")
        try:
            rows, pages, _has_text = extract_pdf(p, keywords, direction, tolerance)
            result.rows.extend(rows)
            result.page_count += pages
            result.file_count += 1
        except Exception as e:  # noqa: BLE001
            result.skipped.append(f"{os.path.basename(p)}：{e}")
    return result


def export_xlsx(rows: list[ExtractRow], out_path: str) -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "提取结果"
    heads = ["文件名", "页码", "关键字", "提取值"]
    head_fill = PatternFill("solid", fgColor="3B82F6")
    for c, h in enumerate(heads, 1):
        cell = ws.cell(1, c, h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for r, row in enumerate(rows, 2):
        ws.cell(r, 1, row.file)
        ws.cell(r, 2, row.page)
        ws.cell(r, 3, row.keyword)
        ws.cell(r, 4, row.value)
    for c, w in enumerate((28, 8, 18, 44), 1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "A2"
    wb.save(out_path)
    return out_path
