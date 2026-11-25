"""112 节点覆盖：0 absent/partial，全部有证据文件；H/T 全通过。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "results" / "app" / "governance" / "registry.json"
COV = ROOT / "results" / "app" / "governance" / "coverage"


def test_coverage_complete() -> None:
    d = json.loads(REG.read_text(encoding="utf-8"))
    nodes = d["coverage"]["nodes"]
    assert len(nodes) == 112
    assert [n["id"] for n in nodes if n["current_state"] in {"absent", "partial"}] == []
    missing = [n["id"] for n in nodes if not (COV / f"{n['id']}.json").is_file()]
    assert missing == []
    assert all(h["current_stage"] == "proven" for h in d["hard_capabilities"])
    assert all(t["status"] == "passed" for t in d["trials"])
