#!/usr/bin/env python3
"""H5.3 三格式 × 三应用首次打开基准。
DOCX: LibreOffice / Calibre / ONLYOFFICE
EPUB: Calibre / ONLYOFFICE / SumatraPDF
PDF:  LibreOffice(Draw) / Calibre / ONLYOFFICE
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pikepdf

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "app" / "core" / "target" / "release" / "nf-app-core.exe"
WORK = REPO / "app" / "core" / "target" / "h53-bench"
SOFFICE = Path(os.environ.get("SOFFICE", "D:/nf-validators/LibreOffice/program/soffice.exe"))
CALIBRE = Path(os.environ.get("EBOOK_CONVERT", "C:/Program Files/Calibre2/ebook-convert.exe"))
OO = Path(os.environ.get("ONLYOFFICE", "D:/nf-validators/DesktopEditors_x86/DesktopEditors.exe"))
SUMATRA = Path(os.environ.get("SUMATRA", "D:/nf-validators/sumatra-portable/SumatraPDF-3.6.1-64.exe"))
DOCS = 3
STD = {"/Quote", "/Note", "/Reference", "/BibEntry", "/Code", "/Span", "/P", "/H", "/H1", "/H2", "/H3", "/H4", "/H5", "/H6", "/Table", "/TR", "/TH", "/TD", "/L", "/LI", "/Lbl", "/LBody", "/Figure", "/Caption", "/Document", "/Sect", "/Div", "/Art", "/Part", "/Aside"}


def core(op: str, req: dict) -> tuple[int, dict]:
    p = subprocess.run([str(CORE), op, "--in", "-"], input=json.dumps(req, ensure_ascii=False).encode(), stdout=subprocess.PIPE, timeout=180)
    return p.returncode, json.loads(p.stdout.decode("utf-8"))


def doc(i: int) -> str:
    return (
        f"# Document {i}\n\nIntro paragraph for document {i}.\n\n"
        f"## Table\n\n| Key | Value |\n|---|---|\n| a | {i} |\n| b | {i + 1} |\n\n"
        f"## List\n\n- first {i}\n- second {i}\n\n## End\n\nClosing paragraph {i}.\n"
    )


def ps(script: str) -> str:
    path = WORK / "helper.ps1"
    path.write_text(script, encoding="utf-8")
    p = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    return p.stdout.decode("utf-8", errors="replace").strip()


def open_onlyoffice(path: Path) -> tuple[bool, str]:
    ss = f"Stop-Process -Name editors,DesktopEditors,editors_helper -Force -ErrorAction SilentlyContinue\n" \
         f"Start-Sleep -Milliseconds 500\n" \
         f"Start-Process -FilePath '{OO}' -ArgumentList '--view={path}' | Out-Null\n" \
         f"Start-Sleep -Seconds 8\n" \
         f"$w = Get-Process editors -ErrorAction SilentlyContinue | Where-Object {{ $_.MainWindowTitle }} | Select-Object -First 1\n" \
         f"if ($w) {{ Write-Output \"OK:$($w.MainWindowTitle)\" }} else {{ Write-Output 'FAIL' }}\n" \
         f"Stop-Process -Name editors,DesktopEditors,editors_helper -Force -ErrorAction SilentlyContinue\n"
    out = ps(ss)
    return out.startswith("OK:"), out


def open_sumatra(path: Path) -> tuple[bool, str]:
    ss = f"Stop-Process -Name SumatraPDF-3.6.1-64 -Force -ErrorAction SilentlyContinue\n" \
         f"Start-Sleep -Milliseconds 500\n" \
         f"Start-Process -FilePath '{SUMATRA}' -ArgumentList '{path}' | Out-Null\n" \
         f"Start-Sleep -Seconds 6\n" \
         f"$p = Get-Process | Where-Object {{ $_.ProcessName -like 'Sumatra*' }} | Select-Object -First 1\n" \
         f"if ($p) {{ Write-Output \"OK:$($p.ProcessName)\" }} else {{ Write-Output 'FAIL' }}\n" \
         f"Stop-Process -Name SumatraPDF-3.6.1-64 -Force -ErrorAction SilentlyContinue\n"
    out = ps(ss)
    return out.startswith("OK:"), out


def tokens(s: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]+", s.lower()))


def main() -> int:
    if not all(p.exists() for p in (CORE, SOFFICE, CALIBRE, OO, SUMATRA)):
        print("missing app/core")
        return 2
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    cases = []
    for i in range(DOCS):
        d = WORK / f"d{i}"
        d.mkdir()
        code, env = core("sdir-import", {"markdown": doc(i), "created_at": "2026-01-01T00:00:00Z", "lang": "en"})
        assert code == 0, env
        sdir = env["result"]
        code, env = core("build-run", {"sdir": sdir, "outputs": [{"path": f"d{i}.docx", "format": "docx"}, {"path": "index.epub", "format": "epub"}], "out_dir": str(d)})
        assert code == 0, env
        cases.append((i, d, sdir))
    # 批量生成 PDF
    pdfdir = WORK / "pdf"
    pdfdir.mkdir()
    cmd = [str(SOFFICE), "--headless", "--norestore", f"-env:UserInstallation=file:///{WORK.as_posix()}/lo-profile",
           "--convert-to", 'pdf:writer_pdf_Export:{"UseTaggedPDF":{"type":"boolean","value":"true"},"PDFUACompliance":{"type":"boolean","value":"true"}}',
           "--outdir", str(pdfdir)] + [str(d / f"d{i}.docx") for i, d, _ in cases]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    for i, d, _ in cases:
        src = pdfdir / f"d{i}.pdf"
        with pikepdf.open(src) as pdf:
            root = pdf.Root.get("/StructTreeRoot")
            rm = root.get("/RoleMap") if root is not None else None
            if rm is not None:
                for key in list(rm.keys()):
                    if key in STD:
                        del rm[key]
            pdf.save(d / "index.pdf")

    opens = 0
    expected_opens = DOCS * 3 * 3
    missing_text = 0
    text_checks = 0
    details = []
    for i, d, _ in cases:
        docx = d / f"d{i}.docx"
        epub = d / "index.epub"
        pdf = d / "index.pdf"
        exp = tokens(doc(i))
        # DOCX
        (d / "lo").mkdir(exist_ok=True)
        p = subprocess.run([str(SOFFICE), "--headless", "--norestore", f"-env:UserInstallation=file:///{WORK.as_posix()}/lo-profile2", "--convert-to", "txt:Text", "--outdir", str(d / "lo"), str(docx)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        lo_txt = (d / "lo" / f"d{i}.txt")
        if p.returncode == 0 and lo_txt.is_file():
            opens += 1
            text_checks += 1
            if exp - tokens(lo_txt.read_text(encoding="utf-8", errors="replace")):
                missing_text += 1
        # LO PDF -> PNG
        p = subprocess.run([str(SOFFICE), "--headless", "--norestore", f"-env:UserInstallation=file:///{WORK.as_posix()}/lo-profile3", "--convert-to", "png:draw_png_Export", "--outdir", str(d / "lo"), str(pdf)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        if p.returncode == 0 and any((d / "lo").glob("*.png")):
            opens += 1
        # Calibre DOCX/EPUB/PDF
        for src, tag in ((docx, "docx"), (epub, "epub"), (pdf, "pdf")):
            out = d / f"cal-{tag}.txt"
            p = subprocess.run([str(CALIBRE), str(src), str(out), "--txt-output-encoding=utf-8"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            if p.returncode == 0 and out.is_file():
                opens += 1
                text_checks += 1
                if exp - tokens(out.read_text(encoding="utf-8", errors="replace")):
                    missing_text += 1
        # ONLYOFFICE DOCX/EPUB/PDF
        for src, tag in ((docx, "docx"), (epub, "epub"), (pdf, "pdf")):
            ok, out = open_onlyoffice(src)
            if ok:
                opens += 1
            details.append({"case": f"d{i}", "app": "ONLYOFFICE", "format": tag, "ok": ok, "out": out})
        # Sumatra EPUB
        ok, out = open_sumatra(epub)
        if ok:
            opens += 1
        details.append({"case": f"d{i}", "app": "SumatraPDF", "format": "epub", "ok": ok, "out": out})

    total = expected_opens
    result = {
        "benchmark": "H5.3",
        "ok": opens == total and missing_text == 0,
        "docs": DOCS,
        "opens": opens,
        "expected_opens": total,
        "text_checks": text_checks,
        "missing_text": missing_text,
        "apps": {"docx": ["LibreOffice", "Calibre", "ONLYOFFICE"], "epub": ["Calibre", "ONLYOFFICE", "SumatraPDF"], "pdf": ["LibreOffice(Draw)", "Calibre", "ONLYOFFICE"]},
        "criteria": {"opens": "27/27", "missing_text": 0, "repair_prompts": 0},
    }
    (REPO / "results" / "app" / "governance" / "benchmarks" / "H53.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
