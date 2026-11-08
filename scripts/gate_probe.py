#!/usr/bin/env python3
"""门禁负向用例探针：量「每个闸门里有没有至少一条拒绝型测试」。

为什么（第 76 轮）：设计里有一条「红不了的门禁等于没有门禁」。现状是我们只有零星变异测试
（同构矩阵 5 条）。要改进先要量：本探针用**命名代理**统计——测试名里出现
`bad/invalid/reject/tamper/mutate/cannot/must_fail/wrong/forged` 之一，即视为「拒绝型用例」。

诚实边界：命名代理会漏（有的拒绝用例名字很普通）也会误（有的只是名字像）。所以本件只出**比率与清单**，
不做 pass/fail 判定；要判定请用逐条变异测试（见 `test_isomorphism_matrix.KILL_TESTS`）。

用法：python scripts/gate_probe.py [--write] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
OUT_REL = "results/ccos/gate_negative_tests.json"
SCHEMA = "nf-gate-negative-tests/1"

#: 拒绝型测试的命名代理（宁可漏判，也不要误报成「已经覆盖」）
NEGATIVE_HINTS = ("bad", "invalid", "reject", "tamper", "mutat", "cannot",
                  "must_fail", "wrong", "forged", "refuse", "denied")


def _gate_rows() -> list[dict[str, str]]:
    """读 precheck 的闸门表（只读；不复制闸门逻辑）。"""
    import precheck  # 同目录脚本

    return [{"id": gid, "module": mod} for gid, mod in
            list(precheck.GATES) + list(precheck.SLOW_GATES)]


def _negative_tests(module: str) -> list[str]:
    """从测试模块源码里找拒绝型测试名（按命名代理）。"""
    parts = module.split(".")
    path = None
    for i in range(len(parts), 0, -1):
        cand = ROOT.joinpath(*parts[:i]).with_suffix(".py")
        if cand.is_file():
            path = cand
            break
    if path is None:
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    names = re.findall(r"def (test_[a-zA-Z0-9_]+)\(", text)
    return [n for n in names if any(h in n.lower() for h in NEGATIVE_HINTS)]


def build() -> dict[str, Any]:
    rows = []
    for row in _gate_rows():
        neg = _negative_tests(row["module"])
        rows.append({"id": row["id"], "module": row["module"],
                     "negative_tests": neg, "count": len(neg),
                     "has_negative": bool(neg)})
    total = len(rows)
    covered = sum(1 for r in rows if r["has_negative"])
    return {"schema": SCHEMA, "gates": total, "gates_with_negative": covered,
            "ratio": round(covered / total, 6) if total else 0.0,
            "missing": [r["id"] for r in rows if not r["has_negative"]],
            "rows": rows,
            "note": "命名代理，只作趋势；判定用逐条变异测试（KILL_TESTS）"}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate_probe",
                                 description="门禁负向用例探针（命名代理，只出比率与清单）")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = build()
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(doc), encoding="utf-8")
        print("OK 已写入 " + OUT_REL + "（闸门 " + str(doc["gates"]) + " · 有拒绝型 "
              + str(doc["gates_with_negative"]) + " · 比率 " + str(doc["ratio"]) + "）")
        return 0
    if args.json:
        print(render(doc), end="")
        return 0
    print("闸门 " + str(doc["gates"]) + " · 有拒绝型用例 " + str(doc["gates_with_negative"])
          + " · 比率 " + str(doc["ratio"]))
    print("缺拒绝型用例的闸门：" + "、".join(doc["missing"]))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
