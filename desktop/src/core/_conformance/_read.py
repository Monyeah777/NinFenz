"""conformance_scan 私有子模块 _read：读取层：共享读 / 原始字节 / 解码 / 内容指纹与逐件摘要。

门面 core.conformance_scan 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import hashlib
import os

from core import atomic_write

from ._resident import _RESIDENT_RAW_MAX_BYTES, _RESIDENT_TEXT_MAX, _resident_key, _resident_under
from ._walk import iter_files
from . import _resident as _rs
from . import _memo as _memo



def read_text_cached(path) -> str:
    """读文本：在 `read_memo()` 作用域内，同一**文件**只读一次（含解码）；域外就是普通读。

    键做**路径归一化**（`normcase(abspath)`）：各扫描器传进来的写法不同（`"."/相对路径`
    vs 绝对路径），不归一会指向不同键、共享失效——实测就是这样（同一份资产仍被读 4 次）。
    """
    key = _resident_key(path)
    if _memo._READ_MEMO is not None:
        hit = _memo._READ_MEMO.get(key)
        if hit is not None:
            return hit
    if _rs._RESIDENT is not None:                   # 常驻层：跨请求复用（按监听路径失效）
        hit = _rs._RESIDENT["text"].get(key)
        if hit is not None:
            if _memo._READ_MEMO is not None:
                _memo._READ_MEMO[key] = hit
            return hit
    # **一次物理读服务三种口径**：字节→文本按「通用换行」解出（与 `Path.read_text("utf-8")` 逐字节
    # 一致，判据 `ResidentRawEquivalenceTest`），摘要直接吃同一份字节（见 `_payload_digest`）。
    raw = _raw_bytes(path, key)
    text = _decode_text(raw)
    if _memo._READ_MEMO is not None:
        _memo._READ_MEMO[key] = text
    if _rs._RESIDENT is not None and _resident_under(key)\
            and len(_rs._RESIDENT["text"]) < _RESIDENT_TEXT_MAX:
        _rs._RESIDENT["text"][key] = text
    return text



def _raw_bytes(path, key: str) -> bytes:
    """取**原始字节**（作用域 + 常驻层优先）：一次物理读之后，文本/字节/摘要三种口径都从这里出。

    读法（实测 2799 件 18.9 MB）：`buffering=0`（裸 FileIO）357 ms 最快，pathlib 408 / 缓冲 532 /
    `os.open` 510 ms。字节进 `_READ_MEMO["b:"+key]` ⇒ 摘要与文本**共用同一次物理读**。
    """
    if _memo._READ_MEMO is not None:
        hit = _memo._READ_MEMO.get("b:" + key)
        if hit is not None:
            return hit
    if _rs._RESIDENT is not None:
        hit = _rs._RESIDENT["raw"].get(key)
        if hit is not None:
            if _memo._READ_MEMO is not None:
                _memo._READ_MEMO["b:" + key] = hit
            return hit
    # 读侧短重试（2026-09-30）：并发原子写（`os.replace`）下 Windows 读者会瞬时拿到
    # PermissionError（WinError 5/32）——实测 119 万次读里 1055 次（≈0.09%）。这里是全仓
    # 语料的**唯一物理读**入口，故重试接在这里即可覆盖 purity / layer_model / 各 check。
    raw = atomic_write.read_bytes(path)
    if _memo._READ_MEMO is not None:
        _memo._READ_MEMO["b:" + key] = raw
    if _rs._RESIDENT is not None and _resident_under(key)\
            and len(_rs._RESIDENT["raw"]) < _RESIDENT_TEXT_MAX:
        used = int(_rs._RESIDENT.get("raw_bytes") or 0)
        if used + len(raw) <= _RESIDENT_RAW_MAX_BYTES:
            _rs._RESIDENT["raw"][key] = raw
            _rs._RESIDENT["raw_bytes"] = used + len(raw)
    return raw



def _decode_text(raw: bytes) -> str:
    """原始字节 → 文本：与 `Path.read_text(encoding="utf-8")` 同语义（含**通用换行**翻译）。

    **这里刻意不用 `utf-8-sig`**（2026-10-10 审计 N4 修正）：本层文本会进**内容摘要**与常驻
    原始层，剥 BOM 会改变带 BOM 件（如 `bom.md`）的摘要值——BOM 边界已由
    `test_conformance_scan` 的 `DigestPayloadEquivalenceTest` / `ResidentRawEquivalenceTest`
    钉住。BOM 容错属于**解析入口**（见 `trace_drill` / `knowledge` / `telemetry_semconv` /
    `registry_loader` 的定向处理），不在这里一刀切。
    """
    import io as _io
    with _io.TextIOWrapper(_io.BytesIO(raw), encoding="utf-8", newline=None) as wrapper:
        return wrapper.read()



def read_bytes_cached(path) -> bytes:
    """读字节：同上（`_recompute_entry` 的逐字节比对用）。作用域与 `raw` 层都归 `_raw_bytes`，
    本函数只多一层「二进制面」常驻条目（`_RESIDENT["bytes"]`）；2026-09-29 去重掉抄一遍的 20 行。"""
    key = _resident_key(path)
    if _rs._RESIDENT is not None:
        hit = _rs._RESIDENT["bytes"].get(key)
        if hit is not None:
            if _memo._READ_MEMO is not None:
                _memo._READ_MEMO["b:" + key] = hit
            return hit
    raw = _raw_bytes(path, key)
    if _rs._RESIDENT is not None and _resident_under(key)\
            and len(_rs._RESIDENT["bytes"]) < _RESIDENT_TEXT_MAX:
        _rs._RESIDENT["bytes"][key] = raw
    return raw



def content_fingerprint(root: str, patterns) -> str:
    """按**内容**给一组文件取指纹（键即内容 ⇒ 内容一变指纹就变，无陈旧风险）。

    用于「派生结果的跨调用缓存」：先在本模块里**穷举输入面**（写成 patterns），再拿指纹当键。
    走共享读（`read_text_cached`），这些文件本来就要被读，指纹近乎白拿。

    枚举走 `iter_files`（`os.scandir` 单遍 + 作用域内记忆）：实测本仓一次 `evaluate` 里
    指纹占 **926 ms / 31%**，而其中「枚举」一项就 463 ms（`community/*/outputs/**/*` 单条
    236 ms 是 pathlib `**` 的逐层重入）——换成单遍后同一条降到 ~90 ms。

    2026-09-29 再进一步：**逐件摘要**（`_payload_digest`）也进两级缓存——作用域内一份、常驻层一份
    （按监听变更**逐件**失效）。于是「面再宽」也只剩「枚举 + 合并」：实测 8 个面（含 3439 件的宽面）
    的见证成本从 **228 ms 降到 ~30 ms**，而**指纹口径逐位不变**（同一件同一 payload ⇒ 同一摘要）。
    """
    rels: List[str] = []
    for pat in patterns:
        rels.extend(iter_files(root, str(pat)))
    return fingerprint_of(root, rels)



def fingerprint_of(root: str, rels) -> str:
    """按**给定的相对路径清单**取内容指纹（口径与 `content_fingerprint` 逐位相同）。

    为什么要这个入口（2026-09-29 实测）：`content_fingerprint` 每调一次就要**枚举一遍面**，而
    `output_forms` 的逐包内容键是按包拼模式调的——470 个包级模式 ⇒ 一次 `nf score` 里
    `iter_files` 被调 **619 次（35.5 ms）**，其中 ~424 次是「同一批面按包切」。能一次枚举、
    按包切片，就只剩四次枚举。
    """
    h = hashlib.sha256()
    for rel in rels:
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(_payload_digest(root, rel))
        h.update(b"\x01")
    return h.hexdigest()



def _payload_digest(root: str, rel: str) -> bytes:
    """单件的**内容摘要**（`sha256` 的 raw digest）；键＝文件，随监听变更逐件失效。

    payload 口径与历史口径**完全一致**：能按 UTF-8 读出的文本按 encode("utf-8")（与重编码后的
    字节等价），读不出（图片等）按**原始字节**。**快路径**：正文无 `\\r` 时「解码再编码」是恒等
    变换（`\\r` 是通用换行翻译的唯一触发器）⇒ 直接摘要原始字节（本仓 2799 件 0 件含 CR，省 ~100 ms）。
    """
    path = os.path.join(str(root), *rel.split("/"))
    key = _resident_key(path)
    if _memo._DIGEST_MEMO is not None:
        hit = _memo._DIGEST_MEMO.get(key)
        if hit is not None:
            return hit
    if _rs._RESIDENT is not None:
        hit = _rs._RESIDENT["digest"].get(key)
        if hit is not None:
            if _memo._DIGEST_MEMO is not None:
                _memo._DIGEST_MEMO[key] = hit
            return hit
    raw = _raw_bytes(path, key)                     # 一次物理读：文本口径也从这份字节解出
    if b"\r" in raw:
        try:
            raw = _decode_text(raw).encode("utf-8")  # 有 CR 才需要通用换行翻译后再编码
        except UnicodeDecodeError:
            pass       # 非 UTF-8（图片等）按**字节**取指纹：多放个二进制附件不该让命令失败
    digest = hashlib.sha256(raw).digest()
    if _memo._DIGEST_MEMO is not None:
        _memo._DIGEST_MEMO[key] = digest
    if _rs._RESIDENT is not None and _resident_under(key):
        _rs._RESIDENT["digest"][key] = digest
    return digest
