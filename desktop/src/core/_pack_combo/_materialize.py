"""pack_combo 私有子模块 _materialize：产物化：把组合落成可装载组合包（摊平引用 + 8 件机验产出面）。

门面 core.pack_combo 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import re

from core import pack_combo as _dm
from ._base import indexes, profiles
from ._const import CERT_SCHEMA



# ---------------------------------------------------------------- 组合包产物化

def _flatten_sources(root: str, packs: Sequence[str]) -> Tuple[Dict[str, List[str]], List[str]]:
    """把选中包摊平成 {源包名: [模块 id…]}（组合包本身再展开一层，避免多层嵌套 references）。"""
    prof = profiles(root)
    out: Dict[str, List[str]] = {}
    combo_packs: List[str] = []
    for name in packs:
        pr = prof.get(name)
        if not pr:
            continue
        if pr.get("references"):
            # 组合包作为来源 → **显式摊平**：保留它自己的模块（它们是真实模块，且是其它源包
            # 发布事件的消费者），同时把它的 references 一并升为本次组合的 references ——
            # 这样嵌套引用是「显式闭合」的（check15 ② 新增判据：嵌套必须显式闭合）。
            combo_packs.append(name)
        out.setdefault(name, [])
        for mid in pr["modules"]:
            if mid not in out[name]:
                out[name].append(mid)
        for ref in pr.get("references") or []:
            src = str(ref.get("source_package") or "")
            if not src:
                continue
            out.setdefault(src, [])
            mid = str(ref.get("module_id") or "")
            if mid and mid not in out[src]:
                out[src].append(mid)
    return out, combo_packs



def prof_get_module(root: str, module_id: str) -> Dict[str, Any]:
    by_id, _pi, _cp = indexes(root)
    return by_id.get(module_id) or by_id.get(str(module_id).split(":")[-1]) or {}



def combo_outputs(root: str, name: str, cert: Dict[str, Any],
                  _layers: Dict[str, List[str]]) -> Dict[str, str]:
    """组合包的机验产出面（8 件）：证书（T4）+ 契约 + 数据 + 图表 + 图示 + 系统卡。"""
    pkg = "community/%s" % name
    import json as _json

    cert_doc = dict(cert)
    cert_doc["label"] = cert_doc.get("label") or ("组合包 %s" % name)
    cert_doc["note"] = cert_doc.get("note") or ("由 nf combine materialize 产物化；"
                                                "组合合法性由五不变量给出")
    params = {"packs": cert["packs"], "extra_modules": cert.get("extra_modules") or [],
              "label": cert_doc["label"], "note": cert_doc["note"]}
    borrow_doc = _combo_borrow(root, cert, name)
    index = _combo_index(name, params)
    from core import domain_pack as dpk

    card = _combo_card(cert, name)
    return {
        "%s/outputs/INDEX.json" % pkg: _json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        "%s/outputs/COMBO_CERT.json" % pkg: _json.dumps(cert_doc, ensure_ascii=False,
                                                       indent=2, sort_keys=True) + "\n",
        "%s/outputs/schemas/COMBO_CERT.schema.json" % pkg:
            _json.dumps(CERT_SCHEMA, ensure_ascii=False, indent=2) + "\n",
        "%s/outputs/BORROW_INDEX.json" % pkg:
            _json.dumps(borrow_doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        "%s/outputs/schemas/BORROW_INDEX.schema.json" % pkg:
            _json.dumps({
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": "组合包借阅索引",
                "type": "object", "additionalProperties": False,
                "required": ["schema", "package", "borrowed"],
                "properties": {"schema": {"const": "nf-combo-borrow/1"},
                               "package": {"type": "string", "minLength": 2},
                               "note": {"type": "string"},
                               "borrowed": {"type": "array", "minItems": 1, "items": {
                                   "type": "object", "additionalProperties": False,
                                   "required": ["source_package", "modules", "mode"],
                                   "properties": {
                                       "source_package": {"type": "string", "minLength": 2},
                                       "modules": {"type": "array", "minItems": 1,
                                                   "items": {"type": "string", "minLength": 2}},
                                       "mode": {"const": "asset_readonly"}}}}},
            }, ensure_ascii=False, indent=2) + "\n",
        "%s/outputs/schemas/SYSTEM_CARD.schema.json" % pkg:
            _json.dumps(dpk.SYSTEM_CARD_SCHEMA_JSON, ensure_ascii=False, indent=2) + "\n",
        "%s/outputs/SYSTEM_CARD.json" % pkg:
            _json.dumps(card, ensure_ascii=False, indent=2) + "\n",
    }



def _combo_borrow(root: str, cert: Dict[str, Any],
                   name: str) -> Dict[str, Any]:
    """借阅索引（源包 → 模块，只读）：组合包不复制资产/模块。"""
    borrow: Dict[str, List[str]] = {}
    for m in cert["modules"]:
        rec = prof_get_module(root, m)
        borrow.setdefault(str(rec.get("pack") or ""), []).append(m)
    borrow_doc = {"schema": "nf-combo-borrow/1",
                  "package": name,
                  "note": "借阅索引：本组合包不复制资产/模块，全部经 references 只读访问",
                  "borrowed": [{"source_package": k, "modules": sorted(v),
                                "mode": "asset_readonly"}
                               for k, v in sorted(borrow.items())]}
    return borrow_doc



def _combo_index(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """组合包产出面清单（nf-output-index/1，8 件）。"""
    index = {
        "schema": "nf-output-index/1",
        "package": name,
        "note": "组合包产出面（由组合引擎生成；check32 output_forms 与 nf output 按此判定）。",
        "outputs": [
            {"path": "outputs/schemas/COMBO_CERT.schema.json", "form": "json-schema",
             "tier": "T2", "role": "schema", "note": "组合证书契约"},
            {"path": "outputs/COMBO_CERT.json", "form": "combo-cert", "tier": "T4",
             "role": "functional", "schema": "outputs/schemas/COMBO_CERT.schema.json",
             "recompute": {"id": "combo-cert", "params": params},
             "note": "组合证书（T4：按 packs+extra_modules 重算逐字段比对）"},
            {"path": "outputs/schemas/BORROW_INDEX.schema.json", "form": "json-schema",
             "tier": "T2", "role": "schema", "note": "借阅索引契约"},
            {"path": "outputs/BORROW_INDEX.json", "form": "json", "tier": "T2",
             "role": "data", "schema": "outputs/schemas/BORROW_INDEX.schema.json",
             "note": "借阅索引（源包 → 模块，只读）"},
            {"path": "outputs/charts/LAYER_STACK.vega.json", "form": "vega-lite",
             "tier": "T3", "role": "chart",
             "render": {"id": "vega-layer-stack", "inputs": ["outputs/COMBO_CERT.json"],
                        "params": {"title": "%s · 层位堆叠" % name}},
             "note": "层位堆叠条形图（由证书确定性生成）"},
            {"path": "outputs/charts/LOAD_ORDER.mmd", "form": "mermaid", "tier": "T3",
             "role": "diagram",
             "render": {"id": "mermaid-layer-load", "inputs": ["outputs/COMBO_CERT.json"]},
             "note": "装载序图（按层分组的 Mermaid）"},
            {"path": "outputs/DEPENDENCY.graphml", "form": "graphml", "tier": "T3",
             "role": "diagram",
             "render": {"id": "graphml-module-deps", "inputs": ["outputs/COMBO_CERT.json"]},
             "note": "模块依赖图（GraphML；端点引用完整性由形态校验器判定）"},
            {"path": "outputs/schemas/SYSTEM_CARD.schema.json", "form": "json-schema",
             "tier": "T2", "role": "schema", "note": "系统卡契约（与常规域包同形）"},
            {"path": "outputs/SYSTEM_CARD.json", "form": "system-card", "tier": "T3",
             "role": "data", "schema": "outputs/schemas/SYSTEM_CARD.schema.json",
             "note": "组合包系统卡（用途 / 限制 / 借阅边界 / 不宣称）"},
        ],
    }
    return index



def _combo_card(cert: Dict[str, Any], name: str) -> Dict[str, Any]:
    """组合包系统卡（用途 / 限制 / 借阅边界 / 不宣称）。"""
    card = {
        "kind": "nf-system-card/1",
        "system": {"id": "NF-COMBO-%s" % re.sub(r"[^A-Za-z0-9]", "-", name)[:20].upper(),
                   "name": name, "version": "1.0.0",
                   "kind_of_system": "domain-package", "model_agnostic": True},
        "intended_use": {
            "purpose": "把 %d 个域包按声明组合成一个可装载装配单元：层位堆叠、依赖与事件闭包、"
                       "只读借阅全部由组合证书机验。" % len(cert["packs"]),
            "consumers": ["装配运行时（%s）" % cert.get("pipeline", ""), "组合调用方"],
            "in_scope": ["组合合法性（五不变量）", "层位堆叠与装载序", "只读借阅索引"]},
        "limitations": [
            "组合包不改源包：借阅只读，模块不改号、资产不复制",
            "组合只保证结构合法与可复算，不保证组合内容的领域质量",
            "广度证明为两两全集 + 定种子抽样，非 2^N 全枚举",
        ],
        "data": {"sources": [{"id": "COMBO_CERT", "kind": "generated",
                              "note": "证书由组合引擎确定性生成并可复算"}],
                 "provenance_policy": "源包资产经 references 只读借阅；组合不新增内容资产",
                 "personal_data": "none"},
        "evaluation": {"method": "组合五不变量 + 证书 T4 复算 + check32 combos 子扫描",
                       "faces": [{"name": "组合合法性", "gate": "check32 combos",
                                  "result": "五不变量全成立"}],
                       "reproduce_command": "python scripts/nf.py combine verify",
                       "not_measured": ["组合内容质量", "高阶组合的全枚举"]},
        "human_oversight": ["组合声明变更须重跑 materialize 与门禁",
 "借阅边界由 references 白名单控制"],
        "risk_management": {"framework": "NIST AI RMF 1.0",
                            "functions": {"GOVERN": ["借阅白名单可审计"],
                                          "MAP": ["组合构成表（源包 → 模块）"],
                                          "MEASURE": ["证书 T4 复算 + 广度证明"],
                                          "MANAGE": ["组合非法即拒（fail-closed）"]},
                            "residual_risks": ["抽样广度非全枚举",
 "源包演进会使组合证书过期（须重签）"]},
        "out_of_scope": ["新增内容资产", "替代源包职责"],
        "not_claims": ["不宣称组合内容质量", "不宣称已穷举所有高阶组合",
                       "不宣称组合包等价于任何源包"],
    }
    return card
