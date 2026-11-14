#!/usr/bin/env python3
# nf-io: inputs=protocol/legal.json,LICENSE,REUSE.toml,THIRD-PARTY-NOTICES.md outputs=-
"""法务/许可/出口 + 开源治理审计（NF-Final WP-0C）。

用法：
  python scripts/legal_audit.py            # 只读：任一条不满足即 exit 1
  python scripts/legal_audit.py --json     # 机读（issues + facts）
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core import legal  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="法务/许可/出口 + 开源治理审计")
    ap.add_argument("--json", action="store_true", help="打印机读结果")
    ap.add_argument("--repo", default=ROOT, help="仓库根（缺省 = 本脚本所在仓）")
    args = ap.parse_args(argv)
    issues, facts = legal.audit(args.repo)
    if args.json:
        print(json.dumps({"ok": not issues, "issues": issues, "facts": facts},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if not issues else 1
    print("== 法务/许可/治理审计 ==")
    print("  许可 %s · REUSE annotation %d · 第三方行 %d · 合同模板 %d · 加密组件 %d · 治理文件 %d"
          % (facts.get("license"), facts.get("reuse_annotations", 0),
             facts.get("third_party_rows", 0), facts.get("contracts", 0),
             facts.get("crypto_components", 0), facts.get("governance_files", 0)))
    for item in issues[:10]:
        print("  ✗ %s" % item, file=sys.stderr)
    return 0 if not issues else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
