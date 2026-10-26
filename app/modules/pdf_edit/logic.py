"""PDF 编辑核心逻辑：渲染预览 + 遮罩重写（PyMuPDF）。

交互口径与套料助手一致：框选矩形以「相对页面尺寸的比例」记录（0~1，左上原点），
应用时按每页实际尺寸换算，实现「一次框选、所有页同位置生效」。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simkai.ttf",
    r"C:\Windows\Fonts\Deng.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
]

RENDER_DPI = 150          # 预览渲染 DPI
MASK_PADDING = 1.5        # 遮罩外扩（pt）
FONT_RATIO = 0.66         # 字号 ≈ 框高 × 系数


@dataclass
class EditSpec:
    rx: float; ry: float; rw: float; rh: float   # 相对比例 0~1，左上原点
    text: str
    font_size: float | None = None               # None = 按框高自动
    align: str = "center"                        # left / center
    mask_color: str = "#ffffff"
    text_color: str = "#000000"


def find_font() -> str:
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return ""


def page_infos(path: str) -> list[dict]:
    import fitz
    infos = []
    with fitz.open(path) as doc:
        for page in doc:
            r = page.rect
            infos.append({"width": r.width, "height": r.height})
    return infos


def render_page_png(path: str, page_no: int, dpi: int = RENDER_DPI) -> bytes:
    """渲染指定页（1 起）为 PNG 字节。"""
    import fitz
    with fitz.open(path) as doc:
        if page_no < 1 or page_no > doc.page_count:
            raise ValueError(f"页码超出范围（1~{doc.page_count}）")
        page = doc[page_no - 1]
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
        return pix.tobytes("png")


def parse_pages(spec: str, page_count: int) -> list[int]:
    """解析页码范围：'all' / '1,3,5-8' → 1 起页码列表。"""
    spec = (spec or "all").strip().lower()
    if spec in ("", "all", "全部"):
        return list(range(1, page_count + 1))
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            pages.update(range(int(a), int(b) + 1))
        else:
            pages.add(int(part))
    bad = [p for p in pages if p < 1 or p > page_count]
    if bad:
        raise ValueError(f"页码超出范围：{sorted(bad)}（共 {page_count} 页）")
    return sorted(pages)


def apply_edits(pdf_path: str, edits: list[EditSpec], pages_spec: str,
                out_path: str | None = None) -> tuple[str, int]:
    """执行遮罩 + 重写，返回 (输出路径, 处理页数)。"""
    import fitz

    if not edits:
        raise ValueError("请先在预览图上框选至少一个区域")
    font_path = find_font()

    if out_path is None:
        base, ext = os.path.splitext(pdf_path)
        out_path = base + "-已编辑" + ext

    doc = fitz.open(pdf_path)
    try:
        targets = parse_pages(pages_spec, doc.page_count)
        for pno in targets:
            page = doc[pno - 1]
            pw, ph = page.rect.width, page.rect.height
            for e in edits:
                x0, y0 = e.rx * pw, e.ry * ph
                x1, y1 = x0 + e.rw * pw, y0 + e.rh * ph
                rect = fitz.Rect(x0, y0, x1, y1)
                # 遮罩：redaction 填充，外扩吃掉框选误差
                mask = fitz.Rect(x0 - MASK_PADDING, y0 - MASK_PADDING,
                                 x1 + MASK_PADDING, y1 + MASK_PADDING) & page.rect
                page.add_redact_annot(mask, fill=fitz.utils.getColor(e.mask_color.lstrip("#")))
            page.apply_redactions()
            for e in edits:
                x0, y0 = e.rx * pw, e.ry * ph
                x1, y1 = x0 + e.rw * pw, y0 + e.rh * ph
                rect = fitz.Rect(x0, y0, x1, y1)
                if not e.text:
                    continue
                size = e.font_size if e.font_size else max(4.0, rect.height * FONT_RATIO)
                align = fitz.TEXT_ALIGN_CENTER if e.align == "center" else fitz.TEXT_ALIGN_LEFT
                color = fitz.utils.getColor(e.text_color.lstrip("#"))
                y_mid = (rect.y0 + rect.y1) / 2
                # 用行高约等于字号的方式估算单行所需的框，垂直居中
                box = fitz.Rect(rect.x0, y_mid - size * 0.75, rect.x1, y_mid + size * 0.85)
                if font_path:
                    page.insert_textbox(box, e.text, fontsize=size, fontname="zh",
                                        fontfile=font_path, color=color, align=align)
                else:
                    page.insert_textbox(box, e.text, fontsize=size, color=color, align=align)
        doc.save(out_path, garbage=3, deflate=True)
    finally:
        doc.close()
    return out_path, len(targets)
