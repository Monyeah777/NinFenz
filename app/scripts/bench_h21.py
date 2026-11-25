#!/usr/bin/env python3
"""H2.1 语义文档 IR 基准：30 份 P0 类文档（md/docx/epub/pdf）导入 IR → 导出 md → 再入 IR。
判据：100% 文档入 IR；往返语义等价 ≥98%。
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE_CORE = Path(os.environ.get("NF_APP_CORE", REPO / "app" / "core" / "target" / "release" / "nf-app-core.exe"))
CORE_DIR = Path(tempfile.mkdtemp(prefix="nf-h21-core-"))
CORE = CORE_DIR / SOURCE_CORE.name
if SOURCE_CORE.exists():
    shutil.copy2(SOURCE_CORE, CORE)
OUT = REPO / "results" / "app" / "governance" / "benchmarks"
CREATED = "2026-01-01T00:00:00Z"


def core(op: str, req: dict) -> tuple[int, dict]:
    p = subprocess.run([str(CORE), op, "--in", "-"], input=json.dumps(req, ensure_ascii=False).encode(), stdout=subprocess.PIPE, timeout=180)
    return p.returncode, json.loads(p.stdout.decode("utf-8"))


def blocks(v: dict):
    yield v
    for c in v.get("children", []):
        yield from blocks(c)


def texts(sdir: dict) -> str:
    vals = [b.get("text", "") for b in blocks(sdir["blocks"][0]) if b.get("text", "").strip()]
    return "\n".join(vals)


def md_doc(i: int) -> str:
    return (
        f"# 文档 {i}\n\n这是第 {i} 份语义 IR 基准文档。\n\n"
        f"## 表格\n\n| 键 | 值 |\n|---|---|\n| a | {i} |\n| b | {i + 1} |\n\n"
        f"## 列表\n\n- 第一项 {i}\n- 第二项 {i}\n\n"
        f"## 结尾\n\n结束段落 {i}。\n"
    )


def import_md(md: str, name: str) -> dict:
    code, env = core("sdir-import", {"markdown": md, "created_at": CREATED, "lang": "zh", "source": {"name": name, "mime": "text/markdown"}})
    assert code == 0, env
    return env["result"]


def build(sdir: dict, fmt: str, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    code, env = core("build-run", {"sdir": sdir, "outputs": [{"path": f"x.{fmt}", "format": fmt}], "out_dir": str(out)})
    assert code == 0, env
    return out / f"x.{fmt}"


def import_file(path: Path, kind: str) -> dict:
    if kind == "md":
        return import_md(path.read_text(encoding="utf-8"), path.name)
    if kind == "docx":
        code, env = core("sdir-import", {"docx_path": str(path), "created_at": CREATED, "lang": "zh"})
    elif kind == "epub":
        code, env = core("sdir-import", {"epub_path": str(path), "created_at": CREATED, "lang": "zh"})
    else:
        req = path.with_suffix(".layout.json")
        p = subprocess.run(
            [sys.executable, str(REPO / "app" / "scripts" / "pdf_layout.py"), "--pdf", str(path), "--out", str(req), "--chunk", "20"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PDFTOHTML": os.environ.get("PDFTOHTML", "C:/Program Files/Calibre2/app/bin/pdftohtml.exe")},
        )
        assert p.returncode == 0, p.stderr.decode("utf-8", errors="replace")[:500]
        code, env = core("layout-import", json.loads(req.read_text(encoding="utf-8")))
    assert code == 0, env
    return env["result"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="nf-h21-"))
    cases: list[tuple[str, Path, str]] = []
    for i in range(10):
        md = tmp / f"d{i}.md"
        md.write_text(md_doc(i), encoding="utf-8")
        cases.append(("md", md, "md"))
        sdir = import_md(md_doc(i), f"d{i}.md")
        cases.append(("docx", build(sdir, "docx", tmp / f"docx{i}"), "docx"))
        if i < 5:
            cases.append(("epub", build(sdir, "epub", tmp / f"epub{i}"), "epub"))
    for i in range(5):
        pdf = tmp / f"p{i}.pdf"
        subprocess.run([sys.executable, str(REPO / "app" / "scripts" / "make_pdf.py"), "--pages", "2", "--out", str(pdf)], check=True, stdout=subprocess.DEVNULL)
        cases.append(("pdf", pdf, "pdf"))
    parity = 0
    for kind, path, _ in cases:
        sdir1 = import_file(path, kind)
        md = build(sdir1, "md", tmp / ("rt-" + path.stem))
        sdir2 = import_md(md.read_text(encoding="utf-8"), md.name)
        a, b = texts(sdir1), texts(sdir2)
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        if ratio >= 0.98:
            parity += 1
    total = len(cases)
    ratio_all = parity / total
    ok = ratio_all >= 0.98
    result = {
        "benchmark": "H2.1",
        "ok": ok,
        "docs": total,
        "by_format": {k: sum(1 for x in cases if x[0] == k) for k in ("md", "docx", "epub", "pdf")},
        "roundtrip_parity": round(ratio_all, 4),
        "criteria": {"docs": 30, "parity": ">=98%"},
    }
    (OUT / "H21.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
