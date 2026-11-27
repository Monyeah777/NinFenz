"""吊销分发件 v0（G2 的可落地部分）：签名 + 单调序号 + 前序链 + 合并。

背景（`docs/ccos/threat-model.md` G2）：吊销表此前只能「包内嵌」或「侧载原始 JSON」——拿到一份表，
既证明不了**来源**，也防不住**回滚**（攻击者给你一份更早的吊销表，读起来完全合法）。本模块补三件事：

1. `nf-revocation-feed/1`：吊销表外面套一层信封（issuer / seq / prev_digest / hmac 签名）；
2. 校验：签名不过 = 不可信（**缺密钥不降级**）；序号与前序摘要必须接得上（防回滚/防分叉）；
3. 合并：多份 feed 按序号链验完再取并集，输出仍是 `nf-revocation/1` 表（喂给 `--revocations`）。

**边界**：本模块不做分发（没有服务器/订阅），也不解决「签发方撤销了但你没收到」这件事；它只把手头
这份表变成「来源可证、回滚可察」。仍未签名时只给 warning（形状可判、来源不可判）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
import hashlib
import hmac
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from core import attest, iso8601

# 实现分片：原模块逻辑在私有子包 _revocations/，本门面按原模块面显式再导出（API 不变）。
from core._revocations._part1 import (
    ALG,
    ALG_ED25519,
    FEED_SCHEMA,
    FRESH,
    GUIDE,
    MAX_TTL,
    STAMP_FMT,
    STAMP_RE,
    TABLE_SCHEMA,
    ZERO,
    SignOptions,
    _expiry_of,
    _sha256_hex,
    _shape_issues,
    _valid_ttl,
    body,
    canonical_bytes,
    digest,
    freshness,
    make_table,
    sign,
    table_of,
)
from core._revocations._part2 import merge, verify
