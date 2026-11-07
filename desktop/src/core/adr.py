"""架构裁决记录（nf-adr/1）+ 文档台账（nf-doc-ledger/1）：把「裁决」做成可校验数据。

为什么不用散文：16 份文档互相打架的地方（双核/ABI/多租户/命名）已经吵过一轮，
散文裁决下一次还会被覆盖。这里把它变成数据 + 校验脚本 + 门禁：
- 每条 ADR：id/title/status/topic/decision/supersedes/evidence/falsifier（可证伪条件必填）；
- 取代关系构成有向图，必须无环；同一 topic 至多一条 current；
- evidence 必须指向仓内**在场**文件（裁决要能被实测支撑）；
- 文档台账：16 份各一个状态，superseded 必须指向在场 current，同 topic 至多一条 current；
- 与仓库现实对账：ADR-004 说 reasoning/ 是 dormant，若目录出现则裁决须改。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ADR_SCHEMA = "nf-adr/1"
LEDGER_SCHEMA = "nf-doc-ledger/1"
ADR_REL = "protocol/adr/registry.json"
LEDGER_REL = "protocol/docs_ledger.json"
STATUSES = ("current", "superseded", "draft", "evidence")
GUIDE = "修复指引："


def _load(root: str, rel: str, schema: str) -> Any:
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError("文件不在场：" + rel + "（" + GUIDE + "确认路径）")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(rel + " 不是合法 JSON：" + str(exc)) from exc
    if str(doc.get("schema") or "") != schema:
        raise ValueError(rel + " schema 不匹配（" + GUIDE + "需要 " + schema + "）")
    return doc


def validate_adr(doc: Any) -> list[str]:
    """校验 ADR 注册表 → 问题列表（空 = 合法）。"""
    issues: list[str] = []
    if not isinstance(doc, dict) or str(doc.get("schema")) != ADR_SCHEMA:
        return ["ADR schema 不匹配（" + GUIDE + "需要 " + ADR_SCHEMA + "）"]
    adrs = doc.get("adrs")
    if not isinstance(adrs, list) or not adrs:
        return ["缺 adrs（" + GUIDE + "至少一条裁决）"]
    seen: set[str] = set()
    current_topics: dict[str, str] = {}
    for item in adrs:
        if not isinstance(item, dict):
            issues.append("adrs 里有非对象条目（" + GUIDE + "改写成对象）")
            continue
        aid = str(item.get("id") or "")
        if not aid.startswith("ADR-"):
            issues.append("裁决 id 必须 ADR- 开头：" + aid)
        if aid in seen:
            issues.append("裁决 id 重复：" + aid)
        seen.add(aid)
        for field in ("title", "decision", "falsifier"):
            if not str(item.get(field) or "").strip():
                issues.append(aid + " 缺 " + field + "（" + GUIDE + "裁决必须可执行、可证伪）")
        if str(item.get("status")) not in STATUSES:
            issues.append(aid + " 的 status 非法：" + str(item.get("status")))
        if str(item.get("status")) == "current":
            topic = str(item.get("topic") or "")
            if not topic:
                issues.append(aid + " 是 current 但没有 topic"
                              "（" + GUIDE + "同主题只能一条 current）")
            elif topic in current_topics:
                issues.append("主题 " + topic + " 有两条 current：" + current_topics[topic]
                              + " 与 " + aid)
            else:
                current_topics[topic] = aid
        ev = item.get("evidence")
        if not isinstance(ev, list) or not ev:
            issues.append(aid + " 缺 evidence（" + GUIDE + "裁决必须列出支撑件）")
    # supersedes 引用必须指向已登记裁决或已登记文档（散文名允许，故只查自引用/成环）
    ids = {str(i.get("id")) for i in adrs if isinstance(i, dict)}
    graph = {str(i.get("id")): [str(x) for x in i.get("supersedes") or []
                                if str(x) in ids]
             for i in adrs if isinstance(i, dict)}
    for node, targets in graph.items():
        for target in targets:
            if target == node:
                issues.append(node + " supersedes 自引用（" + GUIDE + "裁决不能取代自己）")
    for cycle in _cycles(graph):
        issues.append("supersedes 成环：" + cycle)
    return issues


def _cycles(graph: dict[str, list[str]]) -> list[str]:
    state: dict[str, int] = {}
    found: list[str] = []

    def visit(node: str, stack: list[str]) -> None:
        if state.get(node) == 1:
            found.append(node)
            return
        if state.get(node) == 2:
            return
        state[node] = 1
        for nxt in graph.get(node, []):
            visit(nxt, stack + [node])
        state[node] = 2

    for node in graph:
        visit(node, [])
    return sorted(set(found))


def validate_ledger(doc: Any, adr_doc: dict[str, Any] | None = None) -> list[str]:
    """校验文档台账 → 问题列表。"""
    issues: list[str] = []
    if not isinstance(doc, dict) or str(doc.get("schema")) != LEDGER_SCHEMA:
        return ["台账 schema 不匹配（" + GUIDE + "需要 " + LEDGER_SCHEMA + "）"]
    docs = doc.get("docs")
    if not isinstance(docs, list) or not docs:
        return ["台账缺 docs（" + GUIDE + "登记 16 份文档）"]
    names = {str(d.get("name")) for d in docs if isinstance(d, dict)}
    current_topics: dict[str, str] = {}
    adr_ids = {str(a.get("id")) for a in (adr_doc or {}).get("adrs") or []
               if isinstance(a, dict)}
    for item in docs:
        if not isinstance(item, dict):
            issues.append("docs 里有非对象条目")
            continue
        name = str(item.get("name") or "")
        if not name:
            issues.append("有条目缺 name（" + GUIDE + "补文档名）")
            continue
        status = str(item.get("status") or "")
        if status not in STATUSES:
            issues.append(name + " 的 status 非法：" + status)
        if status == "current":
            topic = str(item.get("topic") or "")
            if topic in current_topics:
                issues.append("主题 " + topic + " 有两条 current 文档：" + current_topics[topic]
                              + " 与 " + name)
            else:
                current_topics[topic] = name
        if status == "superseded":
            target = str(item.get("superseded_by") or "")
            if not target:
                issues.append(name + " 是 superseded 但没写 superseded_by")
            elif target not in names:
                issues.append(name + " 的 superseded_by 不在台账：" + target)
            else:
                hit = next((d for d in docs if isinstance(d, dict)
                            and str(d.get("name")) == target), None)
                if hit and str(hit.get("status")) != "current":
                    issues.append(name + " 被 " + target + " 取代，但后者不是 current")
        adr_ref = str(item.get("adr") or "")
        if adr_ref and adr_ids and adr_ref not in adr_ids:
            issues.append(name + " 指向未登记的裁决：" + adr_ref)
    return issues


def load(root: str = ".") -> dict[str, Any]:
    adr_doc = _load(root, ADR_REL, ADR_SCHEMA)
    ledger = _load(root, LEDGER_REL, LEDGER_SCHEMA)
    issues = validate_adr(adr_doc) + validate_ledger(ledger, adr_doc)
    if issues:
        raise ValueError("ADR/台账不合法：" + "；".join(issues[:3]))
    return {"schema": "nf-adr-bundle/1", "adr": adr_doc, "ledger": ledger}


def reconcile(root: str = ".") -> dict[str, Any]:
    """裁决与仓库现实对账 → {ok, findings[], counts}。"""
    bundle = load(root)
    findings: list[dict[str, Any]] = []
    reasoning_dir = Path(root) / "desktop/src/core/meta_cockpit/reasoning"
    adr004 = next((a for a in bundle["adr"]["adrs"] if a.get("id") == "ADR-004"), {})
    if reasoning_dir.is_dir() and str(adr004.get("status")) == "current" \
            and "dormant" in str(adr004.get("decision")):
        findings.append({"code": "R1",
                         "detail": "reasoning/ 已出现在 HEAD，但 ADR-004 仍写 dormant"
                                   "（" + GUIDE + "改为 active 并补默认路径判据）"})
    if not reasoning_dir.is_dir() and "dormant" not in str(adr004.get("decision")).lower():
        findings.append({"code": "R2", "detail": "reasoning/ 不在 HEAD，但 ADR-004 未标 dormant"})
    for adr in bundle["adr"]["adrs"]:
        for ref in adr.get("evidence") or []:
            text = str(ref)
            if text.startswith("git branch") or "（" in text:
                continue
            if not (Path(root) / text).exists():
                findings.append({"code": "R3", "detail": adr.get("id") + " 的 evidence 不在场："
                                                         + text})
    current_docs = [d for d in bundle["ledger"]["docs"] if d.get("status") == "current"]
    return {"schema": "nf-adr-reconcile/1", "ok": not findings, "findings": findings,
            "counts": {"adrs": len(bundle["adr"]["adrs"]),
                       "docs": len(bundle["ledger"]["docs"]),
                       "current_docs": len(current_docs)}}
