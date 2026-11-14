"""策略适配（WP-42，G4）：外置规则集 + 纯函数求值（OPA/Cedar 机制借鉴）。

纪律：
- **策略外置**：规则在 `protocol/policy_rules.json`（`nf-policy/1`），代码只求值，不硬编码；
- **默认拒绝**：无规则命中 → deny；缺事实 → 相关规则不匹配 / 显式拒绝（不猜）；
- **优先级显式**：数值越小越先评估；同优先级 deny 胜 allow；
- **判定可复算**：返回命中规则 id + 理由 + 义务；同输入同输出；
- **不声称 OPA/Cedar 兼容**：只借「策略即代码/判定可复算」机制，不引 Rego/Cedar 运行时；
- 与 WP-31 适配器等级联动：required_level T3/T4 在适配器缺失时 deny（不降级冒充）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-policy/1"
REL = "protocol/policy_rules.json"
GUIDE = "修复指引："
EFFECTS = ("allow", "deny", "require")
FACTS = ("required_level", "achieved_level", "attachment_mode", "has_evidence",
         "contract_status", "role")


class PolicyError(Exception):
    """策略/求值拒绝（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "POLICY-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise PolicyError("缺 %s（修复指引：补策略规则集）" % REL, code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PolicyError("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise PolicyError("registry schema 必须 %s" % SCHEMA)
    return doc


def _matches(when: Dict[str, Any], facts: Dict[str, Any]) -> bool:
    for key, want in when.items():
        if key not in facts:
            return False
        if facts.get(key) != want:
            return False
    return True


def evaluate(facts: Dict[str, Any], root: str = ".") -> Dict[str, Any]:
    """求值 → {allowed, effect, reason, matched, obligations, missing_facts}。"""
    reg = load_registry(root)
    if not isinstance(facts, dict) or not facts:
        raise PolicyError("缺事实（修复指引：给出 required_level/contract_status/has_evidence 等）",
                          code="FACTS-MISSING")
    hits: List[Dict[str, Any]] = []
    for rule in sorted(reg.get("rules") or [], key=lambda r: int(r.get("priority") or 0)):
        when = rule.get("when") or {}
        if _matches(when, facts):
            hits.append({"id": str(rule.get("id")), "effect": str(rule.get("effect")),
                         "priority": int(rule.get("priority") or 0),
                         "reason": str(rule.get("reason"))})
    effect = str(reg.get("default_effect") or "deny")
    reason = "无规则命中 → 默认拒绝（不静默放行）"
    obligations: List[str] = []
    if hits:
        denies = [h for h in hits if h["effect"] == "deny"]
        allows = [h for h in hits if h["effect"] == "allow"]
        requires = [h for h in hits if h["effect"] == "require"]
        if denies:
            effect, reason = "deny", denies[0]["reason"]
        elif requires:
            effect = "require"
            obligations = [h["reason"] for h in requires]
            reason = "需要义务：%s" % "；".join(obligations[:2])
        elif allows:
            effect, reason = "allow", allows[0]["reason"]
    missing = [k for k in ("required_level", "contract_status", "has_evidence") if k not in facts]
    return {"schema": "nf-policy-decision/1", "allowed": effect == "allow",
            "effect": effect, "reason": reason,
            "matched": [h["id"] for h in hits], "obligations": obligations,
            "missing_facts": missing,
            "note": "默认拒绝；同优先级 deny 胜 allow；不声称 OPA/Cedar 兼容"}


def check_registry(root: str = ".") -> List[str]:
    issues: List[str] = []
    reg = load_registry(root)
    if str(reg.get("default_effect")) != "deny":
        issues.append("default_effect 必须 deny（修复指引：默认放行不可接受）")
    rules = reg.get("rules") or []
    if not rules:
        issues.append("规则集为空")
    ids = [str(r.get("id")) for r in rules]
    if len(ids) != len(set(ids)):
        issues.append("规则 id 重复")
    for rule in rules:
        rid = str(rule.get("id"))
        if str(rule.get("effect")) not in EFFECTS:
            issues.append("%s effect 非法：%s" % (rid, rule.get("effect")))
        if not isinstance(rule.get("priority"), int):
            issues.append("%s priority 必须是整数" % rid)
        when = rule.get("when") or {}
        if not when:
            issues.append("%s when 不能为空（空条件=无条件命中）" % rid)
        for key in when:
            if key not in FACTS:
                issues.append("%s when 含未知事实：%s（修复指引：登记到 facts_vocabulary）" % (rid, key))
        if not str(rule.get("reason") or "").strip():
            issues.append("%s 缺 reason" % rid)
    vocab = [str(x) for x in reg.get("facts_vocabulary") or []]
    if sorted(vocab) != sorted(FACTS):
        issues.append("facts_vocabulary 与求值器事实集不一致")
    boundary = " ".join(str(x) for x in reg.get("claims_boundary") or [])
    if "不声称" not in boundary:
        issues.append("claims_boundary 必须写明不声称 OPA/Cedar 兼容")
    return issues
