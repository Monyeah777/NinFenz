"""发布物自证清单：生成器 + 逐件字节摘要 + 真源 SHA（机制借鉴 tokalator / o8 产物嵌双 SHA）。

补 NF「源码判据强、发布物判据弱」：产物清单自带生成器标识与逐件 sha256，
消费方可离线校验产物未被替换；同时强制「覆盖与局限」段（标明未覆盖面）。
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, Iterable, List


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def build(root: str, paths: Iterable[str], generator: str, coverage: str) -> Dict[str, Any]:
    """构造清单；coverage 为必填「覆盖与局限」段。"""
    if not coverage.strip():
        raise ValueError("缺「覆盖与局限」段（修复指引：写清本产物覆盖什么、不覆盖什么）")
    files = {}
    for rel in paths:
        full = os.path.join(root, rel)
        files[rel] = _sha(full)
    return {"generator": generator, "coverage": coverage, "files": files}


def verify(manifest: Dict[str, Any], root: str) -> List[str]:
    """逐件重算 → 漂移清单。"""
    issues: List[str] = []
    if not str(manifest.get("coverage") or "").strip():
        issues.append("清单缺「覆盖与局限」段（修复指引：补 coverage）")
    for rel, want in (manifest.get("files") or {}).items():
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            issues.append("产物缺件：%s（修复指引：重建产物）" % rel)
            continue
        if _sha(full) != want:
            issues.append("产物已漂移：%s（修复指引：重跑生成器重建清单）" % rel)
    return issues
