#!/usr/bin/env python3
# nf-io: inputs=desktop/src/core,scripts,tracked files outputs=results/cq/*
"""全仓 CQ0/CQ1 扫描（NF-Final WP-0H）：工具矩阵 + 全量自动扫描 + 基线/热点。

用法：
  python scripts/cq_scan.py            # 只读：打印摘要（P0>0 即 exit 1）
  python scripts/cq_scan.py --run      # 重算并落 results/cq/{toolchain,scan}.json + findings/hotspots
  python scripts/cq_scan.py --check    # 断言扫描件指纹（HEAD/工作树/工具版本）新鲜
  python scripts/cq_scan.py --json     # 机读摘要
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core import cq_scan  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="全仓 CQ0/CQ1 扫描")
    ap.add_argument("--run", action="store_true", help="重算并写 results/cq/*")
    ap.add_argument("--check", action="store_true", help="断言扫描件新鲜（指纹）")
    ap.add_argument("--json", action="store_true", help="机读摘要")
    ap.add_argument("--repo", default=ROOT, help="仓库根（缺省 = 本脚本所在仓）")
    args = ap.parse_args(argv)

    if args.run:
        issues, doc = cq_scan.write(args.repo)
        tc = doc["toolchain"]
        scan = doc["scan"]
        print("== CQ 扫描 ==")
        print("  工具 %d（blocked %s）· 维度 %d · findings P0=%d P1=%d P2=%d P3=%d"
              % (len(tc["tools"]), ",".join(tc.get("blocked") or []) or "无",
                 len(scan["dimensions"]), scan["findings_counts"]["P0"],
                 scan["findings_counts"]["P1"], scan["findings_counts"]["P2"],
                 scan["findings_counts"]["P3"]))
        for item in issues[:10]:
            print("  ✗ %s" % item, file=sys.stderr)
        return 1 if scan["p0"] else 0
    if args.check:
        issues = cq_scan.check(args.repo)
        if issues:
            for item in issues[:10]:
                print("  ✗ %s" % item, file=sys.stderr)
            return 1
        print("  ✓ CQ 扫描件新鲜（指纹一致）")
        return 0

    tc, scan = cq_scan.build(args.repo)
    if args.json:
        print(json.dumps({"toolchain": tc, "scan": scan},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if not scan["p0"] else 1
    print("== CQ 扫描 ==")
    print("  P0=%d P1=%d P2=%d P3=%d · 热点 %d"
          % (scan["findings_counts"]["P0"], scan["findings_counts"]["P1"],
             scan["findings_counts"]["P2"], scan["findings_counts"]["P3"],
             len(scan.get("hotspots") or [])))
    return 0 if not scan["p0"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
