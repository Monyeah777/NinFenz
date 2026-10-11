#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""canonical JSON 面（P-C1 的 python 实现）：读 JSON → 打印仓库规范化字节（**无尾换行**）。

为什么单独成脚本：跨语言契约对拍需要一个「进程级、可被 harness 调用」的实现面；
规范化本体在 core/attest.py（唯一实现），此处只做 CLI 包装，不复制规范化逻辑。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import attest  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="canonical JSON（仓库口径）")
    ap.add_argument("--file", required=True, help="输入 JSON 文件")
    args = ap.parse_args()
    doc = json.loads(Path(args.file).read_text(encoding="utf-8"))
    sys.stdout.buffer.write(attest.canonical(doc))
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
