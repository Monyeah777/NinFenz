"""output_forms 私有子模块 _gen_b：T4 生成器 B 组（层位堆叠 / 装载序 / 依赖图 / 概念 DAG）+ GENERATORS 登记表。

门面 core.output_forms 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from ._checkers import _check_json, json_schema_check
from ._gen_a import _combo_doc, _gen_combo_cert, _gen_concept_closure, _gen_domain_report, _gen_mermaid, _gen_performance_report, _gen_vega, _gen_vega_metrics
from ._registry import _read_json, _rel
from ._util import _pkg_rel



def _gen_vega_layer_stack(root: str, entry: dict):
    data, err = _combo_doc(root, entry)
    if err:
        return None, [err]
    rows = [{"layer": k, "modules": len(v)}
            for k, v in _stack_pairs(data.get("layer_stacks"))]
    if not rows:
        return None, ["证书无 layer_stacks（无可画数据）"]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": (entry.get("render") or {}).get("params", {}).get("title", "层位堆叠"),
        "data": {"values": rows},
        "mark": {"type": "bar"},
        "encoding": {"x": {"field": "layer", "type": "nominal", "title": "层位",
                           "sort": None},
                     "y": {"field": "modules", "type": "quantitative", "title": "模块数"}},
    }, []



def _gen_mermaid_layer_load(root: str, entry: dict):
    data, err = _combo_doc(root, entry)
    if err:
        return None, [err]
    lines = ["%% 组合包装载序（由 COMBO_CERT.json 确定性派生）", "flowchart LR"]
    for lay, mods in _stack_pairs(data.get("layer_stacks")):
        tag = lay.replace("-", "")
        lines.append('  %s["%s"]' % (tag, lay))
        for i, m in enumerate(mods):
            node = "%s_%d" % (tag, i)
            lines.append('  %s["%s"]' % (node, m))
            lines.append("  %s --> %s" % (tag, node))
    return "\n".join(lines) + "\n", []



def _module_layer_of(m: str, stacks: List[Tuple[str, List[str]]]) -> str:
    for k, v in stacks:
        if m in v:
            return k
    return ""


def _dep_edges(m: str, explicit: set, rec: List[str]) -> List[str]:
    out = []
    for dep in rec:                      # 依赖边：模块 → 其显式依赖（在组合内的）
        if dep in explicit and dep != m:
            out.append('    <edge source="%s" target="%s"/>' % (m, dep))
    return out


def _gen_graphml_module_deps(root: str, entry: dict):
    data, err = _combo_doc(root, entry)
    if err:
        return None, [err]
    mods = list(data.get("modules") or [])
    explicit = set((data.get("dependency_closure") or {}).get("explicit") or [])
    stacks = _stack_pairs(data.get("layer_stacks"))
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
           '  <key id="layer" for="node" attr.name="layer" attr.type="string"/>',
           '  <graph id="combo" edgedefault="directed">']
    for m in mods:
        out.append('    <node id="%s"><data key="layer">%s</data></node>'
                   % (m, _module_layer_of(m, stacks)))
    for m in mods:                      # 依赖边：模块 → 其显式依赖（在组合内的）
        out += _dep_edges(m, explicit, _combo_module_inputs(root, entry, m))
    out += ["  </graph>", "</graphml>"]
    return "\n".join(out) + "\n", []



def _combo_module_inputs(root: str, _entry: dict, module_id: str) -> List[str]:
    from core import pack_combo as pc

    rec = pc.prof_get_module(root, module_id)
    return [str(x) for x in (rec.get("inputs") or [])]



def _stack_pairs(stacks: Any) -> List[Tuple[str, List[str]]]:
    """层栈两种历史形态兼容：列表（当前）[{layer, modules}] 与字典 {P40: [...]}。"""
    if isinstance(stacks, list):
        return [(str(r.get("layer") or ""), [str(x) for x in (r.get("modules") or [])])
                for r in stacks if isinstance(r, dict)]
    if isinstance(stacks, dict):
        return [(str(k), [str(x) for x in v]) for k, v in sorted(stacks.items())]
    return []



def _cert_schema_issues(data: dict, pc) -> List[str]:
    unsup: List[str] = []
    issues = ["证书不合 schema：%s" % e
              for e in pc.CERT_SCHEMA and json_schema_check(data, pc.CERT_SCHEMA,
                                                            unsupported=unsup)[:4]]
    if unsup:
        issues.append("证书校验器遇不支持关键字：%s" % sorted(set(unsup))[:2])
    return issues


def _cert_recompute_issues(root: str, data: dict) -> List[str]:
    fresh, perr = _gen_combo_cert(root, {"recompute": {"params": {
        "packs": data.get("packs"), "extra_modules": data.get("extra_modules")}}})
    if fresh is None:
        return ["复算失败：%s" % e for e in perr]
    issues = []
    if fresh.get("legal") is not True:
        issues.append("组合非法（五不变量未全成立）")
    if fresh.get("digest") != data.get("digest"):
        issues.append("证书摘要与实时复算不一致（组合输入已变）")
    return issues


def _check_combo_cert(root: str, rel: str) -> List[str]:
    """组合证书：schema + 五不变量（复算一致由 recompute 面判）。"""
    from core import pack_combo as pc

    issues = _check_json(root, rel)
    data, err = _read_json(_rel(root, rel))
    if err or not isinstance(data, dict):
        return issues + ([err] if err else [])
    issues += _cert_schema_issues(data, pc)
    issues += _cert_recompute_issues(root, data)
    return issues



def _concept_graph_of(root: str, entry: dict):
    """(相对图路径, 已解析概念图)；两种声明位置（recompute / render）都认。"""
    from core import concept_graph as cg

    spec = entry.get("recompute") or entry.get("render") or {}
    graph_path = _pkg_rel(entry, spec.get("graph") or cg.DEFAULT_ASSET)
    return graph_path, cg.load_graph(_rel(root, graph_path))


def _concept_subgraph_lines(cg, graph, layer: dict) -> List[str]:
    seen_layers = []
    for node in cg.in_package_ids(graph):
        lay = layer.get(node, "P00")
        if lay not in seen_layers:
            seen_layers.append(lay)
    lines = []
    for lay in sorted(seen_layers):
        ids = [n for n in cg.in_package_ids(graph) if layer.get(n) == lay]
        if not ids:
            continue
        lines.append("  subgraph %s[%s]" % (lay, lay))
        for n in ids:
            lines.append("    %s" % n)
        lines.append("  end")
    return lines


def _concept_edge_lines(cg, graph, prereq) -> List[str]:
    lines = []
    for node in cg.in_package_ids(graph):
        for pre in prereq.get(node, []):
            if pre.startswith("C0") and pre == "C00":
                continue
            lines.append("  %s --> %s" % (pre, node))
    return lines


def _gen_mermaid_concept_dag(root: str, entry: dict):
    """概念图 → Mermaid（按层分组的流程图）；图即数据，节点/边由概念图导出。"""
    from core import concept_graph as cg

    graph_path, graph = _concept_graph_of(root, entry)
    if not graph:
        return None, ["概念图 %s 不可解析（无源）" % graph_path]
    prereq = cg.prereqs_of(graph)
    layer = {n: (m.get("layer") or "P00") for n, m in cg.node_meta(graph).items()}
    lines = ["%% 概念前置图（由 " + graph_path + " 确定性派生；唯一机读真相在资产 §4 围栏块）",
             "flowchart TD"]
    lines += _concept_subgraph_lines(cg, graph, layer)
    lines += _concept_edge_lines(cg, graph, prereq)
    return "\n".join(lines) + "\n", []



def _concept_all_nodes(cg, graph, prereq) -> List[str]:
    nodes = list(cg.in_package_ids(graph))
    for node in list(nodes):                # 包外前置（如 C00）：声明存在，作为图节点保留
        for pre in prereq.get(node, []):
            if pre not in nodes:
                nodes.append(pre)
    return nodes


def _concept_node_xml(meta: dict, nodes: List[str]) -> List[str]:
    out = []
    for node in nodes:
        m = meta.get(node, {})
        out.append('    <node id="%s">' % node)
        out.append('      <data key="layer">%s</data>' % (m.get("layer") or ""))
        out.append('      <data key="branch">%s</data>' % (m.get("branch") or ""))
        out.append('    </node>')
    return out


def _concept_edge_xml(meta: dict, nodes: List[str], prereq) -> List[str]:
    out = []
    for node in nodes:
        for pre in prereq.get(node, []):
            out.append('    <edge source="%s" target="%s">' % (pre, node))
            out.append('      <data key="provenance">%s</data>' % (m_prov(meta, node, pre)))
            out.append('    </edge>')
    return out


def _gen_graphml_concept_dag(root: str, entry: dict):
    """概念图 → GraphML（图交换形态）：边端点引用完整性由形态校验器判定。"""
    from core import concept_graph as cg

    graph_path, graph = _concept_graph_of(root, entry)
    if not graph:
        return None, ["概念图 %s 不可解析（无源）" % graph_path]
    prereq = cg.prereqs_of(graph)
    meta = cg.node_meta(graph)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
           '  <key id="layer" for="node" attr.name="layer" attr.type="string"/>',
           '  <key id="branch" for="node" attr.name="branch" attr.type="string"/>',
           '  <key id="provenance" for="edge" attr.name="provenance" attr.type="string"/>',
           '  <graph id="concept-graph" edgedefault="directed">']
    nodes = _concept_all_nodes(cg, graph, prereq)
    out += _concept_node_xml(meta, nodes)
    out += _concept_edge_xml(meta, nodes, prereq)
    out += ['  </graph>', '</graphml>']
    return "\n".join(out) + "\n", []



def m_prov(meta: dict, node: str, _pre: str) -> str:
    """边溯源：取目标节点 provenance（概念图边级溯源在资产内，缺则标 unknown）。"""
    return str((meta.get(node) or {}).get("provenance") or "unknown")



#: 生成器登记（**唯一入口**：渲染与复算共用同一函数——不复算的渲染 = 手写，禁）
GENERATORS: Dict[str, Callable[[str, dict], Tuple[Any, List[str]]]] = {
    "performance-report": _gen_performance_report,
    "concept-closure": _gen_concept_closure,
    "vega-equity-curve": _gen_vega,
    "vega-drawdown": _gen_vega,
    "mermaid-declaration-flow": _gen_mermaid,
    "mermaid-concept-dag": _gen_mermaid_concept_dag,
    "graphml-concept-dag": _gen_graphml_concept_dag,
    "domain-report": _gen_domain_report,
    "vega-metrics": _gen_vega_metrics,
    "combo-cert": _gen_combo_cert,
    "vega-layer-stack": _gen_vega_layer_stack,
    "mermaid-layer-load": _gen_mermaid_layer_load,
    "graphml-module-deps": _gen_graphml_module_deps,
}
