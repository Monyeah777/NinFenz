#!/usr/bin/env python3
"""吸收项能力面（生产入口）：列出 / 自检 吸收项契约电池。

为什么有它：48 个吸收件此前只被各自的单测引用（test_dead_code 的「路径不可达」墓碑）。
本脚本是它们的**生产调用面**：电池逐项真调用入口并与 protocol/capability_contracts.json
里的黄金样例比对。只读；`--check` 任一项不符即 exit 1。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import capability_battery as cb  # noqa: E402 - 承重件在 desktop/src，脚本须能独立运行


def main(argv=None):
    ap = argparse.ArgumentParser(description="吸收项能力面（契约电池；只读）")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", action="store_true", help="结构化输出")
    ap.add_argument("--check", action="store_true", help="任一项契约不符即 exit 1")
    args = ap.parse_args(argv)
    doc = cb.run(args.root)
    if args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== 吸收项契约电池（%d 项）==" % doc["total"])
        for r in doc["rows"]:
            print("  %s %-24s %s.%s" % ("OK" if r["ok"] else "NG", r["id"],
                                        r["module"], r["entry"]))
            for p in r["problems"]:
                print("       %s" % p)
        print("  项 %d · 通过 %d · 未通过 %d" % (doc["total"], doc["passed"], doc["failed"]))
    return 1 if (args.check and doc["failed"]) else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
