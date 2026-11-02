"""Cognition Event：把驾驶舱一次运行收敛成可复算、可引用的证据事件。

纪律：
- 不含质量评分（作者设计：内部无 score/grade）；
- 字段只来自 cockpit manifest + journal（原子轨迹），digest 确定性；
- 事件可写入本地事件库（NF_COCKPIT_HOME/events/<digest>.json），供 ledger/证据卡引用。
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import json_asset

SCHEMA = "nf-cognition-event/1"
SERVER_VERSION = "1.0"


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), default=str).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _home() -> Path:
    base = os.environ.get("NF_COCKPIT_HOME") or str(Path.home() / ".NinFenz" / "cockpit")
    p = Path(base) / "events"
    p.mkdir(parents=True, exist_ok=True)
    return p


def build(manifest: dict, journal: dict | None = None, session_id: str = "") -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema") != "nf-cockpit-manifest/1":
        raise ValueError("manifest schema 须为 nf-cockpit-manifest/1")
    rounds = []
    atoms = []
    if isinstance(journal, dict):
        for ev in journal.get("events") or []:
            ids = [str(x.get("atom_id")) for x in (ev.get("atom_trace") or [])
                   if isinstance(x, dict) and x.get("atom_id")]
            rounds.append({"seq": ev.get("seq"), "atoms": ids,
                           "status": ev.get("status"),
                           "event_digest": ev.get("event_digest")})
            for a in ids:
                if a not in atoms:
                    atoms.append(a)
    sid = session_id or str(manifest.get("journal_digest") or manifest.get("handoff_digest") or "")
    event = {
        "schema": SCHEMA,
        "session_id": sid,
        "manifest_digest": str(manifest.get("digest") or digest(manifest)),
        "machine_digest": str(manifest.get("machine_digest") or ""),
        "runtime_digest": str(manifest.get("runtime_digest") or ""),
        "journal_digest": manifest.get("journal_digest"),
        "handoff_digest": str(manifest.get("handoff_digest") or ""),
        "context_digest": str(manifest.get("context_digest") or ""),
        "prompt_digest": str(manifest.get("prompt_digest") or ""),
        "status": manifest.get("status"),
        "termination": manifest.get("termination"),
        "complete": bool(manifest.get("complete")),
        "turns": int(manifest.get("turns") or 0),
        "context_units_spent": int(manifest.get("context_units_spent") or 0),
        "abstention_status": manifest.get("abstention_status"),
        "human_action_required": bool(manifest.get("human_action_required")),
        "atoms": atoms,
        "rounds": rounds,
        "no_scoring": True,
        "prev": None,
    }
    event["digest"] = digest(event)
    return event


def verify(event: dict) -> list:
    issues = []
    if not isinstance(event, dict) or event.get("schema") != SCHEMA:
        return ["schema"]
    want = event.get("digest")
    clone = {k: v for k, v in event.items() if k != "digest"}
    if want != digest(clone):
        issues.append("digest")
    if event.get("no_scoring") is not True:
        issues.append("no_scoring")
    return issues


def write(event: dict) -> str:
    issues = verify(event)
    if issues:
        raise ValueError("invalid cognition event: %s" % ",".join(issues))
    path = _home() / (event["digest"] + ".json")
    path.write_text(json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return str(path)


def load(event_digest: str) -> dict | None:
    p = _home() / (str(event_digest) + ".json")
    if not p.is_file():
        return None
    return json_asset.load(p)


def from_manifest_file(manifest_path: str | Path, journal_path: str | Path | None = None) -> dict:
    manifest = json_asset.load(Path(manifest_path))
    journal = None
    if journal_path is not None:
        journal = json_asset.load(Path(journal_path))
    event = build(manifest, journal)
    write(event)
    return event
