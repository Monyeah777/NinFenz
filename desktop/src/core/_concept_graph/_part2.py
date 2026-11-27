"""core.concept_graph 私有实现分片 2/2（对外只经 core.concept_graph 门面导入）：problems 等"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from core import conformance_scan as csc

from ._part1 import (
    LAYERS,
    PROVENANCE_STRENGTHS,
    ClosureError,
    alias_map,
    branch_map,
    external_coverage,
    graph_assets,
    load_graph,
    node_branch,
    prereqs_of,
    provenance_strength,
    toposort,
)


def problems(graph: Dict[str, Any]) -> List[str]:
    """图健康度：无环 / 无悬空 / 边有溯源 / 层位合法 / id 唯一 / 别名唯一 / 分支完备 / 证据面。"""
    issues: List[str] = []
    prereqs = prereqs_of(graph)
    ext = {str(x.get("id")) for x in (graph.get("external_prereqs") or [])
           if isinstance(x, dict)}
    declared = set(prereqs) | ext
    legend = {str(k) for k in (graph.get("provenance_legend") or {})}
    strength = provenance_strength(graph)
    if not strength:
        issues.append("图缺 provenance_strength 声明（修复指引：在机读块声明取值 "
                      "%s——证据强度须显式，不得默认按强证据理解）"
                      % " / ".join(PROVENANCE_STRENGTHS))
    elif strength not in PROVENANCE_STRENGTHS:
        issues.append("provenance_strength 越词表：%s（取值 %s）"
                      % (strength, " / ".join(PROVENANCE_STRENGTHS)))
    else:
        # 四级阶梯须与「节点外部覆盖」自洽（可判定：覆盖 = 有非推断来源键的节点数 / 包内节点数）
        covered, total = external_coverage(graph)
        ratio = (float(covered) / total) if total else 0.0
        if strength == "external" and ratio < 1.0:
            issues.append("provenance_strength=external 但外部覆盖仅 %d/%d（修复指引：补齐每节点的"
                          "外部来源锚，或按实况降为 mixed / domain-logic）" % (covered, total))
        elif strength == "mixed" and not (0.0 < ratio < 1.0):
            issues.append("provenance_strength=mixed 但外部覆盖 = %d/%d（修复指引：全覆盖用 "
                          "external；无外部锚用 domain-logic / inferred）" % (covered, total))
        elif strength in ("domain-logic", "inferred") and ratio > 0.0:
            issues.append("provenance_strength=%s 但已有 %d/%d 节点挂外部来源键"
                          "（修复指引：按实况升为 mixed / external）" % (strength, covered, total))
    seen_nodes: Set[str] = set()
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict) or not node.get("id"):
            issues.append("节点缺 id（修复指引：每个节点须有 Cxx 编号）")
            continue
        nid = str(node["id"])
        if nid in seen_nodes:
            issues.append("节点 id 重复：%s（编号须唯一）" % nid)
        seen_nodes.add(nid)
        if not str(node.get("name") or "").strip():
            issues.append("节点 %s 缺 name（修复指引：每个概念须有可读名）" % nid)
        if not node.get("provenance"):
            issues.append("节点 %s 缺 provenance（边无溯源即不可复核）" % nid)
        else:
            for key in node.get("provenance") or []:
                if str(key) not in legend:
                    issues.append("节点 %s 的 provenance 键 %r 不在 provenance_legend 中"
                                  "（修复指引：补图例键，防图例漂移静默）" % (nid, key))
        layer = str(node.get("layer") or "")
        if layer and layer not in LAYERS:
            issues.append("节点 %s 层位越界：%s（取值 %s）" % (nid, layer, "/".join(LAYERS)))
    for nid, ps in sorted(prereqs.items()):
        for p in ps:
            if p not in declared:
                issues.append("悬空前置：%s ← %s（前置不在节点表 / 外部前置族中）" % (nid, p))
            if p == nid:
                issues.append("自环：%s ← %s" % (nid, p))
    bids = node_branch(graph)
    for nid in sorted(set(prereqs) - set(bids)):
        issues.append("概念 %s 未归入任何分支（修复指引：在图 branches 段登记）" % nid)
    for nid in sorted(set(bids) - set(prereqs)):
        issues.append("分支声明了不存在的概念：%s（修复指引：核对 branches.nodes）" % nid)
    flat = [n for v in branch_map(graph).values() for n in v]
    if len(flat) != len(set(flat)):
        issues.append("概念被多个分支重复声明（修复指引：一概念只入一个分支）")
    try:
        alias_map(graph)
    except ClosureError as exc:
        issues.append(str(exc))
    try:
        toposort(graph)
    except ClosureError as exc:
        issues.append(str(exc))
    return issues


# ---------------------------------------------------------------- 门禁扫描
#: `scan()` 的全部输入：概念图就长在各包**资产件**的机读块里（community 各包 + 官方自定义）。
CG_INPUTS = ("community/*/assets/*.md", "05_资产库/**/*")


def _scan_impl(root: str = ".") -> Tuple[List[str], Dict[str, int]]:
    """真算（未命中缓存时走这里）。"""
    """全仓工程度扫描 → (issues, stats)（供 check32 子扫描；无图资产即中性通过）。"""
    issues: List[str] = []
    nodes = edges = 0
    assets = graph_assets(root)
    for rel in assets:
        try:
            graph = load_graph(Path(root) / rel)
        except ClosureError as exc:
            issues.append("%s: %s" % (rel, exc))
            continue
        prereqs = prereqs_of(graph)
        nodes += len(prereqs)
        edges += sum(len(v) for v in prereqs.values())
        for msg in problems(graph):
            issues.append("%s: %s" % (rel, msg))
    return issues, {"graphs": len(assets), "nodes": nodes, "edges": edges}


def scan(root: str = ".") -> Tuple[List[str], Dict[str, int]]:
    """概念图体检（原体见 `_scan_impl`）；派生结果按**输入内容指纹**缓存（键即内容）。

    **冷进程也走这层缓存**（2026-09-29 实测：宽面指纹在同一只读作用域内近乎白拿，而重算这条派生账
    贵得多；见 `quality_depth_scan.scan` 的实测数字）。
    「读盘面 ⊆ 输入面」由 test_conformance_scan.DerivedResultCacheTest 的同一张表守着。
    """
    return csc.memo_pair("concept-graph", CG_INPUTS, _scan_impl, root,
                         code_modules=("core.concept_graph",))
