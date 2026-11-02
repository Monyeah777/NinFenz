#!/usr/bin/env python3
"""Evidence CLI（CI 用）：生成/校验证据卡、导出契约规则表。

用法：
  python scripts/evidence_cli.py card --path docs/mcp.md [--contract 大语言模型] [--min-names 1] [--json]
  python scripts/evidence_cli.py verify --card /tmp/card.json [--json]
  python scripts/evidence_cli.py rules --contract 大语言模型 [--json]
退出码：0=通过/成功；1=校验不通过；2=参数/IO 错误。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import domain_rules, evidence_mcp  # noqa: E402
from core.meta_cockpit import cognition_event  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("card")
    c.add_argument("--path", required=True)
    c.add_argument("--contract", default="")
    c.add_argument("--min-names", type=int, default=evidence_mcp.COVERAGE_MIN_NAMES)
    c.add_argument("--min-fields", type=int, default=evidence_mcp.COVERAGE_MIN_FIELDS)
    c.add_argument("--min-rules", type=int, default=evidence_mcp.COVERAGE_MIN_RULES)
    c.add_argument("--json", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("--card", required=True)
    v.add_argument("--json", action="store_true")
    cev = sub.add_parser("cognition-event")
    cev.add_argument("--manifest", required=True)
    cev.add_argument("--journal", default="")
    cev.add_argument("--json", action="store_true")
    r = sub.add_parser("rules")
    r.add_argument("--contract", required=True)
    r.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        if args.cmd == "card":
            card = evidence_mcp.evidence_card(args.path, ROOT, args.contract, "",
                                              args.min_names, args.min_fields, args.min_rules)
            print(json.dumps(card, ensure_ascii=False, indent=2, sort_keys=True))
            if isinstance(card.get("contract"), dict):
                cov = card["contract"].get("coverage") or {}
                return 0 if cov.get("ok", True) else 1
            return 0
        if args.cmd == "verify":
            card = json.loads(Path(args.card).read_text(encoding="utf-8"))
            res = evidence_mcp.verify_card(card, ROOT)
            print(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if res["ok"] else 1
        if args.cmd == "cognition-event":
            ev = cognition_event.from_manifest_file(args.manifest, args.journal or None)
            print(json.dumps(ev, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.cmd == "rules":
            pack = evidence_mcp._resolve_contract(args.contract, ROOT)
            print(json.dumps(domain_rules.build_rules(str(pack["package"]), ROOT),
                             ensure_ascii=False, indent=2, sort_keys=True))
            return 0
    except (OSError, ValueError, KeyError) as exc:
        print("evidence-cli 失败：%s" % exc, file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
