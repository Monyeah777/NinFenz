# -*- coding: utf-8 -*-
"""内容寻址缓存（W-08）：键即内容，命中前必须 verify，缺失即失效。

纪律（§7.2 + Tup 正确性规则）：
  - 键 = 专家标识 + 读面内容哈希 + 自身代码哈希 + 根路径（防跨根串味）；
  - 命中前 verify：任一输入**缺席**（Tup：缺失即失效）或**内容已变** → 一律当未命中；
  - 只缓存可序列化值；持久层复用 core/disk_cache，进程内另有一层。
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Tuple

from core import disk_cache as dc

#: 本机制自身所在代码面：改这些文件即换键（内容寻址，不靠时间戳）。
CODE_FILES = ("desktop/src/core/gate_faces.py", "desktop/src/core/gate_graph.py",
              "desktop/src/core/gate_router.py")


def file_digest(path: Any) -> str:
    """文件内容 sha256；缺席/不可读 → 空串（调用方据此判失效）。"""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


def face_digest(root: str, rels: Iterable[str]) -> Dict[str, str]:
    """读面/代码面 → {相对路径: 内容哈希}。"""
    return {str(r): file_digest(Path(root) / str(r)) for r in rels}


def key_for(root: str, expert_id: str, reads: Iterable[str],
            code_files: Iterable[str] = CODE_FILES) -> str:
    """内容键：根 + 标识 + 读面 + 代码面（顺序稳定，缺失记空）。"""
    h = hashlib.sha256()
    h.update(str(Path(root).resolve()).encode("utf-8"))
    h.update(b"\0")
    h.update(str(expert_id).encode("utf-8"))
    for rel in list(reads) + list(code_files):
        h.update(b"\0")
        h.update(str(rel).encode("utf-8"))
        h.update(b"\0")
        h.update(file_digest(Path(root) / str(rel)).encode("ascii"))
    return h.hexdigest()


def verify(root: str, entry: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """命中前校验 → (是否有效, 理由)。缺件与内容变更都必须判无效。"""
    reasons: List[str] = []
    for kind in ("reads", "code"):
        for rel, want in sorted((entry.get(kind) or {}).items()):
            got = file_digest(Path(root) / rel)
            if not got:
                reasons.append("输入缺席：%s（Tup 规则：缺失即失效）" % rel)
            elif got != want:
                reasons.append("输入已变：%s（内容寻址：须重算）" % rel)
    return (not reasons), reasons


_MEMO: Dict[str, Tuple[Any, Dict[str, Any]]] = {}


def _shape(value: Any) -> bool:
    return (isinstance(value, dict) and set(value) == {"value", "entry"}
            and isinstance(value["entry"], dict))


def clear() -> None:
    """清进程内层（测试与守护换版时用）。"""
    _MEMO.clear()


def memo(tag: str, ckey: str, impl: Callable[[], Any], root: str = ".",
         reads: Iterable[str] = (), code_files: Iterable[str] = CODE_FILES
         ) -> Tuple[Any, bool]:
    """命中即返回 (值, True)；未命中/失效则算并落盘 → (值, False)。"""
    entry = {"reads": face_digest(root, reads), "code": face_digest(root, code_files)}
    hit = _MEMO.get(ckey)
    if hit is not None:
        ok, _why = verify(root, hit[1])
        if ok:
            return hit[0], True
        _MEMO.pop(ckey, None)
    packed = dc.load(tag, ckey, validate=_shape)
    if isinstance(packed, dict):
        ok, _why = verify(root, packed["entry"])
        if ok:
            _MEMO[ckey] = (packed["value"], packed["entry"])
            return packed["value"], True
    value = impl()
    _MEMO[ckey] = (value, entry)
    dc.store(tag, ckey, {"value": value, "entry": entry})
    return value, False
