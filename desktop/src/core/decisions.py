"""决策记录门禁（ADR：一条决策一编号，采纳后不改不删，只可被取代）。

真源 = decisions/ADR-*.md 的 frontmatter + 正文；decisions/INDEX.md 是投影。

判据（全部可证，零第三方依赖）：
- 编号：id 必须等于文件名前缀 ADR-\\d{4}；全库唯一；
- 状态：status ∈ {proposed, accepted, superseded, deprecated}；date 为 YYYY-MM-DD；
- 三段齐：正文必须含 ## 背景 / ## 决策 / ## 后果；
- 取代链：目标在册、无悬空、无环（DFS 判定：任何环都报，不只回到起点那种）；
  supersedes 与 superseded_by 必须互指（A.supersedes=B ⇔ B.superseded_by=A）；
- 证据：每条须解析到仓库真实**文件**、checkN（verify.sh 在册）或**在册** ADR-N；
  路径必须落在仓库根内（拒绝绝对路径 / .. 逃逸 / 目录 / 指向仓外的符号链接）；
- 不可改：status: accepted 的 ADR 必须已被协议回执锚定（protocol/RECEIPTS.json）——
  正文一改回执即失效，于是「改了」必然被 check35 抓住，决策只能靠新增 + 互指 supersede 演进。

架构（2026-10-19 重构：端口-适配器 + 不可变模型 + 结构化诊断）：
- Adr / Issue 是值对象（frozen dataclass）；规则是纯函数，逐条带稳定 code（ADR0xx）；
- 文件系统 / frontmatter / 回执解析只出现在 load() 这一层；畸形输入一律转 Issue
  （fail-closed），不以 traceback 或静默放行收场；
- scan() 保留旧的 (list[str], list[str], dict) 形状以兼容 nf decisions 既有调用点；
  analyze() 暴露结构化结果（Issue 带 code/severity/path）给新调用方。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from core import doc_family, json_doc

# 实现分片：原模块逻辑在私有子包 _decisions/，本门面按原模块面显式再导出（API 不变）。
from core._decisions._part1 import (
    _ABS,
    _ADR,
    _CHECK,
    _CTRL,
    _DATED,
    _FILE_ID,
    _ID,
    BEGIN,
    DASH,
    END,
    FAIL,
    GLOB,
    INDEX_REL,
    MAX_EVIDENCE_LEN,
    RECEIPTS_REL,
    REQUIRED,
    SECTIONS,
    STATUSES,
    WARN,
    Adr,
    Corpus,
    Issue,
    ScanResult,
    _as_list,
    _duplicate_keys,
    _empty_evidence_slots,
    _fm_lines,
    _r_identity,
    _read_one,
    _read_receipts,
    _structure_issues,
    _top_keys,
    _txt,
    entries,
    load,
)
from core._decisions._part2 import (
    RULES,
    _cell,
    _cycle_key,
    _edge_map,
    _edges,
    _evidence_issue,
    _format_issues,
    _heads,
    _path_reason,
    _r_chains,
    _r_evidence,
    _r_fields,
    _r_lifecycle,
    _r_links,
    _required_issues,
    _shape_reason,
    _stats,
    _superseded_by_issues,
    _supersedes_issues,
    _target_reason,
    _walk,
    analyze,
    check_projection,
    render_corpus,
    render_index,
    scan,
    write_projection,
)
from core.library_entries import parse_frontmatter

# 读点：契约 JSON 解析一律走 core.json_doc.loads / core.json_doc.load（N11）；实现分片见同目录私有子包。
