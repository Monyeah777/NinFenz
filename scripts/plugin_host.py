#!/usr/bin/env python3
"""微内核插件宿主（P5-01…P5-06）——**只在适配器侧**（§18.3 红线：core/ 不得依赖 wasmtime）。

职责四分：

    装载   读清单 → 清单校验 + 与 WIT 契约对账 + 解析产物；三者缺一**不装**
    执行   wasmtime run：fuel 计量（P5-05.1）+ wall-clock 超时（P5-05.2）
    能力   默认无 preopens / 无 network / 无 env（P5-02.2/P5-02.3）；宿主授予集恒为空
    隔离   崩溃 / 超时 / fuel 耗尽 / 产物缺失 → **回退 Python 参考 + 记录降级**（P5-01.2/P5-05）

设计红线（与计划 §18.3/§18.7 对齐）：

- 本模块**不**在 core/ 里，也不被 core/ 依赖；core 侧只有纯判定（plugin_manifest / plugin_gate）。
- 回退**永远不是静默的**：每次回退都带 machine-readable 的 reason 与人类可读的 detail。
- 宿主自己**不死**：任何插件侧异常都被收敛成返回值，进程继续。

用法：

    python scripts/plugin_host.py --in <文件> [--method sha256] [--json]
    python scripts/plugin_host.py --self-test
"""
import argparse
import importlib.util
import json
import subprocess  # nosec B404 - 只跑本仓声明的产物与在场工具链
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from core import plugin_manifest as pm  # noqa: E402

_REF_PATH = ROOT / "scripts" / "plugin_reference.py"
_spec = importlib.util.spec_from_file_location("nf_plugin_ref", str(_REF_PATH))
_ref = importlib.util.module_from_spec(_spec)
sys.modules["nf_plugin_ref"] = _ref
_spec.loader.exec_module(_ref)

DEFAULT_MANIFEST = "engine/wasm/manifests/sha256.json"
#: WIT 契约位置（单点，避免两处写死）
WIT_REL = "engine/wasm/ninfenz-plugin.wit"
#: wasmtime 报告「燃料耗尽」时的 stderr 片段（实测措辞："wasm trap: all fuel consumed
#: by WebAssembly"）。刻意不放裸词 "fuel"——那会把任何提到燃料的报错都误判成耗尽。
FUEL_MARKERS = ("all fuel consumed", "out of fuel", "fuel has been consumed")


def resolve_wasmtime():
    """解析可用的 wasmtime；缺席返回 None（调用方必须回退，不许假装跑过）。"""
    import cross_lang_verify as clv
    return clv.resolve_exe("wasmtime", ["--version"])


def load_declared(manifest_rel: str = DEFAULT_MANIFEST, root: Path = ROOT):
    """装载三件事一次做完：清单校验 + WIT 对账 + 产物解析。→ (doc, issues, artifact)。"""
    doc = pm.load(str(root / manifest_rel))
    issues = pm.validate(doc)
    wit_path = root / WIT_REL
    if wit_path.is_file():
        issues = issues + pm.validate_against_wit(doc, wit_path.read_text(encoding="utf-8"))
    else:
        issues.append(f"WIT 契约缺席：{WIT_REL}")
    artifact = pm.artifact_path(doc, str(root))
    if artifact is None or not artifact.is_file():
        issues.append("插件产物不在场：%s" % (artifact or "未声明"))
    return doc, issues, artifact


def fuel_for(entry: dict, nbytes: int) -> int:
    """按成本模型算燃料预算。

    线性成本必须随输入伸缩（实测 ~138,776 燃料/KiB）：固定预算会变成隐式的输入上限，
    使大输入「必然耗尽燃料」——那不是隔离，是配置错误伪装成安全事件。hard_cap 仍是硬顶。
    """
    fuel = entry.get("fuel") or {}
    budget = int(fuel.get("base") or 0)
    if (entry.get("cost") or {}).get("kind") == "linear":
        per_kib = int(fuel.get("per_kib") or 0)
        budget += per_kib * ((int(nbytes) + 1023) // 1024)
    cap = int(fuel.get("hard_cap") or 0)
    return min(budget, cap) if cap > 0 else budget


def isolation_argv(wasmtime: str, artifact: Path, fuel: int, timeout_ms: int,
                   method: str = "sha256") -> list:
    """宿主侧的**能力收窄**（P5-02/P5-06）——每一条都是显式的 deny，不靠默认值。

    实测口径（wasmtime 49）：不给 --dir 就**没有** preopens；不给 -S inherit-network 就
    **没有**网络；-S inherit-env=n 连环境变量都不传。这三条合起来就是「默认不授予」。
    """
    argv = [wasmtime, "run",
            "-W", f"fuel={int(fuel)}",           # P5-05.1 燃料预算
            "-W", f"timeout={int(timeout_ms)}ms",  # P5-05.2 墙钟（与 epoch 双保险）
            "-W", "epoch-interruption=y",
            "-W", "nan-canonicalization=y",         # 浮点非确定性归一
            "-S", "inherit-env=n",                  # 不传环境
            "-S", "inherit-stdin=y",                # 输入面：管道
            "-S", "inherit-stdout=y",
            "-S", "inherit-stderr=y"]
    argv += [str(artifact), "--method", method]
    return argv


def component_argv(wasmtime: str, artifact: Path, entry: dict, data: bytes,
                   fuel: int, timeout_ms: int) -> list:
    """Component Model 形态的调用 argv（P5-03.2 类型化组件）。

    类型化组件的参数走 **WAVE 字面量经 argv**（组件没有 stdin 约定），故只适合小输入。
    这是有意的分工：「装载期类型校验 + 小样本互证」用组件，「跑量」用 CLI 形态——
    两者能力面不同，谁也不是谁的替代品。
    """
    invoke = str((entry.get("io") or {}).get("invoke") or "")
    literal = "[" + ",".join(str(b) for b in data) + "]"
    return [wasmtime, "run",
            "-W", f"fuel={int(fuel)}",
            "-W", f"timeout={int(timeout_ms)}ms",
            "-W", "epoch-interruption=y",
            "-W", "nan-canonicalization=y",
            "-S", "inherit-env=n",              # 与 CLI 形态同口径：不传环境
            "--invoke", f"{invoke}({literal})",
            str(artifact)]


def parse_wave_result(text: str) -> bytes | None:
    """把 WAVE 的 ok([b0,b1,...]) 解析成字节；err(...) 或形态不符 → None（fail-closed）。"""
    body = text.strip()
    if not body.startswith("ok([") or not body.endswith("])"):
        return None
    inner = body[4:-2].strip()
    if not inner:
        return b""
    try:
        return bytes(int(x) for x in inner.split(","))
    except ValueError:
        return None


#: 「自动解析宿主」的哨兵：与 None（**明确缺席**）区分开——自证要能真的走缺席分支。
_AUTO = object()


def invoke(doc, artifact, method: str, data: bytes, *, wasmtime=_AUTO, root: Path = ROOT,
           timeout_s: float = 60.0):
    """跑一次插件。→ {"ok", "data"|None, "meta"}；任何失败都**不抛**，转成可记录的降级。"""
    wasmtime = resolve_wasmtime() if wasmtime is _AUTO else wasmtime
    entry = pm.method(doc, method)
    meta = {"method": method, "degraded": False, "reason": "", "detail": "",
            "fuel": None, "wall_ms": None, "capabilities": pm.granted_capabilities(doc)}
    if entry is None:
        meta.update(reason="method_not_declared", detail=f"清单未声明方法 {method}")
        return {"ok": False, "data": None, "meta": meta}
    fuel = fuel_for(entry, len(data))
    timeout_ms = int(entry.get("wall_timeout_ms") or 30000)
    meta["fuel"] = fuel
    if not wasmtime:
        meta.update(reason="host_absent", detail="wasmtime 不在场")
        return {"ok": False, "data": None, "meta": meta}
    if artifact is None or not Path(artifact).is_file():
        meta.update(reason="artifact_absent", detail="插件产物不在场")
        return {"ok": False, "data": None, "meta": meta}
    component = str(doc.get("abi") or "") == "wasi-preview2-component"
    if component:
        argv = component_argv(wasmtime, Path(artifact), entry, data, fuel, timeout_ms)
        stdin = None
    else:
        argv = isolation_argv(wasmtime, Path(artifact), fuel, timeout_ms, method)
        stdin = data
    meta["abi"] = str(doc.get("abi") or "")
    started = time.perf_counter()
    try:
        proc = subprocess.run(argv, cwd=str(root), input=stdin, capture_output=True,  # nosec B603
                              timeout=min(timeout_s, timeout_ms / 1000.0 + 5.0))
    except subprocess.TimeoutExpired:
        meta.update(reason="timeout", wall_ms=round((time.perf_counter() - started) * 1000, 3),
                    detail=f"宿主超时（{timeout_s:.1f}s）")
        return {"ok": False, "data": None, "meta": meta}
    except OSError as exc:
        meta.update(reason="host_unusable", detail=f"起不了宿主：{exc}")
        return {"ok": False, "data": None, "meta": meta}
    wall_ms = round((time.perf_counter() - started) * 1000, 3)
    meta["wall_ms"] = wall_ms
    stderr = proc.stderr.decode("utf-8", "replace")
    if proc.returncode != 0:
        low = stderr.lower()
        reason = "fuel_exhausted" if any(m in low for m in FUEL_MARKERS) else "exit_nonzero"
        meta.update(reason=reason,
                    detail=f"退出码 {proc.returncode}：{stderr.strip()[:200]}")
        return {"ok": False, "data": None, "meta": meta}
    out = proc.stdout.decode("utf-8", "replace").strip()
    if component:
        parsed = parse_wave_result(out)
        if parsed is None:
            meta.update(reason="bad_wave_result",
                        detail=f"组件返回不是 ok([...])：{out[:120]}")
            return {"ok": False, "data": None, "meta": meta}
        meta["detail"] = "组件直通（Canonical ABI）"
        return {"ok": True, "data": parsed.hex(), "meta": meta}
    if not out:
        meta.update(reason="empty_output", detail="插件无标准输出")
        return {"ok": False, "data": None, "meta": meta}
    meta["detail"] = "插件直通"
    return {"ok": True, "data": out, "meta": meta}


def invoke_with_fallback(doc, artifact, method: str, data: bytes, **kw):
    """插件优先、**参考实现恒在**：失败即回退并记录降级（§18.5）。"""
    got = invoke(doc, artifact, method, data, **kw)
    if got["ok"]:
        return got
    ref = _ref.METHODS.get(method)
    if ref is None:
        got["meta"]["detail"] += "；参考实现也没有该方法，无法回退"
        return got
    got["meta"]["degraded"] = True
    got["meta"]["fallback"] = "scripts/plugin_reference.py"
    got["data"] = ref(data)
    got["ok"] = True
    return got


def _self_test() -> int:
    checks = 0
    doc, issues, artifact = load_declared()
    assert issues == [], f"自带清单不该有问题：{issues}"
    checks += 1
    # 能力收窄：argv 里不许出现 --dir / inherit-network / inherit-env=y
    argv = isolation_argv("wasmtime", artifact or Path("x.wasm"), 1000, 1000)
    joined = " ".join(argv)
    for forbidden in ("--dir", "inherit-network", "inherit-env=y"):
        assert forbidden not in joined, f"宿主 argv 出现越权开关：{forbidden}"
    for required in ("fuel=", "timeout=", "inherit-env=n", "epoch-interruption=y"):
        assert required in joined, f"宿主 argv 缺 {required}"
    checks += 1
    # 降级路径：宿主缺席必须回退且**标记** degraded
    got = invoke_with_fallback(doc, artifact, "sha256", b"abc", wasmtime=None)
    assert got["ok"] and got["meta"]["degraded"] and got["meta"]["reason"] == "host_absent"
    assert got["data"] == _ref.METHODS["sha256"](b"abc")
    checks += 1
    print(f"self-test OK（{checks} 例）")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="微内核插件宿主（适配器侧；只读）")
    ap.add_argument("--in", dest="inp", default="", help="stdin 夹具文件")
    ap.add_argument("--method", default="sha256")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--require-plugin", action="store_true",
                    help="插件不可用即 exit 1（默认允许回退，只如实标记）")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    doc, issues, artifact = load_declared(args.manifest)
    if issues:
        print("装载被拒：\n  " + "\n  ".join(issues), file=sys.stderr)
        return 2
    data = Path(args.inp).read_bytes() if args.inp else sys.stdin.buffer.read()
    got = invoke_with_fallback(doc, artifact, args.method, data)
    if args.json:
        print(json.dumps({"kind": "nf-plugin-invoke", "data": got["data"], **got["meta"]},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(got["data"])
    if args.require_plugin and got["meta"]["degraded"]:
        return 1
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
