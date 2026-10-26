# -*- coding: utf-8 -*-
"""各模块核心逻辑自测（不依赖 GUI 显示）。"""
import os
import shutil
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, ".."))

ok = 0
fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name} {extra}")


tmp = tempfile.mkdtemp(prefix="rydoc-test-")

# ---------- 造测试 PDF ----------
import fitz

pdf_path = os.path.join(tmp, "sample.pdf")
doc = fitz.open()
page = doc.new_page(width=595, height=842)
page.insert_text((72, 100), "使用订单", fontsize=14)
page.insert_text((160, 100), "H1947-001", fontsize=14)
page.insert_text((72, 140), "规格", fontsize=14)
page.insert_text((72, 160), "AH36-20x2000x8000", fontsize=14)
doc.save(pdf_path)
doc.close()

# ---------- PDF 提取 ----------
from app.modules.pdf_extract import logic as ex

rows, pages, has_text = ex.extract_pdf(pdf_path, ["使用订单", "规格"], "right", 6)
check("提取-向右", any(r.keyword == "使用订单" and r.value == "H1947-001" for r in rows),
      str([(r.keyword, r.value) for r in rows]))
rows2, _p, _t = ex.extract_pdf(pdf_path, ["规格"], "below", 6)
check("提取-向下", any(r.value == "AH36-20x2000x8000" for r in rows2),
      str([(r.keyword, r.value) for r in rows2]))
xlsx = os.path.join(tmp, "out.xlsx")
ex.export_xlsx(rows + rows2, xlsx)
check("导出xlsx", os.path.exists(xlsx) and os.path.getsize(xlsx) > 1000)

# ---------- PDF 编辑 ----------
from app.modules.pdf_edit import logic as ed

edits = [ed.EditSpec(rx=0.2, ry=0.11, rw=0.3, rh=0.03, text="H1948-999")]
out_pdf, n = ed.apply_edits(pdf_path, edits, "all")
check("编辑-应用", n == 1 and os.path.exists(out_pdf))
d2 = fitz.open(out_pdf)
txt = d2[0].get_text()
d2.close()
check("编辑-新文字写入", "H1948-999" in txt, txt[:200])
check("编辑-旧文字遮住", "H1947-001" not in txt, txt[:200])

# ---------- 文件归类 ----------
from app.modules.file_classify import logic as fc

src_dir = os.path.join(tmp, "归源源")
names = [
    "CHB2059HW01CM01.pdf", "CHB2059HW01CF02.pdf",
    "CHB2059HW07PQ01.pdf", "CHB2059HW07CQ01.pdf",   # 同目标重名
    "乱七八糟.pdf",                                   # 未识别
    "readme.txt",                                     # 非 PDF
]
nested = os.path.join(src_dir, "11400")
os.makedirs(nested, exist_ok=True)
for n in names:
    with open(os.path.join(nested, n), "w", encoding="utf-8") as f:
        f.write("x")
plan = fc.analyze_dir(src_dir)
check("归类-解析数量", plan.pdf_count == 5 and plan.other_count == 1, f"{plan.pdf_count}/{plan.other_count}")
check("归类-项目识别", "CHB2059" in plan.projects)
check("归类-重名识别", plan.dup_count == 1, str(plan.dup_count))
check("归类-未识别", len(plan.unrecognized) == 1)
out_dir, count = fc.execute(plan, src_dir, make_zip=False)
t = sorted(os.path.relpath(os.path.join(r, f), out_dir).replace("\\", "/")
           for r, _d, fs in os.walk(out_dir) for f in fs)
check("归类-两级目录", "CHB2059/M/CHB2059HW01CM01.pdf" in t, str(t))
check("归类-重名目录", any("_重名/" in p for p in t), str(t))
check("归类-其他文件", any(p.startswith("其他文件/") for p in t), str(t))
check("归类-未识别目录", any("_未识别/" in p for p in t), str(t))
check("归类-原文件未动", os.path.exists(os.path.join(nested, names[0])))

# zip 来源
zip_src = os.path.join(tmp, "src.zip")
with __import__("zipfile").ZipFile(zip_src, "w") as zf:
    zf.writestr("11400/CHB2059HW01CM01.pdf", "pdf-data")
plan2 = fc.analyze_zip(zip_src)
out2, c2 = fc.execute(plan2, zip_src)
check("归类-zip来源", c2 == 1 and os.path.exists(os.path.join(out2, "CHB2059", "M", "CHB2059HW01CM01.pdf")))

# ---------- 批量重命名 ----------
from app.modules.batch_rename import logic as br

rn = os.path.join(tmp, "rename")
os.makedirs(rn, exist_ok=True)
for n in ["报告-A-v1.txt", "报告-A-v2.txt", "IMG_1.jpg"]:
    with open(os.path.join(rn, n), "w") as f:
        f.write("x")
items = br.scan(rn)
rules = [
    br.Rule("replace", {"find": "报告", "replace": "报表"}),
    br.Rule("add", {"prefix": "2026_", "suffix": ""}),
    br.Rule("number", {"pos": "suffix", "start": 1, "pad": 3, "sep": "_"}),
]
br.preview(items, rules)
names_new = sorted(it.new_name for it in items)
check("重命名-规则链", "2026_报表-A-v1_001.txt" in names_new, str(names_new))
n, errs = br.execute(items, rn)
check("重命名-执行", n == 3 and not errs, f"{n} {errs}")
files_after = sorted(os.listdir(rn))
check("重命名-落盘", "2026_报表-A-v2_002.txt" in files_after, str(files_after))
un, msg = br.undo_last(rn)
files_undo = sorted(os.listdir(rn))
check("重命名-撤销", un == 3 and "报告-A-v1.txt" in files_undo, f"{un} {files_undo}")

# 大小写 / 日期 / 正则
r3 = br.Rule("case", {"mode": "upper", "target": "ext"})
from app.modules.batch_rename.logic import apply_rule
check("重命名-扩展名大写", apply_rule("a.jpg", r3, 0, 0, False) == "a.JPG")
r4 = br.Rule("date", {"pos": "suffix", "fmt": "%Y%m%d", "sep": "_"})
check("重命名-日期", apply_rule("a.txt", r4, 0, 1750000000, False) == "a.txt_20250615",
      apply_rule("a.txt", r4, 0, 1750000000, False))
r5 = br.Rule("replace", {"find": r"v\d+", "replace": "V", "regex": True, "target": "stem"})
check("重命名-正则", apply_rule("文件-v12.txt", r5, 0, 0, False) == "文件-V.txt")

# 冲突检测
items_c = [logic_item for logic_item in []]
import copy
it1 = br.RenameItem(os.path.join(rn, "a.txt"), "a.txt", False)
it2 = br.RenameItem(os.path.join(rn, "b.txt"), "b.txt", False)
br.preview([it1, it2], [br.Rule("replace", {"find": "", "replace": "", "target": "name"}),
                       br.Rule("add", {"prefix": "same_", "suffix": ""})])
check("重命名-批内冲突", it1.status == "conflict" and it2.status == "conflict",
      f"{it1.status}/{it2.status}")

# ---------- UI 模块导入 ----------
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from app.ui.main_window import MainWindow
w = MainWindow()
check("UI-主窗口构建", w.stack.count() == 4)

print()
print(f"结果：{ok} 通过 / {fail} 失败")
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(1 if fail else 0)
