#!/usr/bin/env python3
# nf-io: inputs=desktop/src/core,protocol/independence.json outputs=results/independence.json
"""生产/治理双平面 import 边界门禁（方案 §5.5 IN-01/IN-02/IN-04）。

用法：
  python scripts/check_independence.py            # 只读：生产/治理/共享闭包越界即 exit 1
  python scripts/check_independence.py --json     # 打印机读报告
  python scripts/check_independence.py --write    # 重算并落 results/independence.json
  python scripts/check_independence.py --check    # 断言在盘报告 == 实时重算（check49 用）
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core import independence as ind  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生产/治理双平面 import 边界")
    ap.add_argument("--write", action="store_true", help="重算并写 results/independence.json")
    ap.add_argument("--check", action="store_true", help="断言在盘报告 == 实时重算")
    ap.add_argument("--json", action="store_true", help="打印机读报告")
    ap.add_argument("--repo", default=ROOT, help="仓库根（缺省 = 本脚本所在仓）")
    args = ap.parse_args(argv)

    if args.write:
        issues, doc = ind.write(args.repo)
        print("== 写边界报告 ==")
        print("  %s已写入 %s（模块 %d · 跨界 %d）"
              % ("" if not issues else "（仍有问题）", ind.REPORT_REL,
                 doc["counts"]["modules"], doc["counts"]["forbidden_edges"]))
        for i in issues[:10]:
            print("  ✗ %s" % i, file=sys.stderr)
        return 1 if issues else 0
    if args.check:
        issues = ind.check_committed(args.repo)
        if issues:
            for i in issues[:10]:
                print("  ✗ %s" % i, file=sys.stderr)
            return 1
        print("  ✓ 边界报告与实时重算一致")
        return 0

    doc = ind.build_report(args.repo)
    if args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if doc["ok"] else 1
    print("== 生产/治理双平面边界 ==")
    print("  模块 %d · 生产 %d · 治理 %d · 共享 %d · 跨界 %d · 动态白名单 %d"
          % (doc["counts"]["modules"], doc["counts"]["production"],
             doc["counts"]["governance"], doc["counts"]["shared"],
             doc["counts"]["forbidden_edges"], doc["counts"]["dynamic_allow"]))
    for i in doc["findings"][:10]:
        print("  ✗ %s" % i, file=sys.stderr)
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
