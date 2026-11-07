"""策略编译器 v0：把合规意图编译成 nf-check-policy/1（封闭词表），并如实报告不可表达项。

内部差距（ABI 的 cc_check 缺口）：仓里 v0 只有封闭词表的判定器，缺「法规文本 → 规则」的编译器。
真正的自然语言编译不在本仓能力内，所以这里做的是诚实的中间层：

1. 意图是**人写的结构化 JSON**（nf-check-intent/1），每条 = 一个可命名的合规要求；
2. 编译器把每条意图映射到**封闭词表**的检查（utf8 / regex_present / regex_absent /
   count_at_least / digest_pin），产出可直接喂 nf check --policy 的策略；
3. 表达不了的意图**必须列进 unsupported 并说明需要什么**（模型/载体/时间权威/身份），
   绝不静默丢弃——「编不过就当没提」是这类工具最常见的谎。

纪律：纯函数、无时间戳（同输入逐字节一致）；判据版本随结论走（compiled_from.digest）。
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

INTENT_SCHEMA = "nf-check-intent/1"
POLICY_SCHEMA = "nf-check-policy/1"
GUIDE = "修复指引："

#: 可编译的意图规则：rule -> 必需字段 / 可选字段 / 语义。
SUPPORTED: dict[str, dict[str, Any]] = {
    "explicit_notice": {"needs": ("text",), "optional": ("where",),
                        "why": "显式提示文字出现在对象开头/结尾/任意位置"},
    "forbidden_tokens": {"needs": ("patterns",),
                         "why": "对象里不得出现这些正则（一条一个 regex_absent）"},
    "min_bytes": {"needs": ("n",), "why": "对象至少要有 n 个字节"},
    "require_metadata": {"needs": ("key",), "optional": ("value",),
                         "why": "文本里必须出现 key[=或:]value 形态的元数据声明"},
    "digest_pinned": {"needs": ("sha256",), "why": "对象摘要必须钉在给定 sha256"},
    "utf8": {"needs": (), "why": "对象必须是合法 UTF-8 文本（其余规则的前置）"},
}

#: 明确表达不了的意图：进 unsupported，不静默丢弃。needs 写清楚缺什么能力。
UNSUPPORTED: dict[str, dict[str, str]] = {
    "semantic_claim": {"why": "内容是不是真的 AI 生成 需要模型或人工判断",
                       "needs": "内容判定能力（本仓明确不做）"},
    "carrier_watermark": {"why": "水印是否真的嵌在载体里要读载体像素/容器，文本判据判不了",
                          "needs": "载体面判定（用 nf label extract --mode watermark 单独证；"
                                   "cc_check 只做单对象文本面）"},
    "visual_notice": {"why": "画面角标/字幕这类视觉要素不在文本判据面内",
                      "needs": "媒体渲染与图像判定"},
    "time_window": {"why": "在某时间段内发布需要可信时间",
                    "needs": "可信时间戳权威（威胁模型 G3）"},
    "owner_signature": {"why": "签发人具备资质属于身份与授权面",
                        "needs": "身份认证 / CA / 公钥面"},
}

#: where 词表（explicit_notice 用）
PLACES = ("start", "end", "any")


def canonical(obj: Any) -> bytes:
    """规范化 JSON 编码（与 attest / receipts / check_policy 同一口径）。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def intent_digest(intent: dict[str, Any]) -> str:
    """意图摘要（写进策略的 compiled_from；判据版本随结论走）。"""
    return hashlib.sha256(canonical(intent)).hexdigest()


def _need(req: dict[str, Any], field: str, kind: type, issues: list, where: str) -> Any:
    """取必需字段并校验类型（不合法就记账并返回 None）。"""
    val = req.get(field)
    if not isinstance(val, kind):
        issues.append(f"{where} 的 {field} 类型不对（{GUIDE}期望 {kind.__name__}）")
        return None
    return val


def validate_intent(intent: Any) -> list[str]:
    """意图形状校验 → 问题列表（空 = 可以编译）。不可表达的规则**不算**问题。"""
    issues: list[str] = []
    if not isinstance(intent, dict):
        return ["意图顶层应为对象（" + GUIDE + "请给 nf-check-intent/1 的 JSON 对象）"]
    if intent.get("schema") != INTENT_SCHEMA:
        got = intent.get("schema")
        issues.append(f"意图 schema 不匹配（期望 {INTENT_SCHEMA}，实得 {got!r}）"
                      f"（{GUIDE}请补 schema 后重跑）")
    obj = intent.get("object")
    if not isinstance(obj, str) or not obj.strip():
        issues.append("缺 object（" + GUIDE + "请给被检对象的仓内相对路径）")
    reqs = intent.get("requirements")
    if not isinstance(reqs, list) or not reqs:
        issues.append("缺 requirements（" + GUIDE + "空意图编译不出任何判据，不能当作已体检）")
        return issues
    seen: set[str] = set()
    for i, req in enumerate(reqs, 1):
        where = f"第 {i} 条意图"
        if not isinstance(req, dict):
            issues.append(f"{where} 不是对象（{GUIDE}请写成路由对象）")
            continue
        rid = str(req.get("id") or "")
        if rid:
            if rid in seen:
                issues.append(f"{where} 的 id 重复：{rid}（{GUIDE}请改成唯一 id）")
            seen.add(rid)
        rule = str(req.get("rule") or "")
        if not rule:
            issues.append(f"{where} 缺 rule（{GUIDE}请给规则名；可用见 nf check --list-rules）")
            continue
        if rule in UNSUPPORTED:
            continue
        spec = SUPPORTED.get(rule)
        if spec is None:
            issues.append(f"{where} 的 rule 未知：{rule!r}（{GUIDE}拼写？可用规则见 "
                          "nf check --list-rules）")
            continue
        for field in spec["needs"]:
            if field == "text":
                val = _need(req, "text", str, issues, where)
                if val is not None and not val.strip():
                    issues.append(f"{where} 的 text 为空（{GUIDE}请给要出现的提示文字）")
            elif field == "patterns":
                pats = _need(req, "patterns", list, issues, where)
                if isinstance(pats, list):
                    if not pats:
                        issues.append(f"{where} 的 patterns 为空（{GUIDE}至少给一条）")
                    for pat in pats:
                        if not isinstance(pat, str) or not pat:
                            issues.append(f"{where} 的 patterns 里有非字符串项"
                                          f"（{GUIDE}每条应是正则字符串）")
                            continue
                        try:
                            re.compile(pat)
                        except re.error as exc:
                            issues.append(f"{where} 的 pattern 不是合法正则：{exc}"
                                          f"（{GUIDE}请修正后重跑）")
            elif field == "n":
                val = _need(req, "n", int, issues, where)
                if isinstance(val, int) and val < 0:
                    issues.append(f"{where} 的 n 应为非负整数（{GUIDE}给整数下界）")
            elif field == "key":
                val = _need(req, "key", str, issues, where)
                if isinstance(val, str) and not val.strip():
                    issues.append(f"{where} 的 key 为空（{GUIDE}给元数据字段名）")
            elif field == "sha256":
                val = _need(req, "sha256", str, issues, where)
                if isinstance(val, str) and not re.fullmatch(r"[0-9a-fA-F]{64}", val):
                    issues.append(f"{where} 的 sha256 应为 64 位十六进制（{GUIDE}钉完整摘要）")
        where_val = req.get("where")
        if ("where" in spec.get("optional", ()) and where_val is not None
                and where_val not in PLACES):
            issues.append(f"{where} 的 where 不在词表（实得 {where_val!r}；"
                          f"可选：{', '.join(PLACES)}）（{GUIDE}改用法内取值）")
    return issues


def _rule(rid: str, kind: str, fix: str, **extra: Any) -> dict[str, Any]:
    """拼一条策略规则（固定 schema 面：id/kind/severity/fix + 该 kind 的字段）。"""
    rule: dict[str, Any] = {"id": rid, "kind": kind, "severity": "fail", "fix": fix}
    rule.update(extra)
    return rule


def _compile_one(req: dict[str, Any], idx: int) -> list[dict[str, Any]]:
    """单条意图 → 策略规则列表（调用前已通过校验）。"""
    rule = str(req["rule"])
    rid = str(req.get("id") or f"c{idx}-{rule}")
    if rule == "utf8":
        return [_rule(rid, "utf8", "把对象保存成 UTF-8 文本后重跑")]
    if rule == "explicit_notice":
        text = str(req["text"])
        where = str(req.get("where") or "any")
        escaped = re.escape(text)
        pattern = {"start": "^" + escaped, "end": escaped + "$", "any": escaped}[where]
        place = {"start": "开头", "end": "结尾", "any": "任意位置"}[where]
        return [_rule(rid, "regex_present", f"在对象{place}加上显式提示：{text}",
                      pattern=pattern)]
    if rule == "forbidden_tokens":
        out = []
        for j, pat in enumerate(req["patterns"], 1):
            out.append(_rule(f"{rid}-{j}", "regex_absent",
                             f"删掉被禁用的内容/词（模式 {pat}）", pattern=pat))
        return out
    if rule == "min_bytes":
        n = int(req["n"])
        return [_rule(rid, "count_at_least", f"补足内容到至少 {n} 字节",
                      field="bytes", n=n)]
    if rule == "require_metadata":
        key = re.escape(str(req["key"]))
        value = req.get("value")
        pattern = (rf'"?{key}"?\s*[:=]\s*"?{re.escape(str(value))}'
                   if value is not None else rf'"?{key}"?\s*[:=]')
        return [_rule(rid, "regex_present",
                      f"补上元数据声明：{req['key']}"
                      + (f"={value}" if value is not None else "=…"), pattern=pattern)]
    if rule == "digest_pinned":
        return [_rule(rid, "digest_pin",
                      "对象摘要不再是钉住的值：确认是期望版本，或更新策略里的 sha256",
                      sha256=str(req["sha256"]).lower())]
    raise ValueError(f"未实现的意图规则：{rule}（修复指引：请在 _compile_one 里补分支并加判据）")


def compile_intent(intent: Any) -> dict[str, Any]:
    """意图 → {ok, policy, coverage, unsupported, issues}。形状错则不产出策略。"""
    issues = validate_intent(intent)
    if issues:
        return {"ok": False, "policy": None, "issues": issues,
                "unsupported": [], "coverage": {"requirements": 0, "compiled": 0,
                                                "unsupported": 0, "complete": False}}
    reqs = list(intent["requirements"])
    rules: list[dict[str, Any]] = [
        _rule("c0-utf8", "utf8", "把对象保存成 UTF-8 文本后重跑")]
    unsupported: list[dict[str, Any]] = []
    for idx, req in enumerate(reqs, 1):
        name = str(req["rule"])
        if name in UNSUPPORTED:
            unsupported.append({"rule": name, "why": UNSUPPORTED[name]["why"],
                                "needs": UNSUPPORTED[name]["needs"],
                                "id": str(req.get("id") or f"c{idx}-{name}")})
            continue
        rules.extend(_compile_one(req, idx))
    policy = {
        "schema": POLICY_SCHEMA,
        "object": str(intent["object"]),
        "policy_id": str(intent.get("policy_id") or ""),
        "rules": rules,
        "compiled_from": {"schema": INTENT_SCHEMA, "digest": intent_digest(intent),
                          "requirements": len(reqs)},
    }
    compiled = len(reqs) - len(unsupported)
    return {"ok": True, "policy": policy, "issues": [], "unsupported": unsupported,
            "coverage": {"requirements": len(reqs), "compiled": compiled,
                         "unsupported": len(unsupported),
                         "complete": not unsupported}}


def rules_table() -> dict[str, Any]:
    """规则清单（CLI --list-rules 用）：可编译 + 不可表达，一次给全。"""
    return {"compilable": [{"rule": k, "why": v["why"], "needs": list(v["needs"]),
                            "optional": list(v.get("optional") or ())}
                           for k, v in SUPPORTED.items()],
            "unsupported": [{"rule": k, "why": v["why"], "needs": v["needs"]}
                            for k, v in UNSUPPORTED.items()]}
