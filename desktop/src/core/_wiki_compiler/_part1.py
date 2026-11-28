"""core.wiki_compiler 私有实现分片 1/2（对外只经 core.wiki_compiler 门面导入）：SCHEMA_PAGES 等"""

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


def _protocol_pages(root: str) -> List[Dict[str, Any]]:
    """protocol schema 页（IDL 9 + 生产 5）。"""
    pages: List[Dict[str, Any]] = []
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
    return pages


def _module_pages(root: str) -> Tuple[List[Dict[str, Any]], int]:
    """module 页 + 真源模块数（expected 用真源计数，非页面数）。"""
    modules = _registry_modules(root)
    registry_bytes = _read_bytes(root, REGISTRY_REL)
    module_proto = "wiki:protocol:schema/module"
    pages: List[Dict[str, Any]] = []
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
    return pages, len(modules)


def _pipeline_pages(root: str, pipes: List[str]) -> List[Dict[str, Any]]:
    """pipeline 页。"""
    assembly_proto = "wiki:protocol:production/assembly"
    pages: List[Dict[str, Any]] = []
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
    return pages


def _domain_pages(root: str, rels: List[str]) -> List[Dict[str, Any]]:
    """domain 页。"""
    contract_proto = "wiki:protocol:production/contract"
    pages: List[Dict[str, Any]] = []
    for rel in rels:
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
    return pages


def _asset_pages(root: str, assets: List[str]) -> List[Dict[str, Any]]:
    """asset 页。"""
    pages: List[Dict[str, Any]] = []
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
    return pages


def _index_doc(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """INDEX 文档。"""
    return {"schema": SCHEMA_INDEX,
            "pages": [{"id": p["id"], "type": p["type"], "summary": p["summary"],
                       "source": p["provenance"]["source"],
                       "digest": p["provenance"]["digest"]} for p in pages]}


def _graph_doc(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """GRAPH 文档。"""
    edges = [{"from": p["id"], "kind": r["kind"], "to": r["target"]}
             for p in pages for r in p.get("relations") or []]
    return {"schema": SCHEMA_GRAPH,
            "nodes": [p["id"] for p in pages],
            "edges": sorted(edges, key=lambda e: (e["from"], e["kind"], e["to"]))}


def build(root: str = ".") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """编译 → (pages_doc, expected)；expected = 每类真源计数（覆盖判据用）。"""
    pages: List[Dict[str, Any]] = _protocol_pages(root)
    expected: Dict[str, int] = {"protocol": len(pages)}
    module_pages, module_count = _module_pages(root)
    pages.extend(module_pages)
    expected["module"] = module_count
    pipes = _pipeline_files(root)
    pages.extend(_pipeline_pages(root, pipes))
    expected["pipeline"] = len(pipes)
    domain_specs = _domain_specs(root)
    pages.extend(_domain_pages(root, domain_specs))
    expected["domain"] = len(domain_specs)
    assets = _asset_entries(root)
    pages.extend(_asset_pages(root, assets))
    expected["asset"] = len(assets)
    pages.sort(key=lambda p: p["id"])
    index = _index_doc(pages)
    graph = _graph_doc(pages)
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
