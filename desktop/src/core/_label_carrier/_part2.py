"""core.label_carrier 私有实现分片 2/2（对外只经 core.label_carrier 门面导入）：_embed_jpeg 等"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from core import atomic_write, json_doc, label_ir

from ._part1 import (
    APP15,
    GUIDE,
    JPEG_PREFIX,
    JPEG_SOI,
    KEYWORD,
    MAX_INPUT_BYTES,
    PNG_SIG,
    CarrierError,
    _embed_png,
    _jpeg_seg,
    _jpeg_split,
    _jpeg_structure_issues,
    _read_png,
    jpeg_content_digest,
    jpeg_scan_digest,
)


def _checked_payload(jpeg: bytes, ir: dict[str, Any], segs: list) -> tuple[int, bytes]:
    """校验结构/摘要/上限 → (before 扫描摘要, payload)；不合约抛 CarrierError。"""
    struct_issues = _jpeg_structure_issues(segs)
    if struct_issues:
        raise CarrierError("；".join(struct_issues))
    want = str((ir.get("object") or {}).get("digest") or "")
    got = jpeg_content_digest(jpeg)
    if want != got:
        raise CarrierError("IR 的 object.digest 与输入对象不符（" + GUIDE + "IR 必须针对**这份**"
                           "对象生成（nf label ir <对象>）；JPEG 的摘要基准 = 去掉本件 APP15 "
                           "后的完整字节）")
    before = jpeg_scan_digest(jpeg)
    payload = json.dumps(ir, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(payload) > 8000:
        raise CarrierError(f"IR 太大（{len(payload)} 字节，上限 8000）（"
                           + GUIDE + "减小声明项或改用 sidecar 回退）")
    return before, payload


def _splice_app15(segs: list, app15: bytes) -> list[bytes]:
    """把 APP15 段幂等替换/插入 → 段列表（其余段原样字节保留）。"""
    kept: list[bytes] = []
    replaced = False
    insert_at = 0                    # 原文件没有我们的段时，插在 APP0/APP1 之后
    for marker, body, raw in segs:
        if marker == APP15 and body.startswith(JPEG_PREFIX):
            if not replaced:          # 幂等：原位替换，多余的旧段丢弃（防重复堆积）
                kept.append(app15)
                replaced = True
            continue
        kept.append(raw)              # 其余段**原样字节**保留（含 0xFF 填充）
        if not replaced and marker in (0xE0, 0xE1):
            insert_at = len(kept)
    if not replaced:
        kept.insert(insert_at, app15)
    return kept


def _embed_jpeg(jpeg: bytes, ir: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """把 IR 写进 JPEG 的 APP15 段（幂等替换；扫描数据原样保留）。"""
    segs, tail = _jpeg_split(jpeg)
    before, payload = _checked_payload(jpeg, ir, segs)
    app15 = _jpeg_seg(APP15, payload)
    kept = _splice_app15(segs, app15)
    replaced = any(marker == APP15 and body.startswith(JPEG_PREFIX) for marker, body, _ in segs)
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
    for marker, body, _raw in segs:
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


# ---------------------------------------------------------------- WebP / MP4 / PDF（附加块载体）
WEBP_RIFF = b"RIFF"


WEBP_TAG = b"WEBP"


WEBP_CHUNK = b"NFLA"


MP4_BOX = b"free"


PDF_COMMENT = b"\n%% NF-LABEL "


def _webp_media_digest(data: bytes) -> str:
    """WebP 媒体面摘要（前半 RIFF 不变的那段之外的部分）：用于证明写入不改像素数据。"""
    return hashlib.sha256(data[12:]).hexdigest()


def _embed_webp(data: bytes, ir: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """WebP：在 RIFF 尾部追加私有块 NFLA（解码器按规范跳过未知块；RIFF 长度同步）。"""
    if len(data) < 12 or data[8:12] != WEBP_TAG:
        raise CarrierError("WebP 头部不合法（" + GUIDE + "不是 RIFF/WEBP 容器）")
    body = json.dumps(ir, ensure_ascii=False, sort_keys=True).encode("utf-8")
    pad = b"\x00" if len(body) % 2 else b""
    chunk = WEBP_CHUNK + int.to_bytes(len(body), 4, "little") + body + pad
    riff = bytearray(data)
    new_size = int.from_bytes(riff[4:8], "little") + len(chunk)
    riff[4:8] = int.to_bytes(new_size, 4, "little")
    out = bytes(riff) + chunk
    return out, {"keyword": WEBP_CHUNK.decode("ascii"), "replaced": False,
                 "media_digest": _webp_media_digest(data), "carrier": "webp-chunk",
                 "bytes_before": len(data), "bytes_after": len(out)}


def _read_webp(data: bytes) -> dict[str, Any]:
    res: dict[str, Any] = {"ok": False, "verdict": "invalid", "label": None, "issues": []}
    pos = 12
    while pos + 8 <= len(data):
        name = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        body = data[pos + 8:pos + 8 + size]
        if name == WEBP_CHUNK:
            try:
                ir = json_doc.loads(body[:size].rstrip(b"\x00").decode("utf-8"), dict,
                                what="标注块")
            except (ValueError, UnicodeDecodeError) as exc:
                res["issues"].append(f"WebP 标注块不可解析：{exc}（{GUIDE}重写）")
                return res
            issues = label_ir.validate(ir)["issues"]
            if issues:
                res["issues"].extend(issues)
                return res
            res.update({"ok": True, "verdict": "ok", "label": ir})
            return res
        pos += 8 + size + (size % 2)
    res["issues"].append("WebP 里没有 NFLA 标注块（" + GUIDE + "可能是被重编码/剥离过）")
    return res


def _embed_mp4(data: bytes, ir: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """MP4：尾部追加一个顶层 free 盒（规范允许跳过；不碰 moov/mdat）。"""
    if len(data) < 12 or data[4:8] != b"ftyp":
        raise CarrierError("MP4 头部不合法（" + GUIDE + "不是 ftyp 开头的 ISO BMFF）")
    body = json.dumps(ir, ensure_ascii=False, sort_keys=True).encode("utf-8")
    box = int.to_bytes(8 + len(body), 4, "big") + MP4_BOX + body
    out = data + box
    return out, {"keyword": MP4_BOX.decode("ascii"), "replaced": False,
                 "media_digest": hashlib.sha256(data).hexdigest(), "carrier": "mp4-free-box",
                 "bytes_before": len(data), "bytes_after": len(out)}


def _read_mp4(data: bytes) -> dict[str, Any]:
    res: dict[str, Any] = {"ok": False, "verdict": "invalid", "label": None, "issues": []}
    pos = 0
    while pos + 8 <= len(data):
        size = int.from_bytes(data[pos:pos + 4], "big")
        name = data[pos + 4:pos + 8]
        if size < 8 or pos + size > len(data):
            res["issues"].append("MP4 盒结构不合法（" + GUIDE + "文件可能被截断/改写）")
            return res
        if name == MP4_BOX:
            body = data[pos + 8:pos + size]
            try:
                ir = json_doc.loads(body.decode("utf-8"), dict, what="标注盒")
            except (ValueError, UnicodeDecodeError):
                pos += size
                continue
            issues = label_ir.validate(ir)["issues"]
            if not issues:
                res.update({"ok": True, "verdict": "ok", "label": ir})
                return res
        pos += size
    res["issues"].append("MP4 里没有 free 标注盒（" + GUIDE + "可能被重封装/剥离过）")
    return res


def _embed_pdf(data: bytes, ir: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """PDF：EOF 之后追加一行注释（PDF 允许尾部多余字节；不碰 xref/对象）。"""
    if not data.startswith(b"%PDF-"):
        raise CarrierError("PDF 头部不合法（" + GUIDE + "不是 %PDF 文件）")
    body = base64.b64encode(json.dumps(ir, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    out = data + PDF_COMMENT + body + b"\n"
    return out, {"keyword": "NF-LABEL", "replaced": False,
                 "media_digest": hashlib.sha256(data).hexdigest(), "carrier": "pdf-trailer-comment",
                 "bytes_before": len(data), "bytes_after": len(out)}


def _read_pdf(data: bytes) -> dict[str, Any]:
    res: dict[str, Any] = {"ok": False, "verdict": "invalid", "label": None, "issues": []}
    marker = PDF_COMMENT.strip()
    idx = data.rfind(marker)
    if idx < 0:
        res["issues"].append("PDF 尾部没有 NF-LABEL 注释（" + GUIDE + "可能被重新保存/剥离过）")
        return res
    tail = data[idx + len(marker):].split(b"\n", 1)[0].strip()
    try:
        ir = json_doc.loads(base64.b64decode(tail, validate=True).decode("utf-8"),
                            dict, what="标注注释")
    except (ValueError, UnicodeDecodeError):
        res["issues"].append("PDF 标注注释不可解析（" + GUIDE + "注释行被截断/改动）")
        return res
    issues = label_ir.validate(ir)["issues"]
    if issues:
        res["issues"].extend(issues)
        return res
    res.update({"ok": True, "verdict": "ok", "label": ir})
    return res


def embed(data: bytes, ir: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """按 magic 选载体：PNG → iTXt；JPEG → APP15。其它格式一律带指引拒绝（不猜）。"""
    if len(data) > MAX_INPUT_BYTES:
        raise CarrierError(f"输入对象超过上限（{len(data)} > {MAX_INPUT_BYTES} 字节）"
                           f"（{GUIDE}先缩小对象；载体只写常规图）")
    issues = label_ir.validate(ir)["issues"]
    if issues:
        raise CarrierError("标注 IR 不合法：" + "；".join(issues[:3])
                           + f"（{GUIDE}先 nf label validate 修好，再写载体）")
    if data.startswith(PNG_SIG):
        out, info = _embed_png(data, ir)
        return out, {**info, "format": "png"}
    if data.startswith(JPEG_SOI):
        return _embed_jpeg(data, ir)
    if data.startswith(WEBP_RIFF) and data[8:12] == WEBP_TAG:
        return _embed_webp(data, ir)
    if data[4:8] == b"ftyp":
        return _embed_mp4(data, ir)
    if data.startswith(b"%PDF-"):
        return _embed_pdf(data, ir)
    raise CarrierError("不支持的载体格式（" + GUIDE + "本件写 PNG/JPEG/WebP/MP4/PDF；"
                       "其它格式请用 nf label write 的 sidecar 回退）")


def read(data: bytes) -> dict[str, Any]:
    """按 magic 读载体；不认识就如实 invalid。"""
    if data.startswith(PNG_SIG):
        return _read_png(data)
    if data.startswith(JPEG_SOI):
        return _read_jpeg(data)
    if data.startswith(WEBP_RIFF) and data[8:12] == WEBP_TAG:
        return _read_webp(data)
    if data[4:8] == b"ftyp":
        return _read_mp4(data)
    if data.startswith(b"%PDF-"):
        return _read_pdf(data)
    res = {"ok": False, "verdict": "invalid", "label": None, "issues": []}
    res["issues"].append("不认识的载体格式（" + GUIDE + "本件读 PNG/JPEG/WebP/MP4/PDF）")
    return res


def embed_file(src: str, ir: dict[str, Any], out: str) -> dict[str, Any]:
    """文件级写入：读原图 → 嵌入 → 原子写新文件（**不改输入**）。"""
    if os.path.abspath(src) == os.path.abspath(out):
        raise CarrierError("落点不能等于源文件（" + GUIDE + "本件承诺不改输入；请换一个 --out）")
    with open(src, "rb") as fh:
        png = fh.read()
    if not png:
        raise CarrierError(f"输入为空：{src}（" + GUIDE + "换一份真实图片（PNG/JPEG））")
    new, info = embed(png, ir)
    atomic_write.write_bytes(out, new)
    return {"src": src, "out": out, **info}
