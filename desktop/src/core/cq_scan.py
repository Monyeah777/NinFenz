"""全仓代码质量审查 CQ0/CQ1（NF-Final §13B，WP-0H）：工具固定 + 全量自动扫描 + 基线/热点。

为什么（§13B.8）：CQ 不是「跑一次 lint」——先把**工具与版本固定**（本机可用/缺失都如实记），
再做**全量自动扫描**（全语言：Python 语法、JSON/YAML/Shell、ruff/bandit/radon/vulture），
产出可复算的扫描件与热点，并把发现分诊成 P0/P1/P2 清单。

契约口径（与仓库既有棘轮不冲突）：
- 本模块只**汇总**，不替代既有门禁（verify check12/27/34/35 等）；CQ 是额外纵深；
- 缺失工具（如 cosign/gitleaks）→ `status=blocked`，**不得**写成通过；
- 产物：`results/cq/toolchain.json`、`results/cq/scan.json`、`results/cq/findings.jsonl`、
  `results/cq/hotspots.md`；`docs/CQ_REPORT.md` + `docs/QUALITY_DEBT.md` 人读面；
- 新鲜度：`check()` 比对「HEAD + 工作树状态 + 工具版本」指纹（不重跑全量扫描），
  树/工具一变即要求 `--run` 重算——不把旧报告当新结论。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 实现分片：原模块逻辑在私有子包 _cq_scan/，本门面按原模块面显式再导出（API 不变）。
from core._cq_scan._part1 import (
    BENIGN_PHRASES,
    DIMS,
    DIR_REL,
    FINDINGS_REL,
    FORBIDDEN_WORDS,
    GUIDE,
    HOTSPOTS_REL,
    NEGATION,
    SCAN_REL,
    SCAN_SCHEMA,
    SCANNERS,
    SEVERITIES,
    TOOLCHAIN_REL,
    TOOLCHAIN_SCHEMA,
    TOOLS,
    _finding,
    _fingerprint,
    _run,
    _scan_bandit,
    _scan_claims,
    _scan_json,
    _scan_radon,
    _scan_ruff,
    _scan_shell,
    _scan_syntax,
    _scan_vulture,
    _scan_yaml,
    _tracked,
    toolchain,
)
from core._cq_scan._part2 import (
    artifact_issues,
    build,
    check,
    render_findings,
    render_hotspots,
    render_json,
    write,
)
