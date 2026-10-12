#!/usr/bin/env python3
"""热面剖析取数（P5-09）：cProfile 确定性取数 + py-spy 采样 + hyperfine 基准。

为什么三条都要：计划 §20.5 的 P5-09 细分正是这三件，且三者**不可互替**：
  - cProfile  —— 确定性、逐函数调用次数（可复算的排名地基）；
  - py-spy    —— 采样，不侵入被测进程，能看真热点（cProfile 的插桩会改变时间分布）；
  - hyperfine —— 端到端墙钟基准，带预热与多次取统计（进程启动成本也进账）。
「按测得成本分配语言」（§18.2）要的是这三样一起，而不是其中一样。

工具缺席的姿态（三态口径）：逐工具解析在场与否并**如实呈现**，不假装用过；
解析顺序 PATH → NF_TOOLCHAIN_DIRS → ~/.nftools/<tool>/（与对拍器同一套兜底）。

用法：
    python scripts/hotspot_profile.py --target core.coupling_metrics:scan --arg . --top 15
    python scripts/hotspot_profile.py --sample core.coupling_metrics:scan --arg . --seconds 5
    python scripts/hotspot_profile.py --benchmark "python scripts/jcs.py --file x" \
        "engine/rust/canonical/target/release/nf-canonical --file x"
    python scripts/hotspot_profile.py --self-test
"""
import argparse
import cProfile
import importlib
import json
import os
import shutil
import subprocess  # nosec B404 - 只跑本仓声明过的目标与在场工具链
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import json_doc  # noqa: E402 - 读 JSON 走仓库唯一读点

#: 剖析三件套：cProfile 是 stdlib（恒在），另两件是外部工具（可能缺席）。
STDLIB_TOOL = "cProfile"
EXTERNAL_TOOLS = ("py-spy", "hyperfine")
NFTOOLS = Path.home() / ".nftools"
ENV_DIRS = "NF_TOOLCHAIN_DIRS"
#: 默认目标：耦合度量扫全 core 模块（check12 里的真实一面，成本中等、确定性好）。
DEFAULT_TARGET = "core.coupling_metrics:scan"
DEFAULT_OUT = ".rivet/scratch/profile"


def resolve_tool(name: str) -> str | None:
    """按名解析外部工具：PATH 优先，其后 NF_TOOLCHAIN_DIRS 与 ~/.nftools/<tool>/。"""
    found = shutil.which(name)
    if found:
        return found
    dirs = [p for p in (os.environ.get(ENV_DIRS) or "").split(os.pathsep) if p]
    dirs.append(str(NFTOOLS / name))
    dirs.append(str(NFTOOLS))
    names = [name, name + ".exe"] if os.name == "nt" else [name]
    for base in dirs:
        for cand in names:
            path = Path(base) / cand
            if path.is_file():
                return str(path)
    return None


def tool_state() -> dict[str, str | None]:
    """→ {工具: 路径或 None}——缺席如实记，不许假装用过。"""
    state = {STDLIB_TOOL: "stdlib"}
    state.update({name: resolve_tool(name) for name in EXTERNAL_TOOLS})
    return state


def entry_of(stat: Any) -> dict[str, Any]:
    """pstats 条目 → 规整 dict（字段名跨版本变动，故用 getattr 兜底并显式命名）。"""
    code = getattr(stat, "code", None)
    key = f"{getattr(code, 'co_filename', '?')}:{getattr(code, 'co_name', '?')}"
    return {
        "key": key,
        "calls": int(getattr(stat, "callcount", 0) or 0),
        "tottime_s": float(getattr(stat, "inlinetime", 0.0) or 0.0),
        "cumtime_s": float(getattr(stat, "totaltime", 0.0) or 0.0),
    }


def rank(entries: list[dict[str, Any]], top: int = 20) -> list[dict[str, Any]]:
    """按 cumtime 降序取前 top（并列按 key 升序，保证同输入同输出）。"""
    ordered = sorted(entries, key=lambda e: (-float(e.get("cumtime_s") or 0.0), str(e.get("key"))))
    return ordered[: max(0, int(top))]


def summarize(entries: list[dict[str, Any]], top: int = 20) -> dict[str, Any]:
    """→ 报告（机器面）。同输入必得同输出：除时间字段外全部确定性。"""
    ranked = rank(entries, top)
    total = sum(float(e.get("cumtime_s") or 0.0) for e in entries)
    return {
        "schema": "nf-hotspot-profile/1",
        "entries": len(entries),
        "total_cumtime_s": round(total, 6),
        "top": ranked,
        "tools": tool_state(),
        "note": "cProfile 确定性取数；时间字段随机器负载漂移，排名仅作定位线索",
    }


def profile_callable(func: Callable[..., Any], args: tuple = (),
                     kwargs: dict | None = None) -> list[dict]:
    """真跑一次 cProfile 并取回条目（纯取数，不做判定）。"""
    profiler = cProfile.Profile()
    profiler.enable()
    func(*args, **(kwargs or {}))
    profiler.disable()
    return [entry_of(s) for s in profiler.getstats()]


def resolve_target(spec: str) -> Callable[..., Any]:
    """'module:function' → 可调用对象（缺件即抛，不静默换目标）。"""
    mod_name, _, fn_name = spec.partition(":")
    if not mod_name or not fn_name:
        raise ValueError(f"target 须为 module:function 形态，得到：{spec!r}"
                         "（修复指引：写成 core.coupling_metrics:scan 这样）")
    mod = importlib.import_module(mod_name)
    return getattr(mod, fn_name)


def top_frames(frames: list[dict], samples: list[list[int]], top: int = 20) -> list[dict]:
    """speedscope 的 frames + samples → 按采样命中数排前 top（纯函数）。"""
    hits: Counter[int] = Counter()
    for sample in samples:
        for idx in sample:
            hits[int(idx)] += 1
    rows = []
    for idx, count in hits.items():
        if 0 <= idx < len(frames):
            frame = frames[idx]
            rows.append({"key": f"{frame.get('file', '?')}:{frame.get('name', '?')}",
                         "samples": count, "line": frame.get("line")})
    rows.sort(key=lambda r: (-r["samples"], r["key"]))
    return rows[: max(0, int(top))]


def speedscope_report(doc: dict, top: int = 20) -> dict[str, Any]:
    """speedscope 文档 → 采样报告（py-spy record 的默认输出格式）。"""
    frames: list[dict] = list((doc.get("shared") or {}).get("frames") or [])
    samples: list[list[int]] = []
    for prof in doc.get("profiles") or []:
        samples.extend(prof.get("samples") or [])
    return {"schema": "nf-hotspot-samples/1", "frames": len(frames),
            "samples": len(samples), "top": top_frames(frames, samples, top)}


def _metric_values(result: dict, metric: str) -> list[float]:
    """hyperfine 2.x：measurements[].<metric>.value；1.x 兜底读顶层 times。"""
    values = []
    for m in result.get("measurements") or []:
        entry = m.get(metric)
        if isinstance(entry, dict) and isinstance(entry.get("value"), (int, float)):
            values.append(float(entry["value"]))
    if values:
        return values
    return [float(x) for x in (result.get("times") or [])]


def _stats(values: list[float]) -> tuple[float, float, float]:
    """→ (均值, 总体标准差, 最小值)。自己算而不是读工具的字段：2.x 已不再给 mean/stddev。"""
    if not values:
        return 0.0, 0.0, 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, var ** 0.5, min(values)


def hyperfine_report(doc: dict) -> dict[str, Any]:
    """hyperfine --export-json 文档 → 逐命令统计（含加速比；纯函数）。

    口径按 primary_metric（2.x 默认 time_wall_clock）；1.x 的 mean/stddev 作兜底。
    """
    metric = str(doc.get("primary_metric") or "time_wall_clock")
    rows = []
    for r in doc.get("results") or []:
        values = _metric_values(r, metric)
        if values:
            mean, stddev, low = _stats(values)
        else:
            mean = float(r.get("mean") or 0.0)
            stddev = float(r.get("stddev") or 0.0)
            low = float(r.get("min") or 0.0)
            values = list(r.get("times") or [])
        rows.append({"command": r.get("command"), "mean_s": round(mean, 6),
                     "stddev_s": round(stddev, 6), "min_s": round(low, 6),
                     "runs": len(values)})
    speedup = None
    if len(rows) >= 2 and rows[0]["mean_s"] > 0 and rows[1]["mean_s"] > 0:
        speedup = round(rows[0]["mean_s"] / rows[1]["mean_s"], 3)
    return {"schema": "nf-hotspot-bench/1", "metric": metric, "commands": rows,
            "speedup_first_over_second": speedup}


def _run(argv: list[str], timeout: int = 600) -> tuple[int, str, str]:
    try:
        proc = subprocess.run([str(x) for x in argv], cwd=str(ROOT), capture_output=True,  # nosec B603  # noqa: S603
                              text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr


def run_sample(target: str, args: tuple, seconds: int, out_dir: Path) -> dict[str, Any]:
    """py-spy 采样跑一次目标。工具缺席 → 如实记 absent，不假装。"""
    tool = resolve_tool("py-spy")
    if not tool:
        return {"schema": "nf-hotspot-samples/1", "ok": False, "reason": "py-spy 缺席",
                "why": "装到 ~/.nftools/py-spy/ 或放进 PATH 即可（修复指引）"}
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "speedscope.json"
    argv = [tool, "record", "--format", "speedscope", "--output", str(out),
            "--rate", "200", "--duration", str(int(seconds)), "--",
            sys.executable, str(Path(__file__).resolve()),
            "--target", target, "--run-target"]
    for a in args:
        argv += ["--arg", a]
    rc, _stdout, stderr = _run(argv)
    if rc != 0 or not out.is_file():
        return {"schema": "nf-hotspot-samples/1", "ok": False,
                "reason": f"py-spy 退出码 {rc}", "why": stderr.strip()[:200]}
    rep = speedscope_report(json_doc.load(out, dict, what="speedscope.json"))
    rep.update({"ok": True, "target": target, "seconds": seconds, "file": out.as_posix()})
    return rep


def run_benchmark(commands: list[str], runs: int, out_dir: Path) -> dict[str, Any]:
    """hyperfine 端到端基准（含启动成本）。工具缺席 → 如实记 absent。"""
    tool = resolve_tool("hyperfine")
    if not tool:
        return {"schema": "nf-hotspot-bench/1", "ok": False, "reason": "hyperfine 缺席",
                "why": "装到 ~/.nftools/hyperfine/ 或放进 PATH 即可（修复指引）"}
    if len(commands) < 2:
        return {"schema": "nf-hotspot-bench/1", "ok": False,
                "reason": "需要至少两条命令才能比", "why": "修复指引：--benchmark A B"}
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "hyperfine.json"
    argv = [tool, "--warmup", "1", "--runs", str(int(runs)), "--export-json", str(out), "--"]
    argv += list(commands)
    rc, _stdout, stderr = _run(argv)
    if rc != 0 or not out.is_file():
        return {"schema": "nf-hotspot-bench/1", "ok": False,
                "reason": f"hyperfine 退出码 {rc}", "why": stderr.strip()[:200]}
    rep = hyperfine_report(json_doc.load(out, dict, what="hyperfine.json"))
    rep.update({"ok": True, "runs": runs, "file": out.as_posix()})
    return rep


def _self_test() -> int:
    checks = 0
    fake = [{"key": "b", "calls": 2, "tottime_s": 1.0, "cumtime_s": 1.0},
            {"key": "a", "calls": 1, "tottime_s": 9.0, "cumtime_s": 5.0},
            {"key": "c", "calls": 3, "tottime_s": 0.5, "cumtime_s": 5.0}]
    assert [e["key"] for e in rank(fake, 2)] == ["a", "c"], rank(fake, 2)  # nosec B101  # noqa: S101
    assert rank(fake, 0) == []  # nosec B101  # noqa: S101
    assert [e["key"] for e in rank(fake, 99)] == ["a", "c", "b"], "并列按 key 升序"  # nosec B101  # noqa: S101
    checks += 1
    rep = summarize(fake, 3)
    assert rep["entries"] == 3 and rep["total_cumtime_s"] == 11.0, rep  # nosec B101  # noqa: S101
    assert set(rep["tools"]) == {STDLIB_TOOL, *EXTERNAL_TOOLS}  # nosec B101  # noqa: S101
    checks += 1
    stats = profile_callable(resolve_target("json:dumps"), ({"a": 1},))
    assert stats and all({"key", "calls", "cumtime_s"} <= set(s) for s in stats), stats[:1]  # nosec B101  # noqa: S101
    checks += 1
    for bad in ("", "nosuch:fn", "mod"):
        try:
            resolve_target(bad)
        except (ValueError, ImportError, AttributeError):  # 期望被拒：吞掉后由下方断言兜
            continue
        raise AssertionError(f"应被拒：{bad!r}"
                             "（修复指引：目标解析面过宽，收窄 resolve_target 的判据）")
    checks += 1
    # 采样与基准的**解析面**是纯函数，必须能用合成文档自证（与工具在场与否无关）
    frames = [{"name": "hot", "file": "a.py", "line": 1},
              {"name": "cold", "file": "b.py", "line": 2}]
    samples = [[0, 1], [0], [0], [1]]
    assert [r["key"] for r in top_frames(frames, samples, 2)] == ["a.py:hot", "b.py:cold"]  # nosec B101  # noqa: S101
    assert top_frames(frames, [], 5) == []  # nosec B101  # noqa: S101
    assert speedscope_report({"shared": {"frames": frames}, "profiles": [{"samples": samples}]},  # nosec B101  # noqa: S101
                             1)["samples"] == 4
    checks += 1
    # 2.x 形状（measurements[].time_wall_clock）
    new_schema = {"primary_metric": "time_wall_clock", "results": [
        {"command": "A", "measurements": [{"time_wall_clock": {"value": 2.0, "unit": "second"}},
                                          {"time_wall_clock": {"value": 2.0, "unit": "second"}}]},
        {"command": "B", "measurements": [{"time_wall_clock": {"value": 0.5, "unit": "second"}},
                                          {"time_wall_clock": {"value": 0.5, "unit": "second"}}]}]}
    bench = hyperfine_report(new_schema)
    assert bench["speedup_first_over_second"] == 4.0, bench  # nosec B101  # noqa: S101
    assert bench["commands"][0]["runs"] == 2 and bench["commands"][0]["mean_s"] == 2.0, bench  # nosec B101  # noqa: S101
    # 1.x 形状兜底
    legacy = hyperfine_report({"results": [{"command": "A", "mean": 2.0, "stddev": 0.1,
                                            "min": 1.9, "times": [2, 2]},
                                           {"command": "B", "mean": 0.5, "stddev": 0.01,
                                            "min": 0.49, "times": [0.5, 0.5]}]})
    assert legacy["speedup_first_over_second"] == 4.0, legacy  # nosec B101  # noqa: S101
    assert hyperfine_report({"results": []})["speedup_first_over_second"] is None  # nosec B101  # noqa: S101
    checks += 1
    # 缺席必须如实：把解析面指向一个不存在的目录，必须返回 None 而不是编一个路径
    saved = os.environ.get(ENV_DIRS)
    os.environ[ENV_DIRS] = str(Path("/nonexistent-dir-xyz"))
    try:
        assert resolve_tool("definitely-not-a-tool-xyz") is None  # nosec B101  # noqa: S101
    finally:
        if saved is None:
            os.environ.pop(ENV_DIRS, None)
        else:
            os.environ[ENV_DIRS] = saved
    checks += 1
    print(f"self-test OK（{checks} 例）")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="热面剖析取数（cProfile / py-spy / hyperfine；只读）")
    ap.add_argument("--target", default=DEFAULT_TARGET, help="module:function")
    ap.add_argument("--arg", action="append", default=[], help="位置参数（可重复）")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--sample", default="", help="用 py-spy 采样该目标（module:function）")
    ap.add_argument("--seconds", type=int, default=5, help="采样时长")
    ap.add_argument("--benchmark", nargs="*", default=None, help="hyperfine 比较的命令串（≥2）")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--run-target", action="store_true",
                    help="只跑一次目标（给 py-spy 当目标进程）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    if args.run_target:
        resolve_target(args.target)(*tuple(args.arg))
        return 0
    if args.sample:
        rep = run_sample(args.sample, tuple(args.arg), args.seconds, ROOT / args.out)
    elif args.benchmark is not None:
        rep = run_benchmark(list(args.benchmark), args.runs, ROOT / args.out)
    else:
        try:
            func = resolve_target(args.target)
        except (ValueError, ImportError, AttributeError) as exc:
            print(f"目标不可解析：{args.target}（{exc}）", file=sys.stderr)
            return 2
        rep = summarize(profile_callable(func, tuple(args.arg)), args.top)
        rep["target"] = args.target
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"== {rep['schema']}（ok={rep.get('ok', True)}）==")
        if not rep.get("ok", True):
            print(f"  缺席：{rep.get('reason')} · {rep.get('why')}")
        for row in rep.get("top", []):
            if "samples" in row:
                print(f"  {row['samples']:>6} samples · {row['key']}")
            else:
                print(f"  {row['cumtime_s']:8.3f}s cum · {row['tottime_s']:8.3f}s self"
                      f" · {row['calls']:>6} calls · {row['key']}")
        for row in rep.get("commands", []):
            print(f"  {row['mean_s']:8.4f}s ± {row['stddev_s']:.4f} · {row['command']}")
        if rep.get("speedup_first_over_second") is not None:
            print(f"  加速（前者/后者）：{rep['speedup_first_over_second']}×")
        for name, path in sorted((rep.get("tools") or tool_state()).items()):
            print(f"  工具 {name:<10} {'在场：' + str(path) if path else '缺席'}")
    return 0 if rep.get("ok", True) else 1


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
