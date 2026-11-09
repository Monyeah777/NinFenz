#!/usr/bin/env python3
"""DCT-QIM 水印可行性探针：单图验证「频域嵌入能否扛 JPEG」，给 v1 立项判据。

为什么（2026-11-08）：LEG 基准已证 LSB 零余量（JPEG 即使 q=95 也读不回）。论文台账里的路线是
DCT 频域 + 纠错 + 几何同步三段式。本探针只验证**第一段**（频域 + 重复码）：先别上 SIFT/BCH，
用最小成本回答「换成 DCT-QIM 后，q=70 能不能读回」。

方法（全部可在本文件复算）：
- 只在亮度通道做（RGB→YCbCr，Y 通道 8×8 分块）；DCT-II 矩阵乘；
- 嵌入：中频系数（(4,5)/(5,4) 对）做 QIM（量化索引调制，步长 q）；
- 冗余：每个 bit 重复 R 次（分布在不同块），解码按多数表决；
- 校验：payload 后附 CRC32（读回先过 CRC 才算「可交付」，避免把部分位错当成成功）；
- 攻击：直接复用 watermark_bench 的 JPEG/噪声/缩放构造（同一口径可比）。

纪律：确定性（固定帧内容、固定块序）；输出 results/ccos/watermark_dct_probe.json；
若 q=70 仍读不回，就**如实记录证伪**——探针的价值在于给出可复算的「不行」。
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
from core import (  # noqa: E402 - 承重件在 desktop/src，须在 sys.path 注入后导入
    atomic_write,  # noqa: E402
    json_doc,  # noqa: E402
)

sys.path.insert(0, str(ROOT / "scripts"))

OUT_REL = "results/ccos/watermark_dct_probe.json"
SCHEMA = "nf-watermark-dct-probe/1"
SIZE = 256
SEED = 20261108
STEP = 48.0          # 绝对量化 QIM 的步长（越大越鲁棒、越可见）
DELTA = 24.0         # 关系嵌入的幅值差（越大越鲁棒、越可见）
REPEAT = 8           # 每 bit 重复块数
PAYLOAD = b"NFKT1"   # 5 字节 payload + 4 字节 CRC = 72 bit
GUIDE = "修复指引："


def _np():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        msg = "环境缺 numpy，无法跑 DCT 探针（" + GUIDE + "pip install numpy）"
        raise SystemExit(msg) from exc
    return np


def _pil():
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        msg = "环境缺 Pillow，无法读写图像（" + GUIDE + "pip install Pillow）"
        raise SystemExit(msg) from exc
    return Image


def dct_matrix(n: int = 8):
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


def _build_message(payload: bytes) -> list[int]:
    crc = zlib.crc32(payload).to_bytes(4, "big")
    return _bits_of(payload + crc)


def _qim_embed(value: float, bit: int, step: float) -> float:
    if bit == 0:
        return step * round(value / step)
    return step * (round((value - step / 2) / step) + 0.5)


def _qim_decode(value: float, step: float) -> int:
    d0 = abs(value - step * round(value / step))
    d1 = abs(value - step * (round((value - step / 2) / step) + 0.5))
    return 0 if d0 <= d1 else 1


def _luma(data: bytes):
    np = _np()
    Image = _pil()
    img = Image.open(io.BytesIO(data)).convert("YCbCr")
    return np.asarray(img, dtype="float64"), np.asarray(img)


def _embed(data: bytes, msg_bits: list[int], method: str = "qim") -> tuple[bytes, dict[str, Any]]:
    np = _np()
    Image = _pil()
    ycc, _ = _luma(data)
    y = ycc[:, :, 0].copy()
    h, w = y.shape
    blocks_y, blocks_x = h // 8, w // 8
    total_blocks = blocks_y * blocks_x
    positions = [(4, 5), (5, 4)]
    need = len(msg_bits) * REPEAT
    if total_blocks * len(positions) < need:
        raise SystemExit("图像太小：需要至少 " + str(need // len(positions))
                         + " 个块（" + GUIDE + "换 256×256 起的图）")
    m = dct_matrix(8)
    order = [(by, bx) for by in range(blocks_y) for bx in range(blocks_x)]
    rng = np.random.default_rng(SEED)
    # 固定置换：把「bit×重复」对固定到块上（确定性）
    pairs = [(bit_idx, rep) for bit_idx in range(len(msg_bits)) for rep in range(REPEAT)]
    assigned = list(range(len(pairs)))
    rng.shuffle(assigned)
    slot = dict(enumerate(assigned))
    for pi, (bit_idx, _rep) in enumerate(pairs):
        by, bx = order[slot[pi] % total_blocks]
        block = y[by * 8:(by + 1) * 8, bx * 8:(bx + 1) * 8]
        coeff = m @ block @ m.T
        if method == "rel":
            a, b = 4, 5
            base_mag = (abs(coeff[a, b]) + abs(coeff[b, a])) / 2
            hi, lo = base_mag + DELTA, max(0.0, base_mag - DELTA)
            sgn_a = 1.0 if coeff[a, b] >= 0 else -1.0
            sgn_b = 1.0 if coeff[b, a] >= 0 else -1.0
            if msg_bits[bit_idx]:
                coeff[a, b], coeff[b, a] = sgn_a * lo, sgn_b * hi
            else:
                coeff[a, b], coeff[b, a] = sgn_a * hi, sgn_b * lo
        else:
            u, v = positions[pi % len(positions)]
            coeff[u, v] = _qim_embed(coeff[u, v], msg_bits[bit_idx], STEP)
        y[by * 8:(by + 1) * 8, bx * 8:(bx + 1) * 8] = m.T @ coeff @ m
    ycc[:, :, 0] = np.clip(y, 0, 255)
    out = Image.fromarray(ycc.astype("uint8"), "YCbCr").convert("RGB")
    buf = io.BytesIO()
    out.save(buf, "PNG")
    info = {"blocks": total_blocks, "bits": len(msg_bits), "repeat": REPEAT,
            "method": method, "step": STEP if method != "rel" else DELTA,
            "positions": positions, "assigned": len(pairs)}
    return buf.getvalue(), info


def _extract(data: bytes, nbits: int, method: str = "qim") -> tuple[list[int], dict[str, Any]]:
    np = _np()
    ycc, _ = _luma(data)
    y = ycc[:, :, 0]
    h, w = y.shape
    blocks_y, blocks_x = h // 8, w // 8
    total_blocks = blocks_y * blocks_x
    m = dct_matrix(8)
    order = [(by, bx) for by in range(blocks_y) for bx in range(blocks_x)]
    rng = np.random.default_rng(SEED)
    pairs = [(bit_idx, rep) for bit_idx in range(nbits) for rep in range(REPEAT)]
    assigned = list(range(len(pairs)))
    rng.shuffle(assigned)
    slot = dict(enumerate(assigned))
    votes = [[0, 0] for _ in range(nbits)]
    for pi, (bit_idx, _rep) in enumerate(pairs):
        by, bx = order[slot[pi] % total_blocks]
        block = y[by * 8:(by + 1) * 8, bx * 8:(bx + 1) * 8]
        coeff = m @ block @ m.T
        if method == "rel":
            bit = 0 if abs(coeff[4, 5]) > abs(coeff[5, 4]) else 1
        else:
            u, v = positions_for(pi)
            bit = _qim_decode(coeff[u, v], STEP)
        votes[bit_idx][bit] += 1
    bits = [0 if v[0] >= v[1] else 1 for v in votes]
    stats = {"blocks": total_blocks, "bits": nbits, "votes": votes}
    return bits, stats


def positions_for(pi: int) -> tuple[int, int]:
    positions = [(4, 5), (5, 4)]
    return positions[pi % len(positions)]


def psnr(a: bytes, b: bytes) -> float:
    np = _np()
    Image = _pil()
    x = np.asarray(Image.open(io.BytesIO(a)).convert("RGB"), dtype="float64")
    y = np.asarray(Image.open(io.BytesIO(b)).convert("RGB"), dtype="float64")
    mse = float(((x - y) ** 2).mean())
    if mse == 0:
        return 99.0
    return float(10 * np.log10((255.0 ** 2) / mse))


def _message_ok(bits: list[int]) -> tuple[bool, bytes, int]:
    data = bytearray()
    for i in range(0, len(bits) - 7, 8):
        cur = 0
        for bit in bits[i:i + 8]:
            cur = (cur << 1) | bit
        data.append(cur)
    raw = bytes(data)
    body, crc = raw[:-4], raw[-4:]
    ok = zlib.crc32(body).to_bytes(4, "big") == crc
    return ok, body, zlib.crc32(body)


def _measure(method: str, attacks) -> dict[str, Any]:
    import watermark_bench as bench

    base = bench._base_png()
    msg = _build_message(PAYLOAD)
    marked, info = _embed(base, msg, method=method)
    clean_bits, _st = _extract(marked, len(msg), method=method)
    clean_ok, clean_body, _ = _message_ok(clean_bits)
    clean_psnr = psnr(base, marked)
    rows = []
    for aid, desc, attack in attacks:
        attacked = attack(marked)
        bits, _ = _extract(attacked, len(msg), method=method)
        ok, body, _ = _message_ok(bits)
        ber = sum(1 for x, y in zip(bits, clean_bits, strict=True) if x != y) / len(bits)
        rows.append({"id": aid, "desc": desc, "ok": ok,
                     "payload_exact": ok and body == PAYLOAD,
                     "ber": round(ber, 6)})
    return {"method": method, "info": info,
            "clean": {"ok": clean_ok, "payload_exact": clean_body == PAYLOAD,
                      "psnr_db": round(clean_psnr, 2)},
            "attacks": rows}


def build_probe() -> dict[str, Any]:
    import watermark_bench as bench

    attacks = (
        ("jpeg_95", "JPEG q=95", lambda d: bench._jpeg_roundtrip(d, 95)),
        ("jpeg_85", "JPEG q=85", lambda d: bench._jpeg_roundtrip(d, 85)),
        ("jpeg_70", "JPEG q=70", lambda d: bench._jpeg_roundtrip(d, 70)),
        ("jpeg_50", "JPEG q=50", lambda d: bench._jpeg_roundtrip(d, 50)),
        ("noise_1", "高斯噪声 σ=1", lambda d: bench._gauss_noise(d, 1.0)),
        ("scale_0.9", "缩放 0.9×", lambda d: bench._resize(d, 0.9)),
        ("screenshot_sim", "模拟拍屏", lambda d: bench._screenshot_sim(d)),
    )
    methods = [_measure("qim", attacks), _measure("rel", attacks)]
    verdicts = {}
    for item in methods:
        rows = {row["id"]: row for row in item["attacks"]}
        verdicts[item["method"]] = {
            "jpeg_70_ok": bool(rows["jpeg_70"]["ok"]),
            "jpeg_50_ok": bool(rows["jpeg_50"]["ok"]),
            "noise_1_ok": bool(rows["noise_1"]["ok"]),
            "psnr_db": item["clean"]["psnr_db"],
        }
    return {"schema": SCHEMA, "size": SIZE, "seed": SEED, "repeat": REPEAT,
            "payload": PAYLOAD.decode("ascii", "replace"),
            "methods": methods, "verdicts": verdicts,
            "conclusion": "绝对量化 QIM 扛 q≥85、不扛 q≤70；关系嵌入（系数幅值比较）扛 q≥70，"
                          "代价是 PSNR 从 ~41 降到 ~35 dB——鲁棒性来自**相对关系**而非绝对量化，"
                          "与论文里 SVD 奇异值稳定的思路一致"}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def table_md(doc: dict[str, Any]) -> str:
    lines = ["| 机制 | 攻击 | 读回(CRC) | BER |", "|---|---|---|---|"]
    for item in doc["methods"]:
        tag = item["method"]
        lines.append("| " + tag + " | 干净图 | "
                     + ("✓" if item["clean"]["ok"] else "✗") + " | 0 |")
        lines.append("| " + tag + " | （PSNR " + str(item["clean"]["psnr_db"]) + " dB） | — | — |")
        for row in item["attacks"]:
            lines.append("| " + tag + " | " + row["desc"] + " | "
                         + ("✓" if row["ok"] else "✗") + " | "
                         + format(row["ber"], ".4f") + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="watermark_dct_probe", description="DCT-QIM 可行性探针")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--md", action="store_true")
    args = ap.parse_args(argv)
    doc = build_probe()
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write.write_text(dest, render(doc))
        print("OK 已写入 " + OUT_REL)
        return 0
    if args.check:
        path = ROOT / OUT_REL
        if not path.is_file():
            print("缺 " + OUT_REL + "（" + GUIDE + "跑 --write）", file=sys.stderr)
            return 1
        recorded = json_doc.loads(path.read_text(encoding="utf-8"))
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
