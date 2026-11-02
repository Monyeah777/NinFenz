"""本地驾驶舱日志（append-only JSONL）：把决策/假设/动作落成可追溯记录。

定位：NF 的「第二平面」最小实现——不是笔记，只收四类对象，且每条必须能指向证据。
存储：`NF_COCKPIT_HOME` 或 `~/.NinFenz/cockpit/decisions.jsonl`（仓库外、只追加、无网络）。
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

KINDS = ("context", "claim", "decision", "action", "evidence")
MAX_TEXT = 20000


def _home() -> Path:
    base = os.environ.get("NF_COCKPIT_HOME") or str(Path.home() / ".NinFenz" / "cockpit")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_path() -> Path:
    return _home() / "decisions.jsonl"


def _norm(rec: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(rec, dict):
        raise ValueError("记录必须是对象（修复指引：传 {kind,text} 对象）")
    kind = str(rec.get("kind") or "").strip()
    if kind not in KINDS:
        raise ValueError("kind 须为 %s（修复指引：用 context/claim/decision/action/evidence）" % "/".join(KINDS))
    text = str(rec.get("text") or "").strip()
    if not text:
        raise ValueError("text 不得为空（修复指引：给出该决策/假设的正文）")
    if len(text) > MAX_TEXT:
        raise ValueError("text 超过 %d 字符上限（修复指引：拆分或摘要）" % MAX_TEXT)
    content = {"schema": "nf-cockpit-record/1", "kind": kind, "text": text,
               "refs": [str(x) for x in (rec.get("refs") or [])][:50],
               "evidence": [str(x) for x in (rec.get("evidence") or [])][:50],
               "context": str(rec.get("context") or "")[:2000] or None}
    # 稳定 id：只由内容决定（不含时间）⇒ 同一条记录重复写入可去重
    blob = json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")
    out = dict(content)
    out["id"] = "cog-" + hashlib.sha256(blob).hexdigest()[:16]
    out["created_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return out


def append(record: Dict[str, Any]) -> Dict[str, Any]:
    rec = _norm(record)
    p = log_path()
    if p.is_file():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip() and json.loads(line).get("id") == rec["id"]:
                return {"ok": True, "duplicate": True, "record": rec}
    with p.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return {"ok": True, "duplicate": False, "record": rec}


def records(kind: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    p = log_path()
    if not p.is_file():
        return []
    out: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if kind and rec.get("kind") != kind:
            continue
        out.append(rec)
    return out[-max(1, min(int(limit), 500)):]


def summarize() -> Dict[str, Any]:
    rows = records(limit=500)
    by: Dict[str, int] = {}
    for r in rows:
        by[r.get("kind", "?")] = by.get(r.get("kind", "?"), 0) + 1
    return {"path": str(log_path()), "count": len(rows), "by_kind": by}
