"""真解析器复核 + 行号 + 修复指引（机制借鉴 vivera frontmatter-strict.mjs:1-29）。

NF 有 lazy_yaml 子集解析器（无 PyYAML 时降级），但缺「真解析器复核」这一档；
本模块用仓库既有的惰性 YAML 入口复核并给出**出错行号**。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core import lazy_yaml as _lyaml


def recheck(text: str) -> Dict[str, Any]:
    """→ {ok, line, error, parsed}。解析器不可用时 ok=False 且写明安装指引。"""
    mod = _lyaml.module()
    if mod is None:
        return {"ok": False, "line": None,
                "error": "PyYAML 不在（修复指引：pip install pyyaml）", "parsed": None}
    try:
        return {"ok": True, "line": None, "error": "", "parsed": mod.safe_load(text)}
    except Exception as exc:
        mark = getattr(exc, "problem_mark", None)
        line: Optional[int] = (mark.line + 1) if mark is not None else None
        return {"ok": False, "line": line,
                "error": "YAML 不可解析：%s（修复指引：按行号修语法；真解析器口径见 01 §1.1）" % exc,
                "parsed": None}
