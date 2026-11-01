#!/usr/bin/env python3
# nf-io: inputs=git,docs outputs=-
"""**开发快车道**：按改动跑增量 check（薄适配层；判据真源在 core.gate_*）。

它做什么 / 不做什么
-------------------
- **做**：把「改了什么」→「该跑哪些测试模块」这件事交给既有的门禁影响分析子系统
  （`core/gate_select` 选择 + `core/gate_check` 编排 + `core/gate_verdict` 判定缓存），
  再由本脚本渲染成 verify.sh 口径的人读行。**本脚本不自己判断该跳谁**。
- **不做**：不改 check 判据、不写仓库、不产生「门禁结论」。它是 verify.sh 的
  **增量档**（`bash verify.sh --fast`），**永远不能替代全量档**。
- **不发散**（2026-10-14 复核结论）：这套选择/缓存机制在仓库里已完整实现并有 8 个单测，
  真正缺的只是「没有生产调用方」——本脚本就是那个调用方，不重写任何判据。

为什么是薄层
------------
`scripts/gate.py --check` 已经是同一件事的入口，但它 :109-116 每个模块 spawn 一次
`python -m unittest`（在进程启动贵的平台上是每模块的固定税）。本脚本改为**调用方注入
runner**：默认在 `desktop/` 下起一次 `unittest discover`-等价的模块级子进程，但把
**输出重定向到日志**、只回退出码——省的是解释器启动次数不便，收益来自「并行 + 判定缓存 +
只跑该跑的」；执行契约仍是一个模块一个子进程（与 gate 子系统的假设一致）。
若某次改动就该跳过所有模块（例如只改了文档），本脚本会明说「无待跑模块」。

用法
----
    python scripts/verify_fast.py                    # 变更集 = git diff HEAD~1...HEAD + 工作区
    python scripts/verify_fast.py --base origin/main # 指定比较基线
    python scripts/verify_fast.py --plan-only        # 只出计划，不执行
    python scripts/verify_fast.py --all              # 含慢车道（定时/发布用）
    python scripts/verify_fast.py --strict           # 慢车道让位算 FAIL（发布前用）
    python scripts/verify_fast.py --json             # 机器面

退出码：0 = 该跑的模块全绿；1 = 有红 / --strict 下有让位；2 = 用法或环境错误。

纪律
----
- **只读仓库**：唯一写点是 `tempfile.mkdtemp()` 下的日志目录（自动清理）。
- **fail-closed 沿用 core.gate_select**：未观测 / 读面不可信 / 本模块自身被改 → 一律跑。
- **数据面缺席即明说**：读面数据（faces.json）在缓存区、干净检出必缺；缺时不假装选中，
  直接提示「按 fail-closed 全量」并给出生成办法。
"""
from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404 - 只跑仓库内测试（argv 列表、无 shell）
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write  # noqa: E402 - 落盘唯一入口（脚本面禁裸写）
from core import gate_check as gcheck  # noqa: E402
from core import gate_select as gselect  # noqa: E402


def _norm(p: object) -> str:
    """路径归一：posix 分隔符（与 `gate_faces._posix` 同一口径）。"""
    return str(p).replace("\\", "/")


def _git(*args: str) -> tuple:
    """跑一条只读 git 命令 → (exit_code, stdout)。失败不抛（调用方按三态处理）。"""
    try:
        proc = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,  # noqa: S603,S607
                              timeout=60)  # nosec B603 B607 - 只读 git 子命令，argv 列表（无 shell）
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def changed_files(base: str) -> tuple:
    """→ (changed, note, problems)。

    changed = 去重排序、posix 化的仓库相对路径集合，取三处并集：
      ① `git diff --name-only --diff-filter=ACMR <base>`（base 到工作区，含未提交）；
      ② `git status --porcelain` 的未跟踪件（`git diff` 看不见新文件）。
    这样「改了但没提交」「提交了没 push」两类都能被看见；`--diff-filter=ACMR` 排除已删除件
    （删掉的路径当「变更」会误导读面匹配）。
    """
    problems: list = []
    code, out = _git("rev-parse", "--verify", "--quiet", base + "^{commit}")
    if code != 0 or not out.strip():
        problems.append("比较基线不可解析：%s（深度浅的检出可能没有父提交；用 --base 指定）" % base)
        return [], "", problems
    code, out = _git("diff", "--name-only", "--diff-filter=ACMR", base)
    if code != 0:
        problems.append("git diff 失败（base=%s）" % base)
        return [], "", problems
    changed = {_norm(l.strip()) for l in out.splitlines() if l.strip()}
    code, out = _git("status", "--porcelain")
    if code == 0:
        for line in out.splitlines():
            if line.startswith("?? "):
                changed.add(_norm(line[3:].strip()))
    note = "%s → 工作区（含未跟踪件）" % base
    return sorted(changed), note, problems


def _load_faces_from_file(path: str) -> dict:
    """把一份 faces.json 当**数据源**读进来（不改任何全局状态）→ select 用的 doc。

    为什么需要：`core.gate_select.load_faces` 只读缓存区那个固定落点；本脚本要能把
    「一份归档的读面数据」喂给同一套选择器（单测/CI artifact 两条路径共用）。
    解析失败 → `{}`（调用方按 fail-closed 全跑处理，不抛）。
    """
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    got = doc.get("modules") if isinstance(doc, dict) else None
    return got if isinstance(got, dict) else {}


def _render_plan(plan_doc: dict, changed: list, note: str, faces_seen: int,
                 faces_total: int) -> list:
    """人读行（verify.sh 口径；确定性：所有名单 sorted）。"""
    passed = len(plan_doc["cached"]) + len(plan_doc["to_run"])
    lines = [
        "== 增量核验（开发快车道；真源 = core.gate_*）==",
        "  变更集 %d 件（%s）· 读面数据 %d/%d 模块%s"
        % (len(changed), note, faces_seen, faces_total,
           "" if faces_seen else "（缺席 → fail-closed 全量）"),
        "  计划 %d：命中缓存 %d · 真跑 %d · 慢车道让位 %d · 跳过 %d · 常跑不可缓存 %d"
        % (passed, len(plan_doc["cached"]), len(plan_doc["to_run"]),
           len(plan_doc["deferred"]), len(plan_doc["skipped"]),
           len(plan_doc["uncacheable"])),
    ]
    if plan_doc["deferred"]:
        names = ", ".join(sorted(str(d) for d in plan_doc["deferred"]))
        lines.append("  [让位] 慢车道（不在本档跑，全量档/--all 覆盖）：%s"
                     % (names if len(names) <= 300 else names[:300] + " …"))
    if not passed:
        lines.append("  [i] 本变更集按读面无待跑模块（不等于门禁通过——全量档仍须跑）")
    return lines


def _render_result(result: dict) -> list:
    failed = sorted(result.get("failed") or [])
    lines = ["  执行结果：墙钟 %ss · 绿 %d · 红 %d"
             % (result.get("wall"), len(result.get("fresh") or []), len(failed))]
    for mod in failed:
        lines.append("  [红] %s" % mod)
    return lines

def _make_runner(log_dir: str, timeout: int):
    """→ runner(mod) 契约（与 core.gate_check.execute 的 invoke 同形）。

    输出一律落 `<log_dir>/logs/<mod>.log`，且**经 `core.atomic_write`** 落盘——
    脚本面禁裸写是本仓的既有判据（`test_core_atomic_writes`），本文件不例外。
    超时后**只重试一次**（`unittest` 本身已有超时保护，重试是为覆盖建立进程被杀 的边界）。
    """
    logs = Path(log_dir) / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    def _write_log(mod: str, text: str) -> None:
        atomic_write.write_text(str(logs / ("%s.log" % mod)), text)

    def _run_once(mod: str, timeout_: int) -> tuple:
        import time
        started = time.perf_counter()
        try:
            proc = subprocess.run(  # noqa: S603,S607  # nosec B603 B607
                [sys.executable, "-m", "unittest", "tests.%s" % mod, "-q"],  # argv 列表、无 shell
                cwd=str(ROOT / "desktop"), capture_output=True, timeout=timeout_)
        except subprocess.TimeoutExpired as exc:
            _write_log(mod, "TIMEOUT after %ss\n%s" % (timeout_,
                                                        (exc.stdout or b"").decode("utf-8", "replace")))
            raise
        except OSError as exc:
            _write_log(mod, "OSError: %s\n" % exc)
            return 125, round(time.perf_counter() - started, 2)
        text = (proc.stdout or b"").decode("utf-8", "replace")
        if proc.stderr:
            text += "\n" + proc.stderr.decode("utf-8", "replace")
        _write_log(mod, text)
        return proc.returncode, round(time.perf_counter() - started, 2)

    def _run(mod: str, timeout_: int = timeout):
        try:
            return _run_once(mod, timeout_)
        except subprocess.TimeoutExpired:
            try:
                return _run_once(mod, timeout_)
            except subprocess.TimeoutExpired:
                return 124, float(timeout_)

    return _run


def _tail(path: Path, n: int = 3) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            rows = [l.rstrip() for l in fh if l.strip()]
    except OSError:
        return ""
    return " | ".join(rows[-n:])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="开发快车道：按改动跑增量 check（只读仓库）")
    ap.add_argument("--base", default="HEAD~1",
                    help="比较基线（缺省 HEAD~1；须是能解析的提交）")
    ap.add_argument("--all", action="store_true", help="含慢车道（定时/发布用）")
    ap.add_argument("--strict", action="store_true", help="慢车道让位 / 无待跑模块 也算 FAIL")
    ap.add_argument("--no-cache", action="store_true", help="绕过判定缓存（每次真跑）")
    ap.add_argument("--workers", type=int, default=5, help="并行度（缺省 5）")
    ap.add_argument("--plan-only", action="store_true", help="只出计划，不执行")
    ap.add_argument("--faces", default="", help="读面数据文件（缺省用缓存区的 faces.json）")
    ap.add_argument("--json", action="store_true", help="机器面")
    args = ap.parse_args(argv)

    changed, note, problems = changed_files(args.base)
    if problems:
        for p in problems:
            print("  [FAIL] %s" % p)
        return 2
    doc = _load_faces_from_file(args.faces) if args.faces else gselect.load_faces(str(ROOT))
    tests_dir = ROOT / "desktop" / "tests"
    faces_total = len(list(tests_dir.glob("test_*.py")))
    plan_doc = gcheck.plan(changed, root=str(ROOT), faces=doc or None,
                           tests_dir=tests_dir, quick_only=not args.all,
                           use_cache=not args.no_cache)

    if args.plan_only:
        lines = _render_plan(plan_doc, changed, note, len(doc), faces_total)
        if args.json:
            print(json.dumps({"kind": "verify-fast-plan", "changed": changed,
                              "cached": [m for m, _v in plan_doc["cached"]],
                              "to_run": [m for m, _p in plan_doc["to_run"]],
                              "deferred": [str(d) for d in plan_doc["deferred"]],
                              "uncacheable": plan_doc["uncacheable"],
                              "skipped": len(plan_doc["skipped"])},
                             ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("\n".join(lines))
        return 0

    tmp = tempfile.mkdtemp(prefix="nf_verify_fast_")
    runner = _make_runner(tmp, timeout=600)
    result = gcheck.execute(plan_doc, runner, workers=max(1, args.workers))
    result["failed"] = gcheck.failed(result)
    lines = _render_plan(plan_doc, changed, note, len(doc), faces_total)
    lines += _render_result(result)
    if result["failed"]:
        logs = Path(tmp) / "logs"
        for mod in sorted(result["failed"]):
            tail = _tail(logs / ("%s.log" % mod))
            if tail:
                lines.append("  └ %s：%s" % (mod, tail))
    lines.append("  ⚠ 增量档 ≠ 门禁结论：提交/发布前必须跑全量（bash verify.sh，无参数）")
    if args.json:
        print(json.dumps({"kind": "verify-fast", "changed": changed,
                          "planned": len(plan_doc["cached"]) + len(plan_doc["to_run"]),
                          "cached": [m for m, _v in plan_doc["cached"]],
                          "ran": [m for m, _r, _s in result.get("fresh") or []],
                          "failed": sorted(result["failed"]),
                          "deferred": [str(d) for d in plan_doc["deferred"]],
                          "uncacheable": plan_doc["uncacheable"],
                          "wall": result.get("wall"),
                          "log_dir": tmp,
                          "faces_modules": len(doc)}, ensure_ascii=False,
                         indent=2, sort_keys=True))
        return 1 if result["failed"] else 0
    print("\n".join(lines))

    if result["failed"]:
        print("  [FAIL] 待跑模块有红：%s" % ", ".join(sorted(result["failed"])))
        return 1
    if args.strict and len(plan_doc["deferred"]):
        print("  [FAIL] --strict：有 %d 个模块让位慢车道（发布前须以全量档覆盖）"
              % len(plan_doc["deferred"]))
        return 1
    tail = ("；%d 项让位慢车道，发布前用 --strict 或全量档覆盖" % len(plan_doc["deferred"])
            if plan_doc["deferred"] else "")
    print("  [PASS] 待跑模块全绿（增量档；全量结论仍以 bash verify.sh 为准）%s" % tail)
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
