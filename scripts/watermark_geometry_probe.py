#!/usr/bin/env python3
"""几何提示同步探针：用「标签里记录的原始尺寸」替代频谱模板做几何同步。

为什么（2026-11-08）：上一轮证明固定块网格对不齐非整数重采样。本轮先验证一条**数学判断**：
周期模板的谱峰位置是「每图周期数」，对缩放**不变**（放大 0.85/1.1/1.25× 后峰仍在同一 bin），
所以周期/频谱模板**无法**估计缩放——这条被实测反例坐实。

于是换一条路：标签里本来就记录对象摘要，再记一个原始尺寸（geometry hint）即可反解缩放：
  ŝ = 当前宽高 / 记录宽高；把图缩回记录尺寸后再用块网格 + 偏移搜索解 payload。
翻译（裁剪）不用模板：payload 在块组上重复，偏移 0–7 搜索即可覆盖任意平移残差。

本探针测三件事：
① 谱峰不随缩放移动（反例，可复算）；
② 几何提示 + 关系嵌入能不能在 0.85–1.25× 缩放、裁剪 10%、拍屏下读回 payload；
③ 代价：PSNR 与「依赖元数据」这一前提。

纪律：确定性；输出 results/ccos/watermark_geometry_probe.json；负结果照样记录。
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

OUT_REL = "results/ccos/watermark_geometry_probe.json"
SCHEMA = "nf-watermark-geometry-probe/1"
SIZE = 256
SEED = 20261108
DELTA = 24.0
REPEAT = 8
PAYLOAD = b"NFGEO1"
SYNC_PERIODS = (16.0, 13.0)
GUIDE = "修复指引："
SCALES = (0.85, 0.9, 0.95, 1.0, 1.1, 1.25)
OFFSETS = tuple(range(8))


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
    return _bits_of(PAYLOAD + zlib.crc32(PAYLOAD).to_bytes(4, "big"))


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


def _set_pair(coeff, bit: int) -> None:
    a, b = (4, 5), (5, 4)
    mag = (abs(coeff[a]) + abs(coeff[b])) / 2
    hi, lo = mag + DELTA, max(0.0, mag - DELTA)
    sa = 1.0 if coeff[a] >= 0 else -1.0
    sb = 1.0 if coeff[b] >= 0 else -1.0
    if bit:
        coeff[a], coeff[b] = sa * lo, sb * hi
    else:
        coeff[a], coeff[b] = sa * hi, sb * lo


def _read_pair(coeff) -> int:
    return 0 if abs(coeff[4, 5]) > abs(coeff[5, 4]) else 1


def embed(data: bytes) -> tuple[bytes, dict[str, Any]]:
    np = _np()
    Image = _pil()
    m = _dct_matrix(8)
    ycc = np.asarray(Image.open(io.BytesIO(data)).convert("YCbCr"), dtype="float64")
    y = ycc[:, :, 0].copy()
    h, w = y.shape
    order = [(by, bx) for by in range(h // 8) for bx in range(w // 8)]
    msg = _message_bits()
    for idx, (by, bx) in enumerate(order):
        blk = y[by * 8:(by + 1) * 8, bx * 8:(bx + 1) * 8]
        coeff = m @ blk @ m.T
        _set_pair(coeff, msg[(idx // REPEAT) % len(msg)])
        y[by * 8:(by + 1) * 8, bx * 8:(bx + 1) * 8] = m.T @ coeff @ m
    ycc[:, :, 0] = np.clip(y, 0, 255)
    out = Image.fromarray(ycc.astype("uint8"), "YCbCr").convert("RGB")
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue(), {"geometry": [int(w), int(h)], "repeat": REPEAT,
                            "delta": DELTA, "payload_bits": len(msg)}


def _peaks(data: bytes) -> list[tuple[int, int]]:
    """谱峰（用于反例：缩放前后峰位置不变）。"""
    np = _np()
    Image = _pil()
    a = np.asarray(Image.open(io.BytesIO(data)).convert("L"), dtype="float64")
    a = a - a.mean()
    mag = np.abs(np.fft.fftshift(np.fft.fft2(a)))
    h, w = mag.shape
    cy, cx = h // 2, w // 2
    mag[cy - 2:cy + 3, cx - 2:cx + 3] = 0
    out: list[tuple[int, int]] = []
    for i in mag.ravel().argsort()[::-1][:60]:
        yy, xx = divmod(int(i), w)
        cand = (xx - cx, yy - cy)
        if any(abs(cand[0] - a2) < 3 and abs(cand[1] - b2) < 3 for a2, b2 in out):
            continue
        out.append(cand)
        if len(out) >= 5:
            break
    return out


def _decode_grid(y, rec_w: int, rec_h: int) -> dict[str, Any]:
    """在给定画布上做块网格 + 偏移搜索（0–7 覆盖任意平移残差）。"""
    m = _dct_matrix(8)
    msg = _message_bits()
    best = {"offset": (0, 0), "votes": [[0, 0] for _ in msg], "score": -1}
    for oy in OFFSETS:
        for ox in OFFSETS:
            votes = [[0, 0] for _ in msg]
            blocks_x = rec_w // 8
            for by in range((rec_h - oy) // 8):
                for bx in range((rec_w - ox) // 8):
                    y0, x0 = oy + by * 8, ox + bx * 8
                    blk = y[y0:y0 + 8, x0:x0 + 8]
                    if float(blk.std()) < 2.0:
                        continue          # 补边/空白块没有水印，不能计票
                    # 位序按**绝对块坐标**算（平移/补边不会错位）
                    bit_idx = (((by * blocks_x) + bx) // REPEAT) % len(msg)
                    coeff = m @ blk @ m.T
                    votes[bit_idx][_read_pair(coeff)] += 1
            conf = sum(max(v) for v in votes)
            if conf > best["score"]:
                ok, body = _decode_message([0 if v[0] >= v[1] else 1 for v in votes])
                best = {"offset": (ox, oy), "votes": votes, "score": conf,
                        "ok": ok, "body": body}
    bits = [0 if v[0] >= v[1] else 1 for v in best["votes"]]
    ok, body = _decode_message(bits)
    return {"ok": ok, "payload_exact": ok and body == PAYLOAD,
            "offset": list(best["offset"]), "vote_conf": best["score"],
            "vote_max": sum(max(v) for v in best["votes"])}


def _hypothesis_scale(y0, rec_w: int, rec_h: int, have: list[int]) -> Any:
    """假设 A：纯缩放 → 缩回记录尺寸。"""
    np = _np()
    Image = _pil()
    img = Image.fromarray(np.clip(y0, 0, 255).astype("uint8"), "L")
    return np.asarray(img.resize((rec_w, rec_h), Image.LANCZOS), dtype="float64")


def _hypothesis_crop(y0, rec_w: int, rec_h: int, have: list[int]) -> Any:
    """假设 B：纯居中裁剪 → 把内容贴回记录尺寸画布中央（空处补中位灰）。"""
    np = _np()
    canvas = np.full((rec_h, rec_w), float(np.median(y0)), dtype="float64")
    hh, ww = y0.shape
    oy = max(0, (rec_h - hh) // 2)
    ox = max(0, (rec_w - ww) // 2)
    hh2, ww2 = min(hh, rec_h - oy), min(ww, rec_w - ox)
    canvas[oy:oy + hh2, ox:ox + ww2] = y0[:hh2, :ww2]
    return canvas


def decode(data: bytes, geometry: list[int]) -> dict[str, Any]:
    """几何提示同步：缩放/裁剪两种假设都试，用 CRC 成功与票数裁决。"""
    np = _np()
    Image = _pil()
    img = Image.open(io.BytesIO(data)).convert("YCbCr")
    y0 = np.asarray(img, dtype="float64")[:, :, 0]
    have = [int(img.width), int(img.height)]
    rec_w, rec_h = int(geometry[0]), int(geometry[1])
    hypotheses: list[tuple[str, Any]] = []
    if abs(have[0] - rec_w) <= 1 and abs(have[1] - rec_h) <= 1:
        hypotheses.append(("same", y0))
    else:
        hypotheses.append(("scale", _hypothesis_scale(y0, rec_w, rec_h, have)))
        hypotheses.append(("crop", _hypothesis_crop(y0, rec_w, rec_h, have)))
    best = None
    for name, canvas in hypotheses:
        res = _decode_grid(canvas, rec_w, rec_h)
        res["hypothesis"] = name
        if best is None or (res["ok"], res["vote_conf"]) > (best["ok"], best["vote_conf"]):
            best = res
    best["scale_est"] = [round(have[0] / rec_w, 4), round(have[1] / rec_h, 4)]
    return best


def psnr(a: bytes, b: bytes) -> float:
    np = _np()
    Image = _pil()
    x = np.asarray(Image.open(io.BytesIO(a)).convert("RGB"), dtype="float64")
    y = np.asarray(Image.open(io.BytesIO(b)).convert("RGB"), dtype="float64")
    mse = float(((x - y) ** 2).mean())
    return 99.0 if mse == 0 else float(10 * np.log10((255.0 ** 2) / mse))


def _template_image(data: bytes) -> bytes:
    """加周期模板（用于反例：谱峰不随缩放移动）。"""
    np = _np()
    Image = _pil()
    luma = np.asarray(Image.open(io.BytesIO(data)).convert("L"), dtype="float64")
    h, w = luma.shape
    ys, xs = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    amp = 6.0
    tpl = amp * (np.cos(2 * np.pi * xs / SYNC_PERIODS[0])
                 + np.cos(2 * np.pi * ys / SYNC_PERIODS[1]))
    buf = io.BytesIO()
    Image.fromarray(np.clip(luma + tpl, 0, 255).astype("uint8"), "L").save(buf, "PNG")
    return buf.getvalue()


def build_probe() -> dict[str, Any]:
    import watermark_bench as bench

    base = bench._base_png()
    marked, info = embed(base)
    geometry = info["geometry"]
    clean = decode(marked, geometry)
    rows = []
    attacks = (
        ("scale_0.85", "缩放 0.85×", lambda d: bench._resize(d, 0.85)),
        ("scale_0.9", "缩放 0.9×", lambda d: bench._resize(d, 0.9)),
        ("scale_0.95", "缩放 0.95×", lambda d: bench._resize(d, 0.95)),
        ("scale_1.1", "放大 1.1×", lambda d: bench._resize(d, 1.1)),
        ("scale_1.25", "放大 1.25×", lambda d: bench._resize(d, 1.25)),
        ("crop_10", "裁剪 10%", lambda d: bench._crop(d, 0.9)),
        ("jpeg_70", "JPEG q=70", lambda d: bench._jpeg_roundtrip(d, 70)),
        ("screenshot_sim", "模拟拍屏", lambda d: bench._screenshot_sim(d)),
    )
    for aid, desc, attack in attacks:
        attacked = attack(marked)
        res = decode(attacked, geometry)
        rows.append({"id": aid, "desc": desc, "ok": res["ok"],
                     "payload_exact": res["payload_exact"],
                     "scale_est": res["scale_est"], "offset": res["offset"],
                     "vote_conf": res["vote_conf"], "vote_max": res["vote_max"]})
    # 反例：谱峰不随缩放移动
    templated = _template_image(base)
    expect = {(int(SYNC_PERIODS[0]), 0), (-int(SYNC_PERIODS[0]), 0),
              (0, int(SIZE / SYNC_PERIODS[1])), (0, -int(SIZE / SYNC_PERIODS[1]))}

    def _template_present(data: bytes) -> bool:
        peaks = _peaks(data)
        return all(any(abs(p[0] - e[0]) <= 1 and abs(p[1] - e[1]) <= 1 for p in peaks)
                   for e in expect)

    peak_rows = [{"scale": 1.0, "peaks": _peaks(templated),
                  "template_present": _template_present(templated)}]
    for s in (0.85, 1.1, 1.25):
        scaled = bench._resize(templated, s)
        peak_rows.append({"scale": s, "peaks": _peaks(scaled),
                          "template_present": _template_present(scaled)})
    # 若缩放后模板峰仍在同一 bin（且仍在场），就说明谱峰对缩放不变
    moved = not all(row["template_present"] for row in peak_rows)
    return {"schema": SCHEMA, "size": SIZE, "seed": SEED, "delta": DELTA,
            "repeat": REPEAT, "payload": PAYLOAD.decode("ascii", "replace"),
            "geometry": geometry, "info": info,
            "clean": {"ok": clean["ok"], "psnr_db": round(psnr(base, marked), 2)},
            "attacks": rows,
            "template_invariance": {"rows": peak_rows,
                                    "peaks_moved": bool(moved),
                                    "note": "若 peaks_moved=False，则周期/频谱模板"
                                            "无法估缩放（数学必然）"},
            "conclusion": "几何提示（记录尺寸）能不能替代频谱模板做缩放同步，看 attacks 里 ok"}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def table_md(doc: dict[str, Any]) -> str:
    lines = ["| 攻击 | 解码 | 缩放估计 | 偏移 | 票数 |", "|---|---|---|---|---|"]
    lines.append("| 干净图 | " + ("✓" if doc["clean"]["ok"] else "✗") + " | 1.0 | — | PSNR "
                 + str(doc["clean"]["psnr_db"]) + " dB |")
    for row in doc["attacks"]:
        lines.append("| " + row["desc"] + " | " + ("✓" if row["ok"] else "✗") + " | "
                     + str(row["scale_est"]) + " | " + str(row["offset"]) + " | "
                     + str(row["vote_conf"]) + "/" + str(row["vote_max"]) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="watermark_geometry_probe",
                                 description="几何提示同步探针（尺寸反解 + 偏移搜索）")
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
