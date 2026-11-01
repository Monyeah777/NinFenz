"""注入预算契约（机制借鉴 MemVault agent_adapt.rs:21-58 / lorepack assemble.ts:28-45）。

06 §8 只有散文原则（协议先行/注册表居中/预设殿后、资产条目只在命中时注入），
无量化档位。本模块把档位做成机器可读并确定性选取：**order in = order out**
（预算耗尽不重排）、被省略项逐条带 reason、越界拒绝并写出区间。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def validate(profile: Dict[str, Any]) -> List[str]:
    """档位必填：max_items / token_budget / priority_order；排除类型须为列表。"""
    issues: List[str] = []
    for k in ("max_items", "token_budget", "priority_order"):
        if k not in profile:
            issues.append("注入档位缺 %s（修复指引：补该键后重跑；见 06 §8）" % k)
    if not isinstance(profile.get("priority_order"), list):
        issues.append("priority_order 须为列表（修复指引：给出确定的优先级序）")
    if profile.get("exclude_types") is not None and not isinstance(profile.get("exclude_types"), list):
        issues.append("exclude_types 须为列表（修复指引：[] 表示不排除）")
    return issues


def select(profile: Dict[str, Any], items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """→ (选中, 省略记账)。确定性：按 priority_order 序稳定过滤；不因预算重排。"""
    order = list(profile.get("priority_order") or [])
    rank = {name: i for i, name in enumerate(order)}
    exclude = set(profile.get("exclude_types") or [])
    max_items = int(profile.get("max_items") or 0)
    budget = int(profile.get("token_budget") or 0)
    keep: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    used = 0
    for it in sorted(items, key=lambda x: rank.get(str(x.get("type")), len(rank))):
        name = str(it.get("name"))
        if it.get("type") in exclude:
            dropped.append({"name": name, "reason": "类型被排除：%s" % it.get("type")})
            continue
        cost = int(it.get("tokens") or 0)
        if len(keep) >= max_items:
            dropped.append({"name": name, "reason": "超过 max_items=%d" % max_items})
            continue
        if used + cost > budget:
            dropped.append({"name": name, "reason": "超过 token_budget=%d（已用 %d，本条 %d）"
                            % (budget, used, cost)})
            continue
        keep.append(it)
        used += cost
    return keep, dropped
