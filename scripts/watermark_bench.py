#!/usr/bin/env python3
"""水印鲁棒性基准：把「抗/不抗」从形容词变成 BER 表（攻击矩阵 × 误码率）。

为什么（2026-11-08）：PNG 低位水印在文档里写「不承诺抗 JPEG/缩放/截屏」——但「不承诺」不是判据。
本基准按方法包 watermarking 的证据标准做实测：
- 攻击矩阵：无损重存 / 裁剪(10/25/50%) / 缩放(0.5–2×) / JPEG(q=95/85/70/50) / 高斯噪声(σ=1,3)
  / 亮度 / 模拟拍屏（缩放+轻微模糊+JPEG）；
- 每条攻击给出：是否读回（ok）、BER（误码率）、payload 是否逐字节一致；
- 结果落 results/ccos/watermark_bench.json（确定性：固定随机图 + 固定参数 + 排序），
  --md 时输出可贴文档的表。

纪律：deterministic（同输入两次逐字节一致）；Pillow 是软依赖，缺了明确报错（不静默降级）。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

OUT_REL = "results/ccos/watermark_bench.json"
SCHEMA = "nf-watermark-bench/1"
PAYLOAD = b'{"v":1,"schema":"nf-label/1","items":["E1","I2"]}'
SIZE = 256
SEED = 20261108
GUIDE = "修复指引："


def _pil():
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 环境缺 Pillow
        msg = "环境缺 Pillow，无法跑水印基准（" + GUIDE + "pip install Pillow）"
        raise SystemExit(msg) from exc
    return Image


def _np():
    """软导入 numpy：攻击矩阵里的噪声/亮度要按像素算。缺依赖 fail-closed 并给指引。"""
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - 环境缺 numpy
        msg = "环境缺 numpy，无法构造噪声/亮度攻击（" + GUIDE + "pip install numpy）"
        raise SystemExit(msg) from exc
    return np


def _base_png() -> bytes:
    Image = _pil()
    np = _np()
    arr = np.random.default_rng(SEED).integers(0, 256, (SIZE, SIZE, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, "PNG")
    return buf.getvalue()


def _to_png(img, **save_kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", **save_kw)
    return buf.getvalue()


def _jpeg_roundtrip(data: bytes, quality: int) -> bytes:
    Image = _pil()
    buf = io.BytesIO()
    Image.open(io.BytesIO(data)).convert("RGB").save(buf, "JPEG", quality=quality)
    return _to_png(Image.open(buf))


def _resize(data: bytes, factor: float) -> bytes:
    Image = _pil()
    img = Image.open(io.BytesIO(data))
    size = (max(1, int(img.width * factor)), max(1, int(img.height * factor)))
    return _to_png(img.resize(size, Image.LANCZOS))


def _crop(data: bytes, keep: float) -> bytes:
    Image = _pil()
    img = Image.open(io.BytesIO(data))
    w = int(img.width * keep)
    h = int(img.height * keep)
    left = (img.width - w) // 2
    top = (img.height - h) // 2
    return _to_png(img.crop((left, top, left + w, top + h)))


def _gauss_noise(data: bytes, sigma: float) -> bytes:
    Image = _pil()
    np = _np()
    arr = np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).astype("float32")
    rng = np.random.default_rng(SEED)
    noisy = np.clip(arr + rng.normal(0, sigma, arr.shape), 0, 255).astype("uint8")
    return _to_png(Image.fromarray(noisy, "RGB"))


def _brightness(data: bytes, factor: float) -> bytes:
    Image = _pil()
    np = _np()
    arr = np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).astype("float32")
    out = np.clip(arr * factor, 0, 255).astype("uint8")
    return _to_png(Image.fromarray(out, "RGB"))


def _screenshot_sim(data: bytes) -> bytes:
    """模拟拍屏：先缩到 0.9×（屏幕采样），再轻微模糊，再 JPEG q=80。"""
    Image = _pil()
    try:
        from PIL import ImageFilter
    except ImportError as exc:  # pragma: no cover - 环境缺 Pillow
        msg = "环境缺 Pillow 的 ImageFilter（" + GUIDE + "pip install Pillow）"
        raise SystemExit(msg) from exc
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img = img.resize((int(img.width * 0.9), int(img.height * 0.9)), Image.LANCZOS)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return _to_png(Image.open(buf))


ATTACKS: tuple[tuple[str, str, Any], ...] = (
    ("lossless_resave", "无损重存（PNG）", lambda d: _to_png(_pil().open(io.BytesIO(d)))),
    ("crop_10", "裁剪 10%（中心）", lambda d: _crop(d, 0.9)),
    ("crop_25", "裁剪 25%（中心）", lambda d: _crop(d, 0.75)),
    ("crop_50", "裁剪 50%（中心）", lambda d: _crop(d, 0.5)),
    ("scale_0.5", "缩放 0.5×", lambda d: _resize(d, 0.5)),
    ("scale_0.75", "缩放 0.75×", lambda d: _resize(d, 0.75)),
    ("scale_1.5", "放大 1.5×", lambda d: _resize(d, 1.5)),
    ("scale_2", "放大 2×", lambda d: _resize(d, 2.0)),
    ("jpeg_95", "JPEG q=95 重编码", lambda d: _jpeg_roundtrip(d, 95)),
    ("jpeg_85", "JPEG q=85 重编码", lambda d: _jpeg_roundtrip(d, 85)),
    ("jpeg_70", "JPEG q=70 重编码", lambda d: _jpeg_roundtrip(d, 70)),
    ("jpeg_50", "JPEG q=50 重编码", lambda d: _jpeg_roundtrip(d, 50)),
    ("noise_1", "高斯噪声 σ=1", lambda d: _gauss_noise(d, 1.0)),
    ("noise_3", "高斯噪声 σ=3", lambda d: _gauss_noise(d, 3.0)),
    ("bright_1.05", "亮度 ×1.05", lambda d: _brightness(d, 1.05)),
    ("screenshot_sim", "模拟拍屏（0.9× + blur + q=80）", lambda d: _screenshot_sim(d)),
)


def build_bench() -> dict[str, Any]:
    from core import label_watermark

    base = _base_png()
    marked, info = label_watermark.embed(base, PAYLOAD)
    rows = []
    for aid, desc, attack in ATTACKS:
        attacked = attack(marked)
        res = label_watermark.extract_with_bits(attacked)
        rows.append({
            "id": aid, "desc": desc,
            "ok": bool(res["ok"]),
            "ber": res["ber"],
            "payload_exact": bool(res["ok"] and res["payload"] == PAYLOAD),
            "bytes": len(attacked),
        })
    clean = label_watermark.extract_with_bits(marked)
    return {"schema": SCHEMA, "watermark": "png-lsb", "tile": info["tile"],
            "redundancy": info["redundancy"], "payload_bytes": len(PAYLOAD),
            "frame_bits": clean["frame_bits"], "seed": SEED, "size": SIZE,
            "baseline": {"ok": bool(clean["ok"]), "ber": clean["ber"]},
            "attacks": rows,
            "note": "BER=None 表示读不出帧（与「帧全错」不同）；payload_exact 才是可交付判定"}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def table_md(doc: dict[str, Any]) -> str:
    lines = ["| 攻击 | 读回 | BER | payload 一致 |", "|---|---|---|---|"]
    for row in doc["attacks"]:
        ber = "—" if row["ber"] is None else format(row["ber"], ".4f")
        lines.append("| " + row["desc"] + " | " + ("✓" if row["ok"] else "✗") + " | "
                     + ber + " | " + ("✓" if row["payload_exact"] else "✗") + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="watermark_bench", description="水印鲁棒性基准（BER 表）")
    ap.add_argument("--write", action="store_true", help="写入 results/ccos/watermark_bench.json")
    ap.add_argument("--check", action="store_true", help="校验提交件 == 重算")
    ap.add_argument("--md", action="store_true", help="打印 markdown 表")
    args = ap.parse_args(argv)
    doc = build_bench()
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(doc), encoding="utf-8")
        print("OK 已写入 " + OUT_REL + "（" + str(len(doc["attacks"])) + " 条攻击）")
        return 0
    if args.check:
        path = ROOT / OUT_REL
        if not path.is_file():
            print("缺 " + OUT_REL + "（" + GUIDE + "跑 --write）", file=sys.stderr)
            return 1
        recorded = json.loads(path.read_text(encoding="utf-8"))
        if render(recorded) != render(doc):
            print("基准结果与重算不一致（" + GUIDE + "重跑 --write 后提交）", file=sys.stderr)
            return 1
        print("OK 基准与重算一致")
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
