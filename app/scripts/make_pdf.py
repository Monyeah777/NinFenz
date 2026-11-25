#!/usr/bin/env python3
"""生成确定性测试 PDF（Helvetica，单栏/双栏，标题/正文/表格/脚注）。仅用于基准。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def page_content(n: int, columns: int = 1) -> str:
    out = ["BT /F1 18 Tf 40 755 Td (" + esc(f"Document {n}") + ") Tj ET"]
    x_left = 40
    x_right = 320
    y = 720
    for i in range(28):
        text = f"Page {n} line {i + 1}: the border town waits for the last lantern."
        col = 0 if columns == 1 or i % 2 == 0 else 1
        x = x_left if col == 0 else x_right
        out.append("BT /F1 10 Tf " + str(x) + " " + str(y) + " Td (" + esc(text) + ") Tj ET")
        if columns == 1 or col == 1:
            y -= 14
    # 表格（两列）
    ty = 250
    for row, (a, b) in enumerate([("Place", "Risk"), ("North gate", "High"), ("Inn", "Low")]):
        out.append("BT /F1 9 Tf 40 " + str(ty) + " Td (" + esc(a) + ") Tj ET")
        out.append("BT /F1 9 Tf 200 " + str(ty) + " Td (" + esc(b) + ") Tj ET")
        ty -= 12
    out.append("BT /F1 8 Tf 40 55 Td (" + esc(f"[1] footnote for page {n}") + ") Tj ET")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=500)
    ap.add_argument("--out", required=True)
    ap.add_argument("--columns", type=int, default=1)
    ap.add_argument("--meta")
    args = ap.parse_args()
    n = args.pages
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{4 + i} 0 R" for i in range(n))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    contents_start = 4 + n
    for i in range(n):
        cid = contents_start + i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {cid} 0 R >>".encode()
        )
    for i in range(n):
        content = page_content(i + 1, args.columns).encode("latin-1", errors="replace")
        objects.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(buf)
    buf += f"xref\n0 {len(objects) + 1}\n".encode()
    buf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        buf += f"{off:010d} 00000 n \n".encode()
    buf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(args.out).write_bytes(buf)
    if args.meta:
        Path(args.meta).write_text(
            json.dumps({"pages": n, "columns": args.columns, "bytes": len(buf), "out": args.out}, ensure_ascii=False),
            encoding="utf-8",
        )
    print(json.dumps({"pages": n, "bytes": len(buf)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
