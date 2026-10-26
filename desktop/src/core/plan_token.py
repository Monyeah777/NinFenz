"""一次性计划令牌 + 绑定确认语 + TTL + 单次消费（机制借鉴 DSH-Store）。

写盘/发布前的高危动作，应是「一次性计划 + 精确确认语 + 有限期 + 取用即焚」：
令牌绑定**计划内容摘要**，确认语不符/过期/已消费一律拒绝；消费即置 consumed。
纯逻辑、可注入时钟（确定性，无墙钟依赖）。
"""
from __future__ import annotations

from typing import Any, Dict, Tuple


def issue(plan: str, subject_digest: str, confirm_phrase: str, ttl_seconds: int,
          now: int) -> Dict[str, Any]:
    """签发一次性令牌。"""
    if not plan.strip() or not confirm_phrase.strip():
        raise ValueError("计划与确认语不得为空（修复指引：给出计划正文与精确确认语）")
    return {"plan": plan, "subject_digest": subject_digest, "confirm": confirm_phrase,
            "expires_at": int(now) + int(ttl_seconds), "consumed": False}


def consume(token: Dict[str, Any], confirm_phrase: str, subject_digest: str,
            now: int) -> Tuple[bool, str]:
    """消费令牌 → (ok, reason)。任一条件不符即拒，且**不改动**令牌。"""
    if token.get("consumed"):
        return False, "令牌已被消费（修复指引：重新签发新令牌）"
    if int(now) > int(token.get("expires_at") or 0):
        return False, "令牌已过期（修复指引：重新签发新令牌并尽快执行）"
    if confirm_phrase != token.get("confirm"):
        return False, "确认语不匹配（修复指引：逐字使用签发时的确认语）"
    if subject_digest != token.get("subject_digest"):
        return False, "被作用对象已变（修复指引：对当前内容重新签发令牌）"
    token["consumed"] = True
    return True, "已消费"
