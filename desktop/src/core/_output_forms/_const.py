"""output_forms 私有子模块 _const：常量与词表（形态清单/基线路径、档位/状态、扩展名→形态、形态上限档、输出面输入清单）。

门面 core.output_forms 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import re
from typing import Tuple


REGISTRY_REL = "protocol/output_forms.json"

BASELINE_REL = "protocol/output_forms_baseline.json"

INDEX_REL = "outputs/INDEX.json"

#: 逐包内容键里要一并计入的共享件（registry 的所有包都读它）。
REGISTRY_INPUT = "desktop/src/core/registry.json"


#: 机检档位（递增）；档位 = **本仓可做的判定强度**，不是「格式有多高级」
TIERS: Tuple[str, ...] = ("T0", "T1", "T2", "T3", "T4")


#: 形态状态（对外可判定口径）
#: supported=本仓既有产出/校验面；absorbed=本波从零构建；planned=登记未做（带触发条件）；
#: deferred=暂缓（有明确前置）；unfit=不适面；reference=实现参考（机制借鉴，非产出形态）；
#: unreachable=规范入口本机不可达（实证 false，不假装可达）。
STATUSES = ("supported", "absorbed", "planned", "deferred", "unfit",
            "reference", "unreachable")


_EXT_FORM = {
    ".json": "json", ".jsonl": "jsonl", ".ndjson": "jsonl", ".yaml": "yaml",
    ".yml": "yaml", ".toml": "toml", ".csv": "csv", ".tsv": "csv", ".xml": "xml",
    ".md": "markdown", ".mmd": "mermaid", ".dot": "graphviz-dot", ".gv": "graphviz-dot",
    ".graphml": "graphml", ".svg": "svg", ".txt": "text", ".proto": "protobuf-proto3",
    ".graphql": "graphql-sdl", ".ttl": "turtle", ".sql": "sql-ddl",
}

#: 形态自身可达的**上限**档位（本仓校验器决定；未实现的形态按扩展名给 T1 兜底）
_FORM_MAX_TIER = {
    "json": "T2", "jsonl": "T2", "yaml": "T2", "toml": "T2", "csv": "T2",
    "xml": "T1", "svg": "T1", "markdown": "T1", "text": "T0",
    "json-schema": "T2", "vega-lite": "T3", "mermaid": "T3", "graphviz-dot": "T3",
    "graphml": "T3", "json-graph-format": "T3", "quant-metrics": "T3",
    "performance-report": "T4", "concept-closure": "T4", "system-card": "T3",
    "domain-spec": "T3", "domain-report": "T4",
    "combo-cert": "T4",
}



_DTD_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)", re.I)



_MERMAID_KINDS = ("graph", "flowchart", "sequencediagram", "classdiagram",
                  "erdiagram", "statediagram", "gantt", "pie", "journey", "mindmap")
