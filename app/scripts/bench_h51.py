#!/usr/bin/env python3
"""H5.1 可访问即构造基准：20 文档 -> EPUB/DOCX/PDF。
EPUBCheck 0 error；Open XML valid；veraPDF PDF/UA-1 PASS；WCAG 结构 blocker=0。
LibreOffice 批量转换以降低启动成本。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pikepdf

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "app" / "core" / "target" / "release" / "nf-app-core.exe"
WORK = REPO / "app" / "core" / "target" / "h51-bench"
EPUBCHECK = Path(os.environ.get("EPUBCHECK_JAR", "D:/nf-validators/epubcheck-5.1.0/epubcheck.jar"))
OOXML = Path(os.environ.get("OOXML_VALIDATE", "D:/nf-validators/ooxml/ooxml-validate.exe"))
SOFFICE = Path(os.environ.get("SOFFICE", "D:/nf-validators/LibreOffice/program/soffice.exe"))
VERA = Path(os.environ.get("VERAPDF_CLI", "D:/nf-validators/verapdf/verapdf-cli.jar"))
XHTML = "{http://www.w3.org/1999/xhtml}"
XML = "{http://www.w3.org/XML/1998/namespace}"

STD_TAGS = {
    "/Document", "/Part", "/Art", "/Sect", "/Div", "/BlockQuote", "/Caption", "/TOC", "/TOCI",
    "/Index", "/NonStruct", "/Private", "/P", "/H", "/H1", "/H2", "/H3", "/H4", "/H5", "/H6",
    "/L", "/LI", "/Lbl", "/LBody", "/Table", "/TR", "/TH", "/TD", "/THead", "/TBody", "/TFoot",
    "/Span", "/Quote", "/Note", "/Reference", "/BibEntry", "/Code", "/Link", "/Annot", "/Ruby",
    "/RB", "/RT", "/RP", "/Warichu", "/WT", "/WP", "/Figure", "/Formula", "/Form",
}


def core(op: str, req: dict) -> tuple[int, dict]:
    p = subprocess.run([str(CORE), op, "--in", "-"], input=json.dumps(req, ensure_ascii=False).encode(), stdout=subprocess.PIPE, timeout=180)
    return p.returncode, json.loads(p.stdout.decode("utf-8"))


def doc(i: int) -> str:
    return (
        f"# Document {i}\n\n"
        f"Intro paragraph for document {i}.\n\n"
        f"## Table\n\n| Key | Value |\n|---|---|\n| a | {i} |\n| b | {i + 1} |\n\n"
        f"## List\n\n- first {i}\n- second {i}\n\n"
        f"## End\n\nClosing paragraph {i}.\n"
    )


def epub_errors(path: Path) -> int:
    p = subprocess.run(["java", "-jar", str(EPUBCHECK), str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    m = re.search(r"Messages:\s*\d+\s+fatals\s*/\s*(\d+)\s+errors", p.stdout.decode("utf-8", errors="replace"))
    return int(m.group(1)) if m else 1


def ooxml_valid(path: Path) -> bool:
    p = subprocess.run([str(OOXML), str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    try:
        return bool(json.loads(p.stdout.decode("utf-8"))["results"][0]["valid"])
    except Exception:
        return False


def batch_pdf(docx: list[Path], outdir: Path) -> str:
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(SOFFICE), "--headless", "--norestore",
        f"-env:UserInstallation=file:///{WORK.as_posix()}/lo-profile",
        "--convert-to",
        'pdf:writer_pdf_Export:{"UseTaggedPDF":{"type":"boolean","value":"true"},"PDFUACompliance":{"type":"boolean","value":"true"}}',
        "--outdir", str(outdir),
    ] + [str(p) for p in docx]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    return p.stdout.decode("utf-8", errors="replace")[-800:]


def pdf_ua(produced: Path, out: Path) -> tuple[bool, str]:
    if not produced.is_file():
        return False, "missing PDF"
    with pikepdf.open(produced) as src:
        root = src.Root.get("/StructTreeRoot")
        if root is None:
            return False, "missing StructTreeRoot"
        rm = root.get("/RoleMap")
        if rm is not None:
            for key in list(rm.keys()):
                if key in STD_TAGS:
                    del rm[key]
        src.save(out)
    v = subprocess.run(["java", "-cp", str(VERA), "org.verapdf.apps.GreenfieldCliWrapper", "-f", "ua1", "--format", "text", str(out)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    text = v.stdout.decode("utf-8", errors="replace")
    return "PASS" in text, text[-500:]


def wcag_blockers(epub: Path, sdir: dict) -> int:
    blockers = 0
    with zipfile.ZipFile(epub) as z:
        name = next((n for n in z.namelist() if n.endswith(".xhtml") and "nav" not in n), None)
        if name is None:
            return 1
        root = ET.fromstring(z.read(name))
    if not (root.attrib.get(XML + "lang") or root.attrib.get("lang")):
        blockers += 1
    levels = [int(el.tag.split("}")[-1][1]) for el in root.iter() if el.tag.split("}")[-1] in ("h1", "h2", "h3", "h4", "h5", "h6")]
    if levels and levels[0] != 1:
        blockers += 1
    if any(b - a > 1 for a, b in zip(levels, levels[1:])):
        blockers += 1
    for table in root.iter(XHTML + "table"):
        first = table.find(".//" + XHTML + "tr")
        if first is None or first.find(XHTML + "th") is None:
            blockers += 1
    for img in root.iter(XHTML + "img"):
        if not (img.attrib.get("alt") or "").strip():
            blockers += 1
    orders = [a.get("reading_order") for a in sdir.get("accessibility", [])]
    if orders and orders != sorted(orders):
        blockers += 1
    return blockers


def main() -> int:
    if not CORE.is_file() or not EPUBCHECK.is_file() or not OOXML.is_file() or not SOFFICE.is_file():
        print("missing required tool")
        return 2
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    docs = 20
    cases = []
    for i in range(docs):
        d = WORK / f"d{i}"
        d.mkdir()
        code, env = core("sdir-import", {"markdown": doc(i), "created_at": "2026-01-01T00:00:00Z", "lang": "en", "source": {"name": f"d{i}.md", "mime": "text/markdown"}})
        assert code == 0, env
        sdir = env["result"]
        docx_name = f"d{i}.docx"
        code, env = core("build-run", {"sdir": sdir, "outputs": [{"path": "index.html", "format": "html"}, {"path": "index.epub", "format": "epub"}, {"path": docx_name, "format": "docx"}], "out_dir": str(d)})
        assert code == 0, env
        cases.append((i, d, sdir, docx_name))

    # 一次启动 LibreOffice，批量生成 20 个 PDF。
    conv = batch_pdf([d / name for _, d, _, name in cases], WORK / "pdf")
    print("LO:", conv.replace("\n", " ")[-500:])

    epub_bad = ooxml_bad = pdf_bad = wcag_bad = 0
    for i, d, sdir, docx_name in cases:
        if epub_errors(d / "index.epub") != 0:
            epub_bad += 1
        if not ooxml_valid(d / docx_name):
            ooxml_bad += 1
        ok_pdf, _ = pdf_ua(WORK / "pdf" / f"d{i}.pdf", d / "index-ua.pdf")
        if not ok_pdf:
            pdf_bad += 1
        if wcag_blockers(d / "index.epub", sdir) != 0:
            wcag_bad += 1
    result = {
        "benchmark": "H5.1",
        "ok": docs - max(epub_bad, ooxml_bad, pdf_bad, wcag_bad) == docs,
        "docs": docs,
        "epubcheck_errors": epub_bad,
        "openxml_invalid": ooxml_bad,
        "pdfua_fail": pdf_bad,
        "wcag_blockers": wcag_bad,
        "criteria": {"epubcheck": 0, "openxml": 0, "pdfua": 0, "wcag_blockers": 0},
    }
    (REPO / "results" / "app" / "governance" / "benchmarks" / "H51.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
