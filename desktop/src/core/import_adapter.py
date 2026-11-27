"""读入适配器（v2.3.0 34 方案：A4 双向读入——外部→NF 反向解析层）。

与 exporter._REGISTRY 五出口（全 export-only）对称，提供 adapter_in 反向符号：
- parse_skill(text) -> SkillParseResult：SKILL.md 文本 → NF IRDocument 高保真
  重建（round-trip 与 export(ir,'skill') 逐字节对称）或宽容保留（外部自由文）。
- parse_ccv3(chara, world) -> Ccv3ParseResult：chara_card_v3 dict（+可选独立
  world dict）→ 叙事型 IR 骨架结构还原。

设计约束（34 方案核心 + 外部兼容实证驱动）：
- parse_skill 双层：**结构层**识别 NF 导出 body 层级模式（`## 层 {id} · {name}`、
  `### {full_id} · {name}`、`## 附加规则`）→ 高保真重建 IRDocument；
  **宽容层**对非 NF 层级 body（官方技能自由说明文）不强套层级：frontmatter
  name/description 必填校验 + 扩展字段（license 等）透传 metadata，正文整体
  保留——不崩、不静默丢；是否够格升 IR 由消费方判定（mode='external' 时
  ir=None）。
- frontmatter 解析**自写轻量解析器**（仓库无 PyYAML 硬依赖，pipeline_loader
  用内置回退策略——本模块同样不假设 yaml 在场）；description 支持引号包裹
  （官方 docx 长英文触发描述为双引号单行、内部可含裸单引号）。
- 失败路径（无 frontmatter / 缺 name·description / 空 body / spec 不符）→
  明确 ValueError，不静默产出坏 IR（静默丢内容不变式）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

# 实现分片：原模块逻辑在私有子包 _import_adapter/，本门面按原模块面显式再导出（API 不变）。
from core._import_adapter._part1 import (
    _BUNDLED_DIRS,
    _COMMENT_ASSET,
    _COMMENT_EXTRA,
    _PLACEHOLDER_NO_BODY,
    _RE_COMMENT_LAYER,
    _RE_DESC_CCV3,
    _RE_DESC_NF,
    _RE_EXTRA,
    _RE_LAYER,
    _RE_MODULE,
    Ccv3ParseResult,
    SkillParseResult,
    _entry_to_module,
    _parse_nf_body,
    _record_asset,
    _scan_resources,
    _unquote_yaml_value,
    parse_frontmatter,
    parse_skill,
)
from core._import_adapter._part2 import (
    _ingest_entries,
    _IngestContext,
    _place_module,
    _skip_entry,
    parse_ccv3,
)

from .ir import IRDocument, IRLayer, IRModule
