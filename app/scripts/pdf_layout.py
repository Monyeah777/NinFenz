#!/usr/bin/env python3
"""PDF 版式适配器：Poppler pdftohtml -xml -> layout-import 请求。
支持分块 + checkpoint 续传；不猜 PDF 没有的信息。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tracemalloc
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_PDFTOHTML = os.environ.get("PDFTOHTML", "C:/Program Files/Calibre2/app/bin/pdftohtml.exe")


def parse_chunk(pdf: Path, first: int, last: int, tool: str) -> list[dict]:
    cmd = [tool, "-xml", "-i", "-stdout", "-f", str(first), "-l", str(last), str(pdf)]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", errors="replace")[:500])
    root = ET.fromstring(p.stdout)
    fonts: dict[str, float] = {}
    for f in root.findall("fontspec"):
        try:
            fonts[f.attrib.get("id", "")] = float(f.attrib.get("size", "10"))
        except ValueError:
            pass
    pages = []
    for page in root.findall("page"):
        words = []
        for t in page.findall("text"):
            text = "".join(t.itertext()).strip()
            if not text:
                continue
            try:
                x = float(t.attrib.get("left", "0"))
                y = float(t.attrib.get("top", "0"))
                w = float(t.attrib.get("width", "1"))
                h = float(t.attrib.get("height", "10"))
            except ValueError:
                continue
            size = fonts.get(t.attrib.get("font", ""), h)
            words.append({"text": text, "x": x, "y": y, "w": w, "h": h, "size": size})
        if words:
            pages.append(
                {
                    "number": int(page.attrib.get("number", "1")),
                    "width": float(page.attrib.get("width", "612")),
                    "height": float(page.attrib.get("height", "792")),
                    "words": words,
                }
            )
    return pages


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out")
    ap.add_argument("--checkpoint")
    ap.add_argument("--chunk", type=int, default=50)
    ap.add_argument("--stop-after", type=int, default=0, help="处理 N 页后停止（模拟 kill）")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--created-at", default="2026-01-01T00:00:00Z")
    ap.add_argument("--meta-out")
    args = ap.parse_args()
    pdf = Path(args.pdf)
    if not pdf.is_file():
        raise SystemExit(f"PDF not found: {pdf}")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    size = pdf.stat().st_size
    tracemalloc.start()
    pages: list[dict] = []
    next_page = 1
    if args.checkpoint and Path(args.checkpoint).is_file() and not args.reset:
        cp = json.loads(Path(args.checkpoint).read_text(encoding="utf-8"))
        if cp.get("pdf_sha") != sha:
            raise SystemExit("checkpoint PDF sha mismatch")
        pages = cp.get("pages", [])
        next_page = int(cp.get("next_page", 1))
    info = subprocess.run(
        [os.environ.get("PDFINFO", "C:/Program Files/Calibre2/app/bin/pdfinfo.exe"), str(pdf)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    m = __import__("re").search(r"Pages:\s+(\d+)", info.stdout.decode("utf-8", errors="replace"))
    total_pages = int(m.group(1)) if m else 0
    if total_pages <= 0:
        raise SystemExit("cannot determine PDF page count (pdfinfo)")
    processed_this_run = 0
    while next_page <= total_pages:
        last = min(next_page + args.chunk - 1, total_pages)
        got = parse_chunk(pdf, next_page, last, os.environ.get("PDFTOHTML", DEFAULT_PDFTOHTML))
        if not got:
            break
        pages.extend(got)
        processed_this_run += len(got)
        next_page = last + 1
        if args.checkpoint:
            Path(args.checkpoint).write_text(
                json.dumps({"pdf_sha": sha, "next_page": next_page, "pages": pages}, ensure_ascii=False),
                encoding="utf-8",
            )
        if args.stop_after and processed_this_run >= args.stop_after:
            break
    peak_mb = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
    tracemalloc.stop()
    if args.stop_after:
        print(json.dumps({"stopped": True, "pages": len(pages), "next_page": next_page, "peak_mb": round(peak_mb, 1)}))
        return 0
    req = {
        "source": {"name": pdf.name, "mime": "application/pdf", "bytes_sha": sha, "size": size},
        "created_at": args.created_at,
        "pages": pages,
        "lang": "en",
    }
    text = json.dumps(req, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    meta = {"pages": len(pages), "peak_mb": round(peak_mb, 1), "pdf_sha": sha, "bytes": size}
    if args.meta_out:
        Path(args.meta_out).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
