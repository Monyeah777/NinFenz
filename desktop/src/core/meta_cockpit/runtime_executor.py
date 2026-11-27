"""Deterministic content-pipeline and meta-pipeline executor.

加载方法节点资产、策略表与两条管线，做 shape/policy/graph 校验与拓扑排序，
然后按类型跑三条内容链与元认知管线：
- 纵向：真实 P03 产物（离线确定性抽取）；
- 横向 / 知识体系：已验证的 GOOD 夹具。
输出每节点判据、元管线原子轨迹与整链 verdict；退出码 0 = 机器层全过。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

# 实现分片：原模块逻辑在私有子包 _runtime_executor/，本门面按原模块面显式再导出（API 不变）。
from core.meta_cockpit._runtime_executor._part1 import (
    BASE,
    MAX_MISSING_CAP,
    META_PIPELINE,
    METHOD_SCHEMA,
    METHOD_V,
    NODES,
    PIPE_SCHEMA,
    PIPE_V,
    PIPELINE,
    bigrams,
    doc,
    graph_issues,
    machine_digest,
    numeric_conflict_count,
    p,
    policy_drift,
    policy_issues,
    policy_signature,
    review_status,
    run_meta_pipeline,
    span_anchor_rate,
    topo,
)
from core.meta_cockpit._runtime_executor._part2 import eval_node, main

from . import chain_horizontal as horiz
from . import chain_knowledge as know
from . import chain_vertical as real
from . import json_asset
from . import meta_atom_runtime as atoms
from . import schema_compat as jsonschema
from .repo_context import implementation_files

if __name__ == "__main__":
    sys.exit(main())
