"""资产本体索引：把 101 个域包的 `CONCEPT_GRAPH` 合并成一张可查询的本体图。

背景（T10.2）：概念图目前散在 `community/<域包>/assets/CONCEPT_GRAPH.md` 的 ```yaml
机读块里（唯一机读真相，解析复用 `core.concept_graph.load_graph`，不另造 YAML 口径）。
跨域检索时「同一个概念（尤其 `STD-*` 标准节点）在 100 个域里各出现一次」，没有一张
合并表就无法回答「这个概念在哪些域出现过、它的前置是谁」。

本模块只读扫描并产出 **唯一产物** `protocol/concept_graph_index.json`
（schema `nf-concept-index/1`）：

- **节点**：按 **name 合并跨域同名概念**（`STD-*` 标准节点天然在 ~100 个域重复）；
  记录 `domains[]`、`layers[]`、`sources[]`（provenance 并集）、`aliases[]`、
  `external`（包外前置族）与 `degree`。
- **边**：由节点 `prereqs[]` 派生，方向 **前置 → 后继**，`relation="prereq"`；
  key=(source,target,relation) 去重，保留 `domains[]` 与 `occurrences`。
- **统计**：节点/边/域数量、同名合并数、重复边合并数、孤儿节点、悬空边（前置 id
  既不在本域节点表、也不在 `external_prereqs`）、类别冲突（同名概念 branch 不同 → WARN）。
- **root**：`SHA-256(canonical({"schema", "nodes", "edges"}))`，节点/边均排序 ⇒ 确定性。

补充扫描面：`community/<域包>/outputs/CONCEPT_DAG.graphml`（若可解析）只作**回退**——
当某域包的 `CONCEPT_GRAPH.md` 缺失/不可解析时才用它（同一个域的 graphml 是从 md 派生的
DAG，二者同时收会把同一批边计两遍）。回退使用次数如实写进 `sources.graphml_used`。

纪律：只读；不改各包资产；跳过（无 `concept_graph` 块 / YAML 坏 / graphml 坏）一律
如实记录到 `sources.skipped[]`（不静默），且不影响其它域。
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from core import atomic_write
from core import concept_graph as cg

SCHEMA = "nf-concept-index/1"
INDEX_REL = "protocol/concept_graph_index.json"
MD_GLOB = os.path.join("community", "*", "assets", "CONCEPT_GRAPH.md")
GRAPHML_GLOB = os.path.join("community", "*", "outputs", "CONCEPT_DAG.graphml")
_NS = "{http://graphml.graphdrawing.org/xmlns}"
_EDGE_REL = "prereq"


# ---------------------------------------------------------------- 规范化单图

def _pack_of(rel: str) -> str:
    parts = rel.replace(os.sep, "/").split("/")
    return parts[1] if len(parts) > 2 and parts[0] == "community" else ""


def _norm_md(graph: Dict[str, Any], rel: str) -> Dict[str, Any]:
    """`concept_graph` 机读块 → 规范化单图。"""
    nodes: List[Dict[str, Any]] = []
    for n in graph.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        name = str(n.get("name") or n.get("id") or "").strip()
        if not name:
            continue
        nodes.append({
            "local_id": str(n.get("id") or name),
            "name": name,
            "category": str(n.get("branch") or ""),
            "layers": [str(n.get("layer"))] if n.get("layer") else [],
            "sources": [str(x) for x in (n.get("provenance") or [])],
            "aliases": [str(x) for x in (n.get("aliases") or [])],
            "prereqs": [str(x) for x in (n.get("prereqs") or [])],
        })
    external: Dict[str, str] = {}
    for e in graph.get("external_prereqs") or []:
        if isinstance(e, dict) and e.get("id"):
            external[str(e["id"])] = str(e.get("name") or e["id"])
    return {"kind": "md", "source": rel, "domain": str(graph.get("domain") or _pack_of(rel)),
            "nodes": nodes, "external": external, "edges": []}


def _graphml_keys(root: ET.Element) -> Dict[str, str]:
    keys: Dict[str, str] = {}
    for key in root.iter(_NS + "key"):
        if key.get("for") == "node" and key.get("id"):
            keys[str(key.get("id"))] = str(key.get("attr.name") or key.get("id"))
    return keys


def _norm_graphml(path: str, rel: str) -> Dict[str, Any]:
    """graphml → 规范化单图（回退面；节点名取 `name/label` 数据键，缺则用 id）。"""
    root = ET.parse(path).getroot()
    keys = _graphml_keys(root)
    id2name: Dict[str, str] = {}
    nodes: List[Dict[str, Any]] = []
    for n in root.iter(_NS + "node"):
        nid = str(n.get("id") or "")
        if not nid:
            continue
        data: Dict[str, str] = {}
        for d in n.iter(_NS + "data"):
            data[keys.get(str(d.get("key")), str(d.get("key")))] = (d.text or "").strip()
        name = data.get("name") or data.get("label") or nid
        id2name[nid] = name
        nodes.append({"local_id": nid, "name": name,
                      "category": data.get("branch", ""),
                      "layers": [data["layer"]] if data.get("layer") else [],
                      "sources": [], "aliases": [], "prereqs": []})
    edges: List[Dict[str, str]] = []
    for e in root.iter(_NS + "edge"):
        src, dst = id2name.get(str(e.get("source"))), id2name.get(str(e.get("target")))
        if src and dst:
            edges.append({"source": src, "target": dst})
    return {"kind": "graphml", "source": rel, "domain": _pack_of(rel),
            "nodes": nodes, "external": {}, "edges": edges}


def _load_graphs(root: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """扫描全部域包 → (规范化单图列表, sources 覆盖统计)。md 优先，graphml 仅回退。"""
    md_files = sorted(glob.glob(os.path.join(root, MD_GLOB)))
    graphs: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    covered: set = set()
    for path in md_files:
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        try:
            graphs.append(_norm_md(cg.load_graph(path), rel))
            covered.add(_pack_of(rel))
        except Exception as exc:                              # noqa: BLE001 - 逐件记录不中断
            skipped.append({"path": rel, "reason": "%s: %s" % (type(exc).__name__, exc)})
    gml_files = sorted(glob.glob(os.path.join(root, GRAPHML_GLOB)))
    gml_parsed = gml_used = 0
    for path in gml_files:
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        try:
            norm = _norm_graphml(path, rel)
        except (ET.ParseError, OSError, ValueError) as exc:
            skipped.append({"path": rel, "reason": "graphml: %s" % exc})
            continue
        gml_parsed += 1
        if _pack_of(rel) in covered:
            continue                                          # 同域 md 已覆盖：避免重复计数
        gml_used += 1
        covered.add(_pack_of(rel))
        graphs.append(norm)
    sources = {"md_glob": MD_GLOB.replace(os.sep, "/"), "md_total": len(md_files),
               "md_parsed": len(md_files) - len([s for s in skipped
                                                 if s["path"].endswith("CONCEPT_GRAPH.md")]),
               "graphml_glob": GRAPHML_GLOB.replace(os.sep, "/"),
               "graphml_total": len(gml_files), "graphml_parsed": gml_parsed,
               "graphml_used": gml_used, "skipped": skipped}
    return graphs, sources


# ---------------------------------------------------------------- 合并

def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _add_node(by_name: Dict[str, Dict[str, Any]], name: str, cat: str, layer: str,
              sources: List[str], aliases: List[str], domain: str, external: bool,
              warnings: List[str], declared: bool = True) -> None:
    rec = by_name.get(name)
    if rec is None:
        rec = by_name[name] = {"id": name, "name": name, "category": cat,
                               "categories": set(), "layers": set(), "sources": set(),
                               "aliases": set(), "domains": set(), "decl_occ": 0,
                               "external": external, "degree": 0}
    if declared:
        rec["decl_occ"] += 1
    if cat:
        rec["categories"].add(cat)
    if layer:
        rec["layers"].add(layer)
    rec["sources"].update(sources)
    rec["aliases"].update(aliases)
    rec["domains"].add(domain)
    rec["external"] = bool(rec["external"] and external)
    if len(rec["categories"]) == 2:            # 从单类别变多类别：只报一次
        warnings.append("同名概念类别冲突：%s（%s）"
                        % (name, " / ".join(sorted(rec["categories"]))))


def _resolve(target_id: str, local: Dict[str, Dict[str, Any]],
             external: Dict[str, str]) -> Optional[Dict[str, str]]:
    if target_id in local:
        n = local[target_id]
        return {"name": n["name"], "category": n["category"], "layers": n["layers"],
                "sources": n["sources"], "aliases": n["aliases"], "external": False}
    if target_id in external:
        return {"name": external[target_id], "category": "external", "layers": [],
                "sources": [], "aliases": [], "external": True}
    return None


def merge(graphs: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    """多域单图 → 合并索引 doc（不含统计排序之外的副作用）。"""
    warnings: List[str] = []
    by_name: Dict[str, Dict[str, Any]] = {}
    edge_map: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    dangling: List[Dict[str, str]] = []
    occ_nodes = occ_edges = dup_edges = 0
    domains: List[Dict[str, Any]] = []
    for g in sorted(graphs, key=lambda x: x["domain"]):
        domain = g["domain"]
        local = {n["local_id"]: n for n in g["nodes"]}
        for n in g["nodes"]:
            occ_nodes += 1
            _add_node(by_name, n["name"], n["category"],
                      n["layers"][0] if n["layers"] else "", n["sources"],
                      n["aliases"], domain, False, warnings)
        for n in g["nodes"]:
            for pid in n["prereqs"]:
                occ_edges += 1
                tgt = _resolve(pid, local, g["external"])
                if tgt is None:
                    dangling.append({"source": n["name"], "target_id": pid,
                                     "domain": domain})
                    continue
                _add_node(by_name, tgt["name"], tgt["category"],
                          tgt["layers"][0] if tgt["layers"] else "", tgt["sources"],
                          tgt["aliases"], domain, tgt["external"], warnings,
                          declared=False)
                key = (tgt["name"], n["name"], _EDGE_REL)
                if key in edge_map:
                    dup_edges += 1
                    edge_map[key]["occurrences"] += 1
                    edge_map[key]["domains"].add(domain)
                else:
                    edge_map[key] = {"source": tgt["name"], "target": n["name"],
                                     "relation": _EDGE_REL, "domains": {domain},
                                     "occurrences": 1}
        for e in g["edges"]:                                  # graphml 回退面的显式边
            occ_edges += 1
            # graphml 的边端点已是节点名（_norm_graphml 已把 id 映射成 name）；节点在
            # 上面的声明循环里已入表，这里只做存在性判定，不再重复登记（避免虚增出现次数）。
            if e["source"] not in by_name or e["target"] not in by_name:
                dangling.append({"source": e["source"], "target_id": e["target"],
                                 "domain": domain})
                continue
            key = (e["source"], e["target"], _EDGE_REL)
            if key in edge_map:
                dup_edges += 1
                edge_map[key]["occurrences"] += 1
                edge_map[key]["domains"].add(domain)
            else:
                edge_map[key] = {"source": e["source"], "target": e["target"],
                                 "relation": _EDGE_REL, "domains": {domain},
                                 "occurrences": 1}
        domains.append({"id": domain, "source": g["source"], "kind": g["kind"],
                        "nodes": len(g["nodes"]),
                        "edges": sum(len(n["prereqs"]) for n in g["nodes"]) + len(g["edges"])})
    for e in edge_map.values():
        by_name[e["source"]]["degree"] += 1
        by_name[e["target"]]["degree"] += 1
    nodes_out = [_node_out(n) for n in sorted(by_name.values(), key=lambda x: x["id"])]
    edges_out = [{"source": e["source"], "target": e["target"],
                  "relation": e["relation"], "domains": sorted(e["domains"]),
                  "occurrences": e["occurrences"]}
                 for e in sorted(edge_map.values(),
                                 key=lambda x: (x["source"], x["target"], x["relation"]))]
    orphans = sum(1 for n in nodes_out if n["degree"] == 0)
    merged = sum(max(0, rec["decl_occ"] - 1) for rec in by_name.values())
    stats = {
        "domains": len({d["id"] for d in domains}),
        "node_occurrences": occ_nodes,
        "nodes": len(nodes_out),
        "merged_same_name": merged,
        "external_nodes": sum(1 for n in nodes_out if n["external"]),
        "edge_occurrences": occ_edges,
        "edges": len(edges_out),
        "duplicate_edges_merged": dup_edges,
        "dangling_edges": len(dangling),
        "orphan_nodes": orphans,
        "category_conflicts": sum(1 for w in warnings if w.startswith("同名概念类别冲突")),
        "warnings": len(warnings),
    }
    doc = {
        "schema": SCHEMA,
        "algorithm": {"digest": "sha256", "canonical": "json-sort-keys+compact+utf-8",
                      "node_key": "name（跨域同名概念合并）",
                      "edge_key": "(source,target,relation)"},
        "domains": domains,
        "nodes": nodes_out,
        "edges": edges_out,
        "dangling": dangling,
        "warnings": warnings,
        "stats": stats,
    }
    doc["root"] = root_of(doc)
    return doc, warnings


def _node_out(n: Dict[str, Any]) -> Dict[str, Any]:
    cats = sorted(n["categories"]) or ([n["category"]] if n["category"] else [])
    return {"id": n["id"], "name": n["name"],
            "category": cats[0] if cats else "",
            "categories": cats,
            "layers": sorted(n["layers"]), "sources": sorted(n["sources"]),
            "aliases": sorted(n["aliases"]), "domains": sorted(n["domains"]),
            "external": bool(n["external"]), "degree": int(n["degree"])}


def root_of(doc: Dict[str, Any]) -> str:
    material = {"schema": doc.get("schema"), "nodes": doc.get("nodes") or [],
                "edges": doc.get("edges") or []}
    return hashlib.sha256(_canonical(material)).hexdigest()


# ---------------------------------------------------------------- 生成 / 校验

def compute(root: str = ".") -> Tuple[Dict[str, Any], List[str]]:
    """只读扫描 → (index doc, hard issues)。跳过原因记在 doc.sources.skipped（不静默）。"""
    graphs, sources = _load_graphs(root)
    doc, warnings = merge(graphs)
    doc["sources"] = sources
    issues: List[str] = []
    if not sources["md_total"] and not sources["graphml_total"]:
        issues.append("没扫到任何概念图（%s / %s）——检查是否在仓库根运行"
                      % (MD_GLOB.replace(os.sep, "/"), GRAPHML_GLOB.replace(os.sep, "/")))
    return doc, issues


def dump(doc: Dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _diff(recorded: Dict[str, Any], fresh: Dict[str, Any]) -> List[str]:
    """与实时重算的差异（节点/边/域/统计级，供 --check 的 file:line 级定位提示）。"""
    out: List[str] = []
    rn = {n["id"]: n for n in recorded.get("nodes") or []}
    fn = {n["id"]: n for n in fresh.get("nodes") or []}
    added, removed = sorted(set(fn) - set(rn)), sorted(set(rn) - set(fn))
    if added:
        out.append("新增概念 %d 个（例：%s）" % (len(added), " / ".join(added[:5])))
    if removed:
        out.append("消失概念 %d 个（例：%s）" % (len(removed), " / ".join(removed[:5])))
    for nid in sorted(set(rn) & set(fn)):
        a, b = rn[nid], fn[nid]
        for field in ("categories", "layers", "sources", "domains", "degree"):
            if a.get(field) != b.get(field):
                out.append("概念 %s 的 %s 变：%s → %s"
                           % (nid, field, str(a.get(field))[:120], str(b.get(field))[:120]))
    re_ = {(e["source"], e["target"], e["relation"]) for e in recorded.get("edges") or []}
    fe = {(e["source"], e["target"], e["relation"]) for e in fresh.get("edges") or []}
    if fe - re_:
        out.append("新增边 %d 条（例：%s）" % (len(fe - re_), " → ".join(sorted(fe - re_)[0])))
    if re_ - fe:
        out.append("消失边 %d 条（例：%s）" % (len(re_ - fe), " → ".join(sorted(re_ - fe)[0])))
    if recorded.get("stats") != fresh.get("stats"):
        out.append("统计变：%s → %s" % (json.dumps(recorded.get("stats"), ensure_ascii=False,
                                                  sort_keys=True),
                                       json.dumps(fresh.get("stats"), ensure_ascii=False,
                                                  sort_keys=True)))
    for field in ("domains", "dangling", "warnings", "sources"):
        if recorded.get(field) != fresh.get(field):
            out.append("%s 与实时重算不一致" % field)
    return out


def _self_check(doc: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if doc.get("schema") != SCHEMA:
        issues.append("schema 不是 %s：%r" % (SCHEMA, doc.get("schema")))
    nodes = doc.get("nodes")
    edges = doc.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return issues + ["nodes/edges 不是数组"]
    ids = [n.get("id") for n in nodes]
    if ids != sorted(ids):
        issues.append("nodes 未按 id 排序（顺序不稳定 ⇒ root 不可复现）")
    if len(set(ids)) != len(ids):
        issues.append("nodes 有重复 id")
    names = {n.get("id") for n in nodes}
    for e in edges:
        if e.get("source") not in names or e.get("target") not in names:
            issues.append("边端点不在节点表：%s → %s" % (e.get("source"), e.get("target")))
            break
    if doc.get("root") != root_of(doc):
        issues.append("root 与 nodes/edges 实时重算不一致（index 被改过）")
    stats = doc.get("stats") or {}
    for key, value in (("nodes", len(nodes)), ("edges", len(edges))):
        if stats.get(key) != value:
            issues.append("stats.%s=%r ≠ 数组长度 %d" % (key, stats.get(key), value))
    return issues


def write(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    doc, issues = compute(root)
    if issues:
        return issues, doc
    atomic_write.write_text(os.path.join(root, INDEX_REL), dump(doc))
    return issues, doc


def check(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    doc, issues = compute(root)
    if issues:
        return issues, doc
    path = os.path.join(root, INDEX_REL)
    if not os.path.isfile(path):
        return ["缺 %s（跑 `nf knowledge graph --write` 生成）" % INDEX_REL], doc
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        recorded = json.loads(text)
    except (OSError, ValueError) as exc:
        return ["%s 读不到/不可解析：%s" % (INDEX_REL, exc)], doc
    if not isinstance(recorded, dict):
        return ["%s 顶层不是对象" % INDEX_REL], doc
    issues.extend(_self_check(recorded))
    if dump(recorded) != dump(doc):
        issues.extend(_diff(recorded, doc))
        if not any(k in i for i in issues for k in ("新增概念", "消失概念", "新增边",
                                                    "消失边", "统计变", "不一致")):
            issues.append("%s 与实时重算不一致（跑 `nf knowledge graph --write` 重生成）"
                          % INDEX_REL)
    if doc["sources"]["skipped"]:
        issues.append("%d 个概念图被跳过（见 index.sources.skipped；不影响其它域解析）"
                      % len(doc["sources"]["skipped"]))
    return issues, doc


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """门禁入口（与 repo_stats.scan 同形）：索引 ↔ 实时重算一致。"""
    return check(root)
