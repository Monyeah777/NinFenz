"""概念图资产的门禁体检 + 图语义库（判据面收口，2026-09-20 作者裁决执行）。

背景（内部差距实证，见 `results/audit/docs_audit-50-ai-domain.md` §二）：概念前置偏序图
此前只落在**内容面**（域包资产的机器可读块），check 族全绿与图质量无关——图有环 / 前置
悬空 / 别名重复 / 节点未归支，门禁一条都不会红。本模块补上该判据面，并被两处消费：

- **门禁**：`quality_depth_scan.scan()` 的子扫描 → verify check32（**既有 check 内追加**，
  不新增 check 序号、不改 Schema）；
- **工具**：`scripts/ai_domain_closure.py`（只读求值器）复用本模块语义——图语义单一实现，
  避免「门禁算一套、求值器算另一套」的双源漂移。

判据（全部确定性、零第三方依赖；YAML 复用仓库既有依赖）：
- 结构：节点 id 唯一、层位 ∈ P00–P80、必备字段（name）、**边带 provenance**；
- 图论：无环（拓扑全序可达）、前置无悬空（须在节点表或外部前置族内）、无自环；
- 检索面：别名唯一（重复即歧义）；
- 分支面：分支 id 唯一、每个包内概念恰属一个分支、分支成员须真实存在；
- **证据面**（2026-09-20 作者裁决收口）：节点 provenance 的**每个键都须在图例中在册**
  （防「图例漂移」静默——此前只查 provenance 非空）；且图须声明 `provenance_strength`
  ∈ {external, domain-logic, inferred} 且与图例自洽（`external` 要求图例中至少有一个
  **非推断**来源键）。门禁只判「声明在场 + 与图例一致」，**不判证据是否真的充分**（那不可
  判定，硬判会造假判据）——证据强度的**分级声明**才是可机检的部分。

纪律：没有 `concept_graph:` 机读块的资产一律跳过（不影响既有包与用户自定义资产）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import glob
import heapq
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

from core import conformance_scan as csc

# 实现分片：原模块逻辑在私有子包 _concept_graph/，本门面按原模块面显式再导出（API 不变）。
from core._concept_graph._part1 import (
    _FENCE,
    _NON_SOURCE_KEYS,
    BLOCK_MARKER,
    DEFAULT_ASSET,
    LAYERS,
    PROVENANCE_STRENGTHS,
    SHELF_GLOBS,
    ClosureError,
    alias_map,
    branch_map,
    closure,
    external_coverage,
    fenced_block,
    frontier,
    graph_assets,
    in_package_ids,
    load_graph,
    missing,
    node_branch,
    node_meta,
    prereqs_of,
    provenance_strength,
    resolve,
    toposort,
    violations,
)
from core._concept_graph._part2 import CG_INPUTS, _scan_impl, problems, scan
