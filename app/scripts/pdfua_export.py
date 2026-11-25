#!/usr/bin/env python3
"""桌面 PDF/UA 桥：DOCX -> LibreOffice PDF/UA -> 标准 RoleMap 清理 -> veraPDF。"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import pikepdf

STD = {"/Quote", "/Note", "/Reference", "/BibEntry", "/Code", "/Span", "/P", "/H", "/H1", "/H2", "/H3", "/H4", "/H5", "/H6", "/Table", "/TR", "/TH", "/TD", "/L", "/LI", "/Lbl", "/LBody", "/Figure", "/Caption", "/Document", "/Sect", "/Div", "/Art", "/Part", "/Aside"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--soffice", default="D:/nf-validators/LibreOffice/program/soffice.exe")
    ap.add_argument("--vera", default="D:/nf-validators/verapdf/verapdf-cli.jar")
    args = ap.parse_args()
    docx = Path(args.docx)
    if not docx.is_file():
        raise SystemExit("DOCX not found")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    profile = out.parent / "lo-profile"
    p = subprocess.run([
        args.soffice, "--headless", "--norestore", f"-env:UserInstallation=file:///{profile.as_posix()}",
        "--convert-to", 'pdf:writer_pdf_Export:{"UseTaggedPDF":{"type":"boolean","value":"true"},"PDFUACompliance":{"type":"boolean","value":"true"}}',
        "--outdir", str(out.parent), str(docx),
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    produced = out.parent / (docx.stem + ".pdf")
    if p.returncode != 0 or not produced.is_file():
        print(p.stdout.decode("utf-8", errors="replace")[-500:])
        return 1
    with pikepdf.open(produced) as pdf:
        root = pdf.Root.get("/StructTreeRoot")
        if root is None:
            print("missing StructTreeRoot")
            return 1
        rm = root.get("/RoleMap")
        if rm is not None:
            for key in list(rm.keys()):
                if key in STD:
                    del rm[key]
        pdf.save(out)
    v = subprocess.run(["java", "-cp", args.vera, "org.verapdf.apps.GreenfieldCliWrapper", "-f", "ua1", "--format", "text", str(out)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    text = v.stdout.decode("utf-8", errors="replace")
    print(text[-300:])
    return 0 if "PASS" in text else 1


if __name__ == "__main__":
    sys.exit(main())
