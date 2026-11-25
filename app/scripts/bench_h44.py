#!/usr/bin/env python3
"""H4.4 单 IR 多 Profile 基准：10 文档 × 5 Profile × 3 格式。
判据：语义 parity ≥98%；EPUBCheck/结构校验 0 error。结果写 benchmarks/H44.json。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE_CORE = Path(os.environ.get("NF_APP_CORE", REPO / "app" / "core" / "target" / "release" / "nf-app-core.exe"))
CORE_DIR = Path(tempfile.mkdtemp(prefix="nf-h44-core-"))
CORE = CORE_DIR / SOURCE_CORE.name
if SOURCE_CORE.exists():
    shutil.copy2(SOURCE_CORE, CORE)
OUT = REPO / "results" / "app" / "governance" / "benchmarks"
CREATED = "2026-01-01T00:00:00Z"
PROFILES = ["default", "accessible", "print", "mobile", "large-print"]
EPUBCHECK = Path(os.environ.get("EPUBCHECK_JAR", "D:/tmp/epubcheck/epubcheck-5.1.0/epubcheck.jar"))


def run(op: str, req: dict) -> tuple[int, dict]:
    p = subprocess.run(
        [str(CORE), op, "--in", "-"],
        input=json.dumps(req, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )
    env = json.loads(p.stdout.decode("utf-8"))
    return p.returncode, env


def import_doc(md: str, name: str) -> dict:
    code, env = run("sdir-import", {"markdown": md, "created_at": CREATED, "source": {"name": name, "mime": "text/markdown"}, "lang": "zh"})
    assert code == 0, env
    return env["result"]


def blocks(v: dict):
    yield v
    for c in v.get("children", []):
        yield from blocks(c)


def texts(sdir: dict) -> set[str]:
    return {b["text"].strip() for b in blocks(sdir["blocks"][0]) if b.get("text", "").strip()}


def make_doc(i: int) -> tuple[str, dict]:
    md = (
        f"# 文档 {i}\n\n"
        f"这是第 {i} 份多 Profile 基准文档。\n\n"
        f"## 表格\n\n| 键 | 值 |\n|---|---|\n| a | {i} |\n| b | {i + 1} |\n\n"
        f"## 列表\n\n- 第一项 {i}\n- 第二项 {i}\n\n"
        f"## 结尾\n\n结束段落 {i}。\n"
    )
    return md, import_doc(md, f"h44-{i}.md")


def epubcheck(path: Path) -> tuple[int, str]:
    if not EPUBCHECK.is_file():
        return 1, "EPUBCheck jar missing"
    p = subprocess.run(["java", "-jar", str(EPUBCHECK), str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    out = p.stdout.decode("utf-8", errors="replace")
    m = re.search(r"Messages:\s*(\d+)\s+fatals\s*/\s*(\d+)\s+errors", out)
    errors = int(m.group(2)) if m else 1
    return errors, out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="nf-h44-"))
    docs = [make_doc(i) for i in range(10)]
    parity_ok = 0
    total = 0
    epub_errors = 0
    docx_ok = 0
    html_ok = 0
    for i, (md, sdir) in enumerate(docs):
        expected = texts(sdir)
        for profile in PROFILES:
            out = tmp / f"d{i}" / profile
            out.mkdir(parents=True)
            code, env = run(
                "export-profile",
                {"sdir": sdir, "profile": profile, "formats": ["html", "epub", "docx"], "out_dir": str(out)},
            )
            assert code == 0, env
            total += 1
            epub = out / profile / "index.epub"
            docx = out / profile / "index.docx"
            html = out / profile / "index.html"
            err, _ = epubcheck(epub)
            epub_errors += err
            if epub.is_file():
                code, back = run("sdir-import", {"epub_path": str(epub), "created_at": CREATED, "lang": "zh"})
                if code == 0 and expected <= texts(back["result"]):
                    parity_ok += 1
            if docx.is_file():
                with zipfile.ZipFile(docx) as z:
                    names = set(z.namelist())
                if "[Content_Types].xml" in names and "word/document.xml" in names:
                    docx_ok += 1
            if html.is_file():
                raw = html.read_text(encoding="utf-8")
                if "<html" in raw and "lang=" in raw and "<h1" in raw and "<table" in raw:
                    html_ok += 1
    shutil.rmtree(tmp, ignore_errors=True)
    ratio = parity_ok / max(1, total)
    ok = ratio >= 0.98 and epub_errors == 0 and docx_ok == total and html_ok == total
    result = {
        "benchmark": "H4.4",
        "ok": ok,
        "docs": len(docs),
        "profiles": PROFILES,
        "cases": total,
        "semantic_parity": round(ratio, 4),
        "epubcheck_errors": epub_errors,
        "docx_structural_ok": docx_ok,
        "html_structural_ok": html_ok,
        "epubcheck_jar": str(EPUBCHECK),
        "criteria": {"parity": ">=98%", "epubcheck": 0, "docx": "100%", "html": "100%"},
    }
    path = OUT / "H44.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
