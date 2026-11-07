"""活体驾驶舱单轮协议校验器（schema + 语义）。"""

from __future__ import annotations

from pathlib import Path

from . import json_asset
from . import schema_compat as jsonschema

BASE = Path(__file__).parent
SCHEMA = json_asset.load(BASE / "live_cockpit.schema.json")
ATOMS = {a["id"] for a in json_asset.load(BASE / "meta_atoms.json")["atoms"]}
NEEDS = SCHEMA["properties"]["need"]["enum"]
V = jsonschema.Draft202012Validator(SCHEMA)


def validate(resp: dict) -> list[str]:
    issues = [e.message for e in V.iter_errors(resp)]
    if isinstance(resp, dict):
        cluster = resp.get("cluster")
        if isinstance(cluster, list):
            for a in cluster:
                if a not in ATOMS:
                    issues.append(f"unknown atom: {a}")
        if resp.get("stop") is True and cluster:
            issues.append("stop with non-empty cluster")
        if resp.get("stop") is False and not cluster:
            issues.append("empty cluster without stop")
    return issues
