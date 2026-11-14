#!/usr/bin/env python3
"""离线验证入口（cc_verify 骨架的 CI 面；计划 §8.4）。

用法::

    python scripts/trust_verify.py --bundle B.json --policy P.json [--json] [--out nf-verify.json]

退出码：0 = 达到策略；1 = 验证失败（bundle 自洽性/结构失败）；2 = 不可判定（缺锚/参数/策略）。
边界：T0 可全离线；T1 需签名、T2 需 RFC 3161、T3 需 witness、T4 需公共锚——这些核验在 G2/G4
接线，本入口如实把它们标成缺项并 exit 2，不冒充等级、不写「合规」。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, json_doc  # noqa: E402
from core.trust import verify as tv  # noqa: E402


def _load(path: str, what: str) -> dict:
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"缺 {what}：{path}（修复指引：传存在的 JSON 文件路径）")
    return json_doc.load(target, dict, what=what)


def _summary(report: dict) -> str:
    lines = [
        f"subject: {report['subject']['kind']} {report['subject']['digest'][:16]}",
        f"level: required={report['level']['required']} achieved={report['level']['achieved']}",
    ]
    for check in report["checks"]:
        lines.append(f"check {check['id']}: {'ok' if check['ok'] else 'FAIL'} — {check['detail']}")
    for issue in report["issues"]:
        lines.append(f"issue {issue['code']}: {issue['message']}")
        lines.append(f"  fix: {issue['fix']}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="离线验证 claim bundle（nf-verify/1）")
    ap.add_argument("--bundle", required=True, help="nf-claim-bundle/1 JSON")
    ap.add_argument("--policy", required=True, help="nf-trust-policy/1 JSON")
    ap.add_argument("--root", default=str(ROOT), help="仓库根（读冻结 schema 用）")
    ap.add_argument("--json", action="store_true", help="输出 nf-verify/1 报告 JSON")
    ap.add_argument("--out", default="", help="把报告写入文件（原子写）")
    args = ap.parse_args(argv)
    try:
        bundle = _load(args.bundle, "bundle")
        policy = _load(args.policy, "policy")
        result = tv.verify(bundle, policy, root=args.root)
    except (OSError, ValueError) as exc:
        print(f"不可判定：{exc}", file=sys.stderr)
        return tv.EXIT_UNDECIDABLE
    report = result["report"]
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        atomic_write.write_text(Path(args.out), text)
    if args.json:
        sys.stdout.write(text)
    else:
        sys.stdout.write(_summary(report))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
