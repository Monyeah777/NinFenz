#!/usr/bin/env python3
"""门禁单进程引擎（骨架）——**只做编排，不改判据**。

定位（与计划 L-A 对应）
-----------------------
现状：`verify.sh` 是 bash 主执行体，靠 **42 次 `$PY3` 启动**、**125 次 `git diff`** 与
40 条各自独立的 heredoc 拼出来；实测全量 1462 s，其中 96% 是 check12 的 unittest。

本模块要证明的那一件事：**门禁的 40 条判据可以在一个进程里跑完**——
省掉的是进程启动税与重复读取，判据本身一个字都不动。

两条硬纪律（不可交易）
----------------------
1. **判据零改动**：本引擎不重新实现任何判定逻辑。凡是已有 `core.*` 实现的 check，
   一律**委托**给同一份实现（`verify.sh` 的 heredoc 也是调它），因此「引擎的结论」
   与「门禁的结论」同源；差异只可能来自编排，不可能来自判据。
2. **可比对**：输出行格式与 `verify.sh` 的 `ok/no/wn` **逐字同形**
   （`  [PASS] …` / `  [FAIL] …` / `  [WARN] …`），故可用同一解析器做逐 check 差分，
   等价性是**测出来的**而不是声称的（见 tests 里的 parity 用例）。

三级状态（与 verify.sh 对齐）
----------------------------
- `delegated`：委托 `core.*`，已是生产实现；
- `native`：本引擎内实现（目前仅用于纯结构性 check，逐一对照 verify.sh 手写）；
- `pending`：尚未迁入（仍在 bash 里），引擎如实报「未迁入」，**不假装绿**。

内容寻址 memo
--------------
键 = sha256(根 + check 名 + 代码面内容 + 声明的读面内容)。命中即跳过重算，
但**只在 `--memo` 打开时**——默认关闭，保证「引擎输出 ≡ 门禁输出」这条差分测试
永远测的是真跑，而不是回放。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 必须在补好 sys.path **之后**才能 import core.*（引擎可被当脚本直接跑）。
from core import gate_inproc, gate_labels, gate_native, repo_trust  # noqa: E402

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade
from core._gate_engine import _part2 as _live_part2

# 实现分片：原模块逻辑在私有子包 _gate_engine/，本门面按原模块面显式再导出（API 不变）。
from core._gate_engine._part1 import (
    _MISSING_VERIFY_SH,
    _SRC,
    CODE_FACE,
    FAIL,
    INPROC_CHECKS,
    PASS,
    PENDING,
    REGISTRY,
    SCRIPT_CHECKS,
    STATS_WHITELIST,
    WARN,
    CheckSpec,
    Verdict,
    _delegate,
    _DelegateSpec,
    _native_runner,
    _read_registry_json,
    _resolve_vars,
    _script,
    _trust_gate,
    check,
    emit,
)
from core._gate_engine._part2 import (
    Memo,
    _digest_file,
    _inproc,
    _register_delegated,
    _register_inproc,
    _verify_sh,
    content_key,
    main,
)
from core.gate_labels import Labels  # noqa: E402

_install_live_facade(__name__, {
    "ROOT": _live_part2,
    "build_registry": _live_part2,
    "run_checks": _live_part2,
})

if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
