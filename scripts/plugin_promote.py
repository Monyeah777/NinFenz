#!/usr/bin/env python3
"""晋升门取数入口（P5-10）：真测量 → 第三部分仲裁 → 三判据判定。

流程（每一步都有「缺席即如实记录」的分支，绝不把没测的说成测过）：

  1) 装载   清单校验 + WIT 对账 + 产物在场（缺一即 toolchain.available=false）
  2) 造料   确定性测试输入（默认 32 MiB），落 <NF_HOME>/cache/plugin-promote/（不入库）
  3) 测量   Python 参考 vs 插件，各跑 --repeat 次取**最小值**（子进程计时，含启动成本）
  4) 仲裁   把「字节等价」做成一条真向量，交给 scripts/cross_lang_verify.py 的三态 + 仲裁机制
  5) 判定   core.plugin_gate.decide：三条判据缺一不可

**允许判不通过**（§18.2：按测得成本分配语言）。wasm 沙箱有启动与边界成本，插件并不天然更快；
门若因此拒绝晋升，那是门的正确工作，报告里会带全部数字与理由。
"""
import argparse
import hashlib
import json
import os
import subprocess  # nosec B404 - 只跑本仓声明的产物与在场工具链
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import cross_lang_verify as clv  # noqa: E402
import plugin_host as host  # noqa: E402
from core import plugin_gate as pg  # noqa: E402

REF_CMD = ["python", "scripts/plugin_reference.py", "--method", "sha256"]


def cache_dir(root: Path = ROOT) -> Path:
    """私有缓存目录（测试输入不入库）。"""
    home = os.environ.get("NF_HOME")
    base = Path(home) if home else (root / ".rivet" / "scratch")
    d = base / "plugin-promote"
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_input(size: int, root: Path = ROOT) -> Path:
    """确定性的测试输入：同一 size 必得同一字节（否则「取数可复算」不成立）。"""
    seed = b"ninfenz-plugin-promote\n"
    body = (seed * (size // len(seed) + 1))[:size]
    p = cache_dir(root) / f"input-{size}.bin"
    if not p.is_file() or p.stat().st_size != size:
        p.write_bytes(body)
    return p


def _time(argv, data: bytes, repeat: int, root: Path):
    """跑 repeat 次取最小墙钟（毫秒）；任一非零退出即返回 None（不比较成败不对等的耗时）。"""
    best = None
    for _ in range(max(1, repeat)):
        started = time.perf_counter()
        try:
            proc = subprocess.run([str(x) for x in argv], cwd=str(root), input=data,  # nosec B603
                                  capture_output=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        dt = (time.perf_counter() - started) * 1000.0
        best = dt if best is None else min(best, dt)
    return best


def measure(size: int, repeat: int, resolution, root: Path = ROOT):
    """→ (evidence 片段, 细节 dict)。"""
    fixture = make_input(size, root)
    data = fixture.read_bytes()
    detail = {"input_bytes": size, "input_sha256": hashlib.sha256(data).hexdigest(),
              "repeat": repeat, "fixture": fixture.as_posix()}

    loaded = resolution
    doc, artifact, wasmtime = loaded["doc"], loaded["artifact"], loaded["wasmtime"]
    ref_ms = _time([resolution["python"], *REF_CMD[1:]], data, repeat, root)
    detail["baseline_ms"] = ref_ms
    if not (wasmtime and artifact and Path(artifact).is_file()):
        return {"baseline_ms": ref_ms, "plugin_ms": None,
                "arbitration": {"outcome": "UNKNOWN", "comparable": 0},
                "toolchain": {"available": False, "kind": "wasm32-wasip1+wasmtime",
                              "toolchain_cost": 1}}, detail

    entry = host.pm.method(doc, "sha256") or {}
    fuel = host.fuel_for(entry, len(data))
    detail["fuel"] = fuel
    plug_argv = host.isolation_argv(wasmtime, Path(artifact), fuel, 120000)
    plug_ms = _time(plug_argv, data, repeat, root)
    detail["plugin_ms"] = plug_ms
    detail["plugin_argv"] = [str(x) for x in plug_argv]

    expected = hashlib.sha256(data).hexdigest()
    vector = {"schema": "nf-test-vectors/1", "vectors": [{
        "id": "plugin/sha256-byte-equivalence", "spec_clause": "P5-10.2", "level": "L1",
        "input": fixture.as_posix(), "compare_rule": "byte", "expected": expected + "\n",
        "langs": {
            "python": {"cmd": [resolution["python"], *REF_CMD[1:]], "stdin": fixture.as_posix()},
            "wasm": {"cmd": plug_argv, "stdin": fixture.as_posix()}}}]}
    rep = clv.verify(vector, root=str(root),
                     tools={"python": resolution["python"], "wasm": wasmtime})
    detail["cross_lang"] = rep["vectors"][0]
    detail["artifact_sha256"] = hashlib.sha256(Path(artifact).read_bytes()).hexdigest()
    return {"face": "sha256", "baseline_ms": ref_ms, "plugin_ms": plug_ms,
            "arbitration": rep["arbitration"],
            "toolchain": {"available": True, "kind": "wasm32-wasip1+wasmtime",
                          "toolchain_cost": 1}}, detail


def resolve(root: Path = ROOT):
    """装载 + 工具链解析（缺席不抛，如实返回 None）。"""
    doc, issues, artifact = host.load_declared(root=root)
    return {"doc": doc, "issues": issues, "artifact": artifact,
            "wasmtime": host.resolve_wasmtime(),
            "python": clv.resolve_exe("python", ["--version"]),
            "wit_ok": not [i for i in issues if "WIT" in i]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="插件晋升门取数（只读；允许判不通过）")
    ap.add_argument("--size", type=int, default=32 * 1024 * 1024, help="测试输入字节数")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--require-promoted", action="store_true", help="未晋升即 exit 1")
    args = ap.parse_args(argv)

    res = resolve(ROOT)
    if res["issues"]:
        print("装载被拒：\n  " + "\n  ".join(res["issues"]), file=sys.stderr)
        return 2
    ev, detail = measure(args.size, args.repeat, res, ROOT)
    report = pg.decide(ev)
    report["detail"] = detail
    report["manifest_ok"] = True
    report["wit_ok"] = res["wit_ok"]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        verdict_text = "晋升" if report["promoted"] else "不晋升"
        print(f"== 插件晋升门（{verdict_text}）==")
        for name, c in sorted(report["criteria"].items()):
            mark = "OK" if c["ok"] else "NG"
            print(f"  {mark} {name:<17} {c['detail']}")
        print(f"  测：基线 {detail.get('baseline_ms')} ms · 插件 {detail.get('plugin_ms')} ms"
              f" · 加速 {report['measured']['speedup']}×")
        for r in report["reasons"]:
            print(f"  理由：{r}")
    return 1 if (args.require_promoted and not report["promoted"]) else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
