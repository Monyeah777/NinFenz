"""单对象策略体检——cc_check 的 v0 实装：给定一个对象与一份策略，出可复算的 verdict。

内部差距（2026-11-04 实证）：仓里的判定**全是仓库级**的（nf verify / nf conformance /
nf lint 都是对整个仓库或整类文件），缺「单对象 × 单策略」的入口；而「这个文件符不符合
某条要求」正是合规体检的最小单元。

本模块只做**封闭词表**的确定性判定，不自造 DSL——与 protocol/assertions.json 同一条纪律：
kind 是封闭集，新增规则 = 加一条数据，不扩表达力。业务语义断言仍留在 check 代码里。

判定词表固定 ok / invalid（ABI 的稳定面）；warn 级违规只进 findings，不改 verdict。
纪律：stdlib-only；纯读；**判据版本随结论走**（policy_digest 必填——判据版本不随结论，
结论就不可复算）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from core import json_doc

SCHEMA = "nf-check-policy/1"
#: 规则类别（封闭集）。新增类别 = 破坏性变更：它会让「同一策略」在不同版本判出不同结论。
KINDS = ("utf8", "regex_present", "regex_absent", "count_at_least", "digest_pin")
SEVERITIES = ("fail", "warn")
#: count_at_least 的计数字段（封闭集）
FIELDS = ("bytes", "lines", "chars")
GUIDE = "修复指引："


def canonical(obj: Any) -> bytes:
    """规范化 JSON 编码（与 attest / receipts 同一口径）。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def policy_digest(policy: dict[str, Any]) -> str:
    """策略摘要：判据版本随结论走的前提。"""
    return hashlib.sha256(canonical(policy)).hexdigest()


def _rule_header_issues(rule: dict[str, Any], i: int,
                        seen: set[str]) -> tuple[list[str], str]:
    """规则身份面：id 必填且唯一 → (issues, rid)。"""
    issues: list[str] = []
    rid = str(rule.get("id") or "").strip()
    if not rid:
        issues.append(f"第 {i} 条规则缺 id（{GUIDE}请给唯一 id，结论里要按 id 定位）")
    elif rid in seen:
        issues.append(f"规则 id 重复：{rid}（{GUIDE}请改成唯一 id——重复 id 让结论无法定位）")
    else:
        seen.add(rid)
    return issues, rid


def _rule_kind_issues(rule: dict[str, Any], label: Any) -> list[str]:
    """规则类别/严重度/修复指引三面（封闭词表）。"""
    issues: list[str] = []
    kind = rule.get("kind")
    if kind not in KINDS:
        issues.append(f"规则 {label} 的 kind 不在词表（实得 {kind!r}；可选："
                      f"{', '.join(KINDS)}）（{GUIDE}请改用词表内类别，不要自造 DSL）")
    sev = rule.get("severity", "fail")
    if sev not in SEVERITIES:
        issues.append(f"规则 {label} 的 severity 不在词表（实得 {sev!r}；可选："
                      f"{', '.join(SEVERITIES)}）（{GUIDE}请改成 fail 或 warn）")
    if not str(rule.get("fix") or "").strip():
        issues.append(f"规则 {label} 缺 fix（{GUIDE}每条规则都必须写修复指引——"
                      "判失败却不说怎么改，等于把问题丢回给读者）")
    return issues


def _regex_rule_issues(rule: dict[str, Any], label: Any) -> list[str]:
    """regex_present/regex_absent：pattern 必须是非空且可编译的正则。"""
    issues: list[str] = []
    pat = rule.get("pattern")
    if not isinstance(pat, str) or not pat:
        issues.append(f"规则 {label} 缺 pattern（{GUIDE}请给正则字符串）")
        return issues
    try:
        re.compile(pat)
    except re.error as exc:
        issues.append(f"规则 {label} 的 pattern 不是合法正则：{exc}"
                      f"（{GUIDE}请修正正则后重跑）")
    return issues


def _count_rule_issues(rule: dict[str, Any], label: Any) -> list[str]:
    """count_at_least：field 在词表内 + n 为非负整数。"""
    issues: list[str] = []
    if rule.get("field") not in FIELDS:
        issues.append(f"规则 {label} 的 field 不在词表（实得 {rule.get('field')!r}；"
                      f"可选：{', '.join(FIELDS)}）（{GUIDE}请改用词表内字段）")
    if not isinstance(rule.get("n"), int) or rule.get("n") < 0:
        issues.append(f"规则 {label} 的 n 应为非负整数（{GUIDE}请给整数下界）")
    return issues


def _digest_rule_issues(rule: dict[str, Any], label: Any) -> list[str]:
    """digest_pin：sha256 必须是 64 位十六进制。"""
    if re.fullmatch(r"[0-9a-fA-F]{64}", str(rule.get("sha256") or "")):
        return []
    return [f"规则 {label} 的 sha256 应为 64 位十六进制（{GUIDE}请钉完整摘要）"]


def _rule_issues(rule: Any, i: int, seen: set[str]) -> list[str]:
    """单条规则：身份面 + 类别面 + 按 kind 的专项面。"""
    if not isinstance(rule, dict):
        return [f"第 {i} 条规则不是对象（{GUIDE}请写成规则对象）"]
    issues, rid = _rule_header_issues(rule, i, seen)
    label = rid or i
    issues.extend(_rule_kind_issues(rule, label))
    kind = rule.get("kind")
    if kind in ("regex_present", "regex_absent"):
        issues.extend(_regex_rule_issues(rule, label))
    if kind == "count_at_least":
        issues.extend(_count_rule_issues(rule, label))
    if kind == "digest_pin":
        issues.extend(_digest_rule_issues(rule, label))
    return issues


def validate(policy: Any) -> list[str]:
    """策略形状校验 → 问题列表（空 = 合法）。每条都给可执行指引。"""
    issues: list[str] = []
    if not isinstance(policy, dict):
        return ["策略顶层应为对象（" + GUIDE + "请给 nf-check-policy/1 的 JSON 对象）"]
    if policy.get("schema") != SCHEMA:
        got = policy.get("schema")
        issues.append(f"策略 schema 不匹配（期望 {SCHEMA}，实得 {got!r}）（{GUIDE}请补 "
                      f'"schema": "{SCHEMA}" 后重跑）')
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        issues.append("策略缺 rules（" + GUIDE + "请至少给一条规则；空策略不能判任何结论）")
        return issues
    seen: set[str] = set()
    for i, rule in enumerate(rules, 1):
        issues.extend(_rule_issues(rule, i, seen))
    return issues


def load(path: str) -> dict[str, Any]:
    """读策略文件并校验（坏策略一律带指引拒绝，不静默跳过）。"""
    if not os.path.isfile(path):
        raise ValueError(f"策略文件不存在：{path}（{GUIDE}请给 nf-check-policy/1 的 JSON 路径）")
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        policy = json_doc.loads(raw.decode(), dict, what="策略")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"策略不是合法 UTF-8 JSON：{exc}（{GUIDE}请修正后重跑；"
                         "坏策略不许静默放过）") from exc
    issues = validate(policy)
    if issues:
        raise ValueError("策略不合法：" + "；".join(issues[:3]))
    return policy


def _text(raw: bytes) -> str | None:
    """解码失败返回 None（**不在此抛**：utf8 规则要能给出「不是合法 UTF-8」这条判定）。"""
    try:
        return raw.decode()
    except UnicodeDecodeError:  # 非文本对象：由 utf8 规则判否，不是解析故障
        return None


def _regex_verdict(rule: dict[str, Any], text: str) -> tuple[bool, str]:
    """正则类规则判定（命中/未命中按 kind 反义）。"""
    hit = re.search(str(rule.get("pattern") or ""), text) is not None
    if rule.get("kind") == "regex_present":
        return hit, "命中要求的内容" if hit else "缺要求的内容（pattern 未命中）"
    return (not hit), "未出现禁止内容" if not hit else "出现了禁止内容（pattern 命中）"


def _count_verdict(rule: dict[str, Any], raw: bytes, text: str | None) -> tuple[bool, str]:
    """count_at_least 判定：按封闭字段集算实际值再比下界。"""
    field = str(rule.get("field") or "")
    n = int(rule.get("n") or 0)
    actual = {"bytes": len(raw),
              "lines": len((text or "").replace("\r\n", "\n").splitlines()),
              "chars": len(text or "")}[field]
    return actual >= n, f"{field}={actual}（下界 {n}）"


def _digest_verdict(rule: dict[str, Any], digest: str) -> tuple[bool, str]:
    """digest_pin 判定：对象摘要与钉住的 sha256 逐字比较。"""
    want = str(rule.get("sha256") or "").lower()
    return digest == want, f"摘要={'一致' if digest == want else '不符'}"


def _one(rule: dict[str, Any], raw: bytes, text: str | None,
         digest: str) -> tuple[bool, str]:
    """单条规则判定 → (是否通过, 说明)。"""
    kind = rule.get("kind")
    if kind == "utf8":
        if text is None:
            return False, "不是合法 UTF-8 文本"
        return True, "UTF-8 自检通过"
    if kind in ("regex_present", "regex_absent"):
        if text is None:
            return False, "对象不是 UTF-8 文本，正则类规则无从判定"
        return _regex_verdict(rule, text)
    if kind == "count_at_least":
        return _count_verdict(rule, raw, text)
    if kind == "digest_pin":
        return _digest_verdict(rule, digest)
    return False, f"未知规则类别：{kind}"


def _read_object(obj: str) -> bytes:
    """读体检对象字节；文件不存在即带指引拒绝。"""
    if not os.path.isfile(obj):
        raise ValueError(f"体检对象不存在：{obj}（{GUIDE}请先 ls 定位到具体文件；"
                         "本命令只收单个文件，目录请逐件跑）")
    with open(obj, "rb") as fh:
        return fh.read()


def _policy_findings(policy: dict[str, Any], raw: bytes, text: str | None,
                     digest: str) -> list[dict[str, Any]]:
    """逐条规则判定 → findings（保持策略内顺序）。"""
    findings: list[dict[str, Any]] = []
    for rule in policy.get("rules") or []:
        ok, detail = _one(rule, raw, text, digest)
        findings.append({"rule": str(rule.get("id") or ""),
                         "kind": rule.get("kind"),
                         "severity": rule.get("severity", "fail"),
                         "ok": ok, "detail": detail,
                         "fix": str(rule.get("fix") or "")})
    return findings


def check(obj: str, policy: dict[str, Any]) -> dict[str, Any]:
    """单对象体检 → {verdict, policy_id, policy_digest, object, findings}。"""
    issues = validate(policy)
    if issues:
        raise ValueError("策略不合法：" + "；".join(issues[:3]))
    raw = _read_object(obj)
    text = _text(raw)
    digest = hashlib.sha256(raw).hexdigest()
    findings = _policy_findings(policy, raw, text, digest)
    failed = [f for f in findings if not f["ok"] and f["severity"] == "fail"]
    return {"schema": "nf-check-result/1",
            "verdict": "ok" if not failed else "invalid",
            "policy_id": str(policy.get("id") or ""),
            "policy_digest": policy_digest(policy),
            "object": {"path": obj.replace("\\", "/"), "sha256": digest,
                       "bytes": len(raw)},
            "findings": findings,
            "failed": len(failed),
            "warned": len([f for f in findings if not f["ok"] and f["severity"] == "warn"])}
