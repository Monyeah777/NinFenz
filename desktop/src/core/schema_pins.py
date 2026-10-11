"""按 schema 版本钉扎的旧版契约样本（机制借鉴 restless-core company_projection.rs:800-853）。

NF 的 §7 只有规则与迁移记录散文，无「旧版本样本」可执行侧；本模块登记 pin
并按版本校验样本在场与摘要一致。
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def validate(pins: List[Dict[str, Any]], root: str = ".") -> List[str]:
    issues: List[str] = []
    for p in pins:
        for k in ("schema_version", "fixture", "digest"):
            if not str(p.get(k) or "").strip():
                issues.append("schema pin 缺 %s（修复指引：补该字段）" % k)
        rel = str(p.get("fixture") or "")
        if rel and not os.path.isfile(os.path.join(root, rel)):
            issues.append("schema pin 样本不在场：%s（修复指引：补该版本样本）" % rel)
        elif rel:
            if _sha(os.path.join(root, rel)) != str(p.get("digest")):
                issues.append("schema pin 样本已漂移：%s（修复指引：重签 digest 或换回原样本）" % rel)
    return issues


def covers(versions: List[str], pins: List[Dict[str, Any]]) -> List[str]:
    """哪些版本没有旧版样本（additive 兼容的**可执行**侧缺口）。"""
    have = {str(p.get("schema_version")) for p in pins}
    return [v for v in versions if v not in have]
