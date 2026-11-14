#!/usr/bin/env python3
# nf-io: inputs=protocol/ops.json,protocol/vendors.json outputs=results/ops/drills.json
"""运维演练门禁（NF-Final WP-0D）：IR 桌面演练 + 恢复演练 + 披露演练 + 供应商退出就绪。

用法：
  python scripts/ops_drill.py            # 只读：登记/演练不通过即 exit 1
  python scripts/ops_drill.py --json     # 打印机读报告
  python scripts/ops_drill.py --run      # 重算并落 results/ops/drills.json
  python scripts/ops_drill.py --check    # 断言在盘报告 == 实时重算
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core import ops  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="运维/事件/BCP/供应商登记与演练")
    ap.add_argument("--run", action="store_true", help="重算并写 results/ops/drills.json")
    ap.add_argument("--check", action="store_true", help="断言在盘报告 == 实时重算")
    ap.add_argument("--json", action="store_true", help="打印机读报告")
    ap.add_argument("--repo", default=ROOT, help="仓库根（缺省 = 本脚本所在仓）")
    args = ap.parse_args(argv)

    if args.run:
        issues, doc = ops.write(args.repo)
        print("== 运维演练 ==")
        print("  %s已写入 %s（演练 %d · vendors %d · findings %d）"
              % ("" if not issues else "（仍有问题）", ops.REPORT_REL,
                 doc["counts"].get("drills", 0), doc["counts"].get("vendors", 0),
                 len(issues)))
        for i in issues[:10]:
            print("  ✗ %s" % i, file=sys.stderr)
        return 1 if issues else 0
    if args.check:
        issues = ops.check_committed(args.repo)
        if issues:
            for i in issues[:10]:
                print("  ✗ %s" % i, file=sys.stderr)
            return 1
        print("  ✓ 演练报告与实时重算一致")
        return 0

    doc = ops.build_report(args.repo)
    if args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if doc["ok"] else 1
    print("== 运维演练 ==")
    print("  严重度 %d · runbook %d 步 · 演练 %d · vendors %d"
          % (doc["counts"].get("severities", 0), doc["counts"].get("runbook_steps", 0),
             doc["counts"].get("drills", 0), doc["counts"].get("vendors", 0)))
    for drill in doc.get("drills") or []:
        print("  [%s] %s（%s）" % (drill.get("status"), drill.get("id"), drill.get("kind")))
    for i in doc["findings"][:10]:
        print("  ✗ %s" % i, file=sys.stderr)
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
