"""规范 JSON 与域分隔摘要（信任层单点；nf-canonical 口径）。

冻结依据：ADR-006 与向量集 canonical/domain 族（results/trust/trust_vectors.json）。

规则（与向量集 rules 段逐字对应）：
- canonical：键排序、UTF-8 原样、紧凑分隔（`,` / `:`）、禁 NaN/Infinity；
- **只收 int/bool/null/str/list/object**：float 拒绝——JSON 浮点格式跨语言/平台不稳定，
  会破坏 NFR-DET-01「同输入逐字节一致」。需要小数的场景请用字符串或整数定点自行表达；
- 域分隔：tag 形如 `nf:<schema>:v1:<field>`，摘要 = `sha256(tag_bytes + 0x00 + payload)`；
  0x00 是长度/域歧义的分隔字节，防止「tag 走私」类拼接；
- 叶/节点散列前缀（0x00/0x01）归 Merkle 层，不在本模块重复实现。

与既有实现的边界：本模块是信任层单点，但**不得改变**既有签名口径——`attest.canonical` /
`evidence.canonical` 与同组输入的输出必须逐字节一致（判据见 test_trust_canonical）。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

GUIDE = "修复指引："

#: 规范域标签：schema 段与 field 段都是小写短横线词；版本段从 v1 起。
TAG_RE = re.compile(r"^nf:[a-z0-9-]+:v[1-9][0-9]*:[a-z0-9-]+$")
#: 摘要格式：64 位小写十六进制（与向量集 digest pattern 同源）。
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
#: 域分隔字节：tag 与 payload 之间必须有一个，避免拼接歧义。
DOMAIN_SEP = b"\x00"


def _walk_reject(node: Any, path: str) -> None:
    """递归拒绝 float/非字符串键/不可规范化的容器。"""
    if isinstance(node, float):
        code = ("NONFINITE-FORBIDDEN" if math.isnan(node) or math.isinf(node)
                else "FLOAT-FORBIDDEN")
        raise ValueError(
            f"{path}: {code}（{GUIDE}改用 int/字符串；浮点序列化跨语言不稳定）")
    if isinstance(node, dict):
        for key, sub in node.items():
            if not isinstance(key, str):
                raise ValueError(
                    f"{path}: 对象键必须是字符串（{GUIDE}JSON 对象键只收字符串）")
            _walk_reject(sub, f"{path}.{key}")
    elif isinstance(node, (list, tuple)):
        if isinstance(node, tuple):
            raise ValueError(
                f"{path}: 拒绝 tuple（{GUIDE}先转成 list，JSON 只有数组）")
        for index, sub in enumerate(node):
            _walk_reject(sub, f"{path}[{index}]")
    elif isinstance(node, (bool, int, str)) or node is None:
        return
    elif isinstance(node, (bytes, bytearray)):
        raise ValueError(
            f"{path}: 拒绝 bytes（{GUIDE}先 base64 编码成字符串再进 canonical）")
    elif isinstance(node, (set, frozenset)):
        raise ValueError(
            f"{path}: 拒绝 set（{GUIDE}先排序成 list 再进 canonical）")
    else:
        raise ValueError(
            f"{path}: 不支持的类型 {type(node).__name__}（{GUIDE}只收 "
            "int/bool/null/str/list/object）")


def canonical_text(obj: Any) -> str:
    """规范 JSON 文本（键排序 + UTF-8 原样 + 紧凑分隔；顶层标量也允许）。"""
    _walk_reject(obj, "$")
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def canonical_bytes(obj: Any) -> bytes:
    """规范 JSON 字节（UTF-8）；签名/摘要一律吃这个，不吃 dict 的 repr。"""
    return canonical_text(obj).encode("utf-8")


def digest_of(obj: Any) -> str:
    """对象摘要：sha256(canonical_bytes(obj))。"""
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def is_tag(tag: Any) -> bool:
    """域标签是否合法（未知/畸形标签一律 False，由调用方 fail-closed）。"""
    return isinstance(tag, str) and bool(TAG_RE.match(tag))


def is_digest(value: Any) -> bool:
    """摘要是否是 64 位小写 hex。"""
    return isinstance(value, str) and bool(DIGEST_RE.match(value))


def domain_digest(tag: str, payload: bytes) -> str:
    """域分隔摘要：sha256(tag + 0x00 + payload)。tag 非法即拒绝（不猜、不降级）。"""
    if not is_tag(tag):
        raise ValueError(f"域标签非法：{tag!r}（{GUIDE}形如 nf:<schema>:v1:<field>）")
    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError(f"payload 必须是 bytes（{GUIDE}先用 canonical_bytes 编码）")
    return hashlib.sha256(tag.encode("utf-8") + DOMAIN_SEP + bytes(payload)).hexdigest()
