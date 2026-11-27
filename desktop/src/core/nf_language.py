"""NF 语言面符号索引（编辑器接管面：补全 / 悬停 / 跳定义 / 工作区符号）。

内部差距实证（2026-10-07 审计）：`nf lsp` 此前只有「诊断 + quickfix」——NF 的领域词汇
（模块 id / 资产键 / 事件名 / 层位 id / 管线 id）在编辑器里**没有补全、悬停无元数据、
引用不可跳转**；协议长在 Markdown 上，而「引用真实件」这条使用铁律在编辑器里没有承接面。
编辑器能拿到的只有整文档诊断，于是「IDE 集成」在门禁里只剩一个布尔（见 docs/lsp.md）。

单一真相纪律（I5）：符号表**全部从既有真源派生**，不新造第二份事实——
- 模块 id / 名 = 模块文件自身 `machine_contract.id/name`（01 §1.1，机读契约是模块身份
  的唯一真源；`大语言模型:M01` 落在 `A01a_*.md` 这类文件名与编号不对应的域包上，
  按文件名反解会漏——这正是本索引读契约块而不读文件名的理由）；
- 层位 / 订阅 / 官方核心模块挂载 = `desktop/src/core/registry.json`；
- 事件名 = `protocol/event_registry.json` ∪ registry `subscriptions`（并取发布方）；
- 资产键 = 资产文件名令牌（与 `asset_get` 的文件名候选同口径）；
- 管线 = `03_管线库/*.md` 与 `community/*/pipelines/*.md` 的 `id:` 声明行。

歧义不猜：`resolve` 只在**唯一**时给答案；`resolve_all` 给全部同名候选（悬停展示用），
`M10`（通用:M10 / 生存:M10）与 `P00`（层位 / 官方管线同名先例）正是需要这条纪律的例子。

只读；无网络；mtime 失效；缺件不裸崩（缺号即少给符号，不臆造）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import json_doc

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade
from core._nf_language import _part2 as _live_part2

# 实现分片：原模块逻辑在私有子包 _nf_language/，本门面按原模块面显式再导出（API 不变）。
from core._nf_language._part1 import (
    _ASSET_TOKEN,
    _BARE_NUM,
    _PIPE_ID,
    _TITLE,
    EVENT_REGISTRY_REL,
    KINDS,
    REGISTRY_REL,
    SCAN_GLOBS,
    SymbolIndex,
    SymbolOptions,
    _bare_alias,
    _edge,
    _event_relations,
    _events,
    _head,
    _layers,
    _mount_relations,
    _pipe_id_of,
    _pipeline_relations,
    _read_json,
    _symbol,
    module_meta,
)
from core._nf_language._part2 import (
    _assets,
    _modules,
    _mounts_doc,
    _pipelines,
    _relations,
    _user_assets,
    build,
)

_install_live_facade(__name__, {
    "signature": _live_part2,
})

# 读点：契约 JSON 解析一律走 core.json_doc.loads / core.json_doc.load（N11）；实现分片见同目录私有子包。
