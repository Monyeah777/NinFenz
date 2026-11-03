"""HEIF / ISO BMFF 标识写入（元数据 item 载体）。

作者：impl（DSH agent）· 2026-11-02
依据：`/tmp/oggheif-spec.md` B 节。

写入结构（ISO/IEC 23008-12 HEIF + ISO/IEC 14496-12）：
- 在 `meta` 的 `iinf` 里追加/替换 `infe`（version=2，item_ID=新 id，
  item_protection_index=0，item_type='mime'，item_name="AIGC"，
  content_type="application/json"）；
- 在 `meta` 的 `iloc` 里追加/替换该 item：construction_method=0（文件偏移），
  extent_offset = 文件尾新增 `mdat` 里 JSON 数据的绝对偏移，extent_length=len(json)；
  offset_size/length_size/base_offset_size 沿用原 iloc 设置；
- 文件尾追加**新 `mdat`** 承载 JSON，原 `mdat` 与主图 item 数据字节不变。

关键：`meta` 在 `mdat` 之前 ⇒ 追加 iinf/iloc 会让 meta 变长 delta，后面的原 `mdat`
整体前移 delta；因此**所有既有 iloc 条目里 construction_method=0 且数据位于 meta
之后的 extent_offset 必须 +delta**（读取/内容口径按 pitm→item→iloc 取主图 extent）。
idat（construction_method=1）的相对偏移不受影响。

限制：只支持单 `meta`；不处理 `iref`/`ipma`；offset_size 放不下新偏移时报 ValueError。
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

#: AIGC 元数据 item 的命名（读取面按 item_name 找）。
ITEM_NAME = "AIGC"
#: infe 的 item_type（MIME item）。
ITEM_TYPE = b"mime"
#: infe 的 content_type。
CONTENT_TYPE = b"application/json"


# ---------------------------------------------------------------- 基础
def _read(path) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise ValueError("无法读取文件：%s（%s）" % (path, exc))


def _check_json_text(json_text) -> bytes:
    if not isinstance(json_text, str) or not json_text.strip():
        raise ValueError("json_text 不得为空（修复指引：传标识 JSON 文本）")
    try:
        json.loads(json_text)
    except ValueError as exc:
        raise ValueError("json_text 不是合法 JSON：%s" % exc)
    return json_text.encode("utf-8")


def _atomic_write(path, data: bytes) -> None:
    p = Path(path)
    try:
        mode = stat.S_IMODE(p.stat().st_mode)
    except OSError as exc:
        raise ValueError("无法读取目标文件状态：%s（%s）" % (path, exc))
    fd, tmp = tempfile.mkstemp(prefix="." + p.name + ".", suffix=".tmp",
                               dir=str(p.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, p)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise ValueError("写入失败：%s（%s）" % (path, exc))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------- BMFF 盒
def _boxes(data: bytes, start: int = 0, end: int | None = None):
    """迭代盒 (type, box_start, body_start, box_end)；支持 size==0/1。"""
    pos = start
    end = len(data) if end is None else end
    while pos + 8 <= end:
        size = int.from_bytes(data[pos:pos + 4], "big")
        btype = data[pos + 4:pos + 8]
        hdr = 8
        if size == 1:
            if pos + 16 > end:
                raise ValueError("BMFF 盒 largesize 截断（偏移 %d）" % pos)
            size = int.from_bytes(data[pos + 8:pos + 16], "big")
            hdr = 16
        elif size == 0:
            size = end - pos
        if size < hdr or pos + size > end:
            raise ValueError("BMFF 盒长度越界（%r @ %d）" % (btype, pos))
        yield btype, pos, pos + hdr, pos + size
        pos += size


def _u16(data, off):
    return int.from_bytes(data[off:off + 2], "big")


def _u32(data, off):
    return int.from_bytes(data[off:off + 4], "big")


def _pack(value: int, size: int, what: str) -> bytes:
    if size <= 0:
        return b""
    if value < 0 or value >= (1 << (8 * size)):
        raise ValueError("%s 超出 iloc 原 size 设置（值 %d / %d 字节；"
                         "修复指引：原文件 iloc 的 size 太小）"
                         % (what, value, size))
    return value.to_bytes(size, "big")


def _cstr(data, pos, end):
    """读 NUL 结尾 UTF-8 字符串 → (text, next_pos)。"""
    stop = data.find(b"\x00", pos, end)
    if stop < 0:
        raise ValueError("HEIF 字符串缺少 NUL 终止符（偏移 %d）" % pos)
    return data[pos:stop].decode("utf-8", "replace"), stop + 1


# ---------------------------------------------------------------- iinf
def _parse_iinf(data, body, end):
    """解析 iinf → (version, flags, [infe dict])。"""
    version = data[body]
    flags = data[body + 1:body + 4]
    p = body + 4
    if version == 0:
        p += 2
    else:
        p += 4
    infes = []
    for btype, bstart, bbody, bend in _boxes(data, p, end):
        if btype != b"infe":
            continue
        ver = data[bbody]
        item_id = _u16(data, bbody + 4)
        if ver >= 2:
            item_type = data[bbody + 8:bbody + 12]
            pos = bbody + 12
            name = ctype = None
            if item_type == ITEM_TYPE:
                name, pos = _cstr(data, pos, bend)
                ctype, pos = _cstr(data, pos, bend)
            infes.append({"id": item_id, "version": ver, "type": item_type,
                          "name": name, "content_type": ctype,
                          "raw": data[bstart:bend]})
        else:
            name, _pos = _cstr(data, bbody + 8, bend)
            infes.append({"id": item_id, "version": ver, "type": None,
                          "name": name, "content_type": None,
                          "raw": data[bstart:bend]})
    return version, flags, infes


def _infe_v2(item_id: int, name: str, content_type: bytes) -> bytes:
    body = (bytes([2, 0, 0, 0])
            + item_id.to_bytes(2, "big") + b"\x00\x00" + ITEM_TYPE
            + name.encode("utf-8") + b"\x00" + content_type + b"\x00")
    return (len(body) + 8).to_bytes(4, "big") + b"infe" + body


def _build_iinf(version, flags, infes, aigc_id, new_infe) -> bytes:
    """重建 iinf：AIGC infe 就地替换（保持顺序）；没有则追加。"""
    out = bytearray()
    has = False
    for infe in infes:
        if infe["id"] == aigc_id and (infe["name"] or "").upper() == ITEM_NAME:
            out += new_infe
            has = True
        else:
            out += infe["raw"]
    if not has:
        out += new_infe
    body = bytearray(bytes([version]) + flags)
    count = len(infes) + (0 if has else 1)
    body += count.to_bytes(2 if version == 0 else 4, "big") + bytes(out)
    return (len(body) + 8).to_bytes(4, "big") + b"iinf" + bytes(body)


# ---------------------------------------------------------------- iloc
def _parse_iloc(data, body, end):
    """解析 iloc → dict(version, flags, sizes, items)。"""
    version = data[body]
    flags = data[body + 1:body + 4]
    p = body + 4
    b1 = data[p]
    off_size, len_size = b1 >> 4, b1 & 0x0F
    b2 = data[p + 1]
    base_size = b2 >> 4
    idx_size = (b2 & 0x0F) if version in (1, 2) else 0
    p += 2
    id_size = 2 if version < 2 else 4
    if version < 2:
        count = _u16(data, p)
        p += 2
    else:
        count = _u32(data, p)
        p += 4
    items = []
    for _ in range(count):
        item_id = int.from_bytes(data[p:p + id_size], "big")
        p += id_size
        cm = 0
        if version in (1, 2):
            cm = _u16(data, p) & 0x0F
            p += 2
        data_ref = _u16(data, p)
        p += 2
        base = int.from_bytes(data[p:p + base_size], "big") if base_size else 0
        p += base_size
        ext_count = _u16(data, p)
        p += 2
        exts = []
        for _ in range(ext_count):
            idx = (int.from_bytes(data[p:p + idx_size], "big")
                   if idx_size else 0)
            p += idx_size
            off = int.from_bytes(data[p:p + off_size], "big") if off_size else 0
            p += off_size
            ln = int.from_bytes(data[p:p + len_size], "big") if len_size else 0
            p += len_size
            exts.append({"index": idx, "offset": off, "length": ln})
        items.append({"id": item_id, "cm": cm, "data_ref": data_ref,
                      "base": base, "extents": exts})
    if p > end:
        raise ValueError("iloc 解析越界")
    return {"version": version, "flags": flags, "off_size": off_size,
            "len_size": len_size, "base_size": base_size,
            "idx_size": idx_size, "items": items}


def _encode_item(item, info) -> bytes:
    version = info["version"]
    id_size = 2 if version < 2 else 4
    out = bytearray(item["id"].to_bytes(id_size, "big"))
    if version in (1, 2):
        out += _pack(item.get("cm", 0), 2, "construction_method")
    out += _pack(item.get("data_ref", 0), 2, "data_reference_index")
    out += _pack(item.get("base", 0), info["base_size"], "base_offset")
    exts = item["extents"]
    out += _pack(len(exts), 2, "extent_count")
    for ext in exts:
        if info["idx_size"]:
            out += _pack(ext.get("index", 0), info["idx_size"],
                         "extent_index")
        out += _pack(ext.get("offset", 0), info["off_size"],
                     "extent_offset")
        out += _pack(ext.get("length", 0), info["len_size"],
                     "extent_length")
    return bytes(out)


def _build_iloc(info, items, aigc: dict | None) -> bytes:
    """重建 iloc（保留 version/sizes）；AIGC item 替换/追加，其余原值。"""
    version = info["version"]
    out = bytearray()
    has = False
    for item in items:
        if aigc is not None and item["id"] == aigc["id"]:
            out += _encode_item(aigc, info)
            has = True
        else:
            out += _encode_item(item, info)
    if aigc is not None and not has:
        out += _encode_item(aigc, info)
    body = bytearray(bytes([version]) + info["flags"])
    body += bytes([(info["off_size"] << 4) | info["len_size"]])
    idx_bits = info["idx_size"] if version in (1, 2) else 0
    body += bytes([(info["base_size"] << 4) | idx_bits])
    count = len(items) + (0 if has or aigc is None else 1)
    body += count.to_bytes(2 if version < 2 else 4, "big") + bytes(out)
    return (len(body) + 8).to_bytes(4, "big") + b"iloc" + bytes(body)


# ---------------------------------------------------------------- 主流程
def inject_heif(path, json_text) -> None:
    """把 json_text 写成 HEIF 的 MIME 元数据 item（infe/iloc + 新 mdat）。"""
    jb = _check_json_text(json_text)
    data = _read(path)
    tops = list(_boxes(data, 0, len(data)))
    names = [b[0] for b in tops]
    for need in (b"ftyp", b"meta", b"mdat"):
        if need not in names:
            raise ValueError("不是完整 HEIF（缺 %s）" % need.decode("ascii"))
    if names.count(b"meta") != 1:
        raise ValueError("HEIF 顶层 meta 数量不为 1（不支持）")
    meta = next(b for b in tops if b[0] == b"meta")
    mstart, mbody, mend = meta[1], meta[2], meta[3]

    # 拆 meta 子盒（meta 是 fullbox：body 前 4 字节 version/flags）
    children = list(_boxes(data, mbody + 4, mend))
    iinf_box = next((x for x in children if x[0] == b"iinf"), None)
    iloc_box = next((x for x in children if x[0] == b"iloc"), None)
    if iinf_box is None or iloc_box is None:
        raise ValueError("HEIF meta 缺 iinf 或 iloc")
    iinf_ver, iinf_flags, infes = _parse_iinf(
        data, iinf_box[2], iinf_box[3])
    iloc_info = _parse_iloc(data, iloc_box[2], iloc_box[3])
    prefix = data[mbody:mbody + 4]              # meta 的 version/flags

    # 已有 AIGC：幂等检测（extent 数据 == json 则 no-op）
    aigc_infe = next((ie for ie in infes
                      if (ie["name"] or "").upper() == ITEM_NAME), None)
    aigc_item = None
    if aigc_infe is not None:
        aigc_item = next((it for it in iloc_info["items"]
                          if it["id"] == aigc_infe["id"]), None)
    if aigc_item is not None and len(aigc_item["extents"]) == 1:
        ext = aigc_item["extents"][0]
        start = aigc_item["base"] + ext["offset"]
        if data[start:start + ext["length"]] == jb:
            return

    max_id = max([ie["id"] for ie in infes]
                 + [it["id"] for it in iloc_info["items"]] + [0])
    item_id = aigc_infe["id"] if aigc_infe is not None else max_id + 1
    new_infe = _infe_v2(item_id, ITEM_NAME, CONTENT_TYPE)

    # delta 只取决于盒长度变化（iloc sizes 沿用、与 offset 数值无关）；
    # 用占位 AIGC item 预演 iloc 最终长度（新增/替换都算进去）
    placeholder = {"id": item_id, "cm": 0, "data_ref": 0, "base": 0,
                   "extents": [{"index": 0, "offset": 0, "length": len(jb)}]}
    new_iinf_0 = _build_iinf(iinf_ver, iinf_flags, infes, item_id, new_infe)
    new_iloc_0 = _build_iloc(iloc_info, iloc_info["items"], placeholder)
    delta = ((len(new_iinf_0) - (iinf_box[3] - iinf_box[1]))
             + (len(new_iloc_0) - (iloc_box[3] - iloc_box[1])))
    json_off = len(data) + delta + 8
    new_item = {"id": item_id, "cm": 0, "data_ref": 0, "base": 0,
                "extents": [{"index": 0, "offset": json_off,
                             "length": len(jb)}]}

    # 既有 iloc：cm=0 且数据在 meta 之后 → offset +delta
    for item in iloc_info["items"]:
        for ext in item["extents"]:
            abs_off = item["base"] + ext["offset"]
            if item["cm"] == 0 and abs_off >= mend:
                ext["offset"] = ext["offset"] + delta
    new_iloc = _build_iloc(iloc_info, iloc_info["items"], new_item)
    new_iinf = _build_iinf(iinf_ver, iinf_flags, infes, item_id, new_infe)

    # 重建 meta（子盒顺序与未知子盒原字节不变）
    out_children = bytearray()
    for btype, bstart, bbody, bend in children:
        if btype == b"iinf":
            out_children += new_iinf
        elif btype == b"iloc":
            out_children += new_iloc
        else:
            out_children += data[bstart:bend]
    new_meta_body = bytes(prefix) + bytes(out_children)
    new_meta = ((len(new_meta_body) + 8).to_bytes(4, "big") + b"meta"
                + new_meta_body)

    before = b"".join(data[b[1]:b[3]] for b in tops if b[3] <= mstart)
    after = b"".join(data[b[1]:b[3]] for b in tops if b[1] >= mend)
    new_mdat = (len(jb) + 8).to_bytes(4, "big") + b"mdat" + jb
    _atomic_write(path, before + new_meta + after + new_mdat)
