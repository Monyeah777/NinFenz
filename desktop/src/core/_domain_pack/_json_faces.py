"""domain_pack · _json_faces（自 domain_pack.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from ._catalog import (
    authenticity,
    bindings_full,
)
from ._const import (
    SUB_COUNT,
)
from ._io import (
    standards_catalog,
)

# ---------------------------------------------------------------- 产出面（机验）

def domain_spec_json(spec: Dict[str, Any], root: str = ".") -> str:
    cat = standards_catalog(root)
    subs = []
    _bd = bindings_full(spec, cat)
    probe_dates: List[str] = []
    for s in spec["subdivisions"]:
        sid, why = _bd[s["id"]]["primary"]
        anchors = []
        for role in ("primary", "support"):
            rid, rwhy = _bd[s["id"]][role]
            if not rid:
                continue
            std = cat.get(rid) or {}
            ev = std.get("evidence") or {}
            if ev.get("probe_date"):
                probe_dates.append(str(ev["probe_date"]))
            anchors.append({
                "ref": rid, "role": role, "why": rwhy,
                "layer": std.get("layer", ""), "body": std.get("body", ""),
                "reachable": bool(ev.get("reachable")),
                "http_status": int(ev.get("http_status") or 0),
                "probe_date": str(ev.get("probe_date") or ""),
                "depends_on": list(std.get("depends_on") or []),
            })
        subs.append({
            "id": s["id"], "name": s["name"], "definition": s["definition"],
            "anchor": s["anchor"], "anchor_kind": s.get("anchor_kind", "spec"),
            "anchor_status": int(s.get("anchor_status") or 0),
            "standard_ref": sid, "standard_why": why,
            "standards": anchors,
            "check": s["check"], "pitfall": s["pitfall"],
        })
    auth = authenticity(spec, cat)
    doc = {
        "kind": "nf-domain-spec/1",
        "code": spec["code"],
        "domain": spec["name"],
        "section": spec["section"],
        "anchors_verified_on": "2026-09-22",
        "standard_anchors_verified_on": max(probe_dates) if probe_dates else "",
        "metric_family": spec["metric_family"],
        "content_tier": spec.get("content_tier", "authored"),
        "data_authenticity": {
            "standard_bindings": auth["standard_bindings"],
            "in_catalog_ratio": auth["in_catalog_ratio"],
            "reachable_ratio": auth["reachable_ratio"],
            "probe_evidence_ratio": auth["probe_evidence_ratio"],
            "anchor_probed_ratio": auth["anchor_probed_ratio"],
            "score": auth["score"],
            "threshold": auth["threshold"],
            "bound_standards": auth["bound_standards"],
        },
        "subdivisions": subs,
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"




def domain_spec_schema(spec: Dict[str, Any]) -> str:
    code = spec["code"]
    return json.dumps({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ninfenz.local/schema/domain-spec-%s.schema.json" % code.lower(),
        "title": "%s 域口径表（机读投影）" % spec["name"],
        "description": "assets/DOMAIN_SPEC.md 的机读投影契约；键集须与散文面双向一致（双源一致由 "
                       "check32 output_forms 断言）。",
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "code", "domain", "section", "anchors_verified_on",
                     "standard_anchors_verified_on", "metric_family", "subdivisions",
                     "content_tier", "data_authenticity"],
        "properties": {
            "kind": {"const": "nf-domain-spec/1"},
            "content_tier": {"enum": ["authored", "derived"]},
            "code": {"const": code},
            "domain": {"type": "string", "minLength": 1},
            "section": {"type": "string", "minLength": 1},
            "anchors_verified_on": {"type": "string", "format": "date"},
            "standard_anchors_verified_on": {"type": "string", "minLength": 4},
            "metric_family": {"type": "string", "minLength": 3},
            "data_authenticity": {
                "type": "object", "additionalProperties": False,
                "required": ["standard_bindings", "in_catalog_ratio", "reachable_ratio",
                             "probe_evidence_ratio", "anchor_probed_ratio", "score",
                             "threshold", "bound_standards"],
                "properties": {
                    "standard_bindings": {"type": "integer", "minimum": 1},
                    "in_catalog_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                    "reachable_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                    "probe_evidence_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                    "anchor_probed_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                    "score": {"type": "number", "minimum": 0, "maximum": 1},
                    "threshold": {"type": "number", "minimum": 0, "maximum": 1},
                    "bound_standards": {"type": "array", "minItems": 1,
                                        "items": {"type": "string", "minLength": 2}},
                },
            },
            "subdivisions": {
                "type": "array", "minItems": SUB_COUNT, "maxItems": SUB_COUNT,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "name", "definition", "anchor", "anchor_kind",
                                 "anchor_status", "standard_ref", "standard_why",
                                 "standards", "check", "pitfall"],
                    "properties": {
                        "id": {"type": "string", "pattern": "^%s-[0-9]{2}$" % code},
                        "name": {"type": "string", "minLength": 2},
                        "definition": {"type": "string", "minLength": 8},
                        "anchor": {"type": "string", "format": "uri"},
                        "anchor_kind": {"enum": ["spec", "paper", "repo", "doc", "dataset"]},
                        "anchor_status": {"type": "integer", "minimum": 0},
                        "standard_ref": {"type": "string", "minLength": 2},
                        "standard_why": {"type": "string", "minLength": 3},
                        "standards": {
                            "type": "array", "minItems": 1, "maxItems": 4,
                            "items": {
                                "type": "object", "additionalProperties": False,
                                "required": ["ref", "role", "why", "layer", "body",
                                             "reachable", "http_status", "probe_date",
                                             "depends_on"],
                                "properties": {
                                    "ref": {"type": "string", "minLength": 2},
                                    "role": {"enum": ["primary", "support"]},
                                    "why": {"type": "string", "minLength": 3},
                                    "layer": {"enum": ["data", "iface", "form", "gov", "eng"]},
                                    "body": {"type": "string", "minLength": 1},
                                    "reachable": {"type": "boolean"},
                                    "http_status": {"type": "integer", "minimum": 0},
                                    "probe_date": {"type": "string", "minLength": 4},
                                    "depends_on": {
                                        "type": "array",
                                        "items": {"type": "string", "minLength": 2},
                                    },
                                },
                            },
                        },
                        "check": {"type": "string", "minLength": 10},
                        "pitfall": {"type": "string", "minLength": 6},
                    },
                },
            },
        },
    }, ensure_ascii=False, indent=2) + "\n"




def report_schema(spec: Dict[str, Any]) -> str:
    code = spec["code"]
    return json.dumps({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ninfenz.local/schema/domain-report-%s.schema.json" % code.lower(),
        "title": "%s 域报告（可复算）" % spec["name"],
        "description": "样例集上的口径值报告（T4）：由 outputs/samples/CASES.csv 经 "
                       "core/domain_metrics 重算并逐字段比对。**非模型能力声明**。",
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "code", "domain", "family", "sample", "sample_rows", "metrics"],
        "properties": {
            "kind": {"const": "nf-domain-report/1"},
            "code": {"const": code},
            "domain": {"type": "string", "minLength": 1},
            "family": {"type": "string", "minLength": 3},
            "sample": {"type": "string", "pattern": "^outputs/samples/"},
            "sample_rows": {"type": "integer", "minimum": 1},
            "metrics": {"type": "object", "minProperties": 3},
        },
    }, ensure_ascii=False, indent=2) + "\n"




def system_card(spec: Dict[str, Any], alloc: Dict[str, Any]) -> str:
    code, name = spec["code"], spec["name"]
    doc = {
        "kind": "nf-system-card/1",
        "system": {"id": "NF-%s-PACK" % code, "name": spec["pack_name"], "version": "1.0.0",
                   "kind_of_system": "domain-package", "model_agnostic": True},
        "intended_use": {
            "purpose": "把「%s」这一域的 %d 条细分协议化：口径可判定、判据可机检、锚可复核，"
                       "并产出可复算的域报告与可机验的形态面。" % (name, len(spec["subdivisions"])),
            "consumers": ["装配运行时（%s 管线）" % alloc["pipeline"],
                          "需要该域口径清单的内容/评测生产方",
                          "下游域包（同源引用本域口径面）"],
            "in_scope": ["%d 条细分的定义口径与可机检判据" % len(spec["subdivisions"]),
                         "概念前置偏序与装载序", "样例集上的域度量复算（T4）"],
        },
        "limitations": [
            "覆盖以本节声明的 %d 条细分为界：域内相邻主题未列入者不自动继承"
                "" % len(spec["subdivisions"]),
            "域报告是**样例集（合成夹具）上的口径值**，不代表真实模型/系统能力",
            "外部权威锚只作口径参照，未做逐条规范全文比对",
            "包外前置族（%s-00）不随包交付，装载方须自备领域基础" % code,
        ],
        "data": {
            "sources": [
                {"id": "DOMAIN_SPEC", "kind": "self-authored",
                 "note": "域口径表正文自撰；外部锚仅登记 URL 与可达性，不复制外部文本"},
                {"id": "CASES", "kind": "generated",
                 "note": "度量夹具为确定性合成数据（core/domain_metrics.synthesize，种子 = 域码）"},
            ],
            "provenance_policy": "外部输入只作机制借鉴与口径参照（逐条实测可达性），不作立项理由或"
                                 "质量背书（STRATEGY §3.2/§3.3）",
            "personal_data": "synthetic-only",
        },
        "evaluation": {
            "method": "内部机检链：verify 门禁（check14/23/32/33）+ 域报告复算（T4）+ 单测",
            "faces": [
                {"name": "登记与投影一致", "gate": "check14 ⑦",
                 "result": "protocol.yaml ↔ registry protocols[] ↔ 02 §8 三处一致"},
                {"name": "资产供应链闭合", "gate": "check23",
                 "result": "3 件资产头 ↔ provenance.json 双源一致"},
                {"name": "概念图健康", "gate": "check32 concept_graph",
                 "result": "无环 / 无悬空 / 边有溯源 / 层位合法 / 别名唯一 / 分支完备"},
                {"name": "产出形态与机验率", "gate": "check32 output_forms",
                 "result": "9 面全部 ≥T2（可机验占比 100%）；T4 面复算一致"},
            ],
            "reproduce_command": "python scripts/nf.py output verify --json",
            "not_measured": ["真实模型在该域的能力（本包不含模型，也不做能力声明）",
                             "外部客户端装载实测（外部接触按 STRATEGY 封存）",
                             "锚规范全文一致性（只登记入口与可达性）"],
        },
        "human_oversight": [
            "口径条目变更须走资产表 + 机读投影双改，并重跑门禁（禁止只改 JSON）",
            "不可达锚由维护者复核后更新（本表如实记 ✗，不假装可达）",
            "域包公开面只放结果（资产 + 模块 + 产出面 + 收口注记）",
        ],
        "risk_management": {
            "framework": "NIST AI RMF 1.0",
            "functions": {
                "GOVERN": ["登记三要件由 check14 硬门守住（protocol.yaml / 02 §8 / registry）",
                           "公开文案纪律：只写结果与状态"],
                "MAP": ["域边界 = 本节 %d 条细分表：不覆盖处以新条目显式登记"
                        % len(spec["subdivisions"]),
                        "前置关系显式成图（CONCEPT_GRAPH）"],
                "MEASURE": ["度量族口径显式（%s）并可复算（T4）" % spec["metric_family"],
                            "产出面档位与机验率落基线（回退即 FAIL）"],
                "MANAGE": ["资产/模块状态位支持淘汰流转", "机验率回退即门禁失败"],
            },
            "residual_risks": ["夹具为合成数据，不能替代真实评测",
                               "锚版本漂移需人工复核", "域内细分边界存在主观性（已声明覆盖边界）"],
        },
        "out_of_scope": ["该域的教学内容", "具体模型权重与推理运行时",
                         "外部服务的可用性与定价承诺"],
        "not_claims": ["不做模型能力结论（域报告是样例口径值）",
                       "不宣称外部兼容性（未做客户端装载实测）",
                       "口径表不宣称完备：覆盖以本节声明边界为准",
                       "NIST AI RMF 段为字段映射陈述，不构成合规认证"]
        + (["本包内容为 **derived 档**：细分名与框架判据已登记，领域细则待作者补全——"
            "不得当作领域专家级口径使用"]
           if spec.get("content_tier") == "derived" else []),
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"




def output_index(spec: Dict[str, Any]) -> str:
    code = spec["code"]
    entries = [
        {"path": "outputs/schemas/DOMAIN_SPEC.schema.json", "form": "json-schema",
         "tier": "T2", "role": "schema", "note": "口径表机读投影契约"},
        {"path": "outputs/schemas/DOMAIN_REPORT.schema.json", "form": "json-schema",
         "tier": "T2", "role": "schema", "note": "域报告契约（可复算面）"},
        {"path": "outputs/schemas/SYSTEM_CARD.schema.json", "form": "json-schema",
         "tier": "T2", "role": "schema", "note": "系统卡契约"},
        {"path": "outputs/DOMAIN_SPEC.json", "form": "domain-spec", "tier": "T3",
         "role": "data", "schema": "outputs/schemas/DOMAIN_SPEC.schema.json",
         "dual_source": {"markdown": "assets/DOMAIN_SPEC.md", "field": "id",
                         "key_pattern": "`(%s-[0-9]{2})`" % code},
         "note": "口径表机读投影（与资产双向一致）"},
        {"path": "outputs/samples/CASES.csv", "form": "csv", "tier": "T2", "role": "data",
         "note": "度量夹具（确定性合成；口径可复算，非真实测量）"},
        {"path": "outputs/REPORT.json", "form": "domain-report", "tier": "T4",
         "role": "functional", "schema": "outputs/schemas/DOMAIN_REPORT.schema.json",
         "recompute": {"id": "domain-report",
                       "inputs": ["outputs/samples/CASES.csv"],
                       "params": {"family": spec["metric_family"],
                                  "code": spec["code"], "domain": spec["name"]}},
         "note": "度量族复算报告（check32 重算比对）"},
        {"path": "outputs/charts/METRICS.vega.json", "form": "vega-lite", "tier": "T3",
         "role": "chart",
         "render": {"id": "vega-metrics", "inputs": ["outputs/REPORT.json"],
                    "params": {"title": "%s · 样例口径值" % spec["name"]}},
         "note": "指标条形图（由报告确定性生成）"},
        {"path": "outputs/CONCEPT_DAG.graphml", "form": "graphml", "tier": "T3",
         "role": "diagram",
         "render": {"id": "graphml-concept-dag",
                    "graph": "community/%s/assets/CONCEPT_GRAPH.md" % spec["pack_name"]},
         "note": "概念前置图（图交换形态；边端点引用完整性由形态校验器判定）"},
        {"path": "outputs/charts/CONCEPT_DAG.mmd", "form": "mermaid", "tier": "T3",
         "role": "diagram",
         "render": {"id": "mermaid-concept-dag",
                    "graph": "community/%s/assets/CONCEPT_GRAPH.md" % spec["pack_name"]},
         "note": "概念前置图（按层分组的 Mermaid 形态）"},
        {"path": "outputs/SYSTEM_CARD.json", "form": "system-card", "tier": "T3",
         "role": "data", "schema": "outputs/schemas/SYSTEM_CARD.schema.json",
         "note": "域包系统卡（用途 / 限制 / 数据 / 评测 / 人审 / 风险治理 / 不宣称）"},
    ]
    doc = {
        "schema": "nf-output-index/1",
        "package": spec["pack_name"],
        "note": "机验产出面清单（域包工厂生成；check14/check32 与 nf output 按此判定）。"
                "role 语义：schema 契约 / data 数据 / chart 图表 / diagram 图示 / functional 可复算"
                    "。",
        "outputs": entries,
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
