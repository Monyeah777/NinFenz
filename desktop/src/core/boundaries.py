"""边界登记：边界 → 协议代码文件 + 协议文档（机制借鉴 OpenAgentCore AGENTS 的「边界→协议代码+文档」表）。

LAYERS 登记阶与接口面，但没有「边界→实现件+文档件」这一对；本模块机检两件在场。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List


def validate(entries: List[Dict[str, Any]], root: str = ".") -> List[str]:
    """每条须有 id/code/doc，且 code 与 doc 在仓库内真实存在（不得是空气）。"""
    issues: List[str] = []
    for e in entries:
        bid = str(e.get("id") or "")
        for k in ("code", "doc"):
            rel = str(e.get(k) or "")
            if not rel:
                issues.append("边界 %s 缺 %s（修复指引：给出仓库内相对路径）" % (bid, k))
            elif not os.path.isfile(os.path.join(root, rel)):
                issues.append("边界 %s 的 %s 不在场：%s（修复指引：补该件或改指向真实件）" % (bid, k, rel))
    return issues
