#!/usr/bin/env python3
"""Evidence CLI（CI 用）：生成/校验证据卡、导出契约规则表。

用法：
  python scripts/evidence_cli.py card --path docs/mcp.md [--contract 大语言模型] [--min-names 1] [--json]
  python scripts/evidence_cli.py verify --card /tmp/card.json [--json]
  python scripts/evidence_cli.py rules --contract 大语言模型 [--json]
  python scripts/evidence_cli.py cognition-query [--session S] [--status pass] [--digest D] [--limit 50] [--json]
  python scripts/evidence_cli.py cognition-gc [--keep-last N] [--keep-digest D ...] [--config FILE]
      [--audit] [--canary] [--apply] [--json]
  python scripts/evidence_cli.py cognition-audits [--policy-digest D] [--has-removed] [--limit 50] [--json]
  python scripts/evidence_cli.py cognition-audit-summary [--json]
  python scripts/evidence_cli.py cognition-audit-alerts [--config FILE] [--record] [--json]
  python scripts/evidence_cli.py cognition-alert-history [--json]
  python scripts/evidence_cli.py cognition-alert-trend [--json]
  （--audit：写确定性审计记录 <store>/audit/<digest>.json；--canary：在 <store>/canary 影子库真跑 apply）
  （cognition-gc 默认 dry-run（策略 dry_run 缺省 true），只有 --apply 才真正删事件并重建索引；
    保留策略优先级：显式参数 > NF_COCKPIT_RETENTION(JSON) > --config/retention.json > 默认）
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
    q = sub.add_parser("cognition-query")
    q.add_argument("--session", default="")
    q.add_argument("--status", default="")
    q.add_argument("--digest", default="")
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--json", action="store_true")
    g = sub.add_parser("cognition-gc")
    g.add_argument("--keep-last", type=int, default=None,
                   help="保留最近 N 个会话（缺省走策略/默认 20）")
    g.add_argument("--keep-digest", action="append", default=[])
    g.add_argument("--config", default="",
                   help="保留策略 JSON 文件（缺省读 <store>/retention.json）")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--audit", action="store_true",
                   help="写确定性审计记录（不删真实库）")
    g.add_argument("--canary", action="store_true",
                   help="在 <store>/canary 影子库真跑 apply（真实库不动）")
    g.add_argument("--json", action="store_true")
    au = sub.add_parser("cognition-audits")
    au.add_argument("--policy-digest", default="")
    au.add_argument("--has-removed", action="store_true")
    au.add_argument("--limit", type=int, default=50)
    au.add_argument("--json", action="store_true")
    aus = sub.add_parser("cognition-audit-summary")
    aus.add_argument("--json", action="store_true")
    al = sub.add_parser("cognition-audit-alerts")
    al.add_argument("--config", default="",
                    help="告警规则 JSON 文件（缺省读 <store>/alert_rules.json）")
    al.add_argument("--record", action="store_true",
                    help="把报告落盘 <store>/alerts/<digest>.json（同 digest 不重写）")
    al.add_argument("--json", action="store_true")
    ah = sub.add_parser("cognition-alert-history")
    ah.add_argument("--json", action="store_true")
    at = sub.add_parser("cognition-alert-trend")
    at.add_argument("--json", action="store_true")
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
        if args.cmd == "cognition-query":
            rows = cognition_event.query(
                session_id=args.session or None,
                status=args.status or None,
                digest=args.digest or None,
                limit=args.limit)
            if args.json:
                print(json.dumps(rows, ensure_ascii=False, indent=2,
                                 sort_keys=True))
            else:
                for row in rows:
                    print("%s\t%s\t%s" % (row.get("digest"),
                                           row.get("session_id"),
                                           row.get("status")))
            return 0
        if args.cmd == "cognition-gc":
            if args.audit or args.canary:
                audit = cognition_event.gc_audit(
                    config=args.config or None, canary=bool(args.canary))
                if args.json:
                    print(json.dumps(audit, ensure_ascii=False, indent=2,
                                     sort_keys=True))
                else:
                    print("audit=%s policy_digest=%s removed=%d dry_run=%s%s"
                          % (audit["digest"], audit["policy_digest"],
                             len(audit["removed"]), audit["dry_run"],
                             "" if "canary" not in audit else
                             " canary=%s" % json.dumps(audit["canary"],
                                                       ensure_ascii=False,
                                                       sort_keys=True)))
                return 0
            result = cognition_event.gc(
                keep_last=args.keep_last,
                keep_digests=tuple(args.keep_digest),
                dry_run=False if args.apply else None,
                config=args.config or None)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2,
                                 sort_keys=True))
            else:
                print("dry_run=%s kept=%d removed=%d sessions_kept=%d "
                      "sessions_removed=%d policy=%s"
                      % (result["dry_run"], len(result["kept"]),
                         len(result["removed"]), result["sessions_kept"],
                         result["sessions_removed"],
                         json.dumps(result["policy"], ensure_ascii=False,
                                    sort_keys=True)))
            return 0
        if args.cmd == "cognition-audits":
            rows = cognition_event.query_audits(
                policy_digest=args.policy_digest or None,
                has_removed=True if args.has_removed else None,
                limit=args.limit)
            if args.json:
                print(json.dumps(rows, ensure_ascii=False, indent=2,
                                 sort_keys=True))
            else:
                for row in rows:
                    print("%s\t%s\tremoved=%d" % (
                        row.get("digest"), row.get("policy_digest"),
                        len(row.get("removed") or [])))
            return 0
        if args.cmd == "cognition-audit-summary":
            summary = cognition_event.audit_summary()
            print(json.dumps(summary, ensure_ascii=False, indent=2,
                             sort_keys=True))
            return 0
        if args.cmd == "cognition-audit-alerts":
            if args.record:
                alert = cognition_event.record_alert_report(
                    config=args.config or None)
            else:
                alert = cognition_event.audit_anomalies(
                    config=args.config or None)
            if args.json:
                print(json.dumps(alert, ensure_ascii=False, indent=2,
                                 sort_keys=True))
            elif alert["clean"]:
                print("audit alerts clean（无异常）")
            else:
                print("audit alerts：%d 条 finding%s"
                      % (len(alert["findings"]),
                         "" if len(alert["findings"]) == 1 else "s"))
                for finding in alert["findings"]:
                    print("  [%s] %s audit=%s %s"
                          % (finding["severity"], finding["kind"],
                             finding.get("audit") or "-",
                             finding["detail"]))
            return 0 if alert["clean"] else 1
        if args.cmd == "cognition-alert-history":
            history = cognition_event.audit_alert_history()
            print(json.dumps(history, ensure_ascii=False, indent=2,
                             sort_keys=True))
            return 0
        if args.cmd == "cognition-alert-trend":
            trend = cognition_event.audit_alert_trend()
            print(json.dumps(trend, ensure_ascii=False, indent=2,
                             sort_keys=True))
            return 0
    except (OSError, ValueError, KeyError) as exc:
        print("evidence-cli 失败：%s" % exc, file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):   # 入口钉 UTF-8 stdio（test_stdio_encoding）
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
