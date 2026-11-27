"""core.wiki_compiler 私有实现分片 2/2（对外只经 core.wiki_compiler 门面导入）：validate_pages 等"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ._part1 import (
    DIR_REL,
    GRAPH_REL,
    GUIDE,
    INDEX_REL,
    LLMS_REL,
    MCP_REL,
    PAGE_SCHEMA_REL,
    PAGES_REL,
    _read_bytes,
    build,
    render,
)


def validate_pages(pages_doc: Dict[str, Any], index_doc: Dict[str, Any],
                   graph_doc: Dict[str, Any], mcp_doc: Dict[str, Any],
                   expected: Dict[str, int], root: str = ".") -> List[str]:
    """结构/覆盖/关系/复用判据（真源 digest 由 check 另比）。"""
    from core import json_schema
    issues: List[str] = []
    schema = json.loads(_read_bytes(root, PAGE_SCHEMA_REL))
    pages = pages_doc.get("pages") or []
    ids = [str(p.get("id")) for p in pages if isinstance(p, dict)]
    if len(ids) != len(set(ids)):
        issues.append("页面 ID 重复：%s" % sorted({i for i in ids if ids.count(i) > 1})[:5])
    by_type: Dict[str, int] = {}
    for page in pages:
        pid = str(page.get("id"))
        problems = json_schema.json_schema_check(page, schema)
        for item in problems[:2]:
            issues.append("%s schema：%s" % (pid, item))
        by_type[str(page.get("type"))] = by_type.get(str(page.get("type")), 0) + 1
        if len(str(page.get("summary") or "")) > 240:
            issues.append("%s summary 过长（>240；投影不复制正文）" % pid)
        for banned in ("body", "content", "text"):
            if banned in page:
                issues.append("%s 含 %s 字段（投影页禁复制正文）" % (pid, banned))
    for ptype, want in expected.items():
        if by_type.get(ptype, 0) != want:
            issues.append("%s 覆盖不足（%s/%s；%s 重新 build）"
                          % (ptype, by_type.get(ptype, 0), want, GUIDE))
    page_ids = set(ids)
    for page in pages:
        for rel in page.get("relations") or []:
            target = str((rel or {}).get("target"))
            if target not in page_ids:
                issues.append("%s 的 relation 目标不可解析：%s" % (page.get("id"), target))
    idx_ids = [str(p.get("id")) for p in (index_doc.get("pages") or [])]
    if sorted(idx_ids) != sorted(ids):
        issues.append("INDEX 与 pages ID 集不一致")
    if sorted(graph_doc.get("nodes") or []) != sorted(ids):
        issues.append("GRAPH nodes 与 pages ID 集不一致")
    for edge in graph_doc.get("edges") or []:
        if str(edge.get("from")) not in page_ids or str(edge.get("to")) not in page_ids:
            issues.append("GRAPH 边端点不在 pages：%r" % edge)
    tools = [str(t.get("name")) for t in (mcp_doc.get("tools") or [])]
    for need in ("wiki_get", "wiki_search", "wiki_related", "wiki_context", "wiki_check"):
        if need not in tools:
            issues.append("MCP 工具缺 %s" % need)
    return issues


def stale_issues(pages_doc: Dict[str, Any], root: str = ".") -> List[str]:
    """陈旧判据：committed 页 digest 必须等于真源现算 digest。"""
    live_doc, _ = build(root)
    live = {p["id"]: p for p in live_doc["pages"]}
    issues = []
    for page in pages_doc.get("pages") or []:
        pid = str(page.get("id"))
        old = str((page.get("provenance") or {}).get("digest"))
        new = str(((live.get(pid) or {}).get("provenance") or {}).get("digest"))
        if pid not in live:
            issues.append("页面 %s 已无真源（重新 build）" % pid)
        elif old != new:
            issues.append("页面 %s 陈旧（源 digest 已变；%s 重新 build）" % (pid, GUIDE))
    return issues


def check(root: str = ".") -> List[str]:
    try:
        pages_doc, rest = build(root)
    except (OSError, ValueError) as exc:
        return ["真源不可读，无法编译 Wiki：%s" % exc]
    issues: List[str] = []
    for rel in (PAGES_REL, INDEX_REL, GRAPH_REL, LLMS_REL, MCP_REL):
        if not (Path(root) / rel).is_file():
            issues.append("缺生成物 %s（%s python scripts/nf.py wiki build --write）" % (rel, GUIDE))
    if issues:
        return issues
    try:
        committed = json.loads(_read_bytes(root, PAGES_REL))
        index = json.loads(_read_bytes(root, INDEX_REL))
        graph = json.loads(_read_bytes(root, GRAPH_REL))
        mcp = json.loads(_read_bytes(root, MCP_REL))
    except (OSError, ValueError) as exc:
        return ["wiki 生成物不可解析：%s" % exc]
    issues += validate_pages(committed, index, graph, mcp, rest["expected"], root)
    issues += stale_issues(committed, root)
    return issues


def write(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    from core import atomic_write
    files = render(root)
    dest = Path(root) / DIR_REL
    dest.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        atomic_write.write_text(Path(root) / rel, text)
    issues = check(root)
    stats = {"pages": len(json.loads(files[PAGES_REL])["pages"]),
             "files": len(files)}
    return issues, stats


def _committed(root: str) -> Dict[str, Any]:
    return json.loads(_read_bytes(root, PAGES_REL))


def get(page_id: str, root: str = ".") -> Optional[Dict[str, Any]]:
    for page in _committed(root).get("pages") or []:
        if str(page.get("id")) == page_id:
            return page
    return None


def search(query: str, root: str = ".") -> List[Dict[str, Any]]:
    q = query.lower()
    out = []
    for page in _committed(root).get("pages") or []:
        blob = " ".join([str(page.get("id")), str(page.get("type")),
                         str(page.get("summary"))]).lower()
        if q in blob:
            out.append(page)
    return sorted(out, key=lambda p: p["id"])


def related(page_id: str, root: str = ".") -> Dict[str, List[Dict[str, str]]]:
    pages = {str(p.get("id")): p for p in _committed(root).get("pages") or []}
    outgoing = []
    incoming = []
    for pid, page in pages.items():
        for rel in page.get("relations") or []:
            if str(rel.get("target")) == page_id:
                incoming.append({"from": pid, "kind": str(rel.get("kind"))})
            if pid == page_id:
                outgoing.append({"to": str(rel.get("target")), "kind": str(rel.get("kind"))})
    return {"outgoing": sorted(outgoing, key=lambda x: (x["to"], x["kind"])),
            "incoming": sorted(incoming, key=lambda x: (x["from"], x["kind"]))}


def context(ids: List[str], budget: int = 1200, root: str = ".") -> Dict[str, Any]:
    """打包上下文：按 id 顺序取页 summary+refs，受字符预算限制；带 citations。"""
    picked = []
    used = 0
    for page_id in ids:
        page = get(page_id, root)
        if not page:
            continue
        entry = {"id": page["id"], "type": page["type"], "summary": page["summary"],
                 "spec_ref": page["spec_ref"], "citations": page.get("citations") or []}
        size = len(json.dumps(entry, ensure_ascii=False))
        if used + size > budget:
            if not picked:
                overhead = len(json.dumps({**entry, "summary": ""}, ensure_ascii=False))
                room = budget - used - overhead
                if room > 16:
                    entry["summary"] = entry["summary"][:max(16, room - 8)] + "…"
                    used = budget
                    picked.append(entry)
            break
        used += size
        picked.append(entry)
    return {"schema": "nf-wiki-context/1", "entries": picked, "chars": used,
            "budget": budget, "truncated": len(picked) < len(ids)}
