#!/usr/bin/env python3
"""重新生成 Android PDF/UA 内置字体子集（GB2312 + 当前 UI 文案）。

用法：
  python -m pip install --target /d/tmp/fonttools fonttools
  PYTHONPATH=/d/tmp/fonttools python app/scripts/subset_font.py --source /path/NotoSansSC-VF.ttf

产物覆盖 app/android/app/src/main/assets/fonts/NotoSansSC-VF.ttf。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "app/android/app/src/main/assets/fonts/NotoSansSC-VF.ttf"
RES = ROOT / "app/android/app/src/main/res"


def chars() -> str:
    s = {chr(i) for i in range(0x20, 0x7F)}
    for b1 in range(0xB0, 0xF8):
        for b2 in range(0xA1, 0xFF):
            try:
                s.add(bytes([b1, b2]).decode("gb2312"))
            except Exception:
                pass
    for b1 in range(0xA1, 0xAA):
        for b2 in range(0xA1, 0xFF):
            try:
                s.add(bytes([b1, b2]).decode("gb2312"))
            except Exception:
                pass
    s.update('“”‘’—…、。，；：！？（）《》【】·×÷≤≥→←↑↓')
    for p in RES.glob("values*/strings.xml"):
        try:
            for el in ET.parse(p).getroot().iter():
                if el.text:
                    s.update(el.text)
        except Exception:
            pass
    return "".join(sorted(s))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="完整 Noto Sans SC TTF")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    text = Path("D:/tmp/nf-subset-chars.txt")
    text.write_text(chars(), encoding="utf-8")
    cmd = [
        sys.executable, "-m", "fontTools.subset", args.source,
        "--text-file=" + str(text),
        "--output-file=" + args.out,
        "--no-hinting", "--desubroutinize", "--layout-features=*",
    ]
    print("chars:", len(chars()))
    subprocess.run(cmd, check=True)
    print("wrote:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
