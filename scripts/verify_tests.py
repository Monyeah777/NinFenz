#!/usr/bin/env python3
"""check12 的测试执行器：**按测试粒度分片并行**（只改执行方式，不改任何判据）。

为什么（2026-10-17 实测）：check12 = 3100+ tests / ~1080 s，占全量门禁 95%；单进程串行是纯
执行成本。隔离修好后（`desktop/tests/__init__.py`：NF_HOME 兜底临时目录；守护端口由内核分配），
测试之间不再共享状态，于是可把同一批测试放进 N 个进程——判据一条不动。

纪律（写进判据，不是口头承诺）：
1. **全集等价**：分片里的测试 id 由**一次 discover**产出，逐项分完（不按文件名猜），
   分片并集必须逐项等于 discover 集，否则 exit 1；
2. **失败不被吞**：任一分片非零即整体非零，并打印该分片末 40 行；
3. **可回退**：`--jobs 1` = 串行口径（排障用）；`NF_TEST_JOBS=1` 同义；
4. **可复现分片**：按「历史耗时 LPT（并列按测试 id）」分配，同输入必得同一分片；
5. **不猜权重**：权重来自 `protocol/check12_weights.json`（`--write-weights` 实测生成），
   缺文件按均匀权重——只影响均衡，不影响判据。

用法：
    python scripts/verify_tests.py                    # 默认 jobs=4（或 NF_TEST_JOBS）
    python scripts/verify_tests.py --jobs 1           # 串行（等价历史 discover）
    python scripts/verify_tests.py --write-weights    # 逐模块实测 → 写权重（棘轮基线）
    python scripts/verify_tests.py --list             # 只打印发现到的测试数
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "desktop"
TESTS = DESKTOP / "tests"
WEIGHTS_REL = "protocol/check12_weights.json"
SHARD_TIMEOUT_S = float(os.environ.get("NF_SHARD_TIMEOUT", "1800"))
#: 负载敏感模块：并行段之后独占串行跑（全部用例照跑，只改调度）。见 main 内注释。
SERIAL_MODULES = frozenset({
    "test_atomic_write", "test_daemon",
    # 2026-10-19 复核：串行段一度扩到 9 个模块，结果串行段本身成了 367 s 的新瓶颈（j24 实测
    # 最大片 = 367 s）。逐条回看取证后发现：schema_lint / governance / quality_depth 那一族的
    # 红，全部发生在**工作树不干净**的跑次上（报告/回执/一致性面被判过期），不是读写竞争。
    # 因此收回，只留**真正进程内打桩 + 时间窗**的两族。
    # test_lsp 的 warm 复用判据是时间窗口径（TTL 内只该扫一次签名）：并发把单次扫描拖到窗外
    # 就会"合法地"多扫一次而被判红——属负载敏感，保留串行。
    "test_lsp",
})
# test_governance_faces 也进串行段（2026-10-18 实测）：它扫全仓"模式命中"，16 片并发时
# 别的分片正在写临时产物（如 results/ 中间态），扫到就会红——不是它写错，是"读全仓快照"的
# 判据不能与"会短暂写全仓"的判据同时跑。并发段跑完再独占跑它，判据不变、确定性恢复。

#: 落盘一律走 core.atomic_write（脚本面纪律：不得有裸写 sink）；权重是**仓内**协议件。
sys.path.insert(0, str(DESKTOP / "src"))
from core import atomic_write, json_doc  # noqa: E402 - 先用后置（scripts 面统一写法）
from core.atoms import proc as proc_atom  # noqa: E402


def discover_ids() -> list:
    """一次 discover → 全部测试 id（与 unittest 默认 pattern 同口径）。"""
    sys.path.insert(0, str(DESKTOP))
    suite = unittest.TestLoader().discover(str(TESTS), pattern="test*.py")
    ids = []

    def walk(node):
        if isinstance(node, unittest.TestSuite):
            for child in node:
                walk(child)
        else:
            ids.append(node.id())

    walk(suite)
    return sorted(set(ids))


def module_of(test_id: str) -> str:
    """test id → 模块名（`test_x.Class.test_y` 与 `tests.test_x...` 都归一为 `test_x`）。

    discover 的 top_level_dir 是 tests 目录，故真实 id 形如 `test_x.Class.test_y`（无包前缀）；
    两种形态都归一，权重键与 `--mods` 过滤因此稳定。
    """
    parts = test_id.split(".")
    if parts and parts[0] == "tests" and len(parts) > 1:
        return parts[1]
    return parts[0] if parts else ""


#: 任何**非 core** 变更都要跑的模块：它们读全仓事实（文档/协议/产物/统计），
#: 静态 import 看不到依赖面——宁可多跑，不可漏跑。
#: 任何**非 core** 变更都要跑：只留"改代码就可能打红"的卫生判据（快、与内容无关）。
#: 其余仓库内容扫描（verify_report / conformance_scan / doc_* / net_* / role_model / ledger）
#: 只在 full 档与"文档/协议变更触发的全量兜底"里跑——2026-10-18 实测：把它们塞进常驻集
#: 会让 quick 的测试侧白付 ~120 s（quick 墙钟 124 s 里它占了大头），而它们对"只改代码"
#: 的回归几乎不敏感（内容扫描器判的是文件事实，不是逻辑）。
ALWAYS_MODULES = frozenset({
    "test_purity_scan", "test_style_ratchet", "test_dead_code",
    "test_suite_isolation", "test_check12_budget",
})

#: 明确**不进**常驻集：`test_npm_package` 判的是 payload 清单与 HEAD 一致——那只在
#: 发布/推送前才有意义（`--full` 与 `nf release` 都会跑它），把它塞进开发回路的常驻集
#: 只会让每次提交后都"红到重暂存"为止（2026-10-18 实测：单次 28 s，且并发会话下必红）。

_CORE_REF = (
    r"(?:from\s+core\s+import\s+([A-Za-z0-9_,\s]+)"
    r"|from\s+core\.([A-Za-z0-9_]+)"
    r"|import\s+core\.([A-Za-z0-9_]+))"
)


def changed_paths() -> list:
    """相对仓库根的变更面：tracked diff（HEAD）+ 未跟踪件。"""
    out = []
    try:
        p = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8")
        if p.returncode == 0:
            out += [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]
        q = subprocess.run(["git", "ls-files", "-o", "--exclude-standard"], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8")
        if q.returncode == 0:
            out += [ln.strip() for ln in (q.stdout or "").splitlines() if ln.strip()]
    except (OSError, subprocess.SubprocessError):
        # git 不在场/坏仓库 → 返回空 = 由调用方按"干净树"处理（只跑常驻集），不会静默全绿：
        # 空集合只影响**选哪些测试**，判定本身仍由跑到的测试给出。
        return []
    return sorted(set(out))


def _core_imports(text: str) -> set:
    out = set()
    for m in re.finditer(_CORE_REF, text):
        if m.group(1):
            out.update(x.strip() for x in m.group(1).split(",") if x.strip())
        if m.group(2):
            out.add(m.group(2))
        if m.group(3):
            out.add(m.group(3))
    return out


def _core_reverse_closure(start: set) -> set:
    """变更的 core 模块 → 传递**反向依赖**闭包（谁 import 它）。"""
    graph = {}
    for py in (DESKTOP / "src" / "core").glob("*.py"):
        try:
            graph[py.stem] = _core_imports(py.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            graph[py.stem] = set()
    closure = set(start)
    changed = True
    while changed:
        changed = False
        for mod, imports in graph.items():
            if mod not in closure and imports & closure:
                closure.add(mod)
                changed = True
    return closure


def _test_sources() -> dict:
    out = {}
    for py in TESTS.glob("test*.py"):
        try:
            out[py.stem] = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            out[py.stem] = ""
    return out


def affected_selection(ids: list) -> tuple:
    """变更 → 受影响测试 id；非 core 变更**全量兜底**（宁慢勿漏）。"""
    changed = changed_paths()
    if not changed:
        keep = [t for t in ids if module_of(t) in ALWAYS_MODULES]
        return keep, "干净树（只跑常驻集 %d 个模块）" % len(keep and {module_of(t) for t in keep})
    non_core = [p for p in changed if not p.startswith("desktop/src/core/")]
    if non_core:
        return list(ids), "非 core 变更 %d 个 → 全量兜底" % len(non_core)
    changed_core = {Path(p).stem for p in changed if p.endswith(".py")}
    closure = _core_reverse_closure(changed_core)
    sources = _test_sources()
    keep = []
    for tid in ids:
        mod = module_of(tid)
        if mod in ALWAYS_MODULES or (_core_imports(sources.get(mod, "")) & closure):
            keep.append(tid)
    return keep, "core 变更 %d 个 → 反向依赖闭包 %d 个模块" % (len(changed_core), len(closure))


def load_weights() -> dict:
    """读权重基线（仓内 JSON 走 core.json_doc：形状校验 + 带指引报错）。

    缺文件/坏件 → 空权重：只影响分片均衡，不影响判据（均匀兜底在 test_weights 里）。
    """
    path = ROOT / WEIGHTS_REL
    if not path.is_file():
        return {}
    try:
        doc = json_doc.load(path, dict, what=WEIGHTS_REL)
    except ValueError:
        # 权重是**纯加速参数**：坏件退回均匀权重即可，不必让门禁红（判据面不受影响）。
        return {}
    if not isinstance(doc, dict):
        return {}
    out = {}
    for key in ("modules", "tests"):
        rows = doc.get(key)
        if isinstance(rows, dict):
            out[key] = {str(k): float(v) for k, v in rows.items()
                        if isinstance(v, (int, float))}
    return out


def test_weights(ids: list, weights: dict, per_test: dict = None) -> dict:
    """每测试权重：**有逐测试实测就用实测**，否则按所属模块耗时均分（缺数据按 1.0）。

    为什么需要两档（2026-10-18 实测）：模块内耗时极不均匀——`test_daemon_parity` 里一条
    142 s、其余各 <2 s；按模块均分会让 LPT 把那条重测试算成 6 s，分片严重失衡。
    """
    per_test = per_test or {}
    per_module = {}
    for tid in ids:
        per_module.setdefault(module_of(tid), []).append(tid)
    out = {}
    for mod, group in per_module.items():
        share = weights.get(mod, float(len(group))) / max(1, len(group))
        for tid in group:
            out[tid] = max(0.05, float(per_test.get(tid, share)))
    return out


def chunk_items(ids: list, ws: dict, jobs: int, factor: int = 4) -> list:
    """按权重贪心切片（约 jobs×factor 片），供动态队列消费。

    与 `assign`（静态分箱）并存：`--shard i/n`/CI 矩阵仍用静态分箱（可离线复现），
    单机多进程用队列（能吃满核、摊平长尾）。
    """
    ordered = sorted(ids, key=lambda x: (-ws.get(x, 1.0), x))
    total = sum(ws.get(t, 1.0) for t in ordered)
    target = max(0.5, total / max(1, jobs * factor))
    out, cur, acc = [], [], 0.0
    for t in ordered:
        cur.append(t)
        acc += ws.get(t, 1.0)
        if acc >= target:
            out.append(cur)
            cur, acc = [], 0.0
    if cur:
        out.append(cur)
    return out


def assign(ids: list, ws: dict, jobs: int) -> list:
    """LPT：按权重降序塞进当前最轻的分片（并列按测试 id，保证确定性）。"""
    bins = [[] for _ in range(jobs)]
    load = [0.0] * jobs
    for tid in sorted(ids, key=lambda x: (-ws.get(x, 1.0), x)):
        i = min(range(jobs), key=lambda k: (load[k], k))
        bins[i].append(tid)
        load[i] += ws.get(tid, 1.0)
    return bins


def run_shard(ids: list, index: int, dump: str = "") -> dict:
    """跑一个分片（可选：把逐测试耗时写到 `dump` 路径，供权重实测用）。"""
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="nf_shard_%d_" % index) as spec_dir:
        spec = Path(spec_dir) / "tests.json"
        payload = {"tests": ids}
        if dump:
            payload["dump"] = dump
        atomic_write.write_text(spec, json.dumps(payload, ensure_ascii=False))
        with tempfile.TemporaryDirectory(prefix="nf_shard_home_%d_" % index) as home:
            env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                       NARRATIVE_FORGE_HOME=home)
            env.setdefault("NF_DAEMON_IDLE", "30")
            # 内层并发闸（2026-10-19 实测）：test_daemon_parity 的直跑面默认开 6 路线程，
            # 16 片就是 96 个并发 python 进程——进程创建争用会把整片拖慢。
            # 分片越多、每个分片的内层线程越少，总量固定在 ~16 路。
            # 总并发上限按 8 路算：16 片时内层 = 1（一片同一时刻只 spawn 一个子进程）。
            # 2026-10-19 实测：16 片 × 2 线程仍把单条重测试拖到 352 s，降为 1 路才真正削峰。
            _jobs_hint = int(os.environ.get("NF_TEST_JOBS") or 8)
            if _jobs_hint > 1:
                _inner = max(1, min(6, 8 // max(1, _jobs_hint)))
            else:
                # 单分片（CI 矩阵的一台 runner / --shard 模式）：按核数的一半算——
                # 2 核 runner ≈ 1 路，20 核机 ≈ 6 路；不再假设"单分片就是最强机器"。
                _inner = max(1, min(6, (os.cpu_count() or 4) // 2))
            env["NF_INNER_THREADS"] = str(_inner)
            result = proc_atom.popen_capture(
                [sys.executable, str(Path(__file__).resolve()), "--run-shard", str(spec)],
                cwd=str(DESKTOP), env=env, timeout=SHARD_TIMEOUT_S,
                new_session=os.name != "nt")
            rc = int(result["code"] if result["code"] is not None else 1)
            out = result["out"] + result["err"]
            if result["timed_out"]:
                out += f"\n分片超时（{SHARD_TIMEOUT_S:.0f} s；已回收进程树）"
            cleanup_ok, cleanup_msg = _cleanup_shard_home(Path(home))
            if not cleanup_ok and rc == 0:
                rc = 125
            if cleanup_msg:
                out += "\n[分片清理] " + cleanup_msg
    log_dir = os.environ.get("NF_SHARD_LOG_DIR")
    if log_dir:
        # 诊断用（默认关闭）：把每个分片的**完整**输出落盘——分片失败时只看末 40 行
        # 往往抓不到"哪条测试红"，而这正是并行敏感问题的唯一线索。
        try:
            target = Path(log_dir) / f"shard{index}.log"
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write.write_text(target, out)
        except OSError:
            # 落盘失败只是少一份诊断，不影响判定（分片结果仍按 rc 汇总）。
            pass
    return {"index": index, "rc": rc, "out": out,
            "wall": round(time.perf_counter() - t0, 1), "tests": len(ids)}


def _cleanup_shard_home(home: Path) -> tuple:
    """停掉分片临时 home 内的守护；显式 home 不触发套件级 atexit，故必须由执行器兜底。"""
    state = home / "daemon.json"
    if not state.exists():
        return True, ""
    src = str(DESKTOP / "src")
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {src!r})\n"
        "from core import daemon as dm\n"
        "ok, msg = dm.stop(timeout=3.0)\n"
        "print(msg)\n"
        "raise SystemExit(0 if ok else 1)\n"
    )
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               NARRATIVE_FORGE_HOME=str(home))
    result = proc_atom.run_capture([sys.executable, "-c", code], cwd=str(DESKTOP), env=env,
                                   timeout=15)
    if result["code"] is None:
        return False, f"守护清理失败：{result['err']}（临时 home：{home}）"
    detail = (result["out"] + result["err"]).strip().splitlines()
    msg = "；".join(detail[-2:]) or f"清理 rc={result['code']}"
    ok = result["code"] == 0 or not state.exists() or "没有守护在运行" in msg
    return ok, msg


class _TimingResult(unittest.TextTestResult):
    """记录逐测试墙钟（权重实测专用；不改变任何判定）。"""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.durations = {}

    def startTest(self, test):
        self._t0 = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        self.durations[test.id()] = round(time.perf_counter() - self._t0, 2)
        super().stopTest(test)


def run_shard_mode(spec_path: str) -> int:
    """子进程侧：按测试 id 清单跑（可选把逐测试耗时写到 spec 指定的 dump 路径）。"""
    sys.path.insert(0, str(DESKTOP))
    sys.path.insert(0, str(TESTS))
    spec = json_doc.load(Path(spec_path), dict, what="分片测试清单")
    tests = spec["tests"]
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for tid in tests:
        suite.addTests(loader.loadTestsFromNames([tid]))
    dump = str(spec.get("dump") or "")
    if dump:
        result = unittest.TextTestRunner(verbosity=1, resultclass=_TimingResult).run(suite)
        atomic_write.write_text(Path(dump),
                                json.dumps(result.durations, ensure_ascii=False, sort_keys=True))
    else:
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


def measure_weights(ids: list) -> tuple:
    """逐模块实测（每模块一个子进程，带逐测试计时）→ ({module: s}, {test_id: s})。"""
    per_module = {}
    for tid in ids:
        per_module.setdefault(module_of(tid), []).append(tid)
    out, per_test = {}, {}
    mods = sorted(per_module)
    with tempfile.TemporaryDirectory(prefix="nf_weights_") as dump_dir:
        for i, mod in enumerate(mods, 1):
            dump = str(Path(dump_dir) / ("%03d.json" % i))
            res = run_shard(per_module[mod], i, dump=dump)
            out[mod] = round(res["wall"], 2)
            try:
                per_test.update(json_doc.load(Path(dump), dict, what="逐测试耗时"))
            except ValueError:
                # 该模块的 dump 缺失（崩溃/超时）→ 只丢这批逐测试权重，模块权重仍有效；
                # LPT 会退回"模块内均分"，只影响均衡、不影响判据。
                pass
            print("  [%3d/%3d] %7.1f s  %s" % (i, len(mods), res["wall"], mod), flush=True)
    return out, per_test


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="check12 分片执行器")
    ap.add_argument("mods", nargs="*", help="只跑这些模块（排障用；缺省=全量 discover）")
    ap.add_argument("--jobs", type=int, default=0,
                    help="分片数（0=读 NF_TEST_JOBS，缺省 4；1=串行）")
    ap.add_argument("--write-weights", action="store_true",
                    help="逐模块实测并写 protocol/check12_weights.json")
    ap.add_argument("--list", action="store_true", help="只打印发现的测试数")
    ap.add_argument("--affected", action="store_true",
                    help="只跑**受影响**测试（按变更面的 core 反向依赖闭包；非 core 变更全量兜底）")
    ap.add_argument("--shard", default="",
                    help="矩阵模式：只跑第 i/n 片（如 3/16），供 CI 每台 runner 跑一份")
    ap.add_argument("--plan", type=int, default=0,
                    help="只打印 n 分片的分配计划并校验并集==全集（不跑测试）")
    ap.add_argument("--run-shard", default="", help=argparse.SUPPRESS)
    ap.add_argument("--json", action="store_true", help="输出结构化摘要")
    args = ap.parse_args(argv)

    if args.run_shard:
        return run_shard_mode(args.run_shard)

    ids = discover_ids()
    if args.plan or args.shard:
        # 矩阵分片（CI）：**同一套权重、同一套 LPT**，因此 i=0..n-1 的并集必然等于 discover。
        weights_doc = load_weights()
        ws = test_weights(ids, weights_doc.get("modules", {}), weights_doc.get("tests", {}))
        try:
            if args.plan:
                n = int(args.plan)
                idx = None
            else:
                left, right = args.shard.split("/")
                idx, n = int(left), int(right)
        except (ValueError, TypeError):
            print("--shard 需形如 3/16，--plan 需整数", file=sys.stderr)
            return 2
        if n < 1 or (idx is not None and not 0 <= idx < n):
            print("分片下标/总数越界：%s/%s" % (idx, n), file=sys.stderr)
            return 2
        bins = assign(ids, ws, n)
        flat = [t for b in bins for t in b]
        if sorted(flat) != sorted(ids):
            print("矩阵分片并集与 discover 不一致（漏/重）", file=sys.stderr)
            return 1
        if args.plan:
            for i, b in enumerate(bins):
                print("分片 %2d/%d：%4d 条 · 权重 %.1f s" % (i, n, len(b), sum(ws.get(t, 1.0) for t in b)))
            print("并集校验：%d 条 == discover %d 条" % (len(flat), len(ids)))
            return 0
        ids = bins[idx]
        jobs = 1
        args.jobs = 1
        res = run_shard(ids, idx)
        if args.json:
            print(json.dumps({"schema": "nf-verify-tests/1", "jobs": 1, "shard": args.shard,
                              "wall_s": res["wall"], "tests": res["tests"],
                              "rc": res["rc"]}, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  分片 %s：测试 %d · %.1f s · rc=%d" % (args.shard, res["tests"],
                                                        res["wall"], res["rc"]))
        # 2026-10-21：CI 上分片红只看到 rc=1（unittest 明细被 subprocess 捕获吞掉），
        # 诊断成本极高。失败时把「失败用例名 + 末段堆栈」打到 stderr，job 日志可直接读。
        if res["rc"] != 0:
            out = res.get("out") or ""
            marks = [ln for ln in out.splitlines()
                     if ln.startswith(("FAIL:", "ERROR:")) or "AssertionError" in ln]
            print("---- 分片 %s 失败用例（最多 20 行）----" % args.shard, file=sys.stderr)
            for ln in marks[:20]:
                print("  " + ln.strip(), file=sys.stderr)
            print("---- 分片 %s 末 40 行 ----" % args.shard, file=sys.stderr)
            for ln in out.splitlines()[-40:]:
                print("  " + ln.rstrip(), file=sys.stderr)
        return 0 if res["rc"] == 0 else 1

    if args.mods:
        want = {m[len("tests."):] if m.startswith("tests.") else m for m in args.mods}
        ids = [t for t in ids if module_of(t) in want]
        if not ids:
            print("指定模块里没有测试：%s（修复指引：模块名形如 tests.test_xxx）"
                  % ", ".join(sorted(want)), file=sys.stderr)
            return 2
    if args.list:
        print(json.dumps({"tests": len(ids), "modules": len({module_of(t) for t in ids})},
                         ensure_ascii=False))
        return 0

    if args.affected and not args.write_weights:
        ids, why = affected_selection(ids)
        print("  受影响选择：%s → %d 条测试" % (why, len(ids)))
        if not ids:
            print("  受影响集为空（修复指引：用 --jobs 0 或 --full 档跑全量）", file=sys.stderr)
            return 2

    if args.write_weights:
        t0 = time.perf_counter()
        measured, per_test = measure_weights(ids)
        if args.mods:
            # 增量重测（只重测指定模块）：与既有基线**合并**，而不是整份覆盖——
            # 全量重测是 30 分钟量级，改一条测试就逼全量重测会让棘轮没人肯跟。
            old_path = ROOT / WEIGHTS_REL
            old = json_doc.load(old_path, dict, what=WEIGHTS_REL) if old_path.is_file() else {}
            old_mod = dict(old.get("modules") or {})
            old_tests = {k: v for k, v in (old.get("tests") or {}).items()
                         if module_of(k) not in measured}
            old_mod.update(measured)
            old_tests.update(per_test)
            measured, per_test = old_mod, old_tests
        doc = {"schema": "nf-check12-weights/1",
               "note": "check12 墙钟基线（--write-weights 实测；P0 棘轮与分片均衡共用）",
               "measured_at": time.strftime("%Y-%m-%d"),
               "total_s": round(sum(measured.values()), 1),
               "modules": measured,
               "tests": per_test}
        atomic_write.write_text(
            ROOT / WEIGHTS_REL,
            json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        print("  ✓ 权重已写入 %s：模块 %d · 逐测试 %d · 合计 %.1f s（墙钟 %.1f s）"
              % (WEIGHTS_REL, len(measured), len(per_test), doc["total_s"],
                 time.perf_counter() - t0))
        return 0

    jobs = args.jobs or int(os.environ.get("NF_TEST_JOBS") or 4)
    jobs = max(1, min(jobs, len(ids)))
    weights_doc = load_weights()
    ws = test_weights(ids, weights_doc.get("modules", {}), weights_doc.get("tests", {}))

    # 负载敏感模块走**独占串行段**（2026-10-18 实测）：test_atomic_write / test_daemon 的
    # 失败注入在 8 片并发下会偶发"补丁未生效"（隔离跑必绿、满负载下偶红）。这不是判据强弱问题，
    # 而是**负载敏感**：它们自身要在进程内打桩/起守护，8 路并发把进程创建与文件系统延迟放大到
    # 足以改变时序。
    # 处置：这两族放到并行段之后**独占跑**（仍跑全部用例，一条不减），换确定性。
    serial_ids = [t for t in ids if module_of(t) in SERIAL_MODULES]
    parallel_ids = [t for t in ids if module_of(t) not in SERIAL_MODULES]

    t0 = time.perf_counter()
    results = []
    if jobs == 1:
        results = [run_shard(ids, 0)]
    else:
        pjobs = max(1, min(jobs, max(1, len(parallel_ids))))
        # **动态工作队列**（B1，2026-10-18）：静态 LPT 分箱在"负载不均"时会有长尾（实测 16 片：
        # 均值 259 s / 最大 346 s）。这里把测试按权重切成约 4×jobs 个小片，由一个队列喂给
        # jobs 个 worker——谁先跑完谁领下一片，尾巴被摊平。切片**只改调度**：并集仍逐项等于
        # discover 全集（下面照旧校验），每片仍是独立进程 + 独立 NF_HOME。
        chunks = chunk_items(parallel_ids, ws, pjobs, factor=4)
        flat = [t for c in chunks for t in c]
        if sorted(flat) != sorted(parallel_ids):
            print("工作队列切片与 discover 不一致（漏/重）：%d vs %d"
                  % (len(flat), len(parallel_ids)), file=sys.stderr)
            return 1
        import queue as _queue
        import threading
        q = _queue.Queue()
        for i, c in enumerate(chunks):
            q.put((i, c))
        results_box = []
        lock = threading.Lock()

        def _worker():
            while True:
                try:
                    idx, c = q.get_nowait()
                except _queue.Empty:
                    # 队列已空 = 所有片都被领走，worker 正常退出（不是吞错：没有错误发生，
                    # 也没有任何失败信息被丢弃——失败只会来自 run_shard 的 rc）。
                    break
                try:
                    r = run_shard(c, idx)
                except Exception as exc:          # noqa: BLE001 —— worker 崩了要当分片失败，不是静默
                    r = {"index": idx, "rc": 1, "out": "worker 异常：%r" % (exc,),
                         "wall": 0.0, "tests": len(c)}
                with lock:
                    results_box.append(r)

        threads = [threading.Thread(target=_worker, daemon=True) for _ in range(pjobs)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        results = sorted(results_box, key=lambda r: r["index"])
        if serial_ids:
            results.append(run_shard(serial_ids, len(chunks)))
    wall = time.perf_counter() - t0
    failed = [r for r in results if r["rc"] != 0]

    if args.json:
        print(json.dumps({"schema": "nf-verify-tests/1", "jobs": jobs,
                          "wall_s": round(wall, 1), "tests": len(ids),
                          "failed_shards": len(failed),
                          "shards": [{"index": r["index"], "rc": r["rc"],
                                      "wall_s": r["wall"], "tests": r["tests"]}
                                     for r in results]},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for r in results:
            tail = " ".join(r["out"].strip().splitlines()[-1:])[:110]
            print("  分片%d：测试 %d · %.1f s · rc=%d  %s"
                  % (r["index"], r["tests"], r["wall"], r["rc"], tail))
        print("  合计 %d 条测试 · %d 分片 · 墙钟 %.1f s" % (len(ids), jobs, wall))
    for r in failed:
        print("---- 分片%d 失败（rc=%d）末 40 行 ----" % (r["index"], r["rc"]), file=sys.stderr)
        print("\n".join((r["out"] or "").splitlines()[-40:]), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    # stdio 钉 UTF-8：Windows 控制台 GBK 下 ✓ 即 UnicodeEncodeError（仓库约定同 nf.py）
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
