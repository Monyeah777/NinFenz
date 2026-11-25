#!/usr/bin/env python3
"""T05：DOCX→IR→EPUB/PDF→IR→DOCX 往返；10 文档 × 3 应用首次打开。"""

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
WORK = REPO / "app" / "core" / "target" / "t05-bench"
SOFFICE = Path(os.environ.get("SOFFICE", "D:/nf-validators/LibreOffice/program/soffice.exe"))
CALIBRE = Path(os.environ.get("EBOOK_CONVERT", "C:/Program Files/Calibre2/ebook-convert.exe"))
OO = Path(os.environ.get("ONLYOFFICE", "D:/nf-validators/DesktopEditors_x86/DesktopEditors.exe"))
SUMATRA = Path(os.environ.get("SUMATRA", "D:/nf-validators/sumatra-portable/SumatraPDF-3.6.1-64.exe"))
DOCS = 10
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


def tokens(s: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]+", s.lower()))


def sdir_text(sdir: dict) -> str:
    parts = []
    def walk(v):
        if v.get("text"):
            parts.append(v["text"])
        for c in v.get("children", []):
            walk(c)
    walk(sdir["blocks"][0])
    return chr(10).join(parts)


def parity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / max(1, len(ta | tb))


def ps(script: str) -> str:
    path = WORK / "helper.ps1"
    path.write_text(script, encoding="utf-8")
    p = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    return p.stdout.decode("utf-8", errors="replace").strip()


def open_onlyoffice(path: Path) -> bool:
    ss = f"Stop-Process -Name editors,DesktopEditors,editors_helper -Force -ErrorAction SilentlyContinue\n" \
         f"Start-Sleep -Milliseconds 500\n" \
         f"Start-Process -FilePath '{OO}' -ArgumentList '--view={path}' | Out-Null\n" \
         f"Start-Sleep -Seconds 8\n" \
         f"$w = Get-Process editors -ErrorAction SilentlyContinue | Where-Object {{ $_.MainWindowTitle }} | Select-Object -First 1\n" \
         f"if ($w) {{ Write-Output 'OK' }} else {{ Write-Output 'FAIL' }}\n" \
         f"Stop-Process -Name editors,DesktopEditors,editors_helper -Force -ErrorAction SilentlyContinue\n"
    return ps(ss).startswith("OK")


def open_sumatra(path: Path) -> bool:
    ss = f"Stop-Process -Name SumatraPDF-3.6.1-64 -Force -ErrorAction SilentlyContinue\n" \
         f"Start-Sleep -Milliseconds 500\n" \
         f"Start-Process -FilePath '{SUMATRA}' -ArgumentList '{path}' | Out-Null\n" \
         f"Start-Sleep -Seconds 6\n" \
         f"$p = Get-Process | Where-Object {{ $_.ProcessName -like 'Sumatra*' }} | Select-Object -First 1\n" \
         f"if ($p) {{ Write-Output 'OK' }} else {{ Write-Output 'FAIL' }}\n" \
         f"Stop-Process -Name SumatraPDF-3.6.1-64 -Force -ErrorAction SilentlyContinue\n"
    return ps(ss).startswith("OK")


def pdf_layout(pdf: Path, out: Path) -> dict:
    subprocess.run([sys.executable, str(REPO / "app" / "scripts" / "pdf_layout.py"), "--pdf", str(pdf), "--out", str(out), "--chunk", "20"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    code, env = core("layout-import", json.loads(out.read_text(encoding="utf-8")))
    assert code == 0, env
    return env["result"]


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
    pdfdir = WORK / "pdf"
    pdfdir.mkdir()
    subprocess.run([str(SOFFICE), "--headless", "--norestore", f"-env:UserInstallation=file:///{WORK.as_posix()}/lo",
                    "--convert-to", 'pdf:writer_pdf_Export:{"UseTaggedPDF":{"type":"boolean","value":"true"},"PDFUACompliance":{"type":"boolean","value":"true"}}',
                    "--outdir", str(pdfdir)] + [str(d / f"d{i}.docx") for i, d, _ in cases], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    for i, d, _ in cases:
        with pikepdf.open(pdfdir / f"d{i}.pdf") as pdf:
            root = pdf.Root.get("/StructTreeRoot")
            rm = root.get("/RoleMap") if root is not None else None
            if rm is not None:
                for key in list(rm.keys()):
                    if key in STD:
                        del rm[key]
            pdf.save(d / "index.pdf")
    pngsrc = WORK / "pngsrc"
    pngout = WORK / "pngout"
    pngsrc.mkdir()
    pngout.mkdir()
    for i, d, _ in cases:
        shutil.copy2(d / "index.pdf", pngsrc / f"d{i}.pdf")
    subprocess.run([str(SOFFICE), "--headless", "--norestore", f"-env:UserInstallation=file:///{WORK.as_posix()}/lo-png",
                    "--convert-to", "png:draw_png_Export", "--outdir", str(pngout)] + [str(pngsrc / f"d{i}.pdf") for i, _, _ in cases],
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)

    roundtrip = []
    opens = 0
    expected_opens = DOCS * 9
    text_checks = 0
    missing_text = 0
    details = []
    for i, d, sdir in cases:
        # PDF -> IR -> DOCX
        s_pdf = pdf_layout(d / "index.pdf", d / "pdf.json")
        code, env = core("build-run", {"sdir": s_pdf, "outputs": [{"path": "from-pdf.docx", "format": "docx"}], "out_dir": str(d)})
        assert code == 0, env
        code, env = core("sdir-import", {"docx_path": str(d / "from-pdf.docx"), "created_at": "2026-01-01T00:00:00Z", "lang": "en"})
        assert code == 0, env
        p_pdf = parity(sdir_text(sdir), sdir_text(env["result"]))
        # EPUB -> IR -> DOCX
        code, env = core("sdir-import", {"epub_path": str(d / "index.epub"), "created_at": "2026-01-01T00:00:00Z", "lang": "en"})
        assert code == 0, env
        s_epub = env["result"]
        code, env = core("build-run", {"sdir": s_epub, "outputs": [{"path": "from-epub.docx", "format": "docx"}], "out_dir": str(d)})
        assert code == 0, env
        code, env = core("sdir-import", {"docx_path": str(d / "from-epub.docx"), "created_at": "2026-01-01T00:00:00Z", "lang": "en"})
        assert code == 0, env
        p_epub = parity(sdir_text(sdir), sdir_text(env["result"]))
        roundtrip.append({"doc": i, "pdf_parity": round(p_pdf, 4), "epub_parity": round(p_epub, 4)})

        exp = tokens(doc(i))
        # LibreOffice DOCX
        (d / "lo").mkdir(exist_ok=True)
        p = subprocess.run([str(SOFFICE), "--headless", "--norestore", f"-env:UserInstallation=file:///{WORK.as_posix()}/lo2", "--convert-to", "txt:Text", "--outdir", str(d / "lo"), str(d / f"d{i}.docx")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        if p.returncode == 0 and (d / "lo" / f"d{i}.txt").is_file():
            opens += 1
            text_checks += 1
            if exp - tokens((d / "lo" / f"d{i}.txt").read_text(encoding="utf-8", errors="replace")):
                missing_text += 1
                details.append({"doc": i, "app": "LibreOffice", "format": "docx", "missing": sorted(exp - tokens((d / "lo" / f"d{i}.txt").read_text(encoding="utf-8", errors="replace")))})
        else:
            details.append({"doc": i, "app": "LibreOffice", "format": "docx", "ok": False})
        # LibreOffice PDF -> PNG (batch above)
        if (pngout / f"d{i}.png").is_file():
            opens += 1
        else:
            details.append({"doc": i, "app": "LibreOffice", "format": "pdf", "ok": False})
        # Calibre all formats
        for src, tag in ((d / f"d{i}.docx", "docx"), (d / "index.epub", "epub"), (d / "index.pdf", "pdf")):
            out = d / f"cal-{tag}.txt"
            p = subprocess.run([str(CALIBRE), str(src), str(out), "--txt-output-encoding=utf-8"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            if p.returncode == 0 and out.is_file():
                opens += 1
                text_checks += 1
                if exp - tokens(out.read_text(encoding="utf-8", errors="replace")):
                    missing_text += 1
                    details.append({"doc": i, "app": "Calibre", "format": tag, "missing": sorted(exp - tokens(out.read_text(encoding="utf-8", errors="replace")))})
            else:
                details.append({"doc": i, "app": "Calibre", "format": tag, "ok": False})
        # ONLYOFFICE 3 formats
        for src, tag in ((d / f"d{i}.docx", "docx"), (d / "index.epub", "epub"), (d / "index.pdf", "pdf")):
            ok = open_onlyoffice(src)
            if ok:
                opens += 1
            else:
                details.append({"doc": i, "app": "ONLYOFFICE", "format": tag, "ok": False})
        # Sumatra EPUB
        if open_sumatra(d / "index.epub"):
            opens += 1
        else:
            details.append({"doc": i, "app": "SumatraPDF", "format": "epub", "ok": False})

    min_parity = min(min(r["pdf_parity"], r["epub_parity"]) for r in roundtrip)
    result = {
        "trial": "T05",
        "ok": opens == expected_opens and missing_text == 0 and min_parity >= 0.98,
        "docs": DOCS,
        "opens": opens,
        "expected_opens": expected_opens,
        "text_checks": text_checks,
        "missing_text": missing_text,
        "min_pdf_parity": min_parity,
        "roundtrip": roundtrip,
        "details": details,
        "criteria": {"parity": ">=98%", "opens": "90/90", "missing_text": 0},
    }
    (REPO / "results" / "app" / "governance" / "trials" / "T05.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
