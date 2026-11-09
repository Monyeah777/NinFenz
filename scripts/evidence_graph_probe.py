#!/usr/bin/env python3
"""证据图探针（E1 的可算形态）：把闭包台账读成**陈述 ⇄ 证据**二部图，算悬挂陈述比 H。

为什么（第 48 轮，来自「资产=二部图 + 幻觉=悬挂陈述边」的设计）：
「幻觉」在本仓一直只有词表级别的说法；二部图给了它一个可计算的定义：
**一条陈述没有任何证据邻接 = 悬挂边**。本探针只读台账，不改任何真源。

口径（写死，避免事后解释）：
- 陈述节点 = 台账里的每条 entry（id）；
- 证据节点 = 该 entry 的 criteria 引用（测试文件 + 方法名）与 evidence 命令；
- 悬挂 = criteria 与 evidence **都为空**（有其一即算有边）；
- H = 悬挂数 / 总陈述数（0 表示每条陈述都有可核证据）。

用法：python scripts/evidence_graph_probe.py [--write|--check] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
def _core(name: str):
    """按需导入 desktop/src 下的 core 模块（局部导入：模块级只留纯逻辑，避开 E402）。"""
    src = str(ROOT / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import importlib

    return importlib.import_module("core." + name)

LEDGER_REL = "protocol/closure/ledger.json"
OUT_REL = "results/ccos/evidence_graph.json"
SCHEMA = "nf-evidence-graph/1"
GUIDE = "修复指引："


def build(root: Path = ROOT) -> dict[str, Any]:
    """台账 → 二部图统计（纯读）。"""
    ledger = _core("json_doc").load(root / LEDGER_REL, dict, what=LEDGER_REL)
    entries = ledger.get("entries") or []
    if not entries:
        raise ValueError("闭包台账为空（" + GUIDE + "确认 " + LEDGER_REL + "）")
    claims = []
    dangling = []
    evidence_nodes: set[str] = set()
    for entry in entries:
        eid = str(entry.get("id") or "")
        criteria = [tuple(c) for c in (entry.get("criteria") or [])]
        evidence = [str(x) for x in (entry.get("evidence") or [])]
        edges = [str(c[0]) + "::" + str(c[1]) for c in criteria] + evidence
        for edge in edges:
            evidence_nodes.add(edge)
        degree = len(edges)
        claims.append({"id": eid, "status": entry.get("status"), "degree": degree})
        if degree == 0:
            dangling.append(eid)
    total = len(claims)
    h = round(len(dangling) / total, 6)
    from core import grouped_report  # 局部导入：分组表复用已有度量件（不新写统计）

    by_status_degree = grouped_report.summarize(
        [{"status": str(c["status"]), "degree": c["degree"]} for c in claims],
        "status", "degree")
    return {"schema": SCHEMA, "claims": total, "evidence_nodes": len(evidence_nodes),
            "by_status_degree": by_status_degree,
            "dangling": dangling, "h_dangling_ratio": h,
            "by_status": {s: sum(1 for c in claims if c["status"] == s)
                          for s in sorted({str(c["status"]) for c in claims})},
            "detail": claims,
            "note": "H = 悬挂陈述比；H>0 说明有陈述没有任何可核证据（幻觉面未收口）"}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="evidence_graph_probe",
                                 description="证据图探针：闭包台账 → 二部图悬挂比 H")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    try:
        doc = build()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        _core("atomic_write").write_text(dest, render(doc))
        print("OK 已写入 " + OUT_REL + "（陈述 " + str(doc["claims"]) + " · H "
              + str(doc["h_dangling_ratio"]) + "）")
        return 0
    if args.check:
        path = ROOT / OUT_REL
        if not path.is_file():
            print("缺 " + OUT_REL + "（" + GUIDE + "跑 --write）", file=sys.stderr)
            return 1
        if render(_core("json_doc").load(path, dict, what=OUT_REL)) != render(doc):
            print("探针结果与重算不一致（" + GUIDE + "重跑 --write）", file=sys.stderr)
            return 1
        print("OK 证据图与重算一致")
        return 0
    print(render(doc), end="")
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
