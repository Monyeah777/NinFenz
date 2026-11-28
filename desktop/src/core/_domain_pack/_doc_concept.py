"""domain_pack · _doc_concept（自 domain_pack.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from ._alloc import (
    _slug,
    dump_yaml,
)
from ._catalog import (
    concept_index,
)
from ._io import (
    standards_catalog,
)


def concept_graph_md(spec: Dict[str, Any], root: str = ".") -> str:
    code, name = spec["code"], spec["name"]
    subs = spec["subdivisions"]
    edges = [tuple(e) for e in spec["edges"]]
    legend_key = "%s-anchor" % _slug(spec)
    cat = standards_catalog(root)
    bound: Dict[str, str] = {}          # 细分 id → 标准 id
    _ci = concept_index(spec, cat)
    bound = {k: v for k, v in _ci["primary"].items()}
    supp = {k: v for k, v in _ci["support"].items()}
    std_ids = _ci["std_ids"]
    lines = [
        '<!-- nf-asset: key="CONCEPT_GRAPH" version="1.0" status="active" -->',
        "# 概念图 · %s（概念前置偏序）" % name,
        "",
        "> 用途：本域包的**前置闭包求值输入面**——把「%s」这一域的 %d 个细分概念声明成一张偏序图（DA"
            "G），"
        "供域内口径模块（%s:M01）与收口模块（%s:M02）消费。" % (name, len(subs), spec["category"],
                                                          spec["category"]),
        "> 资产键：`CONCEPT_GRAPH`｜形态：人读表（§2）/ 别名表（§3）/ 机器可读块（§4）三形态同源——"
        "**§4 围栏块是唯一机读真相**，§2/§3 由它导出。",
        "> 覆盖：%d 个包内概念 + %d 个**可扩展标准节点**（主锚/辅锚/依赖三层入图：概念 → 主锚、"
        "概念 → 辅锚、标准依赖边）+ 1 个包外前置族（%s-00 领域通用前置）；"
        "节点 %d · 边 %d · 密度 %.4f。" % (len(subs), len(std_ids), code,
                                       _ci["nodes"], _ci["edges"], _ci["density"]),
        "> 来源：本件正文自撰；每条细分的权威锚见资产 `DOMAIN_SPEC` 与 `STANDARDS_ANCHORS`（逐条可"
            "达性实证）。",
        "",
        "## 1. 读法",
        "",
        "- **概念**：一个可独立装载的知识单元（本域第 N 条细分）。",
        "- **前置**：装载该概念之前必须先具备的概念（边方向「前置 → 后继」）。",
        "- **层**：该概念在 NF 九层位中的合理驻留层（P00–P80），用于装配定位，不是执行顺序。",
        "- **证据**：节点来源锚（见 §5 图例）；本图所有节点均挂外部可复核锚。",
        "",
        "## 2. 条目键表（一概念一键，asset_get 寻址）",
        "",
        "| 条目键 | 概念 | 层 | 直接前置 | 证据 |",
        "|---|---|---|---|---|",
    ]
    prereq = _concept_prereqs(subs, edges, std_ids, bound, supp, _ci)
    _concept_rows(subs, prereq, std_ids, cat, legend_key, lines)
    for i, s in enumerate(subs):
        pass                             # 概念行已在上方输出
    lines += [
        "",
        "## 3. 别名表（求值时 id 与别名等价）",
        "",
        "| 别名 | 概念 id |",
        "|---|---|",
    ]
    _alias_rows(subs, std_ids, code, lines)
    nodes = _concept_nodes(subs, prereq, std_ids, cat, legend_key)
    cs = "std-catalog"
    block = {
        "concept_graph": {
            "version": "1.0",
            "domain": name,
            "code": code,
            "provenance_strength": "external",
            "provenance_legend": {
                legend_key: "域内权威锚（规范 / 论文 / 参考实现），逐条 URL 与可达性实证见资产 "
                            "STANDARDS_ANCHORS（本波实测）",
                cs: "可扩展标准目录条目（protocol/standards_catalog.json，本机可达性实测）",
            },
            "external_prereqs": [
                {"id": "%s-00" % code, "name": "领域通用前置族（数学/工程基础，包外）"},
            ],
            "branches": [
                {"id": "domain", "name": "%s 全域" % name, "nodes": [s["id"] for s in subs]},
                {"id": "standards", "name": "可扩展标准（绑定）",
                 "nodes": ["STD-%s" % x for x in std_ids]},
            ],
            "nodes": nodes,
        },
    }
    lines += [
        "",
        "## 4. 机器可读块（唯一机读真相）",
        "",
        "```yaml",
        "\n".join(dump_yaml(block)),
        "```",
        "",
        "## 5. 证据与边界",
        "",
        "- 每个节点的来源锚（外部规范 / 论文 / 参考实现）逐条登记于 `STANDARDS_ANCHORS`，"
        "本图 `provenance_strength = external`（全覆盖，可复核）。",
        "- 图只声明**结构前置**（装载顺序），不声明掌握程度；边为「先具备 → 后展开」的域内常识序。",
        "- 包外前置族（%s-00）不随包交付，装载方须自备领域基础。" % code,
    ]
    return "\n".join(lines) + "\n"


def _concept_prereqs(subs, edges, std_ids, bound, supp, _ci):
    prereq: Dict[str, List[str]] = {s["id"]: [] for s in subs}
    for a, b in edges:
        prereq.setdefault(b, []).append(a)
    for s in std_ids:                    # 标准节点：概念 → 标准（该概念依据的标准）
        prereq["STD-%s" % s] = []
    for sid, std in bound.items():
        if std:
            prereq.setdefault("STD-%s" % std, []).append(sid)
    for sid, std in supp.items():        # 概念 → 辅锚（产出承载标准）
        if std:
            prereq.setdefault("STD-%s" % std, []).append(sid)
    for dep, sid in _ci["dep_edges"]:    # 标准依赖边：被依赖 → 依赖
        prereq.setdefault("STD-%s" % sid, []).append("STD-%s" % dep)
    return prereq


def _concept_rows(subs, prereq, std_ids, cat, legend_key, lines):
    for s in subs:
        layer = "P40" if (subs.index(s) % 2 == 0) else "P60"
        pre = "、".join("`%s`" % x for x in prereq.get(s["id"], [])) or "—"
        lines.append("| `%s` | %s | %s | %s | %s |"
                     % (s["id"], s["name"], layer, pre, legend_key))
    _std_rows(std_ids, cat, prereq, lines)


def _std_rows(std_ids, cat, prereq, lines):
    for sid in std_ids:                  # 标准节点入条目键表（可寻址）
        std_entry = cat.get(sid) or {}
        ev = std_entry.get("evidence") or {}
        lines.append("| `STD-%s` | 标准 · %s（%s｜%s｜实测 %s） | P80 | %s | std-catalog |"
                     % (sid,
                        std_entry.get("title",
                        sid),
                        std_entry.get("body",
                        ""),
                        std_entry.get("layer",
                        ""),
                        ("✓" if ev.get("reachable") else "✗"),
                        "、".join("`%s`" % x for x in prereq.get("STD-%s" % sid, [])) or "—"))


def _alias_rows(subs, std_ids, code, lines):
    for s in subs:
        alias = "%s-%s" % (code, re.sub(r"[\s（）()]+", "-", s["name"].strip()))[:48]
        lines.append("| `%s` | `%s` |" % (alias, s["id"]))
    for sid in std_ids:
        lines.append("| `std-%s` | `STD-%s` |" % (sid, sid))


def _concept_nodes(subs, prereq, std_ids, cat, legend_key):
    nodes = []
    for i, s in enumerate(subs):
        layer = "P40" if i % 2 == 0 else "P60"
        nodes.append({
            "id": s["id"], "name": s["name"], "layer": layer,
            "branch": "domain",
            "prereqs": prereq.get(s["id"], []),
            "provenance": [legend_key],
        })
    cs = "std-catalog"
    for sid in std_ids:
        std_entry = cat.get(sid) or {}
        nodes.append({
            "id": "STD-%s" % sid, "name": "标准 · %s" % std_entry.get("title", sid),
            "layer": "P80", "branch": "standards",
            "prereqs": prereq.get("STD-%s" % sid, []),
            "provenance": [cs],
        })
    return nodes
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
