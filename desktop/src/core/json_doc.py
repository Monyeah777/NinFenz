#!/usr/bin/env python3
"""JSON 文档读取（单一实现）：契约 / 真源读取点统一在这里校**顶层类型**。

为什么（2026-10-10 全仓审计 N11）：167 个 json.load/loads 站点里 133 个在 ±6 行内没有
isinstance 检查——顶层是 [1,2,3] / "hello" / 42 / null 时，读点要么裸 AttributeError（无修复
指引），要么被读成空结果（fail-open：把「形状不对」当成「没有内容」）。本模块把
「读文件 → 解析 → 校顶层形状 → 带指引报错」收成**一个实现**，读点只声明期望形状。

边界：本层只保证**顶层形状**；字段级校验仍归 json_schema / 各读点——不在这里膨胀第二套 schema。

用法：
    from core import json_doc
    doc = json_doc.load(path, dict, what="协议件 LAYERS.json")
    rows = json_doc.loads(text, list, what="trace 记录")
"""
import json
import functools
from pathlib import Path
from typing import Any

from core import atomic_write

MAX_JSON_DEPTH = 256
#: 单件 JSON 文本/文件上限（32 MiB）：所有真源读取共用，防止外来大件把解析器内存打爆。
MAX_JSON_BYTES = 32 * 1024 * 1024


_DEPTH_CACHE: dict[bytes, bool] = {}


def _too_deep(text: str) -> bool:
    """迭代式 JSON 括号深度预检（字符串/转义内不计），在递归解析前 fail-closed。

    按**正文摘要**缓存结论：同一份 JSON 在一次扫描里会被多条判据反复 load（实测 3,176 次
    预检 ≈ 3.4 s 纯 Python 逐字符），而摘要（blake2b）比逐字符扫描快一个数量级，命中即返回。
    """
    import hashlib
    digest = hashlib.blake2b(text.encode("utf-8", "replace"), digest_size=16).digest()
    got = _DEPTH_CACHE.get(digest)
    if got is not None:
        return got
    return _too_deep_uncached(text, digest)


def _too_deep_uncached(text: str, digest: bytes) -> bool:
    depth = 0
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                return True
        elif ch in "]}":
            depth = max(0, depth - 1)
    _DEPTH_CACHE[digest] = False
    return False


@functools.lru_cache(maxsize=256)
def _read_text_cached(path: str, mtime_ns: int, size: int) -> str:
    """按 (path, mtime, size) 缓存文件文本（同一批读取不再重复 I/O）。"""
    _ = (mtime_ns, size)          # 键的一部分；正文读取只看 path
    return atomic_write.read_text(Path(path))


def _name(value: Any) -> str:
    """人类可读的类型名（报错文案用；与 Python 内置名一致，便于 grep）。"""
    if value is None:
        return "null"
    return type(value).__name__


def _shape(expect: Any) -> str:
    if isinstance(expect, tuple):
        return " 或 ".join(_name(t()) for t in expect)
    if expect is None:
        return "任意"
    return _name(expect())


def check(doc: Any, expect: Any, what: str) -> Any:
    """顶层形状校验（纯函数，可单测）：不符 → 带修复指引的 ValueError。"""
    if expect is None or isinstance(doc, expect):
        return doc
    raise ValueError(
        "%s 顶层形状不对：期望 %s，实为 %s（修复指引：该件顶层须是对象/数组，"
        "不能是标量或 null；确认没把错误页/空文件当数据件读）"
        % (what, _shape(expect), _name(doc)))


def _reject_constant(token: str) -> Any:
    """RFC 8259 只许有限数：NaN/Infinity/-Infinity 一律拒（single-source，见 asset_contract / knowledge）。"""
    raise ValueError("按 RFC 8259 不接受 %s（修复指引：改用 null 或有限数字）" % token)


def loads(text: str, expect: Any = dict, *, what: str = "JSON 文本",
          strict_constants: bool = False, pairs_hook: Any = None) -> Any:
    """解析文本并校顶层形状；**容忍开头 BOM**（解析入口的 BOM 容错，见审计 N4 口径）。

    strict_constants=True 时按 RFC 8259 拒 NaN / ±Infinity（此前 asset_contract 与 knowledge
    各写一份 parse_constant 钩子——收成这里一份）。
    pairs_hook 透传 `object_pairs_hook`：重复键检测那类**校验器**也收进同一个实现
    （output_forms / text_hygiene 此前各写一份）。
    """
    kwargs: dict = {}
    if strict_constants:
        kwargs["parse_constant"] = _reject_constant
    if pairs_hook is not None:
        kwargs["object_pairs_hook"] = pairs_hook
    body = text.lstrip("\ufeff")
    if len(body) > MAX_JSON_BYTES:
        raise ValueError(f"{what} 超过上限 {MAX_JSON_BYTES} 字符（修复指引：拆分或分页）")
    if _too_deep(body):
        raise ValueError("%s 嵌套过深（上限 %d）（修复指引：拆平结构或改为引用，不把树深当协议）"
                         % (what, MAX_JSON_DEPTH))
    try:
        doc = json.loads(body, **kwargs)
    except ValueError as exc:
        raise ValueError("%s 不是合法 JSON：%s（修复指引：核对该件是否被写坏 / 含注释 / 截断）"
                         % (what, exc)) from exc
    return check(doc, expect, what)


def load(path: Any, expect: Any = dict, *, what: str = "", pairs_hook: Any = None) -> Any:
    """读文件 + 解析 + 校顶层形状；文件不在场 / 坏 JSON / 形状不对都给带指引的 ValueError。"""
    p = Path(path)
    name = what or p.as_posix()
    try:
        st = p.stat()
        if int(st.st_size) > MAX_JSON_BYTES:
            raise ValueError(f"{name} 超过上限 {MAX_JSON_BYTES} 字节"
                             "（修复指引：拆分或分页）")
        text = _read_text_cached(str(p.resolve()), int(st.st_mtime_ns), int(st.st_size))
    except OSError as exc:
        raise ValueError("%s 读取失败：%s（修复指引：确认路径存在且可读）" % (name, exc)) from exc
    return loads(text, expect, what=name, pairs_hook=pairs_hook)
