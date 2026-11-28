"""core.pack_combo 私有实现分片 1/2（对外只经 core.pack_combo 门面导入）：combine 等"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core import atomic_write
from core._pack_combo._base import (
    _asset_index,
    _core_ids,
    _digest,
    _module_contracts,
    _read_json,
    indexes,
    profiles,
)
from core._pack_combo._const import CORE13
from core._pack_combo._materialize import _flatten_sources, combo_outputs, prof_get_module
from core._pack_combo._readme import combo_assets_readme, combo_pipeline, combo_readme
from core._pack_combo._combine import combine  # noqa: F401 - 门面按原模块面重新导出
from core._pack_combo._materialize_impl import materialize  # noqa: F401 - 门面按原模块面重新导出


@dataclass(frozen=True)
class BreadthOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    triple_sample: int = 400
    quad_sample: int = 200
    quint_sample: int = 120
    sext_sample: int = 60
    seed: int = 20260923
    _witness: Optional[str] = None
