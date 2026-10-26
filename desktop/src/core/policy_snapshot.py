"""策略快照：canonical JSON + sha256 固化进运行记录（机制借鉴 ForgeLoop RunPolicySnapshot.java:20-59）。

把「这次跑用的是哪份策略」变成可核验事实：快照 digested 进运行记录，
事后可用 matches() 证明复现用的是同一份策略。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def snapshot(policy: Any) -> Dict[str, Any]:
    canonical = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"canonical": canonical, "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def matches(snap: Dict[str, Any], policy: Any) -> bool:
    return snapshot(policy)["digest"] == str(snap.get("digest"))
