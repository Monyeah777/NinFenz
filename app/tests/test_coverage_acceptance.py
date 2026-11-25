"""112 节点逐节点验收证据：state/validation/evidence 不得缺。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "results" / "app" / "governance" / "registry.json"
COV = ROOT / "results" / "app" / "governance" / "coverage"


def test_every_node_has_acceptance_evidence() -> None:
    d = json.loads(REG.read_text(encoding="utf-8"))
    nodes = d["coverage"]["nodes"]
    assert len(nodes) == 112
    missing = []
    for n in nodes:
        p = COV / f"{n['id']}.json"
        if not p.is_file():
            missing.append(f"{n['id']}: file")
            continue
        ev = json.loads(p.read_text(encoding="utf-8"))
        for key in ("state", "validation", "evidence"):
            if not ev.get(key):
                missing.append(f"{n['id']}: {key}")
        if n["current_state"] != "conformant":
            missing.append(f"{n['id']}: state={n['current_state']}")
    assert missing == []
