#!/usr/bin/env python3
"""拍屏水印第五轮探针：更强 delta + 低频系数对 + 块尺寸扫描，摸清模糊边界。

已知（前四轮实测）：关系嵌入扛 JPEG q≥50、缩放、裁剪；**拍屏（0.9×+blur+JPEG）仍失败**。
本轮只问一个问题：**把嵌入强度提上去、换更低频的系数对、放大块尺寸，能不能把拍屏救回来？**

方法：
- 关系嵌入（两系数幅值比较），参数化：delta ∈ {24,32,40,48}、块 ∈ {8,16}、
  系数对 ∈ {(4,5)/(5,4) 中频, (2,3)/(3,2) 低频}；
- 攻击链固定：0.9× 缩放 → 高斯模糊（radius 0.3/0.6/1.0）→ JPEG q=80（模拟拍屏三段）；
- 指标：payload 是否过 CRC32、BER（vs 干净图解码位）、PSNR；
- 输出 results/ccos/watermark_ecc_probe.json（确定性），--md 出表。

纪律：跑不出就如实记录「加大强度也救不回」——这比「再调调看」有用。
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

from core import atomic_write, json_doc  # noqa: E402 承重件须在 path 注入后导入

OUT_REL = "results/ccos/watermark_ecc_probe.json"
SCHEMA = "nf-watermark-ecc-probe/1"
SIZE = 256
SEED = 20261108
PAYLOAD = b"NFECC1"
REPEAT = 8          # 8×8 块默认重复 8 次
GUIDE = "修复指引："
CONFIGS = (
    (24.0, 8, 0), (32.0, 8, 0), (40.0, 8, 0), (48.0, 8, 0),
    (24.0, 16, 0), (32.0, 16, 0), (40.0, 16, 0),
    (32.0, 8, 1), (40.0, 8, 1), (48.0, 8, 1),
)
BLUR_RADII = (0.3, 0.6, 1.0)


def _np():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("环境缺 numpy（" + GUIDE + "pip install numpy）") from exc
    return np


def _pil():
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("环境缺 Pillow（" + GUIDE + "pip install Pillow）") from exc
    return Image


def _dct(n: int):
    np = _np()
    m = np.zeros((n, n), dtype="float64")
    for u in range(n):
        alpha = np.sqrt(1.0 / n) if u == 0 else np.sqrt(2.0 / n)
        for x in range(n):
            m[u, x] = alpha * np.cos((2 * x + 1) * u * np.pi / (2 * n))
    return m


def _bits(data: bytes) -> list[int]:
    out: list[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            out.append((byte >> shift) & 1)
    return out


def _message_bits() -> list[int]:
    return _bits(PAYLOAD + zlib.crc32(PAYLOAD).to_bytes(4, "big"))


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


def _pairs(freq: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """块内系数对：freq=0 → 中频 (4,5)/(5,4)；freq=1 → 低频 (2,3)/(3,2)。"""
    if freq == 0:
        return (4, 5), (5, 4)
    return (2, 3), (3, 2)


def _base_png() -> bytes:
    np = _np()
    Image = _pil()
    arr = np.random.default_rng(SEED).integers(0, 256, (SIZE, SIZE, 3), dtype="uint8")
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, "PNG")
    return buf.getvalue()


def _repeat_for(block_size: int) -> int:
    """重复次数随块尺寸自适应：16×16 块时块数只有 8×8 的 1/4，重复数同步降。"""
    return REPEAT if block_size <= 8 else max(2, REPEAT // 4)


def embed(data: bytes, delta: float, block_size: int, freq: int) -> tuple[bytes, dict[str, Any]]:
    np = _np()
    Image = _pil()
    m = _dct(block_size)
    a, b = _pairs(freq)
    img = Image.open(io.BytesIO(data)).convert("YCbCr")
    ycc = np.asarray(img, dtype="float64")
    y = ycc[:, :, 0].copy()
    h, w = y.shape
    order = [(by, bx) for by in range(h // block_size) for bx in range(w // block_size)]
    msg = _message_bits()
    repeat = _repeat_for(block_size)
    if len(order) < len(msg) * repeat:
        raise SystemExit("块数不足（" + GUIDE + "增大图像或减小 REPEAT）")
    rng = np.random.default_rng(SEED)
    slots = list(range(len(msg) * repeat))
    rng.shuffle(slots)
    for pi in range(len(msg) * repeat):
        bit_idx = pi // repeat
        by, bx = order[slots[pi]]
        y0, x0 = by * block_size, bx * block_size
        blk = y[y0:y0 + block_size, x0:x0 + block_size]
        coeff = m @ blk @ m.T
        mag = (abs(coeff[a]) + abs(coeff[b])) / 2
        hi, lo = mag + delta, max(0.0, mag - delta)
        sa = 1.0 if coeff[a] >= 0 else -1.0
        sb = 1.0 if coeff[b] >= 0 else -1.0
        if msg[bit_idx]:
            coeff[a], coeff[b] = sa * lo, sb * hi
        else:
            coeff[a], coeff[b] = sa * hi, sb * lo
        y[y0:y0 + block_size, x0:x0 + block_size] = m.T @ coeff @ m
    ycc[:, :, 0] = np.clip(y, 0, 255)
    out = Image.fromarray(ycc.astype("uint8"), "YCbCr").convert("RGB")
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue(), {"blocks": len(order), "block": block_size,
                            "delta": delta, "freq": freq, "repeat": repeat}


def extract(data: bytes, delta: float, block_size: int, freq: int) -> list[int]:
    np = _np()
    Image = _pil()
    m = _dct(block_size)
    a, b = _pairs(freq)
    img = Image.open(io.BytesIO(data)).convert("YCbCr")
    y = np.asarray(img, dtype="float64")[:, :, 0]
    h, w = y.shape
    order = [(by, bx) for by in range(h // block_size) for bx in range(w // block_size)]
    msg = _message_bits()
    repeat = _repeat_for(block_size)
    rng = np.random.default_rng(SEED)
    slots = list(range(len(msg) * repeat))
    rng.shuffle(slots)
    votes = [[0, 0] for _ in msg]
    for pi in range(min(len(msg) * repeat, len(order))):
        bit_idx = pi // repeat
        by, bx = order[slots[pi]]
        y0, x0 = by * block_size, bx * block_size
        blk = y[y0:y0 + block_size, x0:x0 + block_size]
        coeff = m @ blk @ m.T
        votes[bit_idx][0 if abs(coeff[a]) > abs(coeff[b]) else 1] += 1
    return [0 if v[0] >= v[1] else 1 for v in votes]


def screenshot(data: bytes, radius: float) -> bytes:
    _np()
    Image = _pil()
    try:
        from PIL import ImageFilter
    except ImportError as exc:  # pragma: no cover - 环境缺 Pillow 的滤镜面
        raise SystemExit("环境缺 Pillow 的 ImageFilter（修复指引：pip install Pillow）") from exc
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img = img.resize((int(img.width * 0.9), int(img.height * 0.9)), Image.LANCZOS)
    img = img.filter(ImageFilter.GaussianBlur(radius=radius))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    out = io.BytesIO()
    Image.open(buf).convert("RGB").save(out, "PNG")
    return out.getvalue()


def psnr(a: bytes, b: bytes) -> float:
    np = _np()
    Image = _pil()
    x = np.asarray(Image.open(io.BytesIO(a)).convert("RGB"), dtype="float64")
    y = np.asarray(Image.open(io.BytesIO(b)).convert("RGB"), dtype="float64")
    mse = float(((x - y) ** 2).mean())
    return 99.0 if mse == 0 else float(10 * np.log10((255.0 ** 2) / mse))


def build_probe() -> dict[str, Any]:
    base = _base_png()
    rows = []
    for delta, block_size, freq in CONFIGS:
        marked, _info = embed(base, delta, block_size, freq)
        clean_bits = extract(marked, delta, block_size, freq)
        ok_clean, _ = _decode_message(clean_bits)
        row = {"delta": delta, "block": block_size, "freq": freq,
               "psnr_db": round(psnr(base, marked), 2),
               "clean_ok": ok_clean, "blur": {}}
        for radius in BLUR_RADII:
            attacked = screenshot(marked, radius)
            bits = extract(attacked, delta, block_size, freq)
            ok, _body = _decode_message(bits)
            ber = sum(1 for x, y in zip(bits, clean_bits, strict=True) if x != y) / len(bits)
            row["blur"][str(radius)] = {"ok": ok, "ber": round(ber, 4)}
        rows.append(row)
    best = [r for r in rows if r["clean_ok"] and all(v["ok"] for v in r["blur"].values())]
    return {"schema": SCHEMA, "size": SIZE, "seed": SEED, "payload": PAYLOAD.decode(),
            "repeat": REPEAT, "configs": len(rows), "rows": rows,
            "verdict": {"any_survives_screenshot": bool(best),
                        "survivors": [{"delta": r["delta"], "block": r["block"],
                                       "freq": r["freq"]} for r in best]},
            "conclusion": ("若 any_survives_screenshot=false：加大强度/降频/放大块都救不回拍屏，"
                           "边界成立（破坏性变换）；否则须复核可见性代价")}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def table_md(doc: dict[str, Any]) -> str:
    lines = ["| delta | 块 | 频段 | PSNR | 干净 | blur0.3 | blur0.6 | blur1.0 |",
             "|---|---|---|---|---|---|---|---|"]
    for row in doc["rows"]:
        blur = row["blur"]
        b3, b6, b10 = blur["0.3"], blur["0.6"], blur["1.0"]
        fmt = lambda cell, key: "✓" if cell["ok"] else f"✗ {cell[key]:.3f}"  # noqa: E731
        band = "中频" if row["freq"] == 0 else "低频"
        mark = "✓" if row["clean_ok"] else "✗"
        lines.append(
            f"| {row['delta']} | {row['block']} | {band} | {row['psnr_db']} | {mark} | "
            f"{fmt(b3, 'ber')} | {fmt(b6, 'ber')} | {fmt(b10, 'ber')} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="watermark_ecc_probe",
                                 description="拍屏水印第五轮探针（强度/块/频段扫描）")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--md", action="store_true")
    args = ap.parse_args(argv)
    doc = build_probe()
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write.write_text(dest, render(doc))
        print("OK 已写入 " + OUT_REL + "（配置 " + str(doc["configs"]) + " 组）")
        return 0
    if args.check:
        path = ROOT / OUT_REL
        if not path.is_file():
            print("缺 " + OUT_REL + "（" + GUIDE + "跑 --write）", file=sys.stderr)
            return 1
        if render(json_doc.load(path, dict, what=OUT_REL)) != render(doc):
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
