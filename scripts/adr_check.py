#!/usr/bin/env python3
"""架构裁决与文档台账门禁：ADR 可校验、台账单一真源、与仓库现实对账。

为什么（2026-11-08）：16 份架构文档互相打架（双核/ABI/多租户/命名），散文裁决下一次还会被覆盖。
本门把裁决做成数据 + 校验 + 对账：
- ADR：字段完整、falsifier 必填、同 topic 至多一条 current、supersedes 无环、evidence 在场；
- 台账：16 份各一状态、superseded 指向在场 current、同 topic 至多一条 current；
- 对账：reasoning/ 是否在 HEAD 与 ADR-004 声明一致；evidence 文件是否都在场。

用法：
  python scripts/adr_check.py --write   # 写 results/ccos/adr_reconcile.json
  python scripts/adr_check.py --check   # 校验提交件 == 重算
  python scripts/adr_check.py --json    # 打印
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import adr  # noqa: E402

OUT_REL = "results/ccos/adr_reconcile.json"
SCHEMA = "nf-adr-report/1"
GUIDE = "修复指引："
EXPECTED_DOCS = 16


def build_report() -> dict[str, Any]:
    bundle = adr.load(str(ROOT))
    res = adr.reconcile(str(ROOT))
    ledger = bundle["ledger"]
    findings = list(res["findings"])
    if len(ledger["docs"]) != EXPECTED_DOCS:
        findings.append({"code": "R4", "detail": "台账文档数 " + str(len(ledger["docs"]))
                                               + " ≠ 16（" + GUIDE + "补齐或说明）"})
    return {"schema": SCHEMA, "ok": not findings, "findings": findings,
            "counts": res["counts"],
            "adrs": [{"id": a["id"], "status": a["status"], "topic": a["topic"]}
                     for a in bundle["adr"]["adrs"]],
            "docs": [{"name": d["name"], "status": d["status"],
                      "superseded_by": d.get("superseded_by"), "adr": d.get("adr")}
                     for d in ledger["docs"]]}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="adr_check", description="ADR/台账门禁与对账")
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
        print("OK 已写入 " + OUT_REL + "（ADR " + str(report["counts"]["adrs"])
              + " 条 · 文档 " + str(report["counts"]["docs"]) + " 份）")
        return 0
    if args.check:
        path = ROOT / OUT_REL
        if not path.is_file():
            print("缺 " + OUT_REL + "（" + GUIDE + "跑 --write）", file=sys.stderr)
            return 1
        recorded = json.loads(path.read_text(encoding="utf-8"))
        if render(recorded) != render(report):
            print("对账报告与重算不一致（" + GUIDE + "重跑 --write）", file=sys.stderr)
            return 1
        print("OK 对账报告与重算一致")
        return 0 if report["ok"] else 1
    print(render(report), end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
