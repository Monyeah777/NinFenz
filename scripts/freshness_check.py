#!/usr/bin/env python3
"""生成物新鲜度前置检查：**提交件 == 实时重算**（秒级，别等分片 25 分钟才发现）。

为什么有它（2026-11-05 实测教训，同一类事在 3 轮里犯了 3 次）：跑完整发布结论才发现
`protocol/role_coordinates.json` / `protocol/verification_report.json` 与实时重算不一致——
根因全是我「改了东西之后忘了重跑生成器」。分片里看见它要 25 分钟，在这里只要十几秒。

判定口径：只读、只比对（不写任何件）。每项给出修复命令，失败即 rc=1。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

#: (id, 人读名, 修复命令)——顺序稳定，便于报告与判据对账。
CHECKS = (
    ("role_coordinates", "职能坐标投影（protocol/role_coordinates.json）", "nf layers --write"),
    ("verify_report", "门检报告（protocol/verification_report.json）",
     "python scripts/verify_report.py --write"),
    ("conformance", "一致性报告（protocol/conformance_report.json）",
     "nf conformance --write"),
    ("audit", "审计件摘要（results/audit/*）", "nf audit rebind"),
)


def _run_role(root: str):
    from core import role_model
    issues, _stats = role_model.scan(root)
    return list(issues)


def _run_verify_report(root: str):
    from core import verify_report
    issues, _live = verify_report.check(root)
    return list(issues)


def _run_conformance(root: str):
    from core import conformance_report
    issues, _live = conformance_report.verify_committed(root)
    return list(issues)


def _run_audit(root: str):
    from core import audit
    issues, _warns, _stats = audit.scan(root)
    return list(issues)


RUNNERS = {
    "role_coordinates": _run_role,
    "verify_report": _run_verify_report,
    "conformance": _run_conformance,
    "audit": _run_audit,
}


def aggregate(rows: list) -> dict:
    """逐项结果 → {ok, issues, checked}（纯函数，便于单测）。"""
    issues = [row for row in rows if row.get("issues")]
    return {"ok": not issues, "checked": len(rows),
            "issues": [{"id": row["id"], "desc": row["desc"], "fix": row["fix"],
                        "issues": row["issues"][:6]} for row in issues]}


def collect(root: str, only: tuple = ()) -> list:
    """跑各项新鲜度检查 → 行列表（坏件/异常都折成 issue，不让整次检查崩掉）。"""
    rows = []
    for cid, desc, fix in CHECKS:
        if only and cid not in only:
            continue
        try:
            issues = RUNNERS[cid](root)
        except (OSError, ValueError, KeyError) as exc:
            issues = [f"新鲜度检查自身失败：{exc}（修复指引：先修这项判据，再谈新鲜度）"]
        rows.append({"id": cid, "desc": desc, "fix": fix, "issues": issues})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="freshness_check",
                                 description="生成物新鲜度前置检查（提交件 == 实时重算）")
    ap.add_argument("--json", action="store_true", help="机读输出")
    ap.add_argument("--only", default="", help="只跑这些项（逗号分隔 id；排障用）")
    ap.add_argument("--quiet", action="store_true", help="只打结论行")
    args = ap.parse_args(argv)
    only = tuple(x.strip() for x in args.only.split(",") if x.strip())
    rows = collect(str(ROOT), only)
    res = aggregate(rows)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.quiet:
        print(f"新鲜度：{res['checked']} 项 · 未过 {len(res['issues'])}")
    else:
        for row in rows:
            mark = "✓" if not row["issues"] else "✗"
            print(f"{mark} {row['desc']}")
            for issue in row["issues"][:6]:
                print(f"    {issue}")
            if row["issues"]:
                print(f"    修复：{row['fix']}")
        print(f"新鲜度：{res['checked']} 项 · 未过 {len(res['issues'])}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    sys.exit(main())
