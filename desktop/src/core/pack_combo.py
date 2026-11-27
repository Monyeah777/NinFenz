"""域包自由组合引擎（任意 n 元 × 任意组件）。

目标：100 个域包（+ 既有社区包）**任意子集**可自由组合；包内组件（协议 / 管线 / 模块 /
资产）也可自由取用；组合广度 = 2^N（不预先枚举）；深度质量 = 每条组合必须过**五条可机检
不变量**；产出 = **可复算证书**（T4：门禁重算并与在盘证书逐字段比对）。

五条不变量（任一不成立即非法，不许静默降级）：
1. **模块唯一可定位**：选中模块 id 唯一，且能定位到机读契约（缺契约即报）；
2. **依赖闭合**：模块 `inputs` 只能指向「组合内模块」∪「官方核心 13 件」，否则报 dangling；
3. **事件闭合**：任一 `subscribe` 必须在本组合内有发布方（本仓域包事件按域码命名空间，
   包内自闭合；跨包订阅须显式事件桥，否则报 unbridged）；
4. **层位堆叠确定**：同层多包默认挂载按（声明序 → 模块 id）确定性堆叠，产出 `layer_stacks`；
5. **资产可寻址**：跨包资产以 `asset_readonly` 借阅，键须能在源包 provenance 台账找到。

广度证明（`breadth`）：全部两两组合（C(N,2)）+ 定种子抽样的三元 / 四元组合跑同一套不变量，
断言「任意组合合法」——广度不靠枚举，靠**不变量在全集上成立**。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。

# 读点：证书/协议件读取在 _pack_combo._base 里仍走 json_doc.loads（N11）。

from __future__ import annotations

import copy
import itertools
import random
import re

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
import sys as _sys
import types as _types
from dataclasses import dataclass
from pathlib import Path

# 依赖面：逐字保留原模块 import 面（含函数内 core import 的边）——
# 耦合图/纯度面按模块级 import 计算，勿删（见 re-export 说明）。
from core import atomic_write, disk_cache, json_doc, official_core
from core import conformance_scan as _csc
from core import conformance_scan as csc
from core import domain_pack as dpk

# 导入闭包指纹：由调用方算（持久层不再反向依赖解析层，见 2026-09-29 拆环）
from core import import_graph as _ig
from core import json_schema as _js  # 只取叶子校验器：不再 import output_forms（断双向对）

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade
from core._pack_combo import _part1 as _live_part1

# 实现分片：原模块逻辑在私有子包 _pack_combo/，本门面按原模块面显式再导出（API 不变）。
from core._pack_combo._part1 import BreadthOptions, materialize
from core._pack_combo._part2 import _scan_impl, breadth, scan

from ._pack_combo._base import (
    _asset_index,
    _cache_key,
    _content_store,
    _core_contracts,
    _core_ids,
    _digest,
    _face_paths,
    _inputs_fingerprint,
    _module_contracts,
    _pack_assets,
    _pack_dirs,
    _parse_protocol,
    _read_json,
    _root_cache,
    cache_clear,
    indexes,
    profiles,
)
from ._pack_combo._cert import (
    _CERT_CACHE,
    _CERT_CACHE_MAX,
    _COMBO_DECL_KEYS,
    _canon,
    _certificate_lines,
    _combo_witness,
    _verdict_cached,
    certify,
    core_contracts_fingerprint,
    declared,
    verify_certificate,
)
from ._pack_combo._const import (
    _CACHE,
    _CACHE_MAX,
    _COMBO_CACHE,
    _COMBO_CACHE_MAX,
    _CONTENT_CACHE,
    _CONTENT_CACHE_MAX,
    _CONTRACTS_CACHE,
    _CONTRACTS_CACHE_MAX,
    CERT_REL,
    CERT_SCHEMA,
    CORE13,
    CORE_CONTRACT_PATTERNS,
    INPUT_PATTERNS,
    MODULE_CONTRACT_PATTERNS,
    PROFILE_PATTERNS,
    SCAN_INPUTS,
)
from ._pack_combo._materialize import (
    _combo_borrow,
    _combo_card,
    _combo_index,
    _flatten_sources,
    combo_outputs,
    prof_get_module,
)
from ._pack_combo._readme import (
    ComboSpec,
    combo_assets_readme,
    combo_pipeline,
    combo_readme,
    combo_register,
)

_install_live_facade(__name__, {
    "combine": _live_part1,
})
