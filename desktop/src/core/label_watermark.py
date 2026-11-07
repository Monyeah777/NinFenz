"""标注**水印层** v0：把 nf-label/1 IR 的摘要**写进像素最低位**，并在读回时做多数表决。

为什么单独一层（2026-11-07）：此前载体的写入面是「可见文本块」（PNG iTXt / JPEG APP15）——
任何人可以整块删掉，那叫 metadata，不叫水印。水印的下限是：**删掉文本块也还在**。

判据决定设计（不求「抗转码」这种做不到的承诺）：
- 帧结构 = 魔数 + 长度 + payload + CRC32：读回自带校验，坏帧直接 None（不猜）；
- 冗余 = 同一帧在每个 24×24 像素块里各写一遍（每块 1728 bit 容量），读回时**逐位多数表决**，
  因此能扛「裁掉一部分」「局部噪声」；
- 对齐 = 读回时尝试 24×24 种网格偏移，因此裁剪/平移只要还剩整块仍可读；
- 上限 = 每帧 ≤ 200 字节；图至少 48×48（2×2 块）。

**不承诺**：抗 JPEG 重编码、抗缩放、抗截屏（有损变换会毁掉低位）。这不是缺陷隐瞒，是这类
水印的物理边界；判据里对「JPEG 转码后读不回」写成**期望行为**，避免下次有人以为它坏了。
"""
from __future__ import annotations

import io
import struct
import zlib
from typing import Any

MAGIC = b"NFWM1"
TILE = 24
FRAME_MAX = 200
MIN_SIDE = TILE * 2
SCHEMA = "nf-label-watermark/1"
GUIDE = "修复指引："


def _pil_image():
    """软导入 Pillow：水印要解码/编码 PNG 位图。缺依赖 fail-closed 并给指引（不静默降级）。"""
    try:
        from PIL import Image
    except ImportError as exc:                    # pragma: no cover - 环境缺 Pillow
        raise ValueError("环境缺 Pillow，无法读写像素水印（修复指引：pip install Pillow；"
                         "或改用 --mode text 的文本载体——那条路是纯标准库）") from exc
    return Image


def _load_rgb(data: bytes):
    Image = _pil_image()
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise ValueError(f"对象不是可解码图像：{exc}（修复指引：水印只支持 PNG 位图）") from exc
    if img.format not in ("PNG",):
        raise ValueError(f"水印载体只支持 PNG（实得 {img.format}）（修复指引：先转成 PNG 再嵌入；"
                         "JPEG/MP4/PDF 的载体见 label_carrier 的文本/附加块方案）")
    if img.width < MIN_SIDE or img.height < MIN_SIDE:
        raise ValueError(f"图太小：{img.width}×{img.height}"
                         f"（修复指引：水印至少 {MIN_SIDE}×{MIN_SIDE}）")
    return img.convert("RGB")


def _frame(payload: bytes) -> bytes:
    if len(payload) > FRAME_MAX:
        raise ValueError(f"水印 payload 过长：{len(payload)} > {FRAME_MAX} 字节"
                         f"（修复指引：只写 IR 的摘要帧，别写整份 IR）")
    head = MAGIC + struct.pack(">H", len(payload)) + payload
    return head + struct.pack(">I", zlib.crc32(payload))


def _bits(frame: bytes):
    for byte in frame:
        for shift in range(7, -1, -1):
            yield (byte >> shift) & 1


def _bits_needed(frame: bytes) -> int:
    return len(frame) * 8


def _tile_slots(img) -> int:
    return TILE * TILE * 3


def embed(data: bytes, payload: bytes) -> tuple[bytes, dict[str, Any]]:
    """把 payload 冗余写进 PNG 每个 48×48 块的最低位 → (新 PNG 字节, 信息)。"""
    frame = _frame(payload)
    need = _bits_needed(frame)
    if need > _tile_slots(img := _load_rgb(data)):
        raise ValueError(f"块容量不足：需要 {need} bit / 块（修复指引：减小 payload 或加大 TILE）")
    px = img.load()
    width, height = img.size
    cols, rows = width // TILE, height // TILE
    bits = list(_bits(frame))
    for ty in range(rows):
        for tx in range(cols):
            idx = 0
            for y in range(ty * TILE, (ty + 1) * TILE):
                for x in range(tx * TILE, (tx + 1) * TILE):
                    r, g, b = px[x, y]
                    for chan, val in enumerate((r, g, b)):
                        if idx >= need:
                            break
                        bit = bits[idx]
                        val = (val & 0xFE) | bit
                        if chan == 0:
                            r = val
                        elif chan == 1:
                            g = val
                        else:
                            b = val
                        idx += 1
                    px[x, y] = (r, g, b)
                    if idx >= need:
                        break
                if idx >= need:
                    break
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue(), {"schema": SCHEMA, "tile": TILE, "frame_bytes": len(frame),
                            "bits_per_tile": need, "tiles": cols * rows,
                            "redundancy": cols * rows, "payload_bytes": len(payload)}


def _read_frame_at(px, width: int, height: int, ox: int, oy: int, nbits: int):
    """按给定网格偏移读 nbits 位并做多数表决 → (frame 或 None, 置信度)。"""
    cols = (width - ox) // TILE
    rows = (height - oy) // TILE
    if cols < 2 or rows < 2:
        return None, 0.0
    votes = [0] * nbits
    total = 0
    for ty in range(rows):
        for tx in range(cols):
            idx = 0
            base_x, base_y = ox + tx * TILE, oy + ty * TILE
            for y in range(base_y, base_y + TILE):
                for x in range(base_x, base_x + TILE):
                    for val in px[x, y]:
                        if idx >= nbits:
                            break
                        votes[idx] += val & 1
                        idx += 1
                    if idx >= nbits:
                        break
                if idx >= nbits:
                    break
            total += 1
    if total == 0:
        return None, 0.0
    agree = 0
    frame = bytearray()
    cur = 0
    for i, v in enumerate(votes):
        bit = 1 if v * 2 > total else 0
        agree += max(v, total - v)
        cur = (cur << 1) | bit
        if i % 8 == 7:
            frame.append(cur)
            cur = 0
    conf = agree / float(len(votes) * total) if total else 0.0
    return bytes(frame), conf


def _unpack(frame: bytes):
    if len(frame) < len(MAGIC) + 2 + 4 or not frame.startswith(MAGIC):
        return None
    (length,) = struct.unpack(">H", frame[len(MAGIC):len(MAGIC) + 2])
    start = len(MAGIC) + 2
    if length > FRAME_MAX or len(frame) < start + length + 4:
        return None
    payload = frame[start:start + length]
    (crc,) = struct.unpack(">I", frame[start + length:start + length + 4])
    if crc != zlib.crc32(payload):
        return None
    return payload


def _read_bits_at(px, ox: int, oy: int, nbits: int) -> list[int]:
    """按网格偏移读**一个块**的 nbits 位（用于先探帧头，避免全量多数表决）。"""
    bits: list[int] = []
    idx = 0
    for y in range(oy, oy + TILE):
        for x in range(ox, ox + TILE):
            for val in px[x, y]:
                bits.append(val & 1)
                idx += 1
                if idx >= nbits:
                    return bits
    return bits


def _probe_prefix(px, width: int, height: int, ox: int, oy: int):
    """探帧头：够魔数 + 长度就该块能认出候选偏移 → 长度或 None。"""
    head_bits = (len(MAGIC) + 2) * 8
    cols = (width - ox) // TILE
    rows = (height - oy) // TILE
    if cols < 2 or rows < 2:
        return None
    bits = _read_bits_at(px, ox, oy, head_bits)
    frame = bytearray()
    cur = 0
    for i, bit in enumerate(bits):
        cur = (cur << 1) | bit
        if i % 8 == 7:
            frame.append(cur)
            cur = 0
    raw = bytes(frame)
    if not raw.startswith(MAGIC):
        return None
    (length,) = struct.unpack(">H", raw[len(MAGIC):len(MAGIC) + 2])
    if length > FRAME_MAX:
        return None
    return length


def extract(data: bytes) -> dict[str, Any]:
    """从 PNG 读回水印 → {ok, payload, confidence, offset, issues}（读不回就 ok=False，不猜）。"""
    res: dict[str, Any] = {"ok": False, "schema": SCHEMA, "payload": b"", "confidence": 0.0,
                           "offset": None, "issues": []}
    try:
        img = _load_rgb(data)
    except ValueError as exc:
        res["issues"].append(str(exc))
        return res
    px = img.load()
    width, height = img.size
    best = (None, 0.0, None)
    for oy in range(TILE):
        for ox in range(TILE):
            length = _probe_prefix(px, width, height, ox, oy)
            if length is None:                 # 帧头都对不上，直接跳过（不必全量表决）
                continue
            nbits = (len(MAGIC) + 2 + length + 4) * 8
            frame, conf = _read_frame_at(px, width, height, ox, oy, nbits)
            if frame is None:
                continue
            payload = _unpack(frame)
            if payload is not None and conf > best[1]:
                best = (payload, conf, (ox, oy))
    if best[0] is None:
        res["issues"].append("读不回转录帧（" + GUIDE + "图可能被有损转码/缩放/大面积裁剪；"
                             "水印不承诺抗 JPEG/缩放）")
        return res
    res.update({"ok": True, "payload": best[0], "confidence": round(best[1], 4),
                "offset": best[2]})
    return res


def _frame_for_ir(ir: dict[str, Any]) -> bytes:
    """IR → 水印帧：只写关键面（schema/standard/object 摘要/条目名），不写整份 IR。"""
    import json as _json
    obj = ir.get("object") or {}
    items = list(ir.get("explicit") or []) + list(ir.get("implicit") or []) + list(
        ir.get("items") or [])
    names = sorted({str(it.get("id") or it.get("kind") or "") for it in items if it})
    digest = str(obj.get("sha256") or obj.get("digest") or "")
    core = {"v": 1, "schema": str(ir.get("schema") or ""),
            "standard": str(ir.get("standard") or ""),
            "object_sha256": digest[:32], "level": str(ir.get("level") or ""),
            "items": names[:8], "items_n": len(items)}
    body = _json.dumps(core, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return body[:FRAME_MAX]
