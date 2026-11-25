#!/usr/bin/env python3
"""H1.1 版式感知接入基准：30 份双栏 PDF × 5 页，含表格与脚注。
判据：阅读顺序 ≥98%；表格 F1 ≥95%；脚注 ≥95%；<60s；0 OOM。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE_CORE = Path(os.environ.get("NF_APP_CORE", REPO / "app" / "core" / "target" / "release" / "nf-app-core.exe"))
CORE_DIR = Path(tempfile.mkdtemp(prefix="nf-h11-core-"))
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
    tmp = Path(tempfile.mkdtemp(prefix="nf-h11-"))
    pages_total = 0
    order_ok = 0
    foot_ok = 0
    tp = fp = fn = 0
    t0 = time.perf_counter()
    for i in range(30):
        pdf = tmp / f"d{i}.pdf"
        subprocess.run([sys.executable, str(REPO / "app" / "scripts" / "make_pdf.py"), "--pages", "5", "--columns", "2", "--out", str(pdf)], check=True, stdout=subprocess.DEVNULL)
        req = tmp / f"d{i}.layout.json"
        p = subprocess.run([sys.executable, str(REPO / "app" / "scripts" / "pdf_layout.py"), "--pdf", str(pdf), "--out", str(req), "--chunk", "5"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, "PDFTOHTML": PDF_TOOL})
        assert p.returncode == 0, p.stderr.decode("utf-8", errors="replace")[:500]
        code, env = core("layout-import", json.loads(req.read_text(encoding="utf-8")))
        assert code == 0, env
        sdir = env["result"]
        blocks = list(walk(sdir["blocks"][0]))
        for page in range(1, 6):
            pages_total += 1
            pblocks = [b for b in blocks if b.get("page") == page]
            paras = [b["text"] for b in pblocks if b["type"] == "paragraph"]
            left = next((t for t in paras if f"Page {page} line 1:" in t), "")
            right = next((t for t in paras if f"Page {page} line 2:" in t), "")
            left_nums = [int(x) for x in re.findall(r"line (\d+):", left)]
            right_nums = [int(x) for x in re.findall(r"line (\d+):", right)]
            if left_nums == list(range(1, 28, 2)) and right_nums == list(range(2, 29, 2)):
                order_ok += 1
            tables = [b for b in pblocks if b["type"] == "table"]
            cells = {c["text"] for t in tables for c in walk(t) if c["type"] == "table_cell"}
            expected = {"Place", "Risk", "North gate", "High", "Inn", "Low"}
            tp += len(cells & expected)
            fp += len(cells - expected)
            fn += len(expected - cells)
            if any("footnote" in b.get("text", "") for b in pblocks if b["type"] == "footnote"):
                foot_ok += 1
    elapsed = time.perf_counter() - t0
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    order = order_ok / pages_total
    foot = foot_ok / pages_total
    ok = order >= 0.98 and f1 >= 0.95 and foot >= 0.95 and elapsed < 60
    result = {
        "benchmark": "H1.1",
        "ok": ok,
        "docs": 30,
        "pages": pages_total,
        "reading_order": round(order, 4),
        "table_precision": round(precision, 4),
        "table_recall": round(recall, 4),
        "table_f1": round(f1, 4),
        "footnote_recall": round(foot, 4),
        "seconds": round(elapsed, 2),
        "oom": 0,
        "criteria": {"order": ">=98%", "table_f1": ">=95%", "footnote": ">=95%", "seconds": "<60", "oom": 0},
    }
    (OUT / "H11.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
