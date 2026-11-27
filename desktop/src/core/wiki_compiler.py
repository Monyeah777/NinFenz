"""LLMWiki 编译器（WP-10，`nf wiki build/check/get/search/related/context`）。

纪律（WK-01…WK-08）：
- **Wiki 是投影，不是第二真源**：页面只由真源（registry/03 管线/05 资产/community DOMAIN_SPEC/
  protocol schemas）编译；页面只存 summary + spec_ref + digest + relations，**不复制正文**；
- 全输出确定性（同输入逐字节一致）；`check` 用真源现算 digest 比对 → 源变即陈旧；
- 覆盖：每类真源至少一页；ID 唯一；relations 目标可解析；
- 三入口：CLI（本模块）、`wiki/llms.txt`、`wiki/mcp.json`（MCP 工具清单）；
- 生成物 `wiki/` 禁手改：`nf wiki check` 依据真源 digest 判 stale，改生成物即红。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_PAGES = "nf-wiki-pages/1"
SCHEMA_INDEX = "nf-wiki-index/1"
SCHEMA_GRAPH = "nf-wiki-graph/1"
SCHEMA_MCP = "nf-wiki-mcp/1"
DIR_REL = "wiki"
PAGES_REL = DIR_REL + "/pages.json"
INDEX_REL = DIR_REL + "/INDEX.json"
GRAPH_REL = DIR_REL + "/GRAPH.json"
LLMS_REL = DIR_REL + "/llms.txt"
MCP_REL = DIR_REL + "/mcp.json"
PAGE_SCHEMA_REL = "protocol/production/wiki-page.schema.json"
REGISTRY_REL = "desktop/src/core/registry.json"
GUIDE = "修复指引："
TYPES = ("protocol", "module", "pipeline", "asset", "domain")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bytes(root: str, rel: str) -> bytes:
    return (Path(root) / rel).read_bytes()


def _dir_digest(root: str, rel: str) -> str:
    """目录树摘要（相对路径 + 每文件 digest，排序后哈希）——不读正文进页面。"""
    base = Path(root) / rel
    entries = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        entries.append(str(path.relative_to(base)).replace("\\", "/")
                       + ":" + _sha(path.read_bytes()))
    return _sha("\n".join(entries).encode("utf-8"))


@dataclass(frozen=True)
class PageOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    digest: str
    relations: Optional[List[Dict[str, str]]] = None
    citations: Optional[List[Dict[str, str]]] = None
    machine_contract: Optional[Dict[str, Any]] = None


def _page(
    page_id: str,
    ptype: str,
    summary: str,
    spec_ref: str,
    source: str,
    opts: PageOptions,
) -> Dict[str, Any]:
    digest = opts.digest
    relations = opts.relations
    citations = opts.citations
    machine_contract = opts.machine_contract
    return {"schema": "nf-wiki-page/1", "id": page_id, "type": ptype,
            "summary": summary, "spec_ref": {"id": spec_ref},
            "machine_contract": machine_contract or {},
            "relations": relations or [],
            "constraints": ["投影页：禁手改；改真源后重编译"],
            "llm_hints": ["需要正文请读 spec_ref 指向的真源"],
            "version": 1,
            "provenance": {"source": source, "digest": digest},
            "citations": citations or [{"id": spec_ref}]}


def _registry_modules(root: str) -> List[Dict[str, Any]]:
    doc = json.loads(_read_bytes(root, REGISTRY_REL))
    return [m for m in doc.get("modules") or [] if isinstance(m, dict)]


def _pipeline_files(root: str) -> List[str]:
    base = Path(root)
    return sorted(p.relative_to(base).as_posix() for p in (base / "03_管线库").glob("*.md"))


def _domain_specs(root: str) -> List[str]:
    base = Path(root)
    return sorted(p.relative_to(base).as_posix()
                  for p in (base / "community").glob("*/outputs/DOMAIN_SPEC.json"))


def _schema_files(root: str) -> List[Tuple[str, str]]:
    out = []
    base = Path(root)
    for sub in ("protocol/schema", "protocol/production"):
        for path in sorted((base / sub).glob("*.schema.json")):
            out.append((sub.split("/")[-1], path.relative_to(base).as_posix()))
    return out


def _asset_entries(root: str) -> List[str]:
    root_path = Path(root)
    base = root_path / "05_资产库"
    if not base.is_dir():
        return []
    out = []
    for path in sorted(base.iterdir()):
        if path.name == "README.md" and path.is_file():
            out.append("05_资产库/README.md")
        elif path.is_file():
            out.append(path.relative_to(root_path).as_posix())
        elif path.is_dir():
            out.append(path.relative_to(root_path).as_posix())
    return out


def build(root: str = ".") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """编译 → (pages_doc, expected)；expected = 每类真源计数（覆盖判据用）。"""
    pages: List[Dict[str, Any]] = []
    expected: Dict[str, int] = {}
    # protocol schema 页（IDL 9 + 生产 5）
    for sub, rel in _schema_files(root):
        data = _read_bytes(root, rel)
        schema = json.loads(data)
        sid = str(schema.get("$id") or schema.get("const") or Path(rel).stem)
        pid = "wiki:protocol:%s/%s" % (sub, Path(rel).name.replace(".schema.json", ""))
        pages.append(_page(
            pid,
            'protocol',
            '%s 契约（%s）' % (Path(rel).name, sid),
            rel,
            rel,
            opts=PageOptions(
                digest=_sha(data),
                machine_contract={'required': schema.get('required') or []},
            ),
        ))
    expected["protocol"] = len(pages)
    # module 页
    modules = _registry_modules(root)
    registry_bytes = _read_bytes(root, REGISTRY_REL)
    module_proto = "wiki:protocol:schema/module"
    for mod in modules:
        mid = str(mod.get("id"))
        if not mid or any(ch.isspace() for ch in mid):
            continue
        pages.append(_page(
            'wiki:module:' + mid,
            'module',
            '%s（%s / 来源 %s）' % (mod.get('name'), mod.get('category'), mod.get('source')),
            '%s#modules/%s' % (REGISTRY_REL, mid),
            REGISTRY_REL,
            opts=PageOptions(
                digest=_sha(registry_bytes),
                relations=[{'kind': 'implements', 'target': module_proto}],
                machine_contract={'mounts': mod.get('mounts') or []},
            ),
        ))
    expected["module"] = len(modules)
    # pipeline 页
    assembly_proto = "wiki:protocol:production/assembly"
    pipes = _pipeline_files(root)
    for rel in pipes:
        data = _read_bytes(root, rel)
        pid = "wiki:pipeline:" + Path(rel).stem
        pages.append(_page(
            pid,
            'pipeline',
            Path(rel).stem + ' 管线',
            rel,
            rel,
            opts=PageOptions(
                digest=_sha(data),
                relations=[{'kind': 'implements', 'target': assembly_proto}],
            ),
        ))
    expected["pipeline"] = len(pipes)
    # domain 页
    contract_proto = "wiki:protocol:production/contract"
    for rel in _domain_specs(root):
        data = _read_bytes(root, rel)
        spec = json.loads(data)
        code = str(spec.get("code") or Path(rel).parent.parent.name)
        pid = "wiki:domain:" + code
        pages.append(_page(
            pid,
            'domain',
            '%s（%s/%s）' % (spec.get('domain') or code, spec.get('section') or '-', spec.get('content_tier') or '-'),
            rel,
            rel,
            opts=PageOptions(
                digest=_sha(data),
                relations=[{'kind': 'references', 'target': contract_proto}],
                machine_contract={'subdivisions': len(spec.get('subdivisions') or [])},
            ),
        ))
    expected["domain"] = len(_domain_specs(root))
    # asset 页
    assets = _asset_entries(root)
    for rel in assets:
        path = Path(root) / rel
        digest = _sha(path.read_bytes()) if path.is_file() else _dir_digest(root, rel)
        pid = "wiki:asset:" + rel.replace("05_资产库/", "").replace("/", "-")
        pages.append(_page(
            pid,
            'asset',
            rel.replace('05_资产库/', ''),
            rel,
            rel,
            opts=PageOptions(
                digest=digest,
                relations=[{'kind': 'references', 'target': 'wiki:protocol:schema/asset_contracts'}],
            ),
        ))
    expected["asset"] = len(assets)
    pages.sort(key=lambda p: p["id"])
    index = {"schema": SCHEMA_INDEX,
             "pages": [{"id": p["id"], "type": p["type"], "summary": p["summary"],
                        "source": p["provenance"]["source"],
                        "digest": p["provenance"]["digest"]} for p in pages]}
    edges = [{"from": p["id"], "kind": r["kind"], "to": r["target"]}
             for p in pages for r in p.get("relations") or []]
    graph = {"schema": SCHEMA_GRAPH,
             "nodes": [p["id"] for p in pages],
             "edges": sorted(edges, key=lambda e: (e["from"], e["kind"], e["to"]))}
    pages_doc = {"schema": SCHEMA_PAGES, "pages": pages}
    return pages_doc, {"index": index, "graph": graph, "expected": expected}


def _llms_text(index: Dict[str, Any]) -> str:
    lines = ["# NF LLMWiki（投影；正文在 spec_ref 指向的真源，本处不复制）", ""]
    for page in index["pages"]:
        lines.append("- %s — %s（%s；source=%s）"
                     % (page["id"], page["summary"], page["type"], page["source"]))
    return "\n".join(lines) + "\n"


def _mcp_doc() -> Dict[str, Any]:
    tools = [
        {"name": "wiki_get", "args": {"id": "string"}, "desc": "按 id 取单页（含 spec_ref/relations）"},
        {"name": "wiki_search", "args": {"q": "string"}, "desc": "按 id/summary/type 子串检索"},
        {"name": "wiki_related", "args": {"id": "string"}, "desc": "邻居（出边+入边）"},
        {"name": "wiki_context", "args": {"ids": "string[]", "budget": "int"},
         "desc": "打包上下文（带 citations，受预算限制）"},
        {"name": "wiki_check", "args": {}, "desc": "完整性/陈旧/关系/ID 自检"},
    ]
    return {"schema": SCHEMA_MCP, "tools": tools}


def render(root: str = ".") -> Dict[str, str]:
    pages_doc, rest = build(root)
    index = rest["index"]
    files = {PAGES_REL: json.dumps(pages_doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
             INDEX_REL: json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
             GRAPH_REL: json.dumps(rest["graph"], ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n",
             LLMS_REL: _llms_text(index),
             MCP_REL: json.dumps(_mcp_doc(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"}
    return files


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
