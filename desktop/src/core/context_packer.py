"""Context Packer（WP-12）：按角色/预算把 Wiki 页打包成带 citations 的上下文。

纪律（WK-07 / PR-06 / §13A L3）：
- **引用齐全**：每个条目必带 citations（指向 spec_ref）；citation_rate 写入报告；
- **预算硬上限**：按字符预算装箱，超预算必截断（truncated=true），**spec_ref/citations 永不截掉**；
- **角色隔离**：author / reviewer / governance 各有页面类型白名单；未知角色=拒绝（角色升级=0）；
- **抗注入**：页面 summary 命中可疑指令模式即移除并计数（injection>0 写入报告），不执行页面内指令；
- **确定性**：同 task/ids + 同预算 + 同角色 → 逐字节一致（排序稳定，无时间戳）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

PAGES_REL = "wiki/pages.json"
PACK_SCHEMA = "nf-context-pack/1"
REPORT_SCHEMA = "nf-context-report/1"
GUIDE = "修复指引："
#: 角色 → 允许的页面类型（最小权限；未列即不可见）
ROLES: Dict[str, tuple] = {
    "author": ("module", "pipeline", "domain"),
    "reviewer": ("protocol", "module", "pipeline", "domain", "asset"),
    "governance": ("protocol", "asset"),
}
#: 注入模式：命中即从 summary 移除并计数（不执行页面内任何指令）
INJECTION_PATTERNS = (
    r"ignore\s+(all\s+)?previous", r"disregard\s+(all\s+)?(previous|above)",
    r"override\s+(the\s+)?instructions", r"you\s+are\s+now", r"system\s*prompt",
    r"<\|\s*im_start\s*\|>", r"忽略(以上|之前|前面)", r"无视(以上|之前|前面)",
    r"系统指令", r"你现在是", r"覆盖(以上|之前)指令",
)
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)
SANITIZED = "[已移除可疑指令]"


class PackError(Exception):
    """带错误码的打包拒绝（消息必含修复指引，供 check33 raise 审计）。"""

    def __init__(self, message: str, code: str = "CONTEXT-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _pages(root: str) -> Dict[str, Dict[str, Any]]:
    path = Path(root) / PAGES_REL
    if not path.is_file():
        raise PackError(
            "缺 %s（Wiki 未编译；修复指引：先跑 python scripts/nf.py wiki build --write）"
            % PAGES_REL, code="WIKI-ID-UNKNOWN")
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {str(p.get("id")): p for p in doc.get("pages") or [] if isinstance(p, dict)}


def _entry(page: Dict[str, Any]) -> tuple:
    """→ (entry, size)；size 按不含 sanitized 的载荷计（预算口径稳定）。"""
    summary = str(page.get("summary") or "")
    sanitized = False
    if _INJECTION_RE.search(summary):
        summary = _INJECTION_RE.sub(SANITIZED, summary)
        sanitized = True
    payload = {"id": str(page.get("id")), "type": str(page.get("type")),
               "summary": summary, "spec_ref": page.get("spec_ref"),
               "citations": list(page.get("citations") or [])}
    entry = dict(payload)
    entry["sanitized"] = sanitized
    return entry, len(json.dumps(payload, ensure_ascii=False))


def _ordered_candidates(pages: Dict[str, Dict[str, Any]], ids: List[str],
                        role: str) -> List[Dict[str, Any]]:
    """候选：直接 context_refs 优先，再本页 relations 目标的邻居（仅允许类型）。"""
    allowed = ROLES.get(role)
    if allowed is None:
        raise PackError(
            "未知角色 %r（修复指引：role 只允许 %s；角色升级=拒绝）"
            % (role, "/".join(sorted(ROLES))), code="ROLE-FORBIDDEN")
    missing = [pid for pid in ids if pid not in pages]
    if missing:
        raise PackError(
            "Wiki 页不在场：%s（修复指引：先编译 Wiki 或用 nf wiki search 查 id）" % missing[:3],
            code="WIKI-ID-UNKNOWN")
    seen: set = set()
    ordered: List[Dict[str, Any]] = []
    for pid in ids:
        page = pages[pid]
        if str(page.get("type")) in allowed:
            ordered.append({"page": page, "weight": 2})
            seen.add(pid)
    for pid in ids:
        for rel in pages[pid].get("relations") or []:
            target = str((rel or {}).get("target"))
            if target in pages and target not in seen and str(pages[target].get("type")) in allowed:
                ordered.append({"page": pages[target], "weight": 1})
                seen.add(target)
    return ordered


def pack_ids(ids: List[str], root: str = ".", budget_chars: int = 4000,
             role: str = "author", task_slot: str = "") -> Dict[str, Any]:
    """按 id 列表打包（CLI/测试共用）；同输入逐字节确定。"""
    if budget_chars < 200:
        raise PackError(
            "预算过小：%s（修复指引：budget_chars ≥200，否则连 spec_ref 都放不下）"
            % budget_chars, code="BUDGET-TOO-SMALL")
    pages = _pages(root)
    candidates = _ordered_candidates(pages, [str(x) for x in ids], role)
    entries: List[Dict[str, Any]] = []
    used = 0
    truncated = False
    injection = 0
    for item in candidates:
        entry, size = _entry(item["page"])
        if str(item["page"].get("type")) not in ROLES[role]:
            continue
        if SANITIZED in str(entry["summary"]):
            injection += 1
        if used + size > budget_chars:
            if entries:
                truncated = True
                break
            # 首条也放不下：截 summary（spec_ref/citations 永不截）
            overhead = len(json.dumps({**entry, "summary": ""}, ensure_ascii=False))
            room = budget_chars - overhead
            if room > 16:
                entry["summary"] = str(entry["summary"])[:max(16, room - 8)] + "…"
                size = len(json.dumps({k: v for k, v in entry.items()
                                       if k != "sanitized"}, ensure_ascii=False))
                truncated = True
            else:
                raise PackError(
                    "预算 %s 放不下首条（修复指引：调大 budget_chars）" % budget_chars,
                    code="BUDGET-TOO-SMALL")
        used += size
        entries.append(entry)
    citations: List[Dict[str, Any]] = []
    seen_cit: set = set()
    for entry in entries:
        for cite in entry.get("citations") or []:
            key = json.dumps(cite, sort_keys=True, ensure_ascii=False)
            if key not in seen_cit:
                seen_cit.add(key)
                citations.append(cite)
    cited = sum(1 for e in entries if e.get("citations"))
    rate = 1.0 if entries and cited == len(entries) else (cited / len(entries) if entries else 0.0)
    report = {"schema": REPORT_SCHEMA, "task_slot": task_slot, "role": role,
              "budget_chars": budget_chars, "used_chars": used,
              "entries": len(entries), "truncated": truncated, "injection": injection,
              "citation_rate": round(rate, 4), "role_isolated": True,
              "allowed_types": list(ROLES[role]), "over_budget": used > budget_chars}
    return {"schema": PACK_SCHEMA, "task_slot": task_slot, "role": role,
            "entries": entries, "citations": citations,
            "budget": {"max_chars": budget_chars, "used_chars": used},
            "truncated": truncated, "report": report}


def pack_task(task: Dict[str, Any], root: str = ".", budget_chars: int = 4000,
              role: str = "author") -> Dict[str, Any]:
    """从 nf-task/1 打包：context_refs 为起点；slot 决定报告里的 task_slot。"""
    if not isinstance(task, dict) or str(task.get("schema")) != "nf-task/1":
        raise PackError(
            "task 不是 nf-task/1（修复指引：先用 nf spec compile 生成任务再打包）",
            code="CONTEXT-INVALID")
    slot = str((task.get("slot") or {}).get("id") or "")
    ids = [str((c or {}).get("id")) for c in task.get("context_refs") or []]
    if not ids:
        raise PackError(
            "task 缺 context_refs（修复指引：重新编译 spec/task 补上下文引用）",
            code="CONTEXT-INVALID")
    return pack_ids(ids, root, budget_chars, role, slot)


def validate_pack(pack: Dict[str, Any]) -> List[str]:
    """打包契约：schema/引用/预算/角色/注入/确定性字段。"""
    issues: List[str] = []
    if str(pack.get("schema")) != PACK_SCHEMA:
        issues.append("pack.schema 必须 %s" % PACK_SCHEMA)
    role = str(pack.get("role"))
    if role not in ROLES:
        issues.append("pack.role 非法：%s" % role)
        return issues
    allowed = set(ROLES[role])
    for entry in pack.get("entries") or []:
        if str(entry.get("type")) not in allowed:
            issues.append("角色隔离失败：%s 类型 %s 不在 %s 白名单"
                          % (entry.get("id"), entry.get("type"), role))
        if not entry.get("citations"):
            issues.append("条目缺 citations：%s" % entry.get("id"))
        if not entry.get("spec_ref"):
            issues.append("条目缺 spec_ref：%s" % entry.get("id"))
    budget = pack.get("budget") or {}
    used = int(budget.get("used_chars") or 0)
    if used > int(budget.get("max_chars") or 0):
        issues.append("超预算未截断：used=%s > max=%s" % (used, budget.get("max_chars")))
    report = pack.get("report") or {}
    if report.get("citation_rate") != 1.0 and pack.get("entries"):
        issues.append("citation_rate 非 100%%：%s" % report.get("citation_rate"))
    if int(report.get("injection") or 0) and not any(
            e.get("sanitized") for e in pack.get("entries") or []):
        issues.append("injection>0 但无 sanitized 标记")
    return issues


def render(pack: Dict[str, Any]) -> str:
    return json.dumps(pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
