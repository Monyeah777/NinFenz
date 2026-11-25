#!/usr/bin/env python3
"""H1.2 保真账本基准：30 份 5 页 PDF，账本 features 与源真值逐项一致；
unprovenanced=0；losses=0；page 覆盖 1..5。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE_CORE = Path(os.environ.get("NF_APP_CORE", REPO / "app" / "core" / "target" / "release" / "nf-app-core.exe"))
CORE_DIR = Path(tempfile.mkdtemp(prefix="nf-h12-core-"))
CORE = CORE_DIR / SOURCE_CORE.name
if SOURCE_CORE.exists():
    shutil.copy2(SOURCE_CORE, CORE)
OUT = REPO / "results" / "app" / "governance" / "benchmarks"
PDF_TOOL = os.environ.get("PDFTOHTML", "C:/Program Files/Calibre2/app/bin/pdftohtml.exe")


def core(op: str, req: dict) -> tuple[int, dict]:
    p = subprocess.run([str(CORE), op, "--in", "-"], input=json.dumps(req, ensure_ascii=False).encode(), stdout=subprocess.PIPE, timeout=180)
    return p.returncode, json.loads(p.stdout.decode("utf-8"))


def walk(v: dict):
    yield v
    for c in v.get("children", []):
        yield from walk(c)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="nf-h12-"))
    docs = 30
    exact = 0
    no_loss = 0
    pages_ok = 0
    for i in range(docs):
        pdf = tmp / f"d{i}.pdf"
        subprocess.run([sys.executable, str(REPO / "app" / "scripts" / "make_pdf.py"), "--pages", "5", "--columns", "2", "--out", str(pdf)], check=True, stdout=subprocess.DEVNULL)
        req = tmp / f"d{i}.layout.json"
        p = subprocess.run([sys.executable, str(REPO / "app" / "scripts" / "pdf_layout.py"), "--pdf", str(pdf), "--out", str(req), "--chunk", "5"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, "PDFTOHTML": PDF_TOOL})
        assert p.returncode == 0, p.stderr.decode("utf-8", errors="replace")[:500]
        code, env = core("layout-import", json.loads(req.read_text(encoding="utf-8")))
        assert code == 0, env
        sdir = env["result"]
        fid = sdir["meta"]["fidelity"]
        expected = {"document": 1, "heading": 5, "paragraph": 10, "table": 5, "table_row": 15, "table_cell": 30, "footnote": 5}
        if fid["features"] == expected and fid["source_pages"] == 5:
            exact += 1
        if fid["losses"] == [] and fid["unprovenanced_blocks"] == 0:
            no_loss += 1
        pages = {b.get("page") for b in walk(sdir["blocks"][0]) if b.get("type") != "document"}
        if pages == {1, 2, 3, 4, 5}:
            pages_ok += 1
    ok = exact == docs and no_loss == docs and pages_ok == docs
    result = {
        "benchmark": "H1.2",
        "ok": ok,
        "docs": docs,
        "features_exact": exact,
        "no_silent_loss": no_loss,
        "page_bbox_full": pages_ok,
        "criteria": {"features": "100%", "loss": 0, "page_bbox": "100%"},
    }
    (OUT / "H12.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
