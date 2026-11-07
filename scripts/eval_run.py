#!/usr/bin/env python3
"""预注册评测出口：冻结协议 + harness 演练（**不伪造测量**）。

本脚本只做两件事：
1. 校验 protocol/eval/protocol.json（冻结、无打分键、反窄化指标在场）；
2. 用**明确标注 synthetic** 的夹具跑一遍 record_run + 演示 compare 的拒绝逻辑，
   证明 harness 能工作——但 synthetic 数据永远不会被当成证据（compare 直接拒）。

真实测量（measured）需要外部盲评，本仓不代跑（作者纪律：外部实测仅由作者显式触发）。

用法：
  python scripts/eval_run.py --write   # 写 results/ccos/eval_protocol.json
  python scripts/eval_run.py --check
  python scripts/eval_run.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import eval_harness as eh  # noqa: E402

OUT_REL = "results/ccos/eval_protocol.json"
SCHEMA = "nf-eval-protocol-report/1"
GUIDE = "修复指引："


def _fixture_items(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    """演练夹具：所有指标都按「占位」计，不代表真实测量。"""
    items = []
    samples = int(protocol["samples_per_task"])
    for cond in protocol["conditions"]:
        for task in protocol["tasks"]:
            for sample in range(1, samples + 1):
                items.append({
                    "condition": cond["id"], "task": task["id"], "sample": sample,
                    "values": {dim["id"]: 0 for dim in protocol["dimensions"]},
                })
    return items


def build_report() -> dict[str, Any]:
    protocol = eh.load_protocol(str(ROOT))
    fixture = eh.record_run(protocol, {"source": "synthetic",
                                       "items": _fixture_items(protocol)})
    synthetic_blocked = False
    blocked_reason = ""
    try:
        eh.compare(protocol, [fixture])
    except ValueError as exc:
        synthetic_blocked = True
        blocked_reason = str(exc)
    return {"schema": SCHEMA, "protocol": {
                "version": protocol["version"],
                "registered_at": protocol["registered_at"],
                "frozen_before_run": protocol["frozen_before_run"],
                "conditions": [c["id"] for c in protocol["conditions"]],
                "tasks": [t["id"] for t in protocol["tasks"]],
                "dimensions": [d["id"] for d in protocol["dimensions"]],
                "samples_per_task": protocol["samples_per_task"],
                "prohibitions": protocol["prohibitions"]},
            "harness": {"fixture_digest": fixture["digest"],
                        "synthetic_blocked": synthetic_blocked,
                        "blocked_reason": blocked_reason},
            "measurement": {"status": "not-run",
                            "why": "真实测量需外部盲评；本仓不代跑（作者纪律：外部实测由作者显式触发）"},
            "ok": synthetic_blocked}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_run", description="预注册评测：协议冻结 + harness 演练")
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
        print("OK 已写入 " + OUT_REL + "（协议 " + report["protocol"]["version"]
              + " · 对照组 " + str(len(report["protocol"]["conditions"])) + "）")
        return 0
    if args.check:
        path = ROOT / OUT_REL
        if not path.is_file():
            print("缺 " + OUT_REL + "（" + GUIDE + "跑 --write）", file=sys.stderr)
            return 1
        recorded = json.loads(path.read_text(encoding="utf-8"))
        if render(recorded) != render(report):
            print("评测报告与重算不一致（" + GUIDE + "重跑 --write）", file=sys.stderr)
            return 1
        print("OK 评测报告与重算一致")
        return 0 if report["ok"] else 1
    print(render(report), end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
