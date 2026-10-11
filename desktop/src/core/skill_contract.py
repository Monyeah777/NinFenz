"""skill/工具文本不携带授权红线（机制借鉴 restless-core skill-contract.md:1）。

tool_face 现只写「引用 ≠ 背书」，未否授权；本模块检出 skill/工具说明里
**授予权限/绕过门禁**的措辞，避免「技能文本自带授权」。
"""
from __future__ import annotations

import re
from typing import List

_GRANT = re.compile(r"(已获授权|无需审批|可绕过|跳过验证|自动批准|拥有全部权限|免检|绕过门禁|不需要确认)")


def check(text: str) -> List[str]:
    """→ issue 列表（命中授权性措辞即报）。"""
    out = []
    for i, line in enumerate((text or "").splitlines(), 1):
        for m in _GRANT.finditer(line):        # 穷尽报错：一行多处命中全部列出
            out.append("第 %d 行含授权性措辞 %r（修复指引：技能文本不携带授权；权限由运行时的批准记录决定）"
                       % (i, m.group(0)))
    return out
