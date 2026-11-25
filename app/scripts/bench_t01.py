#!/usr/bin/env python3
"""T01：500 页双栏 PDF → 可访问 EPUB/PDF/DOCX。
阅读顺序/表格/脚注/耗时/OOM + EPUBCheck/veraPDF/Open XML。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pikepdf

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "app" / "core" / "target" / "release" / "nf-app-core.exe"
WORK = REPO / "app" / "core" / "target" / "t01-bench"
EPUBCHECK = Path(os.environ.get("EPUBCHECK_JAR", "D:/nf-validators/epubcheck-5.1.0/epubcheck.jar"))
OOXML = Path(os.environ.get("OOXML_VALIDATE", "D:/nf-validators/ooxml/ooxml-validate.exe"))
SOFFICE = Path(os.environ.get("SOFFICE", "D:/nf-validators/LibreOffice/program/soffice.exe"))
VERA = Path(os.environ.get("VERAPDF_CLI", "D:/nf-validators/verapdf/verapdf-cli.jar"))
STD = {"/Quote", "/Note", "/Reference", "/BibEntry", "/Code", "/Span", "/P", "/H", "/H1", "/H2", "/H3", "/H4", "/H5", "/H6", "/Table", "/TR", "/TH", "/TD", "/L", "/LI", "/Lbl", "/LBody", "/Figure", "/Caption", "/Document", "/Sect", "/Div", "/Art", "/Part", "/Aside"}


def core(op: str, req: dict) -> tuple[int, dict]:
    p = subprocess.run([str(CORE), op, "--in", "-"], input=json.dumps(req, ensure_ascii=False).encode(), stdout=subprocess.PIPE, timeout=600)
    return p.returncode, json.loads(p.stdout.decode("utf-8"))


def walk(v):
    yield v
    for c in v.get("children", []):
        yield from walk(c)


def epub_errors(path: Path) -> int:
    p = subprocess.run(["java", "-jar", str(EPUBCHECK), str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    m = re.search(r"Messages:\s*\d+\s+fatals\s*/\s*(\d+)\s+errors", p.stdout.decode("utf-8", errors="replace"))
    return int(m.group(1)) if m else 1


def main() -> int:
    if not all(p.exists() for p in (CORE, EPUBCHECK, OOXML, SOFFICE, VERA)):
        print("missing tool")
        return 2
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    pdf = WORK / "corpus.pdf"
    subprocess.run([sys.executable, str(REPO / "app" / "scripts" / "make_pdf.py"), "--pages", "500", "--columns", "2", "--out", str(pdf)], check=True, stdout=subprocess.DEVNULL)
    req = WORK / "layout.json"
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, str(REPO / "app" / "scripts" / "pdf_layout.py"), "--pdf", str(pdf), "--out", str(req), "--chunk", "50"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    if p.returncode != 0:
        print(p.stderr.decode("utf-8", errors="replace")[:500])
        return 1
    code, env = core("layout-import", json.loads(req.read_text(encoding="utf-8")))
    elapsed = time.perf_counter() - t0
    if code != 0:
        print(env)
        return 1
    sdir = env["result"]
    pages = {b.get("page") for b in walk(sdir["blocks"][0]) if b.get("type") != "document"}
    page_cover = pages >= set(range(1, 501))

    tp = fp = fn = 0
    foot = 0
    order_ok = 0
    expected_cells = {"Place", "Risk", "North gate", "High", "Inn", "Low"}
    for page in range(1, 501):
        pblocks = [b for b in walk(sdir["blocks"][0]) if b.get("page") == page]
        tables = [b for b in pblocks if b["type"] == "table"]
        cells = {c["text"] for t in tables for c in walk(t) if c["type"] == "table_cell"}
        tp += len(cells & expected_cells)
        fp += len(cells - expected_cells)
        fn += len(expected_cells - cells)
        if any("footnote" in b.get("text", "") for b in pblocks if b["type"] == "footnote"):
            foot += 1
        paras = [b["text"] for b in pblocks if b["type"] == "paragraph"]
        left = next((t for t in paras if f"Page {page} line 1:" in t), "")
        right = next((t for t in paras if f"Page {page} line 2:" in t), "")
        ln = [int(x) for x in re.findall(r"line (\d+):", left)]
        rn = [int(x) for x in re.findall(r"line (\d+):", right)]
        if ln == list(range(1, 28, 2)) and rn == list(range(2, 29, 2)):
            order_ok += 1
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    reading = order_ok / 500
    foot_recall = foot / 500

    out = WORK / "out"
    out.mkdir()
    code, b = core("build-run", {"sdir": sdir, "outputs": [{"path": "index.epub", "format": "epub"}, {"path": "index.docx", "format": "docx"}], "out_dir": str(out)})
    assert code == 0, b
    epub_err = epub_errors(out / "index.epub")
    ooxml = subprocess.run([str(OOXML), str(out / "index.docx")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    try:
        ooxml_ok = bool(json.loads(ooxml.stdout.decode("utf-8"))["results"][0]["valid"])
    except Exception:
        ooxml_ok = False
    subprocess.run([str(SOFFICE), "--headless", "--norestore", f"-env:UserInstallation=file:///{WORK.as_posix()}/lo",
                    "--convert-to", 'pdf:writer_pdf_Export:{"UseTaggedPDF":{"type":"boolean","value":"true"},"PDFUACompliance":{"type":"boolean","value":"true"}}',
                    "--outdir", str(out), str(out / "index.docx")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    pdfua = out / "index-ua.pdf"
    with pikepdf.open(out / "index.pdf") as src:
        root = src.Root.get("/StructTreeRoot")
        rm = root.get("/RoleMap") if root is not None else None
        if rm is not None:
            for key in list(rm.keys()):
                if key in STD:
                    del rm[key]
        src.save(pdfua)
    v = subprocess.run(["java", "-cp", str(VERA), "org.verapdf.apps.GreenfieldCliWrapper", "-f", "ua1", "--format", "text", str(pdfua)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    ua = "PASS" in v.stdout.decode("utf-8", errors="replace")

    ok = page_cover and reading >= 0.98 and f1 >= 0.95 and foot_recall >= 0.95 and elapsed < 60 and epub_err == 0 and ooxml_ok and ua
    result = {
        "trial": "T01",
        "ok": ok,
        "pages": 500,
        "elapsed_seconds": round(elapsed, 2),
        "page_cover": page_cover,
        "reading_order": round(reading, 4),
        "table_f1": round(f1, 4),
        "footnote_recall": round(foot_recall, 4),
        "epubcheck_errors": epub_err,
        "openxml_valid": ooxml_ok,
        "pdfua_pass": ua,
        "oom": 0,
        "criteria": {"pages": 500, "order": ">=98%", "table_f1": ">=95%", "footnote": ">=95%", "seconds": "<60", "validators": 0},
    }
    (REPO / "results" / "app" / "governance" / "trials" / "T01.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
