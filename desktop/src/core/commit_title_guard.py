"""提交标题禁内部流水账/内部编号/金额（机制借鉴 nuke AGENTS.md:113-128；对齐 STRATEGY §四公开文案纪律）。

commit-msg 门禁（scripts/commit_msg_check.py）管 Conventional Commits 格式；
本模块补**内容**：标题不得含计划波次号/§ 编号/内部案例号/金额。
"""
from __future__ import annotations

import re
from typing import List

_INTERNAL = re.compile(r"(波[A-Z]|W\d{1,2}\b|§\d|C\d{2,3}\b|计划第|内部编号|流水账)")
#: 数量上界 + 前缀边界：防「长数字串 + 必需字面量」的超线性回溯（redos_scan 实测 65k 输入 71s）
_AMOUNT = re.compile(r"(?<!\d)\d{1,12}(?:\.\d+)?\s*(?:万|亿|元|美元)")


def check(title: str) -> List[str]:
    out: List[str] = []
    for m in _INTERNAL.finditer(title or ""):
        out.append("提交标题含内部流水账/编号 %r（修复指引：公开面只写结果，不写计划波次与内部编号）" % m.group(0))
    for m in _AMOUNT.finditer(title or ""):
        out.append("提交标题含金额 %r（修复指引：公开面不写金额）" % m.group(0))
    return out
