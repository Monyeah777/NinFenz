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

import json
import struct
import zlib
from typing import Any

from core import atomic_write, label_ir

PNG_SIG = b"\x89PNG\r\n\x1a\n"
KEYWORD = "AIGC"                      # iTXt 关键字：载体里能看见的锚点
GUIDE = "修复指引："
SCHEMA = "nf-label/1"


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
    """iTXt 体 → 文本；keyword 不是 AIGC 就返回 None（别人的块不碰）。"""
    parts = body.split(b"\x00", 5)
    if len(parts) < 6:
        return None
    if parts[0].decode("latin-1", "replace") != KEYWORD:
        return None
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


def embed(png: bytes, ir: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """把 IR 写进 PNG 的 AIGC iTXt 块 → (新字节, 摘要信息)。已存在则**替换**（幂等）。"""
    issues = label_ir.validate(ir)["issues"]
    if issues:
        raise CarrierError("标注 IR 不合法：" + "；".join(issues[:3])
                           + f"（{GUIDE}先 nf label validate 修好，再写载体）")
    obj = ir.get("object") or {}
    want = str(obj.get("digest") or "")
    if not want:
        raise CarrierError("IR 缺 object.digest（" + GUIDE + "用 nf label ir 针对该文件重编 IR）")
    chunks = _iter_chunks(png)
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


def read(png: bytes) -> dict[str, Any]:
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
                doc = json.loads(text)
            except json.JSONDecodeError as exc:
                res["issues"].append(f"AIGC iTXt 不是合法 JSON：{exc}"
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


def embed_file(src: str, ir: dict[str, Any], out: str) -> dict[str, Any]:
    """文件级写入：读原图 → 嵌入 → 原子写新文件（**不改输入**）。"""
    with open(src, "rb") as fh:
        png = fh.read()
    if not png:
        raise CarrierError(f"输入为空：{src}（" + GUIDE + "换一份真实 PNG）")
    new, info = embed(png, ir)
    atomic_write.write_bytes(out, new)
    return {"src": src, "out": out, **info}
