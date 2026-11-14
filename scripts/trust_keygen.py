#!/usr/bin/env python3
"""本地 HMAC key 生成入口（0600；不覆盖；不生成非对称私钥）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import key_material  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成 HMAC key（0600，拒绝覆盖）")
    ap.add_argument("--out", required=True, help="key 文件路径（hex，0600）")
    ap.add_argument("--alg", default="hmac-sha256", choices=["hmac-sha256"])
    args = ap.parse_args(argv)
    try:
        meta = key_material.generate_hmac_key(args.out, args.alg)
    except (OSError, ValueError) as exc:
        print(f"不可判定：{exc}", file=sys.stderr)
        return 2
    print(json.dumps(meta, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
