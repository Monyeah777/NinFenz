#!/usr/bin/env python3
"""闭包审计：核对每条断言引用的判据是否真实在场，并统计 closed / debt。

为什么（2026-11-08）：前 14 轮攒了 15 个模块、250+ 项判据，但没有一份统一台账。
本脚本把「声称完成」压成可核对的数据：引用不存在的测试方法 → fail-closed
（这正是第一次跑就抓到的错）。

用法：
  python scripts/closure_audit.py --write   # 写 results/ccos/closure.json
  python scripts/closure_audit.py --check   # 校验提交件 == 重算
  python scripts/closure_audit.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import closure  # noqa: E402

OUT_REL = "results/ccos/closure.json"
SCHEMA = "nf-closure-report/1"
GUIDE = "修复指引："


def build_report() -> dict[str, Any]:
    doc = closure.load(str(ROOT))
    summary = closure.summary(doc)
    rows = []
    for item in doc["entries"]:
        rows.append({"id": item["id"], "module": item["module"],
                     "status": item["status"], "claim": item["claim"],
                     "criteria": ["::".join(ref) for ref in item["criteria"]],
                     "reverse_fixture": item["reverse_fixture"],
                     "debt": item.get("debt", "")})
    return {"schema": SCHEMA, "ok": True, "summary": summary, "rows": rows,
            "note": "closed = 有判据 + 有反例；debt = 已写明债务。"
                    "判据引用由 AST 核对真实存在。"}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="closure_audit", description="闭包台账审计")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        report = build_report()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(report), encoding="utf-8")
        s = report["summary"]
        print("OK 已写入 " + OUT_REL + "（" + str(s["total"]) + " 条：closed "
              + str(s["by_status"].get("closed", 0)) + " · debt "
              + str(s["by_status"].get("debt", 0)) + "）")
        return 0
    if args.check:
        path = ROOT / OUT_REL
        if not path.is_file():
            print("缺 " + OUT_REL + "（" + GUIDE + "跑 --write）", file=sys.stderr)
            return 1
        recorded = json.loads(path.read_text(encoding="utf-8"))
        if render(recorded) != render(report):
            print("闭包报告与重算不一致（" + GUIDE + "重跑 --write）", file=sys.stderr)
            return 1
        print("OK 闭包报告与重算一致")
        return 0
    if args.json:
        print(render(report), end="")
        return 0
    s = report["summary"]
    print("== 闭包审计（" + str(s["total"]) + " 条）==")
    for row in report["rows"]:
        mark = "✓" if row["status"] == "closed" else "债"
        print("  " + mark + " " + row["id"] + " [" + row["module"] + "] " + row["claim"][:48])
        print("      判据：" + "、".join(row["criteria"]))
        if row["debt"]:
            print("      债务：" + row["debt"][:60])
    print("  closed " + str(s["by_status"].get("closed", 0)) + " · debt "
          + str(s["by_status"].get("debt", 0)))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
