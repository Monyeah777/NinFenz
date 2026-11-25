#!/usr/bin/env python3
"""112 节点覆盖审计：状态、hard_ids、证据缺口；生成 COVERAGE_MATRIX.md。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "results" / "app" / "governance" / "registry.json"
OUT = ROOT / "results" / "app" / "governance"
COV = OUT / "coverage"
MATRIX = OUT / "COVERAGE_MATRIX.md"


def main() -> int:
    d = json.loads(REG.read_text(encoding="utf-8"))
    nodes = d["coverage"]["nodes"]
    COV.mkdir(parents=True, exist_ok=True)
    gaps = {"absent": [], "partial": [], "missing_evidence": []}
    rows = []
    for n in nodes:
        nid = n["id"]
        ev = COV / f"{nid}.json"
        if n["current_state"] == "absent":
            gaps["absent"].append(nid)
        elif n["current_state"] == "partial":
            gaps["partial"].append(nid)
        if not ev.is_file():
            gaps["missing_evidence"].append(nid)
        rows.append(f"| {nid} | {n['layer']} | {n['name']} | {n['priority']} | {n['current_state']} | {','.join(n['hard_ids']) or '-'} | {'yes' if ev.is_file() else 'no'} |")
    MATRIX.write_text(
        "# 112 节点覆盖矩阵\n\n"
        f"> absent={len(gaps['absent'])} partial={len(gaps['partial'])} missing_evidence={len(gaps['missing_evidence'])}\n\n"
        "| 节点 | 层 | 名称 | 优先级 | 状态 | H | 证据 |\n|---|---|---|---|---|---|---|\n"
        + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    (COV / "gaps.json").write_text(json.dumps(gaps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"total": len(nodes), "absent": len(gaps["absent"]), "partial": len(gaps["partial"]), "missing_evidence": len(gaps["missing_evidence"])}, ensure_ascii=False))
    return 1 if gaps["absent"] else 0


if __name__ == "__main__":
    sys.exit(main())
