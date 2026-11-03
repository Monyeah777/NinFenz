"""确定性 trace 小工具：canonical JSON 字节 + sha256 digest。

session / 上层 journal 都用同一口径：同输入两次 canonical 逐字节一致。这里只做
纯序列化，不读写状态、不联网、不做任何评分。
"""

from __future__ import annotations

import hashlib
import json


def canonical(value) -> bytes:
    """value → 稳定排序、紧凑 separators 的 UTF-8 JSON 字节。"""

    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def digest(value) -> str:
    """canonical(value) 的 sha256 hex（64 位）。"""

    return hashlib.sha256(canonical(value)).hexdigest()
