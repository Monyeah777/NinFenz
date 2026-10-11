#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NFA-L/R 规则层 CLI：读 JSON 规则文档 → 定点推导（只读）。

用法：
  python scripts/nfal_rules.py --file rules.json [--fuel 1000] [--json]
退出码：INVALID 或 FUEL_EXHAUSTED → 1（燃料不足**不得**当成功）。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import nfal_rules as nr  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NFA-L/R 规则求值（只读）")
    ap.add_argument("--file", required=True)
    ap.add_argument("--fuel", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = json.loads(Path(args.file).read_text(encoding="utf-8"))
    got = nr.evaluate(doc, fuel=args.fuel or None)
    if args.json:
        print(json.dumps(got, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== NFA-L/R 求值 ==")
        print("  status=%s facts=%d fuel=%d/%d rounds=%d"
              % (got["status"], len(got["facts"]), got["fuel_used"], got["fuel_total"],
                 got["rounds"]))
        for i in got.get("issues") or []:
            print("  [FAIL] %s" % i, file=sys.stderr)
    return 1 if got["status"] in ("INVALID", "FUEL_EXHAUSTED") else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
