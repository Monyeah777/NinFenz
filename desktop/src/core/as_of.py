"""as-of 取数纪律：评测某时点结论只许用其之前已知的输入（机制借鉴 nuke AGENTS.md:8 / README.md:40-41）。

防前视/泄漏：用了晚于评测时点的输入即判红。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List


def usable_inputs(inputs: List[Dict[str, Any]], as_of: str) -> List[str]:
    """known_at <= as_of 的输入 id。"""
    return [str(i.get("id")) for i in inputs if str(i.get("known_at") or "") <= as_of]


def check(inputs: List[Dict[str, Any]], as_of: str, used_ids: Iterable[str]) -> List[str]:
    """用了 as_of 之后才知道的输入 → 前视泄漏。"""
    late = {str(i.get("id")) for i in inputs if str(i.get("known_at") or "") > as_of}
    return ["前视泄漏：评测时点 %s 之前不可知却被使用：%s（修复指引：只用 known_at<=as_of 的输入）"
            % (as_of, x) for x in sorted(set(used_ids) & late)]
