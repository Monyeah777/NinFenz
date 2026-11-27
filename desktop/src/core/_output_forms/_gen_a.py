"""output_forms 私有子模块 _gen_a：T4 生成器 A 组（性能报告 / 概念闭包 / Vega / Mermaid / 域报告 / 组合证书）。

门面 core.output_forms 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

from ._registry import _read_json, _rel
from ._util import _pkg_rel


def _gen_performance_report(root: str, entry: dict):
    """由净值数据用本仓引擎装配绩效报告（GIPS 对齐披露面）。"""
    from core import quant_metrics as qm

    spec = entry.get("recompute") or entry.get("render") or {}
    inputs = spec.get("inputs") or []
    if not inputs:
        return None, ["声明可复算/可渲染但缺 inputs（无源即无功能）"]
    src = _pkg_rel(entry, inputs[0])
    series, err = qm.load_equity_curve(_rel(root, src))
    if err:
        return None, ["输入 %s %s" % (src, err)]
    params = dict(spec.get("params") or {})
    try:
        return qm.performance_report(series, opts=qm.ReportOptions(**params)), []
    except Exception as exc:  # 参数口径错误必须可见，不得静默兜底
        return None, ["复算异常 %s: %s" % (type(exc).__name__, exc)]



def _gen_concept_closure(root: str, entry: dict):
    """由概念图资产复算闭包/装载序（AI系统域包的 M25/M26 产物面）。"""
    from core import concept_graph as cg

    spec = entry.get("recompute") or entry.get("render") or {}
    graph_path = _pkg_rel(entry, spec.get("graph") or cg.DEFAULT_ASSET)
    target = spec.get("target") or ""
    if not target:
        return None, ["声明可复算但缺 target"]
    graph = cg.load_graph(_rel(root, graph_path))
    if not graph:
        return None, ["概念图 %s 不可解析（无源）" % graph_path]
    return {
        "kind": "nf-concept-closure/1",
        "graph": graph_path,
        "target": target,
        "closure": [cg.resolve(graph, x) for x in cg.closure(graph, target)],
        "load_order": cg.toposort(graph),
        "alias": [[k, v] for k, v in sorted(cg.alias_map(graph).items())],
    }, []



def _gen_vega(root: str, entry: dict):
    from core import quant_metrics as qm

    spec = entry.get("recompute") or entry.get("render") or {}
    inputs = spec.get("inputs") or []
    if not inputs:
        return None, ["图表面缺 inputs"]
    src = _pkg_rel(entry, inputs[0])
    series, err = qm.load_equity_curve(_rel(root, src))
    if err:
        return None, ["输入 %s %s" % (src, err)]
    params = dict(spec.get("params") or {})
    which = spec.get("id")
    if which == "vega-drawdown":
        return qm.vega_drawdown(series, **params), []
    return qm.vega_equity_curve(series, **params), []



def _gen_mermaid(_root: str, entry: dict):
    from core import quant_metrics as qm

    spec = entry.get("recompute") or entry.get("render") or {}
    if spec.get("id") == "mermaid-declaration-flow":
        return qm.mermaid_declaration_flow(), []
    return None, ["未登记 Mermaid 生成器：%r" % spec.get("id")]



def _gen_domain_report(root: str, entry: dict):
    """域包 T4 面：由样例夹具按声明度量族重算域报告（core/domain_metrics）。"""
    from core import domain_metrics as dm

    spec = entry.get("recompute") or entry.get("render") or {}
    inputs = spec.get("inputs") or []
    params = dict(spec.get("params") or {})
    family = str(params.pop("family", ""))
    if not inputs or not family:
        return None, ["域报告缺 inputs 或 family（无源/无族即无功能）"]
    src = _pkg_rel(entry, inputs[0])
    rows, err = dm.load_rows(_rel(root, src))
    if err:
        return None, ["输入 %s %s" % (src, err)]
    try:
        metrics = dm.evaluate(family, rows, **params)
    except Exception as exc:  # 口径参数错误必须可见
        return None, ["复算异常 %s: %s" % (type(exc).__name__, exc)]
    return {
        "kind": "nf-domain-report/1",
        "code": str(params.get("code") or ""),
        "domain": str(params.get("domain") or ""),
        "family": family,
        "sample": inputs[0],
        "sample_rows": len(rows),
        "metrics": metrics,
    }, []



def _gen_vega_metrics(root: str, entry: dict):
    """指标条形图：由域报告里的标量指标确定性生成 Vega-Lite 规格。"""
    spec = entry.get("render") or entry.get("recompute") or {}
    inputs = spec.get("inputs") or []
    if not inputs:
        return None, ["图表面缺 inputs"]
    data, err = _read_json(_rel(root, _pkg_rel(entry, inputs[0])))
    if err:
        return None, ["输入 %s %s" % (inputs[0], err)]
    vals = []
    for k, v in sorted((data.get("metrics") or {}).items()):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            vals.append({"metric": k, "value": float(v)})
    if not vals:
        return None, ["报告里没有可画的标量指标"]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": str(spec.get("params", {}).get("title") or "域指标"),
        "data": {"values": vals},
        "mark": {"type": "bar"},
        "encoding": {
            "x": {"field": "value", "type": "quantitative", "title": "口径值"},
            "y": {"field": "metric", "type": "nominal", "title": "指标",
                  "sort": "-x"},
        },
    }, []



def _gen_combo_cert(root: str, entry: dict):
    """组合包 T4 面：按 INDEX 声明的 packs/extra_modules 重算组合证书。"""
    from core import pack_combo as pc

    spec = entry.get("recompute") or {}
    params = dict(spec.get("params") or {})
    packs = list(params.get("packs") or [])
    mods = list(params.get("extra_modules") or [])
    if not packs and not mods:
        return None, ["组合证书缺 packs/extra_modules（无输入即无复算）"]
    cert = pc.combine(root, packs=packs, extra_modules=mods)
    if params.get("label"):
        cert["label"] = params["label"]
    if params.get("note"):
        cert["note"] = params["note"]
    return cert, []



def _combo_doc(root: str, entry: dict) -> Tuple[Any, str]:
    """读证书输入（供图表/图示生成器复用）。"""
    spec = entry.get("render") or {}
    rel = (spec.get("inputs") or ["outputs/COMBO_CERT.json"])[0]
    data, err = _read_json(_rel(root, _pkg_rel(entry, rel)))
    return (data, "") if not err else (None, "输入 %s %s" % (rel, err))
