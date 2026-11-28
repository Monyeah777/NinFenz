"""core.cq_scan 私有实现分片 2/2（对外只经 core.cq_scan 门面导入）：build、artifact_issues 等"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ._part1 import (
    DIMS,
    DIR_REL,
    GUIDE,
    SCAN_REL,
    SCAN_SCHEMA,
    SCANNERS,
    SEVERITIES,
    TOOLCHAIN_REL,
    TOOLCHAIN_SCHEMA,
    TOOLS,
    _fingerprint,
    _tracked,
    toolchain,
)


def _scan_dims(root: str, files: Any
               ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """跑 SCANNERS 全维 → (dims, findings, hotspots)；findings 的 id 依序编号。"""
    dims: Dict[str, Any] = {}
    findings: List[Dict[str, Any]] = []
    hotspots: List[Dict[str, Any]] = []
    for dim, fn in SCANNERS:
        stats, got = fn(root, files)
        dims[dim] = stats
        for item in got:
            item["id"] = "F-%03d" % (len(findings) + 1)
            findings.append(item)
        if dim == "radon-cc":
            hotspots = stats.get("hotspots") or []
    return dims, findings, hotspots


def build(root: str = ".") -> Dict[str, Any]:
    """跑全量自动扫描 → (toolchain, scan)。"""
    tc = toolchain(root)
    dims, findings, hotspots = _scan_dims(root, _tracked(root))
    p0 = [f for f in findings if f["severity"] == "P0"]
    p1 = [f for f in findings if f["severity"] == "P1"]
    scan = {"schema": SCAN_SCHEMA, "fingerprint": _fingerprint(root, tc),
            "toolchain_fingerprint": tc.get("blocked"),
            "dimensions": dims, "findings_counts":
                {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES},
            "p0": len(p0), "findings": findings, "hotspots": hotspots,
            "note": "全量自动扫描（CQ1）；缺失工具记 blocked，不冒充通过；P0/P1 进整改"}
    return tc, scan


def artifact_issues(tc: Dict[str, Any], scan: Dict[str, Any]) -> List[str]:
    """扫描件结构判据（供测试/变异自证复用；不重跑扫描）。"""
    issues = _toolchain_issues(tc)
    issues += _scan_head_issues(scan)
    issues += _dimension_issues(scan.get("dimensions") or {})
    findings = scan.get("findings") or []
    issues += _finding_issues(findings)
    issues += _count_issues(findings, scan.get("findings_counts") or {})
    issues += _hotspot_issues(scan.get("hotspots") or [])
    return issues


def _toolchain_issues(tc: Dict[str, Any]) -> List[str]:
    """toolchain 头与工具条目面。"""
    issues: List[str] = []
    if str(tc.get("schema")) != TOOLCHAIN_SCHEMA:
        issues.append("toolchain schema 不匹配")
    tools = tc.get("tools") or []
    if len(tools) < len(TOOLS):
        issues.append("toolchain 工具数少于登记矩阵（%d < %d）" % (len(tools), len(TOOLS)))
    for entry in tools:
        issues += _tool_entry_issues(entry)
    blocked = tc.get("blocked") or []
    if blocked != [e["id"] for e in tools if e.get("status") != "ok"]:
        issues.append("blocked 列表与工具状态不一致（缺失=BLOCKED，不冒充通过）")
    return issues


def _tool_entry_issues(entry) -> List[str]:
    """单条工具条目的 status/理由/版本口径。"""
    issues: List[str] = []
    if not isinstance(entry, dict) or not str(entry.get("id")):
        issues.append("toolchain 含无效条目")
        return issues
    if str(entry.get("status")) not in ("ok", "blocked"):
        issues.append("%s 的 status 非法：%s" % (entry.get("id"), entry.get("status")))
    if entry.get("status") == "blocked" and not str(entry.get("blocked_reason") or "").strip():
        issues.append("%s blocked 但缺理由" % entry.get("id"))
    if entry.get("status") == "ok" and not str(entry.get("version") or "").strip():
        issues.append("%s ok 但缺版本（工具版本必须固定记录）" % entry.get("id"))
    return issues


def _scan_head_issues(scan: Dict[str, Any]) -> List[str]:
    """scan 头（schema / fingerprint）。"""
    issues: List[str] = []
    if str(scan.get("schema")) != SCAN_SCHEMA:
        issues.append("scan schema 不匹配")
    fp = str(scan.get("fingerprint") or "")
    if len(fp) != 64:
        issues.append("scan.fingerprint 必须是 64 位 sha256")
    return issues


def _dimension_issues(dims: Dict[str, Any]) -> List[str]:
    """扫描维度齐备。"""
    issues: List[str] = []
    for dim in DIMS:
        if dim not in dims:
            issues.append("缺扫描维度：%s" % dim)
    return issues


def _finding_issues(findings: List[Any]) -> List[str]:
    """findings 的 severity 词表与必填字段（首个违规即止）。"""
    issues: List[str] = []
    for item in findings:
        if str(item.get("severity")) not in SEVERITIES:
            issues.append("findings 含非法 severity：%s" % item.get("severity"))
            break
        if not str(item.get("dim")) or not str(item.get("owner")) or not str(item.get("status")):
            issues.append("finding %s 缺 dim/owner/status" % item.get("id"))
            break
    return issues


def _count_issues(findings: List[Any], counts: Dict[str, Any]) -> List[str]:
    """findings_counts 与实况一致。"""
    issues: List[str] = []
    for sev in SEVERITIES:
        want = sum(1 for f in findings if f.get("severity") == sev)
        if counts.get(sev) != want:
            issues.append("%s 计数不一致（记录 %s / 实际 %s）" % (sev, counts.get(sev), want))
    return issues


def _hotspot_issues(hotspots: List[Any]) -> List[str]:
    """hotspots 按复杂度降序。"""
    issues: List[str] = []
    if any(int(h.get("complexity") or 0) < int(hotspots[i + 1].get("complexity") or 0)
           for i, h in enumerate(hotspots[:-1])):
        issues.append("hotspots 未按复杂度降序")
    return issues


def render_json(doc: Dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_findings(findings: List[Dict[str, Any]]) -> str:
    return "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n"
                   for f in findings)


def render_hotspots(scan: Dict[str, Any]) -> str:
    rows = scan.get("hotspots") or []
    lines = ["# CQ 热点（复杂度 top）", "",
             "> 由 `python scripts/cq_scan.py --run` 生成；radon CC 单函数 ≥20 入榜。", "",
             "| 文件 | 函数 | CC | 行 |", "|---|---|---|---|"]
    for item in rows:
        lines.append("| `%s` | `%s` | %s | %s |" % (item.get("file"), item.get("name"),
                                                    item.get("complexity"), item.get("lineno")))
    if not rows:
        lines.append("| — | — | — | — |")
    return "\n".join(lines) + "\n"


def write(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    from core import atomic_write
    tc, scan = build(root)
    dest = Path(root) / DIR_REL
    dest.mkdir(parents=True, exist_ok=True)
    atomic_write.write_text(dest / "toolchain.json", render_json(tc))
    atomic_write.write_text(dest / "scan.json", render_json(scan))
    atomic_write.write_text(dest / "findings.jsonl", render_findings(scan["findings"]))
    atomic_write.write_text(dest / "hotspots.md", render_hotspots(scan))
    issues = []
    if scan["p0"]:
        issues.append("P0=%d（%s 先修 P0 再进 CQ2）" % (scan["p0"], GUIDE))
    if tc.get("blocked"):
        issues.append("缺失/不可用工具：%s（BLOCKED，不冒充通过）" % ", ".join(tc["blocked"]))
    return issues, {"toolchain": tc, "scan": scan}


def check(root: str = ".") -> List[str]:
    """新鲜度：产物在场 + 指纹（输入件内容 + 工具版本）与实时一致。"""
    scan_path = Path(root) / SCAN_REL
    tc_path = Path(root) / TOOLCHAIN_REL
    for path in (scan_path, tc_path):
        if not path.is_file():
            return ["缺 %s（%s 跑 python scripts/cq_scan.py --run）"
                    % (path.relative_to(Path(root)).as_posix(), GUIDE)]
    try:
        scan = json.loads(scan_path.read_text(encoding="utf-8"))
        tc = json.loads(tc_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["CQ 产物不可解析：%s" % exc]
    live_tc = toolchain(root)
    live_fp = _fingerprint(root, live_tc)
    if scan.get("fingerprint") != live_fp:
        return ["CQ 扫描件过期（输入件或工具版本已变；%s 跑 python scripts/cq_scan.py --run）"
                % GUIDE]
    return []
