#!/usr/bin/env python3
"""NinFenz 资产供应链台账（40 总纲 v2.7 波 A S2：资产六环中的 入库/溯源/浏览/版本/淘汰）。

设计定位：
- 台账 = 资产根目录下 provenance.json（溯源键表，机读唯一真相）；
- 每个托管资产文件头部写入一行机器可读头（nf-asset header），与台账双源一致；
- 生命周期：active -> deprecated -> retired（deprecate/restore 经 CLI 流转）；
- verify.sh check23 = 供应链闭合门禁：每资产可溯源（source）、可发现（文件在册）、
  键无孤儿（文件头键 ∈ 台账 且 台账条目文件实存且头一致）。

纯 Python 标准库、零第三方依赖（L2 core 红线）。路径均为显式传入，便于单测隔离。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
import datetime
import glob
import json
import os
import re
from dataclasses import dataclass

from core import atomic_write, paths
from core import repo_face as _repo_face

# 实现分片：原模块逻辑在私有子包 _asset_ledger/，本门面按原模块面显式再导出（API 不变）。
from core._asset_ledger._part1 import (
    _HEADER_RE,
    HEADER_MARK,
    LEDGER_FILE,
    LEDGER_SCHEMA_VERSION,
    SHELF_GLOBS,
    STATUS_ACTIVE,
    STATUS_DEPRECATED,
    STATUS_RETIRED,
    VALID_STATUS,
    VALID_TIER,
    AssetLedgerError,
    AssetOptions,
    EntryOptions,
    _guard_duplicates,
    _guard_tier,
    _load_for_update,
    _safe_join,
    _set_status_locked,
    _today,
    add_asset,
    blank_ledger,
    default_ledger_path,
    load_ledger,
    make_entry,
    parse_header,
    render_header,
    save_ledger,
    set_status,
)
from core._asset_ledger._part2 import (
    _iter_md_candidates,
    _walk_repo,
    filter_rows,
    inventory_root,
    iter_assets,
    remove_entry,
    verify_ledger_dir,
    verify_root,
    verify_shelf_shape,
)
