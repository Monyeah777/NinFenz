"""注入 → 结局 → 效果 配对回执（机制借鉴 MemVault compliance.rs:69-89 / effectiveness.rs:84-154）。

NF 有注入端（instruction_evidence / knowledge_usage）与结局端（06 §4 质检门），
中间缺一条**可核验的配对**：素材被真的用了，还是只是被注入了。
本模块给出配对台账；「未判定」是一等状态（不伪造判决，留空并保留重试）。
"""
from __future__ import annotations

from typing import Any, Dict, List

UNJUDGED = "unjudged"      # 无法判定（一等状态，非 None/非 False）
UNUSED = "unused"
USED = "used"


def record_injection(ledger: Dict[str, Any], turn: str, item: str) -> None:
    """登记一次注入（幂等）。"""
    ledger.setdefault("injections", {}).setdefault(turn, [])
    if item not in ledger["injections"][turn]:
        ledger["injections"][turn].append(item)


def record_outcome(ledger: Dict[str, Any], turn: str, ok: bool) -> None:
    """登记该回合结局（pass/warn/fail 折算为 bool）。"""
    ledger.setdefault("outcomes", {})[turn] = bool(ok)


def judge_effect(ledger: Dict[str, Any], turn: str, item: str, effect: str) -> None:
    """登记单条素材的效果判定；effect ∈ {used, unused, unjudged}。"""
    if effect not in (USED, UNUSED, UNJUDGED):
        raise ValueError("effect 越词表：%r（修复指引：取 %s 之一）" % (effect, "/".join((USED, UNUSED, UNJUDGED))))
    ledger.setdefault("effects", {}).setdefault(turn, {})[item] = effect


def report(ledger: Dict[str, Any]) -> Dict[str, Any]:
    """汇总 → {pairs, unjudged, used, unused}。未给出判定的一律计 unjudged（不猜）。"""
    inj = ledger.get("injections") or {}
    eff = ledger.get("effects") or {}
    out = ledger.get("outcomes") or {}
    used = unused = unjudged = 0
    pairs: List[Dict[str, Any]] = []
    for turn, items in inj.items():
        decided = eff.get(turn) or {}
        for it in items:
            e = decided.get(it, UNJUDGED)
            if e == USED:
                used += 1
            elif e == UNUSED:
                unused += 1
            else:
                unjudged += 1
            pairs.append({"turn": turn, "item": it, "effect": e,
                          "outcome": out.get(turn)})
    return {"pairs": pairs, "used": used, "unused": unused, "unjudged": unjudged}
