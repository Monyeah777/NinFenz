"""anchor 核验内部件（对外只经 core.trust.anchor 门面导入）：verify_anchor_set 及其判据件。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core import json_schema


def _tsa_root(policy: dict, tsa_id: str) -> dict | None:
    for item in (policy or {}).get("tsa_roots") or []:
        if isinstance(item, dict) and str(item.get("id")) == tsa_id:
            return item
    return None


def _anchor_failure(code: str, message: str, fix: str) -> dict:
    return {"facts": {"time_token": "invalid", "transparency_sth": "invalid",
                      "public_anchor": "none"},
            "details": [], "issues": [{"code": code, "message": message, "fix": fix}]}


def _rfc3161_detail(
    item: dict, detail: dict, target_digest: str, checks: dict, policy: dict
) -> dict:
    tsa_id = str(item.get("tsa") or "")
    root_item = _tsa_root(policy, tsa_id)
    if root_item is None:
        detail.update(status="none", reason="TSA-ROOT-MISSING")
    elif not callable(checks.get("rfc3161")):
        detail.update(status="none", reason="VERIFIER-MISSING")
    else:
        got = checks["rfc3161"](item, target_digest)
        detail.update(status="ok" if got.get("ok") else "invalid",
                      reason=got.get("reason", ""), gen_time=got.get("gen_time", ""))
    return detail


def _checked_detail(
    item: dict, detail: dict, target_digest: str, checks: dict, kind: str
) -> dict:
    if not callable(checks.get(kind)):
        detail.update(status="none", reason="VERIFIER-MISSING")
    else:
        got = checks[kind](item, target_digest)
        detail.update(status="ok" if got.get("ok") else "invalid",
                      reason=got.get("reason", ""))
    return detail


def _git_detail(item: dict, detail: dict, target_digest: str, checks: dict) -> dict:
    if not callable(checks.get("git-commit")):
        detail.update(status="none", reason="VERIFIER-MISSING")
    else:
        got = checks["git-commit"](item, target_digest)
        detail.update(status="ok" if got.get("ok") else "invalid",
                      reason=got.get("reason", ""),
                      warnings=got.get("warnings") or [])
    return detail


def _anchor_detail(item: dict, target_digest: str, checks: dict, policy: dict) -> dict:
    kind = str(item.get("kind"))
    detail = {"kind": kind, "status": "none"}
    if kind == "rfc3161":
        return _rfc3161_detail(item, detail, target_digest, checks, policy)
    if kind == "transparency-sth":
        return _checked_detail(item, detail, target_digest, checks, "transparency-sth")
    if kind == "witness":
        return _checked_detail(item, detail, target_digest, checks, "witness")
    if kind == "git-commit":
        return _git_detail(item, detail, target_digest, checks)
    return detail


def _ordered_status(statuses: list) -> str:
    if "invalid" in statuses:
        return "invalid"
    if "ok" in statuses:
        return "ok"
    return "none"


def _witness_threshold_issue(policy: dict, statuses: list, facts: dict) -> list:
    threshold = int(((policy or {}).get("anchors") or {}).get("witness_threshold") or 0)
    if (threshold > 0 and facts["transparency_sth"] == "ok"
            and statuses.count("ok") < threshold):
        facts["transparency_sth"] = "none"
        return [{"code": "WITNESS-THRESHOLD-NOT-MET",
                 "message": f"witness 有效 {statuses.count('ok')} "
                            f"< 策略阈值 {threshold}",
                 "fix": "收集足够 witness 签名后重验"}]
    return []


def _facts_from_statuses(status_by_kind: dict, policy: dict) -> tuple[dict, list]:
    facts = {"time_token": "none", "transparency_sth": "none", "public_anchor": "none"}
    issues: list = []
    for kind, statuses in status_by_kind.items():
        if kind == "rfc3161":
            facts["time_token"] = _ordered_status(statuses)
        elif kind == "transparency-sth":
            facts["transparency_sth"] = _ordered_status(statuses)
        elif kind == "witness":
            if "invalid" in statuses:
                facts["transparency_sth"] = "invalid"
            issues += _witness_threshold_issue(policy, statuses, facts)
    return facts, issues


def _invalid_detail_issues(details: list) -> list:
    issues: list = []
    for detail in details:
        if detail["status"] == "invalid":
            code = str(detail.get("reason") or "ANCHOR-INVALID")
            issues.append({"code": code,
                           "message": f"{detail['kind']} 锚核验失败",
                           "fix": "修锚件/换正确信任根后重验；被篡改的锚必须拒"})
    return issues


def verify_anchor_set(doc: Any, target_digest: str, policy: dict,
                      verifiers: dict | None = None,
                      schema: dict | None = None,
                      root: str = ".") -> dict:
    """核验锚件 → {facts, details, issues}。facts 供 verify.decide 使用。"""
    if schema is None:
        from core.trust.anchor import load_schema

        schema = load_schema(root)
    check_schema = schema
    problems = json_schema.json_schema_check(doc, check_schema)
    if problems:
        return _anchor_failure("ANCHOR-SCHEMA-INVALID", problems[0],
                               "按 nf-anchor/1 修锚件后重验")
    if doc.get("target_digest") != target_digest:
        return _anchor_failure("ANCHOR-TARGET-MISMATCH", "锚件 target_digest 与被证摘要不符",
                               "重新对正确摘要做锚，别把旧锚挂到新对象上")
    checks = verifiers or {}
    details: list = []
    status_by_kind: dict = {}
    for item in doc.get("anchors") or []:
        kind = str(item.get("kind"))
        detail = _anchor_detail(item, target_digest, checks, policy)
        details.append(detail)
        status_by_kind.setdefault(kind, []).append(detail["status"])
    facts, fact_issues = _facts_from_statuses(status_by_kind, policy)
    issues = fact_issues + _invalid_detail_issues(details)
    return {"facts": facts, "details": details, "issues": issues}
