"""驾驶会话事件账本：提交、恢复、哈希链与重复提交防护。"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# 实现分片：原模块逻辑在私有子包 _session_journal/，本门面按原模块面显式再导出（API 不变）。
from core.meta_cockpit._session_journal._part1 import (
    BASE,
    FORBIDDEN_KEYS,
    MAX_JOURNAL_BYTES,
    NF_ROOT,
    RUNTIME_FILES,
    SCHEMA,
    SCHEMA_NAME,
    VALIDATOR,
    TurnOptions,
    _canonical,
    _document_digest,
    _event_digest,
    _file_revision,
    _forbidden_paths,
    _now,
    _source_drift,
    _validate,
    _write,
    contracts_digest,
    current_state,
    digest,
    reconcile_calibration,
    replay,
    runtime_digest,
)
from core.meta_cockpit._session_journal._part2 import append_turn, ensure, load

from . import atomic_io, calibration_ledger, epistemic_agenda, file_lock, json_asset, method_memory
from . import live_selector as ls
from . import schema_compat as jsonschema
from .repo_context import implementation_files, repository_root
