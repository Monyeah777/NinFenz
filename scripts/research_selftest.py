#!/usr/bin/env python3
"""Research 入口自检（生产面）：真调用 App 门面/导入/PBE/约束/灰度/实验健康。

为什么有它：这 8 个 `core/research` 模块此前只被各自单测 import，
`test_dead_code` 判「路径不可达」的墓碑。本脚本是它们的可调用入口——
同一份样例、确定性输出；`--check` 任一入口失败即 exit 1。

    python scripts/research_selftest.py --check
    python scripts/research_selftest.py --json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.research import runtime  # noqa: E402 - 承重件在 desktop/src，脚本须能独立运行


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="research 入口自检（只读、确定性）")
    ap.add_argument("--json", action="store_true", help="结构化输出")
    ap.add_argument("--check", action="store_true", help="任一项失败即 exit 1")
    args = ap.parse_args(argv)
    doc = runtime.selftest()
    if args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== research 入口自检（%d 项）==" % doc["total"])
        for row in doc["rows"]:
            print("  %s %-18s %s" % ("OK" if row["ok"] else "NG",
                                     row["module"], row["detail"]))
        print("  项 %d · 通过 %d · 未通过 %d" % (doc["total"], doc["passed"], doc["failed"]))
    return 1 if (args.check and doc["failed"]) else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
