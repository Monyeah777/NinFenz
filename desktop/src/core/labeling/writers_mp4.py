"""MP4 标识写入（GB 20257A 标准位置 + XMP uuid 兼容载体）。

两个入口
--------
- `inject_mp4_meta(path, json_text)`：**标准位置**——重建 moov，在
  `moov.udta.meta` 下写 `hdlr(handler='mdir')` + `keys`（mdta 键 "AIGC"）
  + `ilst`（data type=1 UTF-8）；同时移除旧顶层 XMP uuid（一份标识），
  并按新布局修正 moov 内 `stco`/`co64` 的 chunk 偏移；
- `inject_mp4_xmp(path, json_text)`：**兼容载体**——在文件末尾追加/替换顶层
  XMP `uuid` 盒（Adobe XMP for MP4 既定做法），可被 `metadata.extract` 的
  `mp4.uuid` 分支读回。两入口不混用：标准位置写入会清掉旧顶层 XMP。

硬约束（写入即判据）
------------------
- **只追加/替换顶层 XMP uuid 盒**；ftyp / moov / mdat 的字节一律不改写、不移动
  （mdat 载荷逐字节不变）。实现方式是「保留每个既有顶层盒的原始字节 + 在末尾
  追加新 uuid 盒」，因此不会重排任何盒；
- 已存在的 XMP 只清理**顶层** uuid（本写入器的产物，位于文件末尾）。历史文件里
  嵌在 `moov/udta` 内的 XMP **不删除**——删它会改写 moov 字节，违反硬约束。
  因此「文件里只有 1 份 XMP」只对本写入器产出的文件成立；
- 顶层盒结构非法（头不完整 / 长度越界 / 顶层 `size=0` 延伸到文件尾导致无法安全
  追加）→ `ValueError`（带偏移说明），不静默猜测、不写坏文件；
- 写入走「同目录临时件 + os.replace」原子替换，失败不留半成品。

调用
----
    from nf_labelcheck.writers_mp4 import inject_mp4_xmp
    inject_mp4_xmp("a.mp4", '{"Label": 1, "ContentProducer": "示例"}')

读回：`metadata.extract("a.mp4")` 的 `mp4.uuid` 条目，或
`metadata.extract_json_candidates("a.mp4")` 直接拿 JSON 对象。

已知限制
--------
- `inject_mp4_meta` 不支持分片 MP4（moof）与 64 位 largesize 盒（ValueError 明确拒绝）；
- `inject_mp4_meta` 只改 `moov.udta.meta`；trak 级 udta 与其它私有盒原样保留，不识别其语义；
- `inject_mp4_meta` 要求 moov 内 stco/co64 结构合法，否则 ValueError（不猜、不重建轨道表）；
- 不删除 moov 内的历史 XMP（见上）；
- 本写入器只产生**末尾** XMP；若输入文件的 XMP 位于中间，删除它会让后续盒
  前移（各盒字节不变，但文件偏移改变）——正常产物不会出现这种布局；
- 不支持顶层 `size=0`（延伸至 EOF）的盒布局；不支持 `mdat` 巨型盒的 64 位
  长度重排（本实现不触达 mdat，故无需支持）；
- 整文件读入内存再拼接（内存占用约为文件的 2 倍）；原型阶段接受，超大文件
  可后续改为流式重写；
- 不做签名/时间戳，只负责把**已生成**的标识 JSON 放进容器。
"""

from __future__ import annotations

import html
import json
import os
import struct
import tempfile

from .metadata import XMP_UUID

#: XMP 包前缀：TC260 命名空间（GB 45438 / TC260-PG-202511A 的隐式标识）。
TC260_NS = "http://www.tc260.org.cn/ns/AIGC/1.0/"
#: XMP 包开始 / 结束标记（Adobe XMP 规范）。
PACKET_BEGIN = '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
PACKET_END = '<?xpacket end="w"?>'
#: 单个 uuid 盒的固定头开销：size(4) + type(4) + UUID(16)。
_UUID_HEADER = 24


def build_xmp_packet(json_text: str) -> str:
    """JSON 文本 → XMP 包（TC260 ns；XML 文本必需的 &、<、> 转义）。

    只转义 XML 文本内容必需的三个字符（引号在文本节点里合法，保留原样）；
    `metadata` 的 `_unescape_xml` 会用 `html.unescape` 还原，故读回逐字相等。
    """
    if not isinstance(json_text, str):
        raise ValueError("json_text 必须是 str（收到 %r）" % type(json_text))
    if not json_text.strip():
        raise ValueError("json_text 为空")
    try:
        json.loads(json_text)
    except ValueError as exc:
        raise ValueError("json_text 不是合法 JSON：%s" % exc)
    escaped = html.escape(json_text, quote=False)
    lines = [
        PACKET_BEGIN,
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">',
        ' <rdf:RDF xmlns:rdf='
        '"http://www.w3.org/1999/02/22-rdf-syntax-ns#">',
        '  <rdf:Description rdf:about="" xmlns:TC260="%s">' % TC260_NS,
        "   <TC260:AIGC>%s</TC260:AIGC>" % escaped,
        "  </rdf:Description>",
        " </rdf:RDF>",
        "</x:xmpmeta>",
        PACKET_END,
    ]
    return "\n".join(lines)


def _uuid_box(packet: bytes) -> bytes:
    """uuid 盒：size(4) + 'uuid'(4) + UUID(16) + XMP 包字节。"""
    payload = XMP_UUID + packet
    return struct.pack(">I", 8 + len(payload)) + b"uuid" + payload


def _read_tlv(data: bytes, off: int):
    """读一个顶层盒头 → (size, type, header_len)。畸形抛 ValueError。"""
    n = len(data)
    if off + 8 > n:
        raise ValueError("MP4 顶层盒头不完整：偏移 %d（文件长 %d）" % (off, n))
    size = int.from_bytes(data[off:off + 4], "big")
    btype = data[off + 4:off + 8]
    hdr = 8
    if size == 1:                       # 64 位长度（largesize）
        if off + 16 > n:
            raise ValueError("MP4 盒 largesize 头不完整：偏移 %d" % off)
        size = int.from_bytes(data[off + 8:off + 16], "big")
        hdr = 16
    elif size == 0:
        raise ValueError(
            "MP4 顶层盒 size=0（延伸到文件尾）：偏移 %d type=%r；"
            "本写入器只追加末尾盒，无法安全处理该布局（修复指引：先用 "
            "ffmpeg -movflags +faststart 等工具规范化为显式 size）"
            % (off, btype))
    if size < hdr:
        raise ValueError("MP4 盒长度非法（size=%d < 头 %d）：偏移 %d"
                         % (size, hdr, off))
    if off + size > n:
        raise ValueError("MP4 盒长度越界：偏移 %d size=%d 超出文件尾 %d"
                         % (off, size, n))
    return size, btype, hdr


def _top_boxes(data: bytes):
    """遍历顶层盒 → [(box_start, box_end, type, body_start)]；畸形抛 ValueError。"""
    out = []
    off = 0
    while off < len(data):
        size, btype, hdr = _read_tlv(data, off)
        out.append((off, off + size, btype, off + hdr))
        off += size
    return out


def _is_xmp_uuid(data: bytes, body_start: int, box_end: int) -> bool:
    return (body_start + 16 <= box_end
            and data[body_start:body_start + 16] == XMP_UUID)


def inject_mp4_xmp(path: str, json_text: str):
    """把标识 JSON 写成顶层 XMP uuid 盒（替换既有顶层 XMP，或在末尾新增）。

    - 既有顶层 XMP uuid 会被移除（其余顶层盒逐字节保留、顺序不变）；
    - 新 uuid 盒追加到文件末尾；
    - ftyp/moov/mdat 的字节与 mdat 载荷不变；
    - 成功返回 None；坏文件/坏 JSON 抛 ValueError（带说明）。
    """
    packet = build_xmp_packet(json_text).encode("utf-8")
    with open(path, "rb") as fh:
        data = fh.read()
    if not data:
        raise ValueError("MP4 文件为空：%s" % path)
    kept = []
    replaced = 0
    for box_start, box_end, btype, body in _top_boxes(data):
        if btype == b"uuid" and _is_xmp_uuid(data, body, box_end):
            replaced += 1
            continue
        kept.append(data[box_start:box_end])
    _write_atomic(path, b"".join(kept) + _uuid_box(packet))



# ---------------------------------------------------------------- 标准位置
#: moov 重建时递归进入的容器盒（用于定位 stco/co64）。
_WALK_CONTAINERS = {
    b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"dinf",
    b"mvex", b"udta", b"meta", b"moof", b"traf",
}
#: GB 20257A 标准位置的键名 / keys 命名空间 / meta 处理器 / data 类型。
META_KEY = b"AIGC"
META_NAMESPACE = b"mdta"
META_HANDLER = b"mdir"
_DATA_TYPE_UTF8 = 1


def _write_atomic(path: str, data: bytes) -> None:
    """同目录临时件 + os.replace 原子替换；保留权限位，失败不留半成品。"""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        mode = os.stat(path).st_mode & 0o7777
    except OSError:
        mode = None
    fd, tmp = tempfile.mkstemp(prefix=".nf-xmp-", suffix=".tmp",
                               dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _box(btype: bytes, payload: bytes) -> bytes:
    """32 位 size 的盒（标准位置写入拒绝 64 位 largesize）。"""
    if len(btype) != 4:
        raise ValueError("盒类型必须是 4 字节：%r" % (btype,))
    size = 8 + len(payload)
    if size > 0xFFFFFFFF:
        raise ValueError("盒过大（%d 字节），本实现只写 32 位 size" % size)
    return struct.pack(">I", size) + btype + payload


def _read_tlv_in(data: bytes, off: int, end: int):
    """在 [off, end) 内读一个盒头 → (size, type, hdr)；畸形 ValueError。"""
    if off + 8 > end:
        raise ValueError("子盒头不完整：偏移 %d（区间尾 %d）" % (off, end))
    size = int.from_bytes(data[off:off + 4], "big")
    btype = data[off + 4:off + 8]
    if size == 0:
        raise ValueError("子盒 size=0 非法：偏移 %d type=%r" % (off, btype))
    if size == 1:
        raise ValueError(
            "子盒用 64 位 largesize：偏移 %d type=%r；本实现只支持 32 位 size"
            "（修复指引：先用工具把 moov 内盒规范化为 32 位）"
            % (off, btype))
    if size < 8 or off + size > end:
        raise ValueError("子盒长度越界：偏移 %d size=%d 区间尾=%d"
                         % (off, size, end))
    return size, btype, 8


def _iter_children(data: bytes, start: int, end: int):
    """迭代 [start, end) 内的子盒 → (type, body_start, box_end)。"""
    off = start
    while off < end:
        size, btype, hdr = _read_tlv_in(data, off, end)
        yield btype, off + hdr, off + size
        off += size


def _children_raw(data: bytes, start: int, end: int):
    """子盒 → [(type, 原始盒字节, body_start, box_end)]（保序）。"""
    out = []
    for btype, body, bend in _iter_children(data, start, end):
        out.append((btype, data[body - 8:bend], body, bend))
    return out


def _parse_top_strict(data: bytes):
    """严格解析顶层盒 → (boxes, moov_box)；拒绝 moof / size=0 / largesize。"""
    if not data:
        raise ValueError("MP4 文件为空")
    boxes = []
    off = 0
    while off < len(data):
        if off + 8 > len(data):
            raise ValueError("MP4 顶层盒头不完整：偏移 %d" % off)
        size = int.from_bytes(data[off:off + 4], "big")
        btype = data[off + 4:off + 8]
        if size == 0:
            raise ValueError(
                "MP4 顶层盒 size=0（延伸到文件尾）：偏移 %d type=%r；"
                "标准位置写入不支持该布局" % (off, btype))
        if size == 1:
            raise ValueError(
                "MP4 顶层盒 64 位 largesize：偏移 %d type=%r；"
                "标准位置写入不支持（修复指引：规范化为 32 位 size）"
                % (off, btype))
        if size < 8 or off + size > len(data):
            raise ValueError("MP4 顶层盒长度越界：偏移 %d size=%d 文件长=%d"
                             % (off, size, len(data)))
        boxes.append({"start": off, "end": off + size,
                      "type": btype, "body": off + 8})
        off += size
    if any(b["type"] == b"moof" for b in boxes):
        raise ValueError(
            "分片 MP4（moof）不支持：标准位置写入要求单文件 moov + mdat "
            "布局（修复指引：先做非分片封装）")
    moovs = [b for b in boxes if b["type"] == b"moov"]
    if not moovs:
        raise ValueError("MP4 缺 moov 盒，无法写标准位置标识")
    if len(moovs) > 1:
        raise ValueError("MP4 有 %d 个 moov 盒，无法确定写入目标"
                         % len(moovs))
    return boxes, moovs[0]


def _json_bytes(json_text: str) -> bytes:
    """校验并编码 JSON 文本（合法性由 json.loads 兜底）。"""
    if not isinstance(json_text, str):
        raise ValueError("json_text 必须是 str（收到 %r）" % type(json_text))
    if not json_text.strip():
        raise ValueError("json_text 为空")
    try:
        json.loads(json_text)
    except ValueError as exc:
        raise ValueError("json_text 不是合法 JSON：%s" % exc)
    return json_text.encode("utf-8")


def _build_hdlr() -> bytes:
    """meta 的 hdlr：version/flags=0，pre_defined=0，handler_type='mdir'。

    Apple 规范字段：version/flags(4) + pre_defined(4) + handler_type(4)
    + reserved(12) + name（空串也要保留 NUL 终止符）。
    """
    payload = (struct.pack(">I", 0) + struct.pack(">I", 0)
               + META_HANDLER + b"\x00" * 12 + b"\x00")
    return _box(b"hdlr", payload)


def _build_data(json_bytes: bytes) -> bytes:
    """ilst 的 data 盒：type=1（UTF-8）+ locale=0 + 值。"""
    return _box(b"data", struct.pack(">I", _DATA_TYPE_UTF8)
                + struct.pack(">I", 0) + json_bytes)


def _build_keys(fvb: bytes, entries: list, tail: bytes = b"") -> bytes:
    """keys 盒：fullbox(version/flags) + entry_count + 条目（size=8+名字长）。"""
    payload = fvb + struct.pack(">I", len(entries))
    payload += b"".join(raw for raw, _ns, _name in entries) + tail
    return _box(b"keys", payload)


def _new_key_entry() -> bytes:
    return (struct.pack(">I", 8 + len(META_KEY)) + META_NAMESPACE
            + META_KEY)


def _parse_keys(data: bytes, body: int, end: int):
    """解析 keys 盒 → (version/flags 4 字节, [(raw, namespace, name)], tail)。"""
    if end - body < 8:
        raise ValueError("meta.keys 太短（<8 字节，缺 fullbox/entry_count）")
    fvb = data[body:body + 4]
    count = int.from_bytes(data[body + 4:body + 8], "big")
    entries = []
    off = body + 8
    for _ in range(count):
        if off + 8 > end:
            raise ValueError("meta.keys 条目越界：偏移 %d" % off)
        size = int.from_bytes(data[off:off + 4], "big")
        if size < 9 or off + size > end:
            raise ValueError("meta.keys 条目长度非法：偏移 %d size=%d"
                             % (off, size))
        namespace = data[off + 4:off + 8]
        name = data[off + 8:off + size]
        entries.append((data[off:off + size], namespace, name))
        off += size
    return fvb, entries, data[off:end]


def _rebuild_keys(data: bytes, body: int, end: int):
    """复用/追加 "AIGC" 键 → (keys 盒字节, 该键 1 基索引)。"""
    fvb, entries, tail = _parse_keys(data, body, end)
    for idx, (_raw, namespace, name) in enumerate(entries, 1):
        if namespace == META_NAMESPACE and name == META_KEY:
            return _build_keys(fvb, entries, tail), idx
    entries.append((_new_key_entry(), META_NAMESPACE, META_KEY))
    return _build_keys(fvb, entries, tail), len(entries)


def _rebuild_ilst_item(data: bytes, body: int, end: int,
                       item_type: bytes, json_bytes: bytes) -> bytes:
    """重建单个 ilst 条目：data 子盒换成新值（多余 data 丢弃）。"""
    parts = []
    placed = False
    for btype, raw, _cbody, _cend in _children_raw(data, body, end):
        if btype == b"data":
            if not placed:
                parts.append(_build_data(json_bytes))
                placed = True
        else:
            parts.append(raw)
    if not placed:
        parts.append(_build_data(json_bytes))
    return _box(item_type, b"".join(parts))


def _rebuild_ilst(data: bytes, body: int, end: int, index: int,
                  json_bytes: bytes) -> bytes:
    """重建 ilst：目标条目第 index 个（1 基）换成新 data，其余原样保留。"""
    target = struct.pack(">I", index)
    parts = []
    found = False
    for btype, raw, cbody, cend in _children_raw(data, body, end):
        if btype == target:
            parts.append(_rebuild_ilst_item(data, cbody, cend,
                                            target, json_bytes))
            found = True
        else:
            parts.append(raw)
    if not found:
        parts.append(_box(target, _build_data(json_bytes)))
    return _box(b"ilst", b"".join(parts))


def _build_meta_new(json_bytes: bytes) -> bytes:
    """从零构建 meta：version/flags=0 + hdlr + keys(AIGC@1) + ilst。"""
    keys = _build_keys(struct.pack(">I", 0),
                       [(_new_key_entry(), META_NAMESPACE, META_KEY)])
    ilst = _box(b"ilst", _box(struct.pack(">I", 1),
                              _build_data(json_bytes)))
    return _box(b"meta", struct.pack(">I", 0) + _build_hdlr()
                + keys + ilst)


def _rebuild_meta(data: bytes, box, json_bytes: bytes) -> bytes:
    """重建 meta（fullbox）：保 hdlr/未知盒，确保 keys/ilst 且写 AIGC。"""
    if box is None:
        return _build_meta_new(json_bytes)
    _btype, _raw, body, end = box
    if end - body < 4:
        raise ValueError("meta 是 fullbox，至少 4 字节版本/标志")
    fvb = data[body:body + 4]
    parts = []
    hdlr_ok = keys_found = ilst_found = False
    keys_box = ilst_box = None
    for ctype, craw, cbody, cend in _children_raw(data, body + 4, end):
        if ctype == b"hdlr":
            hdlr_ok = True
            parts.append(("hdlr", craw))
        elif ctype == b"keys":
            if keys_found:
                raise ValueError("meta 下有多个 keys 盒，无法确定目标")
            keys_found = True
            keys_box = (cbody, cend)
            parts.append(("keys", None))
        elif ctype == b"ilst":
            if ilst_found:
                raise ValueError("meta 下有多个 ilst 盒，无法确定目标")
            ilst_found = True
            ilst_box = (cbody, cend)
            parts.append(("ilst", None))
        else:
            parts.append(("other", craw))
    if keys_box is None:
        keys_bytes = _build_keys(
            struct.pack(">I", 0),
            [(_new_key_entry(), META_NAMESPACE, META_KEY)])
        index = 1
    else:
        keys_bytes, index = _rebuild_keys(data, *keys_box)
    if ilst_box is None:
        ilst_bytes = _box(b"ilst", _box(struct.pack(">I", index),
                                        _build_data(json_bytes)))
    else:
        ilst_bytes = _rebuild_ilst(data, *ilst_box, index, json_bytes)
    if not hdlr_ok:
        parts.insert(0, ("hdlr", _build_hdlr()))
    out = []
    for kind, payload in parts:
        if kind == "keys":
            out.append(keys_bytes)
        elif kind == "ilst":
            out.append(ilst_bytes)
        else:
            out.append(payload)
    if not keys_found:
        pos = len(out)
        for i, (kind, _payload) in enumerate(parts):
            if kind == "ilst":
                pos = i
                break
        out.insert(pos, keys_bytes)
    if not ilst_found:
        out.append(ilst_bytes)
    return _box(b"meta", fvb + b"".join(out))


def _rebuild_udta(data: bytes, box, json_bytes: bytes) -> bytes:
    """重建 udta：保留其它子盒与顺序，确保唯一 meta。"""
    if box is None:
        return _box(b"udta", _build_meta_new(json_bytes))
    _btype, _raw, body, end = box
    parts = []
    meta_idx = None
    meta_box = None
    for ctype, craw, cbody, cend in _children_raw(data, body, end):
        if ctype == b"meta":
            if meta_idx is not None:
                raise ValueError("udta 下有多个 meta 盒，无法确定目标")
            meta_idx = len(parts)
            meta_box = (ctype, craw, cbody, cend)
            parts.append(None)
        elif ctype == b"uuid" and craw[8:8 + 16] == XMP_UUID:
            # 兼容载体（旧 XMP uuid）一并清掉：保证「一份标识」
            continue
        else:
            parts.append(craw)
    if meta_box is None:
        parts.append(_build_meta_new(json_bytes))
    else:
        parts[meta_idx] = _rebuild_meta(data, meta_box, json_bytes)
    return _box(b"udta", b"".join(parts))


def _rebuild_moov(data: bytes, box, json_bytes: bytes) -> bytes:
    """重建 moov：保留全部子盒与顺序，确保唯一 udta/meta。"""
    _btype, _raw, body, end = box
    parts = []
    udta_idx = None
    udta_box = None
    for ctype, craw, cbody, cend in _children_raw(data, body, end):
        if ctype == b"udta":
            if udta_idx is not None:
                raise ValueError("moov 下有多个 udta 盒，无法确定标准位置")
            udta_idx = len(parts)
            udta_box = (ctype, craw, cbody, cend)
            parts.append(None)
        else:
            parts.append(craw)
    if udta_box is None:
        parts.append(_rebuild_udta(data, None, json_bytes))
    else:
        parts[udta_idx] = _rebuild_udta(data, udta_box, json_bytes)
    return _box(b"moov", b"".join(parts))


def _collect_chunk_boxes(data: bytes, start: int, end: int, out: list):
    """递归收集 moov 内 stco/co64 → [(type, body_start, box_end)]。"""
    for btype, body, bend in _iter_children(data, start, end):
        if btype in (b"stco", b"co64"):
            out.append((btype, body, bend))
        elif btype == b"meta":
            _collect_chunk_boxes(data, body + 4, bend, out)
        elif btype in _WALK_CONTAINERS:
            _collect_chunk_boxes(data, body, bend, out)


def _shift_offset(value: int, deltas: list) -> int:
    """旧 chunk 偏移 → 新偏移：落在任一 mdat 区间才加该 mdat 的 delta。"""
    for old_start, old_end, delta in deltas:
        if old_start <= value < old_end:
            return value + delta
    return value


def _chunk_entries(data: bytes, btype: bytes, body: int,
                   bend: int) -> tuple:
    """解析 stco/co64 的 (条目数, 条目起始偏移)。

    兼容两种布局：ISO 标准（version/flags + entry_count + entries）与
    无 version/flags 的简化布局（entry_count + entries；部分夹具/原型
    工具会这么写）。按盒长精确匹配判定，不靠猜测。
    """
    width = 4 if btype == b"stco" else 8
    name = btype.decode("ascii")
    size = bend - body
    if size < 8:
        raise ValueError("%s 盒太短（<8 字节）" % name)
    std_count = int.from_bytes(data[body + 4:body + 8], "big")
    if size == 8 + std_count * width:
        return std_count, body + 8
    simple_count = int.from_bytes(data[body:body + 4], "big")
    if size == 4 + simple_count * width:
        return simple_count, body + 4
    raise ValueError("%s 条目数与盒长不一致：%d 字节（标准布局 %d 条 / "
                     "简化布局 %d 条均不匹配）"
                     % (name, size, std_count, simple_count))


def _patch_chunk_offsets(moov: bytes, old_mdats: list,
                         new_mdats: list) -> bytes:
    """对 moov 内所有 stco/co64 条目做 mdat 区间内偏移修正。

    delta = new_mdat_start - old_mdat_start（按 mdat 出现顺序一一配对）。
    不在任何 mdat 区间内的条目保持不动；stco 溢出 32 位即 ValueError。
    """
    deltas = [(old[0], old[1], new[0] - old[0])
              for old, new in zip(old_mdats, new_mdats)]
    buf = bytearray(moov)
    targets = []
    _collect_chunk_boxes(moov, 0, len(moov), targets)
    for btype, body, bend in targets:
        width = 4 if btype == b"stco" else 8
        count, entry_off = _chunk_entries(moov, btype, body, bend)
        off = entry_off
        for _ in range(count):
            old = int.from_bytes(moov[off:off + width], "big")
            new = _shift_offset(old, deltas)
            if new < 0 or (width == 4 and new > 0xFFFFFFFF):
                raise ValueError("chunk 偏移修正越界：%d → %d" % (old, new))
            if new != old:
                buf[off:off + width] = new.to_bytes(width, "big")
            off += width
    return bytes(buf)


def inject_mp4_meta(path: str, json_text: str) -> None:
    """把标识 JSON 写进 GB 20257A 标准位置：moov.udta.meta 的 keys/ilst。

    流程（顺序即正确性）：
    1. 严格解析顶层盒；拒绝 moof（分片）/ size=0 / 64 位 largesize；
    2. 重建 moov：保留未知盒原字节与顺序；确保 udta → meta(fullbox) →
       hdlr(handler='mdir') + keys(mdta "AIGC") + ilst(data type=1 UTF-8)；
    3. 移除旧 XMP uuid（顶层 + udta 内的兼容载体）——保证「一份标识」；
    4. 按**新布局**重算每个 mdat 的 new_start，对 moov 内所有 stco/co64 条目
       做 delta = new_start - old_start（仅落在旧 mdat 区间内的条目；
       stco/co64 兼容 ISO 标准布局与无 version/flags 的简化布局）；
    5. 同目录临时件 + os.replace 原子写盘（保留权限位）。

    幂等：同一 json_text 再次写入 → moov 长度不变、stco delta=0，输出逐字节
    相同；换 json_text → 原位替换 data，不新增 keys/ilst 条目。
    """
    json_bytes = _json_bytes(json_text)
    with open(path, "rb") as fh:
        data = fh.read()
    boxes, moov = _parse_top_strict(data)
    old_moov = (b"moov", data[moov["start"]:moov["end"]],
                moov["body"], moov["end"])
    new_moov = _rebuild_moov(data, old_moov, json_bytes)
    layout = []
    for b in boxes:
        if b is moov:
            layout.append((b"moov", new_moov))
        elif b["type"] == b"uuid" and _is_xmp_uuid(data, b["body"], b["end"]):
            continue
        else:
            layout.append((b["type"], data[b["start"]:b["end"]]))
    old_mdats = [(b["start"], b["end"]) for b in boxes
                 if b["type"] == b"mdat"]
    new_mdats = []
    pos = 0
    for btype, payload in layout:
        if btype == b"mdat":
            new_mdats.append((pos, pos + len(payload)))
        pos += len(payload)
    if len(old_mdats) != len(new_mdats):
        raise ValueError("内部布局错误：mdat 数量不一致")
    patched = _patch_chunk_offsets(new_moov, old_mdats, new_mdats)
    out = b"".join(patched if btype == b"moov" else payload
                   for btype, payload in layout)
    _parse_top_strict(out)          # 写盘前自检：顶层结构必须完整
    _write_atomic(path, out)

__all__ = [
    "XMP_UUID",
    "TC260_NS",
    "PACKET_BEGIN",
    "PACKET_END",
    "META_KEY",
    "META_NAMESPACE",
    "build_xmp_packet",
    "inject_mp4_xmp",
    "inject_mp4_meta",
]
