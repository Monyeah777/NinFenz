"""闭包台账（nf-closure/1）：把「声称完成」变成「可核对的断言 → 判据 → 反例」。

为什么（2026-11-08，盲区审计协议 L96-101）：能力存在 ≠ 能力被证明。
本模块不写新判据，只做一件事：核对**引用**——
- 每条闭包断言必须给 status：closed（有判据+有反例）或 debt（写明债务原因）；
- 引用的判据必须是**真实存在的测试方法**（AST 扫 desktop/tests，方法名不存在即 fail-closed）；
- 引用证据必须是可跑命令（含 python -m unittest / scripts/）；
- closed 缺判据或缺反例 → 违规；debt 缺 debt 说明 → 违规。
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List

from core import json_doc

SCHEMA = "nf-closure/1"
REL = "protocol/closure/ledger.json"
GUIDE = "修复指引："
STATUSES = ("closed", "debt")


def _load(root: str) -> Any:
    path = Path(root) / REL
    if not path.is_file():
        raise ValueError("闭包台账不在场：" + REL + "（" + GUIDE + "确认 protocol/closure/）")
    try:
        return json_doc.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(REL + " 不是合法 JSON：" + str(exc)) from exc


def test_methods(root: str = ".") -> dict[str, set[str]]:
    """扫 desktop/tests 下所有测试方法 → {文件名: {方法名}}。"""
    out: dict[str, set[str]] = {}
    base = Path(root) / "desktop" / "tests"
    for path in sorted(base.glob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # 语法坏的测试文件不计入索引：它本身会被 unittest 报红
            continue
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                names.add(node.name)
        out[path.name] = names
    return out


def _field_issues(cid: str, item: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for field in ("module", "claim", "reverse_fixture"):
        if not str(item.get(field) or "").strip():
            out.append(cid + " 缺 " + field
                       + "（" + GUIDE + "闭包必须有断言/反例）")
    return out


def _criterion_issues(cid: str, available: dict, ref: Any) -> List[str]:
    if not isinstance(ref, (list, tuple)) or len(ref) != 2:
        return [cid + " 的 criteria 条目必须是 [文件, 方法名]"]
    fname, method = str(ref[0]), str(ref[1])
    if fname not in available:
        return [cid + " 引用了不存在的测试文件：" + fname]
    if method not in available[fname]:
        return [cid + " 引用了不存在的测试方法：" + fname + "::" + method]
    return []


def _criteria_issues(cid: str, available: dict, criteria: Any) -> List[str]:
    if not isinstance(criteria, list) or not criteria:
        return [cid + " 缺 criteria（" + GUIDE + "必须引用真实测试方法）"]
    out: List[str] = []
    for ref in criteria:
        out += _criterion_issues(cid, available, ref)
    return out


def _evidence_issues(cid: str, evidence: Any) -> List[str]:
    if not isinstance(evidence, list) or not evidence:
        return [cid + " 缺 evidence（" + GUIDE + "给可跑命令）"]
    out: List[str] = []
    for cmd in evidence:
        text = str(cmd)
        if not (text.startswith("python ") or text.startswith("bash ")):
            out.append(cid + " 的 evidence 不是可跑命令：" + text[:40])
    return out


def _closed_debt_issues(cid: str, status: str, item: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    if status == "closed" and not item.get("criteria"):
        out.append(cid + " 标 closed 却没有判据（" + GUIDE + "降为 debt 或补判据）")
    if status == "debt" and not str(item.get("debt") or "").strip():
        out.append(cid + " 标 debt 却没写债务原因")
    return out


def _entry_issues(available: dict, item: Any, seen: set) -> List[str]:
    if not isinstance(item, dict):
        return ["entries 里有非对象条目"]
    cid = str(item.get("id") or "")
    if not cid:
        return ["有条目缺 id（" + GUIDE + "给 C-01/D-01 形式 id）"]
    issues: List[str] = []
    if cid in seen:
        issues.append("闭包 id 重复：" + cid)
    seen.add(cid)
    status = str(item.get("status") or "")
    if status not in STATUSES:
        issues.append(cid + " 的 status 非法：" + status)
    issues += _field_issues(cid, item)
    issues += _criteria_issues(cid, available, item.get("criteria"))
    issues += _evidence_issues(cid, item.get("evidence"))
    issues += _closed_debt_issues(cid, status, item)
    return issues


def validate(doc: Any, root: str = ".") -> list[str]:
    """校验台账 → 问题列表（空 = 合法）。"""
    if not isinstance(doc, dict) or str(doc.get("schema")) != SCHEMA:
        return ["台账 schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）"]
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        return ["台账没有 entries（" + GUIDE + "至少一条闭包断言）"]
    available = test_methods(root)
    seen: set[str] = set()
    issues: list[str] = []
    for item in entries:
        issues += _entry_issues(available, item, seen)
    return issues


def load(root: str = ".") -> dict[str, Any]:
    doc = _load(root)
    issues = validate(doc, root)
    if issues:
        raise ValueError("闭包台账不合法：" + "；".join(issues[:3]))
    return doc


def summary(doc: dict[str, Any]) -> dict[str, Any]:
    """按状态与模块汇总（只计数，不打分）。"""
    by_status: dict[str, int] = {}
    by_module: dict[str, dict[str, int]] = {}
    for item in doc.get("entries") or []:
        status = str(item.get("status"))
        by_status[status] = by_status.get(status, 0) + 1
        mod = str(item.get("module"))
        bucket = by_module.setdefault(mod, {})
        bucket[status] = bucket.get(status, 0) + 1
    return {"schema": "nf-closure-summary/1", "total": len(doc.get("entries") or []),
            "by_status": by_status, "by_module": by_module,
            "open_debt": [item.get("id") for item in doc.get("entries") or []
                          if item.get("status") == "debt"]}
