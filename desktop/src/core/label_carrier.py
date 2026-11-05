"""标注载体 v0：把 nf-label/1 真正**写进** PNG 的 iTXt 块（可读回、可证像素未变）。

为什么只做 PNG 一种（2026-11-06）：本仓没有标识写入子系统，上一轮只做到 sidecar（声明与对象
绑定，但「对象里到底有没有」证不了）。PNG 的 iTXt 是**公开规范 + 纯字节可逆**的载体，纯标准库
就能写且能读回自证；其它格式（JPEG/MP4/PDF）各自有一套嵌入规则，没有实测就不宣称。

只承诺这里能证的三件事：
1. 写入后**能被自己读回**（同 keyword、同 IR、JSON 语义等价）；
2. 写入**不改像素**（IDAT 块逐字节一致）；
3. 写入后文件仍是**结构合法**的 PNG（每个块 CRC 正确、签名正确）。

不承诺：抗裁剪/抗转码/抗截屏（那是水印，不在本件）；不承诺别的格式。
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import zlib
from typing import Any

from core import atomic_write, json_doc, label_ir

PNG_SIG = b"\x89PNG\r\n\x1a\n"
KEYWORD = "AIGC"                      # iTXt 关键字：载体里能看见的锚点
GUIDE = "修复指引："
SCHEMA = "nf-label/1"
#: 输入对象上限（防 OOM）：常规图远小于此；超大件请先缩，再写载体
MAX_INPUT_BYTES = 64 * 1024 * 1024


class CarrierError(ValueError):
    """载体面失败（不是 PNG / 块结构坏 / 标识读不出 / IR 与对象不符）。"""


def _iter_chunks(data: bytes) -> list[tuple[str, bytes]]:
    """拆 PNG 块 → [(类型, 数据)]；结构不合法就抛 CarrierError（含具体位置）。"""
    if not data.startswith(PNG_SIG):
        raise CarrierError("不是 PNG（签名不符）(" + GUIDE + "本件只写 PNG；其它格式请用 "
                           "nf label write 的 sidecar 回退）")
    out: list[tuple[str, bytes]] = []
    pos = len(PNG_SIG)
    while pos < len(data):
        if pos + 8 > len(data):
            raise CarrierError(f"PNG 块头截断（偏移 {pos}）("
                           + GUIDE + "文件不完整，重导出一份再写）")
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8].decode("latin-1")
        body_end = pos + 8 + length
        if body_end + 4 > len(data):
            raise CarrierError(f"PNG 块 {ctype} 数据截断（偏移 {pos}）(" + GUIDE + "文件不完整）")
        body = data[pos + 8:body_end]
        crc = struct.unpack(">I", data[body_end:body_end + 4])[0]
        if crc != zlib.crc32(data[pos + 4:body_end]) & 0xFFFFFFFF:
            raise CarrierError(f"PNG 块 {ctype} CRC 不符（偏移 {pos}）(" + GUIDE + "文件已损坏，"
                               "不要手工修补——重新导出原图）")
        out.append((ctype, body))
        pos = body_end + 4
    return out


def _chunk(ctype: str, body: bytes) -> bytes:
    head = struct.pack(">I", len(body)) + ctype.encode("latin-1")
    return head + body + struct.pack(">I", zlib.crc32(ctype.encode("latin-1") + body) & 0xFFFFFFFF)


def _itxt_body(text: str) -> bytes:
    """iTXt（UTF-8，未压缩）：keyword\0 flag\0 method\0 lang\0 translated\0 text。"""
    return (KEYWORD.encode("latin-1") + b"\x00" + b"\x00\x00" + b"\x00" + b"\x00"
            + text.encode("utf-8"))


def _itxt_text(body: bytes) -> str | None:
    """iTXt 体 → 文本；keyword 不是 AIGC 就返回 None（别人的块不碰）。

    AIGC 关键字但结构不完整 → **fail-closed**：旧实现返回 None 会被当成「不是我们的块」，
    于是畸形 AIGC 块被静默跳过、再插一块同 keyword，读面从此不确定。
    """
    keyword = body.split(b"\x00", 1)[0].decode("latin-1", "replace")
    if keyword != KEYWORD:
        return None
    parts = body.split(b"\x00", 5)
    if len(parts) < 6:
        raise CarrierError("AIGC iTXt 块结构不完整（" + GUIDE + "载体被改坏——按 invalid 处理，"
                           "不要静默跳过再插同 keyword 块）")
    try:
        return parts[5].decode("utf-8")
    except UnicodeDecodeError:
        raise CarrierError("AIGC iTXt 块不是合法 UTF-8（" + GUIDE + "块被改坏了，"
                           "用 nf label read 读 sidecar 核原声明") from None


def pixel_digest(data: bytes) -> str:
    """像素面摘要：所有 IDAT 块字节按序拼接后的 sha256（载体承诺「不改像素」的判据）。"""
    import hashlib
    h = hashlib.sha256()
    for ctype, body in _iter_chunks(data):
        if ctype == "IDAT":
            h.update(body)
    return h.hexdigest()


def content_digest(png: bytes) -> str:
    """内容摘要 = 去掉本件 AIGC iTXt 块后的 PNG 字节摘要（IR.object.digest 的比对基准）。

    为什么不是 sha256(整文件)：已标注的文件再写一次（幂等）时整文件带着标识；IR 描述的是
    「写入前内容」，把本件标签块去掉后的字节序列就是那个内容。
    """
    kept = [(t, b) for t, b in _iter_chunks(png)
            if not (t == "iTXt" and _itxt_text(b) is not None)]
    return hashlib.sha256(PNG_SIG + b"".join(_chunk(t, b) for t, b in kept)).hexdigest()


def _structure_issues(chunks: list[tuple[str, bytes]]) -> list[str]:
    """embed 前的结构闸：IHDR 首 / IEND 尾 / 至少两个块（空壳或半截一律拒）。"""
    if not chunks:
        return ["PNG 没有任何块（空壳/仅签名）（" + GUIDE + "换一份真实 PNG）"]
    issues: list[str] = []
    if chunks[0][0] != "IHDR":
        issues.append("首个块不是 IHDR（" + GUIDE + "换一份真实 PNG，不要手工拼签名）")
    if chunks[-1][0] != "IEND":
        issues.append("末块不是 IEND（" + GUIDE + "文件被截断或尾部有多余字节，重新导出）")
    return issues


def _embed_png(png: bytes, ir: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """把 IR 写进 PNG 的 AIGC iTXt 块 → (新字节, 摘要信息)。已存在则**替换**（幂等）。"""
    issues = label_ir.validate(ir)["issues"]
    if issues:
        raise CarrierError("标注 IR 不合法：" + "；".join(issues[:3])
                           + f"（{GUIDE}先 nf label validate 修好，再写载体）")
    obj = ir.get("object") or {}
    want = str(obj.get("digest") or "")
    if not want:
        raise CarrierError("IR 缺 object.digest（" + GUIDE + "用 nf label ir 针对该文件重编 IR）")
    if len(png) > MAX_INPUT_BYTES:
        raise CarrierError(f"输入对象超过上限（{len(png)} > {MAX_INPUT_BYTES} 字节）"
                           f"（{GUIDE}先缩小对象；载体只写常规图）")
    chunks = _iter_chunks(png)
    struct_issues = _structure_issues(chunks)
    if struct_issues:
        raise CarrierError("；".join(struct_issues))
    got = content_digest(png)
    if want != got:
        raise CarrierError("IR 的 object.digest 与输入对象不符（" + GUIDE + "IR 必须针对**这份**"
                           "对象生成（nf label ir <对象>）；声明的是写入前内容，不是任意对象）")
    before = pixel_digest(png)
    payload = json.dumps(ir, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(payload) > 8000:
        raise CarrierError(f"IR 太大（{len(payload)} 字节，上限 8000）（{GUIDE}减小声明项或改用 "
                           "sidecar 回退）")
    kept: list[tuple[str, bytes]] = []
    replaced = False
    for ctype, body in chunks:
        if ctype == "iTXt" and _itxt_text(body) is not None:
            if not replaced:
                kept.append(("iTXt", _itxt_body(json.dumps(ir, ensure_ascii=False,
                                                           sort_keys=True))))
                replaced = True
            continue
        kept.append((ctype, body))
    if not replaced:
        # 插在 IHDR 之后：所有解码器都会读到，且不打断 IDAT/IEND 的相对顺序
        insert_at = 1 if kept and kept[0][0] == "IHDR" else 0
        kept.insert(insert_at, ("iTXt", _itxt_body(json.dumps(ir, ensure_ascii=False,
                                                              sort_keys=True))))
    out = PNG_SIG + b"".join(_chunk(t, b) for t, b in kept)
    after = pixel_digest(out)
    if after != before:
        raise CarrierError("内部错误：写入改动了像素数据（" + GUIDE
                           + "这是判据 bug，别发布这份产物）")
    return out, {"keyword": KEYWORD, "bytes": len(out), "pixel_digest": before,
                 "replaced": replaced}


def _read_png(png: bytes) -> dict[str, Any]:
    """读回载体里的 IR → {ok, verdict, label, issues}（形状与 sidecar.read 对齐）。"""
    res: dict[str, Any] = {"ok": False, "verdict": "invalid", "label": None,
                           "carrier": "itxt", "issues": []}
    try:
        for ctype, body in _iter_chunks(png):
            if ctype != "iTXt":
                continue
            text = _itxt_text(body)
            if text is None:
                continue
            try:
                doc = json_doc.loads(text, dict, what="载体 IR")
            except ValueError as exc:
                res["issues"].append(f"AIGC iTXt 不是合法 IR JSON：{exc}"
                                     f"（{GUIDE}载体被改坏，按 invalid 处理）")
                return res
            issues = label_ir.validate(doc)["issues"]
            if issues:
                res["issues"].append("载体里的 IR 不合法：" + "；".join(issues[:3]))
                return res
            res.update({"ok": True, "verdict": "ok", "label": doc, "embedded": True})
            return res
    except CarrierError as exc:
        res["issues"].append(str(exc))
        return res
    res["issues"].append("载体里没有 AIGC iTXt 块（" + GUIDE + "该文件从未写入标识；"
                         "若声明来自 sidecar，请用 nf label read 核对）")
    return res


# ---------------------------------------------------------------- JPEG（APP15 文本段）

JPEG_SOI = b"\xff\xd8"
APP15 = 0xEF
#: JPEG 段：APP15 里放 "AIGC\0" + JSON（UTF-8）。为什么是 APP15：应用私有段，解码器按规范跳过。
JPEG_PREFIX = b"AIGC\x00"
_JPEG_STANDALONE = frozenset({0x01, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7})


def _jpeg_split(data: bytes) -> tuple[list[tuple[int, bytes]], bytes]:
    """JPEG → (SOS 之前的段列表 [(marker, payload)], 从 SOS 到 EOF 的原始字节)。

    SOS 之后是熵编码数据，**必须原样保留**——载体承诺「不改扫描数据」的判据就是它。
    """
    if not data.startswith(JPEG_SOI):
        raise CarrierError("不是 JPEG（缺 SOI）(" + GUIDE + "JPEG 必须以 FFD8 开头；"
                           "其它格式请用 nf label write 的 sidecar 回退）")
    pos = len(JPEG_SOI)
    segs: list[tuple[int, bytes]] = []
    n = len(data)
    while pos < n:
        if data[pos] != 0xFF:
            raise CarrierError(f"JPEG 段边界不符（偏移 {pos} 应为 0xFF）("
                               + GUIDE + "文件损坏，重新导出原图再写）")
        while pos < n and data[pos] == 0xFF:      # 填充字节 0xFF 合法，跳过
            pos += 1
        if pos >= n:
            break
        marker = data[pos]
        pos += 1
        if marker == 0xDA:                        # SOS：后面全是熵数据
            if pos + 2 > n:
                raise CarrierError("JPEG SOS 段头截断（" + GUIDE + "文件不完整）")
            seg_len = struct.unpack(">H", data[pos:pos + 2])[0]
            if pos + seg_len > n:
                raise CarrierError("JPEG SOS 段数据截断（" + GUIDE + "文件不完整）")
            return segs, data[pos - 2:]           # 从 SOS 标记起原样返回（含 FFDA 与长度）
        if marker in _JPEG_STANDALONE:
            segs.append((marker, b""))
            continue
        if pos + 2 > n:
            raise CarrierError("JPEG 段长度截断（" + GUIDE + "文件不完整）")
        seg_len = struct.unpack(">H", data[pos:pos + 2])[0]
        if seg_len < 2 or pos + seg_len > n:
            raise CarrierError(f"JPEG 段长度非法（marker=0x{marker:02X}）("
                               + GUIDE + "文件损坏，重新导出原图再写）")
        segs.append((marker, data[pos + 2:pos + seg_len]))
        pos += seg_len
    raise CarrierError("JPEG 缺 SOS（" + GUIDE + "文件不完整，重新导出原图再写）")


def jpeg_scan_digest(data: bytes) -> str:
    """扫描数据摘要：SOS 到 EOF 的原始字节 sha256（判「不改扫描数据」）。"""
    import hashlib
    _segs, tail = _jpeg_split(data)
    return hashlib.sha256(tail).hexdigest()


def _jpeg_seg(marker: int, payload: bytes) -> bytes:
    body = JPEG_PREFIX + payload if marker == APP15 else payload
    return b"\xff" + bytes([marker]) + struct.pack(">H", len(body) + 2) + body


def _embed_jpeg(jpeg: bytes, ir: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """把 IR 写进 JPEG 的 APP15 段（幂等替换；扫描数据原样保留）。"""
    segs, tail = _jpeg_split(jpeg)
    before = jpeg_scan_digest(jpeg)
    payload = json.dumps(ir, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(payload) > 8000:
        raise CarrierError(f"IR 太大（{len(payload)} 字节，上限 8000）（"
                           + GUIDE + "减小声明项或改用 sidecar 回退）")
    app15 = _jpeg_seg(APP15, payload)
    kept: list[bytes] = []
    replaced = False
    insert_at = 0                    # 原文件没有我们的段时，插在 APP0/APP1 之后
    for marker, body in segs:
        if marker == APP15 and body.startswith(JPEG_PREFIX):
            if not replaced:          # 幂等：原位替换，多余的旧段丢弃（防重复堆积）
                kept.append(app15)
                replaced = True
            continue
        kept.append(_jpeg_seg(marker, body))
        if not replaced and marker in (0xE0, 0xE1):
            insert_at = len(kept)
    if not replaced:
        kept.insert(insert_at, app15)
    out = JPEG_SOI + b"".join(kept) + tail
    after = jpeg_scan_digest(out)
    if after != before:
        raise CarrierError("内部错误：写入改动了扫描数据（" + GUIDE
                           + "这是判据 bug，别发布这份产物）")
    return out, {"keyword": KEYWORD, "format": "jpeg", "bytes": len(out),
                 "scan_digest": before, "replaced": replaced}


def _read_jpeg(jpeg: bytes) -> dict[str, Any]:
    res: dict[str, Any] = {"ok": False, "verdict": "invalid", "label": None,
                           "carrier": "jpeg-app15", "issues": []}
    try:
        segs, _tail = _jpeg_split(jpeg)
    except CarrierError as exc:
        res["issues"].append(str(exc))
        return res
    for marker, body in segs:
        if marker != APP15 or not body.startswith(JPEG_PREFIX):
            continue
        text = body[len(JPEG_PREFIX):].decode("utf-8", "replace")
        try:
            doc = json_doc.loads(text, dict, what="JPEG APP15 里的 AIGC 声明")
        except ValueError as exc:
            res["issues"].append(str(exc))
            return res
        issues = label_ir.validate(doc)["issues"]
        if issues:
            res["issues"].append("载体里的 IR 不合法：" + "；".join(issues[:3]))
            return res
        res.update({"ok": True, "verdict": "ok", "label": doc, "embedded": True})
        return res
    res["issues"].append("载体里没有 AIGC APP15 段（" + GUIDE + "该文件从未写入标识；"
                         "若声明来自 sidecar，请用 nf label read 核对）")
    return res


# ---------------------------------------------------------------- 分发（格式按 magic）

def embed(data: bytes, ir: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """按 magic 选载体：PNG → iTXt；JPEG → APP15。其它格式一律带指引拒绝（不猜）。"""
    issues = label_ir.validate(ir)["issues"]
    if issues:
        raise CarrierError("标注 IR 不合法：" + "；".join(issues[:3])
                           + f"（{GUIDE}先 nf label validate 修好，再写载体）")
    if data.startswith(PNG_SIG):
        out, info = _embed_png(data, ir)
        return out, {**info, "format": "png"}
    if data.startswith(JPEG_SOI):
        return _embed_jpeg(data, ir)
    raise CarrierError("不支持的载体格式（" + GUIDE + "本件只写 PNG 与 JPEG；"
                       "其它格式请用 nf label write 的 sidecar 回退）")


def read(data: bytes) -> dict[str, Any]:
    """按 magic 读载体；不认识就如实 invalid。"""
    if data.startswith(PNG_SIG):
        return _read_png(data)
    if data.startswith(JPEG_SOI):
        return _read_jpeg(data)
    res = {"ok": False, "verdict": "invalid", "label": None, "issues": []}
    res["issues"].append("不认识的载体格式（" + GUIDE + "本件只读 PNG 与 JPEG）")
    return res


def embed_file(src: str, ir: dict[str, Any], out: str) -> dict[str, Any]:
    """文件级写入：读原图 → 嵌入 → 原子写新文件（**不改输入**）。"""
    if os.path.abspath(src) == os.path.abspath(out):
        raise CarrierError("落点不能等于源文件（" + GUIDE + "本件承诺不改输入；请换一个 --out）")
    with open(src, "rb") as fh:
        png = fh.read()
    if not png:
        raise CarrierError(f"输入为空：{src}（" + GUIDE + "换一份真实 PNG）")
    new, info = embed(png, ir)
    atomic_write.write_bytes(out, new)
    return {"src": src, "out": out, **info}
