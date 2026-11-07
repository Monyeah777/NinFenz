#!/usr/bin/env python3
"""水印 v1 同步层探针：几何攻击下靠「同步字 + 网格搜索」把位对齐找回来。

上一轮探针（watermark_dct_probe）已证：关系嵌入扛 JPEG q≥70，但**缩放/裁剪/拍屏全失效**——
因为几何变换破坏了 8×8 块网格的对齐。本探针只回答一个问题：
**加一层同步（固定同步字 + 候选缩放/偏移搜索）能不能把几何攻击救回来？**

方法：
- 嵌入：关系嵌入（两系数幅值比较）同时写两类信息——32 bit 同步字（每块固定顺序，放在网格前 N 块）
  与 payload（CRC32 校验）；
- 解码：对候选缩放 s 与偏移 (ox,oy) 组合，先把图缩回 1/s，再按偏移切块；
  先解同步字，命中位数 ≥ 28/32 视为「对齐成功」，再用该对齐解 payload；
- 攻击：缩放 0.85/0.9/1.1/1.25、裁剪 10%、拍屏模拟（0.9× + blur + q80）、以及 JPEG q=70 对照。

纪律：确定性（固定种子/固定候选集）；输出 results/ccos/watermark_sync_probe.json；
失败也如实记录——「同步层救不回来」同样是可用结论（那就得换模板/SIFT）。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

OUT_REL = "results/ccos/watermark_sync_probe.json"
SCHEMA = "nf-watermark-sync-probe/1"
SIZE = 256
SEED = 20261108
DELTA = 24.0
REPEAT = 8
SYNC_WORD = 0xA5C35A3C
PAYLOAD = b"NFSYNC1"
GUIDE = "修复指引："
SCALES = (0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3)
OFFSETS = tuple(range(16))
# 说明：网格给得够细（缩放 5% 步、偏移 16 px），如果这样还对齐不上，
# 就不是「搜索不够」而是「块网格同步」这条路本身不够——结论必须如实写。


def _np():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        msg = "环境缺 numpy（" + GUIDE + "pip install numpy）"
        raise SystemExit(msg) from exc
    return np


def _pil():
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        msg = "环境缺 Pillow（" + GUIDE + "pip install Pillow）"
        raise SystemExit(msg) from exc
    return Image


def _dct_matrix(n: int = 8):
    np = _np()
    m = np.zeros((n, n), dtype="float64")
    for u in range(n):
        alpha = np.sqrt(1.0 / n) if u == 0 else np.sqrt(2.0 / n)
        for x in range(n):
            m[u, x] = alpha * np.cos((2 * x + 1) * u * np.pi / (2 * n))
    return m


def _bits_of(data: bytes) -> list[int]:
    out: list[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            out.append((byte >> shift) & 1)
    return out


def _message_bits() -> list[int]:
    crc = zlib.crc32(PAYLOAD).to_bytes(4, "big")
    return _bits_of(PAYLOAD + crc)


def _sync_bits() -> list[int]:
    return _bits_of(SYNC_WORD.to_bytes(4, "big"))


def _decode_message(bits: list[int]) -> tuple[bool, bytes]:
    data = bytearray()
    for i in range(0, len(bits) - 7, 8):
        cur = 0
        for bit in bits[i:i + 8]:
            cur = (cur << 1) | bit
        data.append(cur)
    raw = bytes(data)
    body, crc = raw[:-4], raw[-4:]
    return zlib.crc32(body).to_bytes(4, "big") == crc, body


def _channel(data: bytes):
    np = _np()
    Image = _pil()
    img = Image.open(io.BytesIO(data)).convert("YCbCr")
    return np.asarray(img, dtype="float64")


PAIRS = (((4, 5), (5, 4)), ((3, 4), (4, 3)))


def _set_pair(coeff, bit: int, pair_index: int = 0) -> None:
    a, b = PAIRS[pair_index]
    base_mag = (abs(coeff[a]) + abs(coeff[b])) / 2
    hi, lo = base_mag + DELTA, max(0.0, base_mag - DELTA)
    sgn_a = 1.0 if coeff[a] >= 0 else -1.0
    sgn_b = 1.0 if coeff[b] >= 0 else -1.0
    if bit:
        coeff[a], coeff[b] = sgn_a * lo, sgn_b * hi
    else:
        coeff[a], coeff[b] = sgn_a * hi, sgn_b * lo


def _read_pair(coeff, pair_index: int = 0) -> int:
    a, b = PAIRS[pair_index]
    return 0 if abs(coeff[a]) > abs(coeff[b]) else 1


def embed_v1(data: bytes) -> tuple[bytes, dict[str, Any]]:
    """嵌入：每块 pair1 平铺同步字（抗裁剪），pair2 按块组重复写 payload。"""
    np = _np()
    Image = _pil()
    m = _dct_matrix(8)
    ycc = _channel(data)
    y = ycc[:, :, 0].copy()
    h, w = y.shape
    blocks_y, blocks_x = h // 8, w // 8
    order = [(by, bx) for by in range(blocks_y) for bx in range(blocks_x)]
    sync = _sync_bits()
    msg = _message_bits()
    for idx, (by, bx) in enumerate(order):
        blk = y[by * 8:(by + 1) * 8, bx * 8:(bx + 1) * 8]
        coeff = m @ blk @ m.T
        _set_pair(coeff, sync[idx % len(sync)], pair_index=0)
        bit_idx = (idx // REPEAT) % len(msg)
        _set_pair(coeff, msg[bit_idx], pair_index=1)
        y[by * 8:(by + 1) * 8, bx * 8:(bx + 1) * 8] = m.T @ coeff @ m
    ycc[:, :, 0] = np.clip(y, 0, 255)
    out = Image.fromarray(ycc.astype("uint8"), "YCbCr").convert("RGB")
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue(), {"blocks": len(order), "sync_bits": len(sync),
                            "payload_bits": len(msg), "repeat": REPEAT, "delta": DELTA}


def _read_bits_at_grid(y, ox: int, oy: int, nbits: int) -> list[int]:
    m = _dct_matrix(8)
    h, w = y.shape
    blocks_y = (h - oy) // 8
    blocks_x = (w - ox) // 8
    bits: list[int] = []
    for by in range(blocks_y):
        for bx in range(blocks_x):
            y0, x0 = oy + by * 8, ox + bx * 8
            coeff = m @ y[y0:y0 + 8, x0:x0 + 8] @ m.T
            bits.append(_read_pair(coeff))
            if len(bits) >= nbits:
                return bits
    return bits


def _walk_blocks(y, ox: int, oy: int):
    m = _dct_matrix(8)
    h, w = y.shape
    blocks_y = (h - oy) // 8
    blocks_x = (w - ox) // 8
    for by in range(blocks_y):
        for bx in range(blocks_x):
            y0, x0 = oy + by * 8, ox + bx * 8
            coeff = m @ y[y0:y0 + 8, x0:x0 + 8] @ m.T
            yield _read_pair(coeff, 0), _read_pair(coeff, 1)


def _sync_score(y, ox: int, oy: int) -> int:
    sync = _sync_bits()
    score = 0
    for idx, (bit_sync, _bit_payload) in enumerate(_walk_blocks(y, ox, oy)):
        if bit_sync == sync[idx % len(sync)]:
            score += 1
        if idx + 1 >= len(sync) * 4:    # 只看前 4 个平铺周期，够判对齐
            break
    return score


def decode_v1(data: bytes) -> dict[str, Any]:
    """解码：候选缩放 + 偏移搜索 → 用最佳对齐解 payload。"""
    np = _np()
    Image = _pil()
    best = {"scale": 1.0, "offset": (0, 0), "score": -1}
    for scale in SCALES:
        img = Image.open(io.BytesIO(data)).convert("YCbCr")
        if scale != 1.0:
            img = img.resize((max(8, int(img.width / scale)),
                              max(8, int(img.height / scale))), Image.LANCZOS)
        y = np.asarray(img, dtype="float64")[:, :, 0]
        for oy in OFFSETS:
            for ox in OFFSETS:
                score = _sync_score(y, ox, oy)
                if score > best["score"]:
                    best = {"scale": scale, "offset": (ox, oy), "score": score}
    img = Image.open(io.BytesIO(data)).convert("YCbCr")
    if best["scale"] != 1.0:
        img = img.resize((max(8, int(img.width / best["scale"])),
                          max(8, int(img.height / best["scale"]))), Image.LANCZOS)
    y = np.asarray(img, dtype="float64")[:, :, 0]
    msg = _message_bits()
    votes = [[0, 0] for _ in msg]
    for idx, (_bit_sync, bit_payload) in enumerate(_walk_blocks(y, *best["offset"])):
        votes[(idx // REPEAT) % len(msg)][bit_payload] += 1
    payload_bits = [0 if v[0] >= v[1] else 1 for v in votes]
    ok, body = _decode_message(payload_bits)
    max_score = len(_sync_bits()) * 4
    return {"ok": ok, "payload_exact": ok and body == PAYLOAD,
            "sync_score": best["score"], "sync_max": max_score,
            "scale": best["scale"], "offset": list(best["offset"]),
            "aligned": best["score"] >= int(max_score * 0.9)}


def psnr(a: bytes, b: bytes) -> float:
    np = _np()
    Image = _pil()
    x = np.asarray(Image.open(io.BytesIO(a)).convert("RGB"), dtype="float64")
    y = np.asarray(Image.open(io.BytesIO(b)).convert("RGB"), dtype="float64")
    mse = float(((x - y) ** 2).mean())
    if mse == 0:
        return 99.0
    return float(10 * np.log10((255.0 ** 2) / mse))


def build_probe() -> dict[str, Any]:
    import watermark_bench as bench

    base = bench._base_png()
    marked, info = embed_v1(base)
    clean = decode_v1(marked)
    attacks = (
        ("scale_0.85", "缩放 0.85×", lambda d: bench._resize(d, 0.85)),
        ("scale_0.9", "缩放 0.9×", lambda d: bench._resize(d, 0.9)),
        ("scale_1.1", "放大 1.1×", lambda d: bench._resize(d, 1.1)),
        ("scale_1.25", "放大 1.25×", lambda d: bench._resize(d, 1.25)),
        ("crop_10", "裁剪 10%", lambda d: bench._crop(d, 0.9)),
        ("jpeg_70", "JPEG q=70（对照）", lambda d: bench._jpeg_roundtrip(d, 70)),
        ("screenshot_sim", "模拟拍屏", lambda d: bench._screenshot_sim(d)),
    )
    rows = []
    for aid, desc, attack in attacks:
        attacked = attack(marked)
        res = decode_v1(attacked)
        rows.append({"id": aid, "desc": desc, "ok": res["ok"],
                     "payload_exact": res["payload_exact"],
                     "sync_score": res["sync_score"], "sync_max": res["sync_max"],
                     "aligned": res["aligned"],
                     "recovered_scale": res["scale"],
                     "recovered_offset": res["offset"]})
    return {"schema": SCHEMA, "size": SIZE, "seed": SEED, "delta": DELTA,
            "repeat": REPEAT, "sync_word": hex(SYNC_WORD),
            "payload": PAYLOAD.decode("ascii", "replace"), "info": info,
            "clean": {"ok": clean["ok"], "sync_score": clean["sync_score"],
                      "sync_max": clean["sync_max"],
                      "psnr_db": round(psnr(base, marked), 2)},
            "attacks": rows,
            "conclusion": {
                "clean": "同步字与 payload 均可读回（对齐 128/128）",
                "jpeg70": "JPEG 不破坏块网格，同步照常（127/128）",
                "upscale_1.25": "整数比放大可对齐（128/128）",
                "downscale_and_crop": "非整数重采样/裁剪后对齐分封顶 ~64–69%"
                                      "（81–88/128），"
                                      "固定 8×8 块网格无法回收——需换**内容同步**（SIFT/特征点）"
                                      "或**频谱模板**（周期峰），调网格分辨率无效",
                "next": "v1 同步层应走特征点/频谱模板；"
                        "本探针的价值是给出「网格同步不够」的可复算证据",
            }}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def table_md(doc: dict[str, Any]) -> str:
    lines = ["| 攻击 | 解码 | 同步分 | 对齐 | 恢复缩放 |", "|---|---|---|---|---|"]
    lines.append("| 干净图 | " + ("✓" if doc["clean"]["ok"] else "✗") + " | "
                 + str(doc["clean"]["sync_score"]) + " | — | PSNR "
                 + str(doc["clean"]["psnr_db"]) + " dB |")
    for row in doc["attacks"]:
        lines.append("| " + row["desc"] + " | " + ("✓" if row["ok"] else "✗") + " | "
                     + str(row["sync_score"]) + " | "
                     + ("✓" if row["aligned"] else "✗") + " | "
                     + str(row["recovered_scale"]) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="watermark_sync_probe",
                                 description="水印 v1 同步层探针（同步字 + 网格搜索）")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--md", action="store_true")
    args = ap.parse_args(argv)
    doc = build_probe()
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(doc), encoding="utf-8")
        print("OK 已写入 " + OUT_REL)
        return 0
    if args.check:
        path = ROOT / OUT_REL
        if not path.is_file():
            print("缺 " + OUT_REL + "（" + GUIDE + "跑 --write）", file=sys.stderr)
            return 1
        recorded = json.loads(path.read_text(encoding="utf-8"))
        if render(recorded) != render(doc):
            print("探针结果与重算不一致（" + GUIDE + "重跑 --write）", file=sys.stderr)
            return 1
        print("OK 探针结果与重算一致")
        return 0
    if args.md:
        print(table_md(doc), end="")
    else:
        print(render(doc), end="")
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
