#!/usr/bin/env python3
"""发布结论一键复跑（release conclusion）：干净树 → checks-only → N 分片 → 汇总。

为什么有它（2026-11-04 实测教训）：verify.sh 的 full 档单进程在本机要 35–40 分钟；
而发布结论只要求「check1-42 全过」。本脚本把这件事拆成三步可复跑，并把**我自己踩过的坑**
做成闸门：

- **脏树直接拒跑**：在改到一半的树上跑分片会产生「与输入无关的假红」（实测：文档改到一半
  去跑分片，报了一堆 conformance/living-docs 失败，全是中间态）。脏树时按 rc=2 退出。
- **先跑 checks-only**：快、抓结构性红（结构/契约/回执/纯度），失败就不必再花 40 分钟跑测试。
- **分片并行 + 并集断言**：执行器自带「分片并集 == discover 全集」断言，因此分片跑与全量跑
  判据等价；并行只改墙钟。

用法：
  python scripts/release_conclusion.py                # 缺省串行（8 片依次跑，墙钟换正确性）
  python scripts/release_conclusion.py --jobs 8       # 并发：只建议给独立 runner（单机有争用）
  python scripts/release_conclusion.py --dry-run      # 只打印计划，不执行
  python scripts/release_conclusion.py --json         # 机读汇总
与 nf release（发布编排/冻结链）分工：那个管「按什么次序冻结」，本件管「冻结后能不能发布」。
执行器：bash verify.sh --checks-only + python scripts/verify_tests.py --shard i/n
退出码：0 全过 / 1 有失败 / 2 前置不满足（脏树、参数错）。
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: **分区数**与**并发数**是两件事（2026-11-04 实测教训）：
#: - 分区（--shards）默认 8：每个分区是**独立进程**（各自 import 一套模块），因此分区并集 = 全量
#:   且互不污染。单片跑全量（--shards 1）会变成「所有测试共享一个进程」，su^ite 级顺序敏感性
#:   全部暴露（实测：单片全量出现 8 处 red，同内容 8 片独立进程全绿）。
#: - 并发（--jobs）默认 1 = 顺序执行：分片是为「CI 矩阵各跑一片（不同机器）」设计的；同一台机
#:   并发多片会在守护端口/临时目录/计时判据上互相干扰（实测 8 片并发有假红）。
DEFAULT_SHARDS = 8
DEFAULT_JOBS = 1
GUIDE = "修复指引："

def _core(name: str):
    """按需导入 desktop/src 下的 core 模块（局部导入：模块级只留纯逻辑，避开 E402）。"""
    src = str(ROOT / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import importlib

    return importlib.import_module("core." + name)


def porcelain_lines(text: str) -> list[str]:
    """git status --porcelain 输出 → 非空行列表（脏树判据的纯函数，便于单测）。"""
    return [ln for ln in (text or "").splitlines() if ln.strip()]


def dirty_guard(lines: list[str], allow_dirty: bool) -> str:
    """脏树闸门 → 拒绝原因（空串 = 放行）。"""
    if not lines or allow_dirty:
        return ""
    sample = "；".join(ln.strip() for ln in lines[:5])
    return (f"工作树不干净（{len(lines)} 处变更：{sample}）（{GUIDE}先提交或收干净再跑——"
            "在改到一半的树上跑分片会产生与输入无关的假红；确需跑加 --allow-dirty）")


def payload_drift_guard(manifest: dict | None, head: str) -> str:
    """npm payload 与 HEAD 的耦合闸门 → 拒绝原因（空串 = 放行）。

    为什么必须前置（2026-11-04 实测踩了三次）：npm 门槛要求 payload 清单里的 source_commit
    == HEAD，而 payload 是**忽略文件**——所以「工作树干净」并不代表「payload 是最新的」。
    不前置的话，要跑满 8 片（约 30 分钟）才在最后一处看见「payload 与 HEAD 不一致」，
    而且报出来的只是某个分片的一条红。
    """
    if not isinstance(manifest, dict):
        return ""                        # payload 不在场：忽略面（发布前才 stage）
    commit = str(manifest.get("source_commit") or "")
    if not commit or not head:
        return ""
    if head.startswith(commit) or commit.startswith(head):
        return ""
    return (f"npm payload 与 HEAD 不一致（清单 {commit[:12]} ≠ HEAD {head[:12]}）"
            f"（{GUIDE}在 packaging/npm 里跑 node tools/stage-payload.mjs 重新暂存——"
            "它只写忽略文件，不产生提交；暂存后再跑本件）")


def read_payload_manifest(path) -> dict | None:
    """读 payload 清单 → dict 或 None（坏件也当不在场：这条只是前置提示，不是判据本体）。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        doc = json.loads(raw)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def midrun_drift_guard(head_start: str, head_now: str, dirty_now: list[str],
                       initial_dirty: list[str] | None = None) -> str:
    """跑分片途中的树变动 → 停止原因（空串 = 稳定，可继续）。

    为什么要在**每片之前**再查一次（2026-11-06 实测）：并发会话在分片跑到一半时提交，
    8 片会分别落在不同 HEAD 上，红绿都不可信；等跑完 25 分钟才发现「HEAD 变了」太贵。
    脏变更同样致命：分片读到的是别人改了一半的文件。

    initial_dirty：启动时的脏树快照。给了它，就按「相对启动态是否**新增/变化**」判；
    不给（None）则沿用「非空即变动」。为什么要这个参数（2026-11-06）：--allow-dirty 显式
    允许起始脏树，若仍把「非空」当途中变动，第 1 片结束就会误停，选项等于失效。
    """
    if (head_now or "").strip() != (head_start or "").strip():
        return (f"HEAD 在分片途中变化（{str(head_start)[:12]} → {str(head_now)[:12]}）"
                f"（{GUIDE}已停止剩余分片——本结论无效，等树静止后重跑）")
    if not dirty_now:
        return ""
    if initial_dirty is not None and sorted(dirty_now) == sorted(initial_dirty):
        return ""
    return (f"工作树在分片途中出现改动（{len(dirty_now)} 处，例：{dirty_now[0][:60]}）"
            f"（{GUIDE}已停止剩余分片——分片读到的是改到一半的文件，结论无效）")


#: 快照模式下**不传给内层**的旗标（内层在快照目录里跑，自己就是「本仓」）。
SNAPSHOT_STRIP = ("--snapshot", "--keep-snapshot")


def strip_snapshot_flag(argv: list[str]) -> list[str]:
    """去掉外层消费的旗标 → 内层 argv（纯函数，便于单测）。"""
    return [a for a in argv if a not in SNAPSHOT_STRIP]




#: 快照互斥锁（2026-11-08 实测教训：本仓与其它工作区同时跑三份全量快照，
#: CPU 争抢把 45 分钟拉成 65+ 分钟，且两个外层进程会互相清理对方的 worktree）。
LOCK_NAME = ".snapshot.lock"
LOCK_MAX_AGE_S = 3 * 3600.0



def _read_lock_meta(lock: Path) -> dict | None:
    """读锁元数据 → dict 或 None（坏件/缺件返回 None，由调用方按「可抢」处理）。"""
    if not lock.is_file():
        return None
    try:
        doc = _core("json_doc").load(lock, dict, what=str(lock))
    except (OSError, ValueError):   # 半截/坏件锁 = 不可信 → 当作没有锁（可抢）
        return None
    return doc if isinstance(doc, dict) else None


def lock_should_reclaim(meta: dict | None, pid_alive: bool, age_s: float,
                        max_age_s: float = LOCK_MAX_AGE_S) -> str:
    """锁是否可抢 → 空串=不可抢 / 非空=可抢的理由（纯函数，便于判据）。

    口径（fail-closed）：
    ① 没有元数据（空/坏件）→ 可抢（残留锁不该永久挡住发布）；
    ② 持有进程已死 → 可抢；
    ③ 持有进程活着且未超龄 → **不可抢**（宁可让调用方等，也不并发跑两份）；
    ④ 超龄（默认 3 小时）→ 可抢（真挂死的进程不该锁死整条线）。
    """
    if not isinstance(meta, dict) or not meta:
        return "锁内容为空或坏件"
    if not pid_alive:
        return "持有进程已不在（pid=" + str(meta.get("pid")) + "）"
    if age_s >= max_age_s:
        return "锁已超龄 " + str(round(age_s / 60.0)) + " 分钟（上限 " \
               + str(round(max_age_s / 60.0)) + " 分钟）"
    return ""


def lock_acquire(base: Path, head: str, *, pid: int | None = None,
                 now: float | None = None, force: bool = False) -> tuple[bool, str]:
    """拿快照锁 → (是否拿到, 提示)。返回 False 时调用方**不得**继续跑快照。"""
    import time as _time
    lock = Path(base) / LOCK_NAME
    pid = os.getpid() if pid is None else int(pid)
    now = _time.time() if now is None else float(now)
    meta = None
    if lock.is_file():
        meta = _read_lock_meta(lock)
    if meta and not force:
        holder = int(meta.get("pid") or 0)
        age = max(0.0, now - float(meta.get("started_at") or 0.0))
        why = lock_should_reclaim(meta, _pid_alive(holder), age)
        if not why:
            return False, ("另一份全量快照正在跑（pid " + str(holder) + " · HEAD "
                           + str(meta.get("head"))[:12] + " · 已 "
                           + str(round(age / 60.0)) + " 分钟）；"
                           + GUIDE + "等它结束，或确认其进程已死后重试，或加 --force-lock")
        print("  [snapshot] 接管陈旧锁：" + why, file=sys.stderr, flush=True)
    base.mkdir(parents=True, exist_ok=True)
    _core("atomic_write").write_text(
        lock, json.dumps({"pid": pid, "head": str(head), "started_at": now},
                         ensure_ascii=False, sort_keys=True))
    return True, ""


def lock_release(base: Path, *, pid: int | None = None) -> None:
    """释放锁（只删自己的锁：别的进程接管后不误删）。"""
    lock = Path(base) / LOCK_NAME
    pid = os.getpid() if pid is None else int(pid)
    meta = _read_lock_meta(lock)
    if isinstance(meta, dict) and int(meta.get("pid") or 0) == pid:
        try:
            lock.unlink()   # 只删自己的锁；删不掉说明已被别人接管
        except OSError:     # 权限/竞态：锁已在别处处理，静默降级不阻断
            return




def lock_acquire_wait(base: Path, head: str, *, pid: int | None = None,
                      wait_s: float = 0.0, poll_s: float = 5.0,
                      force: bool = False) -> tuple[bool, str]:
    """拿锁（可等待）→ (是否拿到, 提示)。

    为什么不只是「拿不到就退出」：并发会话里**等待**比报错更省人力（尤其夜里排队跑）；
    等待期间每 poll_s 复查一次，被抢断/超龄就立刻接管，不会无限等一份死锁。
    wait_s<=0 → 只试一次（与 lock_acquire 等价）。
    """
    import time as _time

    deadline = _time.time() + max(0.0, float(wait_s))
    while True:
        ok, why = lock_acquire(base, head, pid=pid, force=force)
        if ok or _time.time() >= deadline:
            return ok, why
        print("  [snapshot] 等待快照锁：" + why, file=sys.stderr, flush=True)
        _time.sleep(max(0.5, float(poll_s)))

def _pid_alive(pid: int) -> bool:
    """进程是否还活着（Windows: tasklist 绝对路径；POSIX: os.kill(pid, 0)）。

    一律走 core 的受控进程原子（argv 列表 / 无 shell / 超时即回收）——脚本面不自己起
    subprocess（SAST S603/S607 与 purity R6 都盯这条），这也是本件 `_run` 的既有口径。
    """
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:   # 非 Windows 存活探测：OSError = 进程不存在（按死处理）
            return False
    src = str(ROOT / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from core.atoms import proc as proc_atom  # 局部导入：模块级只留纯逻辑

    exe = shutil.which("tasklist")
    if not exe:
        return False
    got = proc_atom.run_capture([exe, "/FI", "PID eq " + str(pid), "/NH"], timeout=15)
    return str(pid) in str(got.get("out") or "")


def snapshot_dir_name(head: str) -> str:
    """快照目录名：带 HEAD 短哈希，冲突可辨（纯函数）。"""
    return f"nf-gate-snap-{str(head)[:12]}"


#: 快照默认落点：仓库同盘的 .worktrees/（已被 .gitignore 忽略）。为什么不放 $TEMP：
#: 2026-11-06 实测 C 盘 100% 满（剩余 84 MB），tempfile.mkdtemp 直接把整次门禁打成 ENOSPC。
SNAP_BASE_DEFAULT = ".worktrees/gate-snap"

def snapshot_base(root: Path, override: str = "") -> Path:
    """快照基目录（纯函数）：显式覆盖优先，否则落在仓库同盘。"""
    raw = (override or "").strip() or SNAP_BASE_DEFAULT
    path = Path(raw)
    return path if path.is_absolute() else (root / path)


def _snapshot_free_bytes(path: Path) -> int:
    """落点所在卷的可用字节；量不出来就返回 -1（不阻断，只告警）。"""
    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    try:
        return int(shutil.disk_usage(str(probe)).free)
    except OSError:
        return -1


def _rm_tree(path: str) -> None:
    """删一棵**本模块自己建的**临时树（单一 sink 站点；落点从不来自外部输入）。"""
    shutil.rmtree(path, ignore_errors=True)


def stale_snapshot_dirs(entries: list[tuple[str, float]], live: set, now: float,
                        max_age_s: float = 6 * 3600.0, keep: str = "") -> list[str]:
    """陈旧快照目录（纯函数，判据可单测）→ 待清理的绝对路径列表。

    规则：**已注册的在跑 worktree 永不清**、当前这次的不清、其余超过 max_age_s 才清。
    为什么要清（2026-11-06 实测）：失败/中断的快照会留在 .worktrees/gate-snap/，几个就几百 MB，
    迟早把盘撞满——那会伪装成「门禁红」。
    """
    out = []
    for raw, mtime in entries:
        path = str(raw)
        if path == keep:
            continue
        if os.path.abspath(path) in live:
            continue
        if now - float(mtime or 0.0) < max_age_s:
            continue
        out.append(path)
    return sorted(out)


def _live_worktree_paths() -> set:
    proc = _run(["git", "worktree", "list", "--porcelain"], 120)
    out = set()
    for line in (proc.get("out") or "").splitlines():
        if line.startswith("worktree "):
            out.add(os.path.abspath(line[len("worktree "):].strip()))
    return out


def _snapshot_prune(base: Path, keep_wt: str = "") -> list[str]:
    """清掉陈旧快照（先交还 git 注册，再删目录）→ 已清理路径列表。"""
    if not base.is_dir():
        return []
    live = _live_worktree_paths()
    entries = []
    for child in sorted(base.iterdir()):
        try:
            entries.append((str(child), child.stat().st_mtime))
        except OSError:  # 刚被别的进程清掉/无权限读 mtime：跳过这目录即可，清理不依赖它
            continue
    stale = stale_snapshot_dirs(entries, live, time.time(), keep=keep_wt)
    for path in stale:
        _run(["git", "worktree", "remove", "--force", path], 300)
        _rm_tree(path)
    if stale:
        _run(["git", "worktree", "prune"], 120)
    return stale


def _snapshot_create(head: str, base: Path, need_mb: int = 400) -> tuple[str, str]:
    """在临时目录建 HEAD 的 detached worktree → (路径, 错误说明)。

    为什么要快照（2026-11-06 实测）：本仓常有并发 agent 会话，它们会在我跑 36 分钟门禁的
    时候提交、改文件、甚至改门禁脚本自己——8 片于是落在不同状态上，红绿都不可信。
    快照把结论**钉在一个 SHA** 上：证明「这个提交的内容是绿的」，与工作区完全解耦。
    """
    free = _snapshot_free_bytes(base)
    if 0 <= free < need_mb * 1024 * 1024:
        return "", (f"快照落点空间不足（{base} 可用 {free // 1048576} MB，需 ≥{need_mb} MB）"
                    f"（{GUIDE}用 --snapshot-dir 指到空间充足的卷，或先清理旧快照）")
    base.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix=snapshot_dir_name(head) + "-", dir=str(base)))
    path = str(run_dir / "wt")
    proc = _run(["git", "worktree", "add", path, "--detach", head], 300)
    if proc.get("code") != 0:
        _rm_tree(str(run_dir))
        return "", (f"建快照失败（{proc.get('err') or proc.get('out') or '未知错误'}）"
                    f"（{GUIDE}确认 git 可用、HEAD={str(head)[:12]} 存在）")
    return path, ""


def _snapshot_stage_payload(path: str) -> str:
    """在快照里按该 SHA 重新暂存 npm payload（只写忽略文件；不产生提交）。→ 错误说明"""
    proc = _run(["node", "tools/stage-payload.mjs"], 900, cwd=os.path.join(path, "packaging",
                                                                        "npm"))
    if proc.get("code") != 0:
        return (f"快照里 payload 暂存失败（{proc.get('err') or proc.get('out')}）"
                f"（{GUIDE}确认 node 可用，或改用 --allow-dirty 在活树上跑）")
    return ""


def _snapshot_remove(path: str) -> None:
    _run(["git", "worktree", "remove", "--force", path], 300)
    _run(["git", "worktree", "prune"], 120)


def _snapshot_remove_tmp(path: str) -> None:
    """清掉快照的独立临时目录（盘根 .nf-gate-tmp 下，与路径一起收）。"""
    drive = os.path.splitdrive(os.path.abspath(path))[0] or ""
    run_name = os.path.basename(os.path.dirname(path))
    if drive and run_name:
        shutil.rmtree(os.path.join(drive + os.sep, ".nf-gate-tmp", run_name),
                      ignore_errors=True)


def head_move_guard(start: str, end: str) -> str:
    """运行期间 HEAD 是否移动 → 无效原因（空串 = 没移动，结论可用）。

    为什么要这条（2026-11-05 实测）：本仓常有并发 agent 会话。我第一次跑发布结论时，
    另一个会话在跑动中提交了 3 个 commit——分片们分别在不同 HEAD 上跑完，出来的红全是
    别人的中间态，那份结论既不能当绿也不能当真红。结论必须绑定**一个** HEAD。
    """
    start = (start or "").strip()
    end = (end or "").strip()
    if not start or not end or start == end:
        return ""
    return (f"工作树在运行期间被改动（HEAD {start[:12]} → {end[:12]}）"
            f"（{GUIDE}本次结论无效：请在工作区静止后重跑；并发会话下先确认 HEAD 不再移动）")


def aggregate(results: list[dict]) -> dict:
    """分片结果汇总 → {ok, total, failed, wall}（纯函数，便于单测）。"""
    failed = [r for r in results if int(r.get("rc") or 0) != 0]
    return {"ok": bool(results) and not failed,
            "total": len(results),
            "failed": [{"shard": r.get("shard"), "rc": r.get("rc")} for r in failed],
            "wall": round(sum(float(r.get("wall") or 0.0) for r in results), 1)}


def _run(argv: list[str], timeout: float, cwd: str = "", env: dict | None = None) -> dict:
    """跑**本仓固定命令** → {code, out, err}；cwd 缺省为仓库根。

    统一走 core 的受控进程原子：本件不再自己起 subprocess（那是 SAST 面要逐处标注的东西，
    而受控原子已经把「argv 列表 / 无 shell / 超时即回收」写死在一处）。
    """
    src = str(ROOT / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from core.atoms import proc as proc_atom  # 局部导入：模块级只留纯逻辑
    return proc_atom.run_capture(argv, cwd=cwd or str(ROOT), env=env, timeout=timeout)


def _git_status() -> list[str]:
    proc = _run(["git", "status", "--porcelain"], 120)
    if proc.get("code") is None:
        # git 不可用（非 git 检出/权限）：按「无脏树信息」处理，不阻断——判据只做门禁不放行
        return []
    return porcelain_lines(proc.get("out") or "")


#: 生成物新鲜度前置（秒级）：提交件 == 实时重算。脚本自带逐项修复命令。
FRESHNESS_SCRIPT = "scripts/freshness_check.py"


def _step_freshness(verbose: bool) -> dict:
    """跑生成物新鲜度前置检查 → 行结果（失败带末段输出）。"""
    t0 = time.perf_counter()
    proc = _run([sys.executable, FRESHNESS_SCRIPT], 900)
    rc = proc.get("code")
    out = (proc.get("out") or "") + (proc.get("err") or "")
    row = {"id": "freshness", "rc": 1 if rc is None else int(rc),
           "wall": round(time.perf_counter() - t0, 1)}
    if row["rc"] != 0:
        row["tail"] = [ln for ln in out.splitlines() if ln.strip()][-12:]
    if verbose:
        mark = "✓" if row["rc"] == 0 else "✗"
        print(f"  {mark} 生成物新鲜度 · {row['wall']} s", flush=True)
    return row


#: 静态棘轮（秒级）：风格 / 代码规模与复杂度 / 模块级耦合 / SAST。
#: 这四条都是「超基线即红」的静态判据，合计约 12 s——比花 6 分钟跑 checks-only、
#: 再花 30 分钟跑测试去撞它划算得多（2026-11-05 实测：跨会话留下的风格债就是这么撞到的）。
RATCHET_STEPS = (
    ("style", ["python", "scripts/style_check.py"], "风格棘轮（命中只许下降）"),
    ("code_metrics", ["python", "scripts/code_metrics.py"], "代码规模/复杂度上限"),
    ("coupling", ["python", "scripts/coupling_metrics.py"], "模块级耦合度量（环/SDP）"),
    ("sast", ["python", "scripts/sast_check.py"], "SAST 基线闸门（bandit/ruff-S）"),
)


def ratchet_issues(rows: list[dict]) -> list[str]:
    """静态棘轮结果 → 问题列表（纯函数：便于单测门槛本身）。"""
    out = []
    for row in rows:
        if row.get("skipped") or int(row.get("rc") or 0) == 0:
            continue
        tail = (row.get("tail") or [""])[-1]
        out.append(f"{row.get('id')} 未过：{tail}")
    return out


def _step_ratchets(verbose: bool) -> list[dict]:
    """跑四条静态棘轮（各脚本自带修复指引；失败带末几行输出）。"""
    rows: list[dict] = []
    for cid, argv, desc in RATCHET_STEPS:
        t0 = time.perf_counter()
        proc = _run([sys.executable, *argv[1:]], 900)
        rc = proc.get("code")
        row = {"id": cid, "desc": desc, "rc": 1 if rc is None else int(rc),
               "wall": round(time.perf_counter() - t0, 1)}
        if row["rc"] != 0:
            out = (proc.get("out") or "") + (proc.get("err") or "")
            row["tail"] = [ln for ln in out.splitlines() if ln.strip()][-8:]
        if verbose:
            mark = "✓" if row["rc"] == 0 else "✗"
            print(f"  {mark} {cid} · {desc} · {row['wall']} s", flush=True)
        rows.append(row)
    return rows


#: 我们需要的 bash：git-bash / MSYS / cygwin 一类（能认 Windows 路径、能跑本仓 verify.sh）。
#: System32 里的 bash.exe 是 WSL：在 Windows 上它会把 /d/NinFenz 当成不存在的路径，
#: 于是 bash verify.sh --checks-only 返回 rc=1 且**零输出**——看起来像「checks-only 未过」。
BASH_MARKERS = ("msys", "cygwin", "mingw", "git")


def bash_identity_ok(uname_o: str) -> str:
    """bash 身份判据（纯函数）→ 空串=可用；否则给原因（带指引）。"""
    text = (uname_o or "").strip().lower()
    if not text:
        return ("bash 身份探针无输出（修复指引：确认 bash 可用；Windows 上请用 git-bash，"
                "别落到 System32 的 bash.exe（那是 WSL））")
    if any(marker in text for marker in BASH_MARKERS):
        return ""
    got = uname_o.strip()
    return (f"bash 不是 git-bash 系（uname -o 返回 {got}）（修复指引：Windows 上从 PowerShell "
            "启动时 PATH 里的 bash 可能是 WSL——请显式用 git-bash 的 bash.exe，或直接走 "
            "ops_bash 的 bash 跑本件）")


def _step_checks_only(verbose: bool) -> tuple[int, float]:
    t0 = time.perf_counter()
    if verbose:
        print("[4/5] bash verify.sh --checks-only …", flush=True)
    probe = _run(["bash", "-c", "uname -o"], 60)
    ident = bash_identity_ok(probe.get("out") or "")
    if ident:
        if verbose:
            print(f"  ✗ {ident}", flush=True)
        return 2, time.perf_counter() - t0
    proc = _run(["bash", "verify.sh", "--checks-only"], 3600)
    out = (proc.get("out") or "") + (proc.get("err") or "")
    tail = [ln for ln in out.splitlines() if ln.strip()][-1:]
    rc = proc.get("code")
    if verbose:
        print(f"  => rc={rc} · {tail[0] if tail else '（无输出）'}", flush=True)
    return (1 if rc is None else int(rc)), time.perf_counter() - t0




#: 供应链核对步骤（G5）：站点数字与根投影必须与「本轮真源」一致。
#: 为什么进 gate 而不是留在文档里：这两条此前是「记得手动跑」的命令，而它们正是发布文案的
#: 数字来源——忘了跑就把旧数字发出去（我为此犯过两次）。步骤本身很便宜（秒级）。
SUPPLY_STEPS = (
    ("site_numbers", ["node", "site/tools/sync-numbers.mjs"],
     "站点数字（质量凭证 / 规模 / npm 口径）"),
    ("llms_projection", ["python", "scripts/sync_llms.py", "--check"],
     "根 llms-full 投影与 site 逐字节一致"),
)


def supply_chain_issues(rows: list[dict]) -> list[str]:
    """供应链步骤结果 → 问题列表（纯函数：便于单测门槛逻辑本身）。"""
    out = []
    for row in rows:
        if row.get("skipped"):
            continue
        if int(row.get("rc") or 0) != 0:
            tail = (row.get("tail") or [""])[-1]
            out.append(f"{row.get('id')} 未过：{tail}")
    return out


def _step_supply_chain(verbose: bool) -> list[dict]:
    """跑供应链核对步骤（缺工具则记 skipped，不假装通过）。"""
    rows: list[dict] = []
    for cid, argv, desc in SUPPLY_STEPS:
        if argv[0] == "python":
            argv = [sys.executable, *argv[1:]]
        t0 = time.perf_counter()
        proc = _run(argv, 300)
        rc = proc.get("code")
        row = {"id": cid, "desc": desc, "rc": 1 if rc is None else int(rc),
               "wall": round(time.perf_counter() - t0, 1)}
        if rc is None:
            row["skipped"] = True
            row["rc"] = 0
        if row["rc"] != 0:
            out = (proc.get("out") or "") + (proc.get("err") or "")
            row["tail"] = [ln for ln in out.splitlines() if ln.strip()][-6:]
        if verbose:
            mark = "✓" if row["rc"] == 0 else "✗"
            more = "（工具缺失，跳过）" if row.get("skipped") else ""
            print(f"  {mark} {cid} · {desc}{more}", flush=True)
        rows.append(row)
    return rows


def _shard_one(index: int, total: int) -> dict:
    t0 = time.perf_counter()
    argv = [sys.executable, "scripts/verify_tests.py", "--shard",
            f"{index}/{total}", "--json"]
    proc = _run(argv, 3600)
    rc = proc.get("code")
    row = {"shard": f"{index}/{total}", "rc": 1 if rc is None else int(rc),
           "wall": round(time.perf_counter() - t0, 1)}
    if row["rc"] != 0:
        # 失败必须自带证据：只报「某片红了」等于把诊断成本丢给下一个人（实测教训：
        # 全量串行红了一次却因为没留分片输出，只能整轮重跑取证）。
        out = (proc.get("out") or "") + (proc.get("err") or "")
        row["tail"] = [ln for ln in out.splitlines() if ln.strip()][-40:]
    return row


def _read_text(path: str) -> str:
    """读内层日志（大件也一次性读；门禁日志量级 < 1 MB）。读不到就当空串。"""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def snapshot_temp_dir(path: str) -> str:
    """快照内层临时目录：**同一卷、且在主仓树之外**的盘根独立目录。

    两个约束都来自实测（2026-11-06）：① 与快照同盘，否则 C 盘满时测试自己 ENOSPC；
    ② 不能落在任何仓库树内，否则 npm 包的 findRepoRoot 会向上命中活树、不触发解包，
    test_payload_is_extracted_to_cache_and_runs 假红。
    """
    drive = os.path.splitdrive(os.path.abspath(path))[0] or ""
    run_name = os.path.basename(os.path.dirname(path))
    return os.path.join(drive + os.sep, ".nf-gate-tmp", run_name, "tmp")


def snapshot_home_dir(path: str) -> str:
    """快照内层 NF_HOME：快照旁边（不进仓库树），守护/缓存/会话自成一户。"""
    return os.path.join(path, "..", "home")


def snapshot_log_path(path: str) -> str:
    """内层日志：放在 run 目录里（worktree 之外，不会把快照弄脏）。"""
    return os.path.join(os.path.dirname(path), "gate.log")


def _run_in_snapshot(args, head: str) -> int:
    """外层入口：**先拿互斥锁**再建快照，结束后无论成败都释放。

    为什么加锁（2026-11-08 实测）：本仓与其它工作区同时跑三份全量快照，
    CPU 争抢把 45 分钟拉到 65+ 分钟，且两份外层会互相清理对方 worktree。
    锁是 fail-closed 的：拿不到就不跑，宁可让调用方等。
    """
    base = snapshot_base(ROOT, getattr(args, "snapshot_dir", "") or "")
    # 测试/CI 可把锁落到独立目录（避免测试与真跑抢同一把锁）
    lock_base = Path(os.environ.get("NF_SNAPSHOT_LOCK_DIR") or base)
    ok, why = lock_acquire_wait(lock_base, head,
                                wait_s=float(getattr(args, "lock_wait", 0.0) or 0.0),
                                force=bool(getattr(args, "force_lock", False)))
    if not ok:
        print("  ✗ " + why, file=sys.stderr)
        return 2
    try:
        return _run_in_snapshot_body(args, head)
    finally:
        lock_release(lock_base)


def _run_in_snapshot_body(args, head: str) -> int:
    """外层主体：建快照 → 在快照里跑一遍本件（不带 --snapshot）→ 回报 → 清理。

    内层是**独立进程**：它的 ROOT 就是快照目录，所以 payload 对账 / 新鲜度 / 分片天然
    都作用在快照上，无需把 cwd 透传到每个 helper。结论因此绑定**一个 SHA**。
    """
    base = snapshot_base(ROOT, getattr(args, "snapshot_dir", "") or "")
    src = str(ROOT / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from core import json_doc as json_doc_mod  # 局部导入：模块级只留纯逻辑

    pruned = _snapshot_prune(base)
    if pruned:
        names = ", ".join(p.split(os.sep)[-1] for p in pruned)
        print(f"  [snapshot] 清理陈旧快照 {len(pruned)} 个：{names}",
              file=sys.stderr, flush=True)
    path, err = _snapshot_create(head, base)
    if err:
        print(f"  ✗ {err}", file=sys.stderr)
        return 2
    log_path = snapshot_log_path(path)
    print(f"  [snapshot] HEAD {head[:12]} · 内层日志 {log_path}（可另开终端 tail -f）",
          file=sys.stderr, flush=True)
    try:
        stage_err = _snapshot_stage_payload(path)
        if stage_err:
            print(f"  ✗ {stage_err}", file=sys.stderr)
            return 2
        inner = [sys.executable, os.path.join(path, "scripts", "release_conclusion.py"),
                 *strip_snapshot_flag(sys.argv[1:])]
        # 内层临时件要同时满足两件事（2026-11-06 快照实测都是真红）：
        # ① 与快照同盘：C 盘满时测试自己会 ENOSPC（实测 84 MB 剩余跑不完）；
        # ② **在主仓树之外**：若 %TEMP% 落在仓库树内，npm 包的 findRepoRoot 会从 %TEMP% 向上
        #    命中活树，于是不触发解包，test_payload_is_extracted_to_cache_and_runs 假红。
        #    所以用「盘根下独立目录」：同盘、且任何仓库根的祖先都不是它。
        tmp_dir = snapshot_temp_dir(path)
        os.makedirs(tmp_dir, exist_ok=True)
        home_dir = snapshot_home_dir(path)
        os.makedirs(home_dir, exist_ok=True)
        env = {**os.environ, "TEMP": tmp_dir, "TMP": tmp_dir,
               # 独立 NF_HOME：快照里的守护/缓存/会话都自成一户，不会连上活树里的守护
               "NARRATIVE_FORGE_HOME": home_dir,
               "NF_GATE_IN_SNAPSHOT": "1"}
        # 内层输出**边跑边落盘**：外层用 bash 重定向（受控进程原子照旧），这样 12 分钟里
        # 另开终端 tail 就能看到进度，而不是盯一个空文件等半小时。
        quoted = " ".join(f'"{a}"' for a in inner)
        launcher = ['bash', '-c',
                    f'{quoted} > "{log_path}" 2>&1; echo "NFGATE_EXIT=$?"']
        proc = _run(launcher, 7200, cwd=path, env=env)
        out = _read_text(log_path)
        err_meta = proc.get("out") or ""
        inner_rc = None
        for line in err_meta.splitlines():
            if line.startswith("NFGATE_EXIT=") and line.split("=", 1)[1].strip().isdigit():
                inner_rc = int(line.split("=", 1)[1])
        # 先把内层输出整段回显（含逐片进度），再按内层退出码返回——顺序错了就等于
        # 「跑完了但什么都没告诉你」（第一版真踩过）。
        if getattr(args, "json", False) and out.strip():
            try:
                doc = json_doc_mod.loads(out, dict, what="内层门禁结论")
            except ValueError:
                sys.stdout.write(out)
            else:
                doc["snapshot"] = {"path": path, "head": head}
                print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            sys.stdout.write(out)
        if inner_rc is None:
            return 3 if proc.get("code") is None else int(proc.get("code"))
        return inner_rc
    finally:
        if getattr(args, "keep_snapshot", False):
            print(f"  [keep-snapshot] {path}", file=sys.stderr)
        else:
            _snapshot_remove(path)
        _snapshot_remove_tmp(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="release_conclusion",
                                 description="发布结论一键复跑（干净树 → 供应链核对 → "
                                             "checks-only → 分片）")
    ap.add_argument("--shards", type=int, default=DEFAULT_SHARDS,
                    help=f"分区数（缺省 {DEFAULT_SHARDS}；每片独立进程，并集 == 全量）")
    ap.add_argument("--jobs", type=int, default=DEFAULT_JOBS,
                    help=f"并发数（缺省 {DEFAULT_JOBS} = 顺序跑；>1 只建议给独立 runner）")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="允许在脏树上跑（默认拒绝：脏树会产生与输入无关的假红）")
    ap.add_argument("--skip-checks", action="store_true", help="跳过 checks-only 步骤")
    ap.add_argument("--snapshot-dir", default="",
                    help="快照落点基目录（缺省 .worktrees/gate-snap，与仓库同盘）")
    ap.add_argument("--keep-snapshot", action="store_true",
                    help="快照跑完不删（排障用；会打印路径）")
    ap.add_argument("--snapshot", action="store_true",
                    help="在 HEAD 的临时 worktree 快照里跑（免疫并发会话的实时改动）")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不执行")
    ap.add_argument("--only-preflight", action="store_true",
                    help="只跑前置面（脏树 / payload / 供应链），不跑 checks-only 与分片")
    ap.add_argument("--lock-wait", type=float, default=0.0,
                    help="拿不到快照锁时最多等多少秒（缺省 0=立刻失败；>0 排队等）")
    ap.add_argument("--force-lock", action="store_true",
                    help="接管仍在跑的快照锁（确认另一进程已死/卡死时才用）")
    ap.add_argument("--json", action="store_true", help="机读汇总")
    args = ap.parse_args(argv)

    shards = max(1, min(int(args.shards), 32))
    concurrency = max(1, min(int(args.jobs), shards))
    plan = {"root": str(ROOT), "shards": shards, "concurrency": concurrency,
            "checks_only": not args.skip_checks,
            "steps": ["git status --porcelain",
                      "packaging/npm/payload/payload-manifest.json 的 source_commit == HEAD",
                      "供应链核对（node site/tools/sync-numbers.mjs + "
                      "python scripts/sync_llms.py --check）",
                      "生成物新鲜度（python scripts/freshness_check.py）",
                      "静态棘轮（style / code_metrics / coupling / sast）",
                      "bash verify.sh --checks-only"]
                     + [f"python scripts/verify_tests.py --shard {i}/{shards}"
                        for i in range(shards)]}

    dirty = _git_status()
    initial_dirty = list(dirty)
    blocked = dirty_guard(dirty, args.allow_dirty)
    head = (_run(["git", "rev-parse", "HEAD"], 60).get("out") or "").strip()
    manifest = read_payload_manifest(ROOT / "packaging" / "npm" / "payload"
                                     / "payload-manifest.json")
    payload_blocked = payload_drift_guard(manifest, head)
    if args.snapshot and args.dry_run:
        plan["snapshot"] = f"git worktree add <tmp> --detach {head[:12]}（快照里重跑本件）"
    if args.snapshot and not args.dry_run:
        return _run_in_snapshot(args, head)

    if args.dry_run:
        payload = {"schema": "nf-release-conclusion/1", "dry_run": True, "plan": plan,
                   "dirty": dirty, "blocked": blocked, "payload_blocked": payload_blocked}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if not (blocked or payload_blocked) else 2
    if blocked:
        print(f"  ✗ {blocked}", file=sys.stderr)
        return 2
    if payload_blocked:
        payload = {"schema": "nf-release-conclusion/1", "ok": False,
                   "payload_blocked": payload_blocked, "head": head,
                   "supply_chain": [], "freshness": {"id": "freshness", "rc": 2},
                   "note": "npm payload 与 HEAD 不一致：先重新暂存再跑本件",
                   "wall": 0.0}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
              if args.json else f"  ✗ {payload_blocked}")
        if not args.json:
            print(f"  ✗ {payload_blocked}", file=sys.stderr)
        return 2
    if dirty:
        print(f"  [WARN] 脏树放行（{len(dirty)} 处变更）——结果可能含中间态假红",
              file=sys.stderr)

    t0 = time.perf_counter()
    if not args.json:
        print("[1/5] 供应链核对（站点数字 + 根投影）…", flush=True)
    supply = _step_supply_chain(not args.json)
    supply_issues = supply_chain_issues(supply)
    if not args.json:
        print("[2/5] 生成物新鲜度（提交件 == 实时重算）…", flush=True)
    fresh = _step_freshness(not args.json)
    if fresh["rc"] != 0:
        payload = {"schema": "nf-release-conclusion/1", "ok": False,
                   "supply_chain": supply, "freshness": fresh,
                   "note": "生成物已过期：先按上面的修复命令重算，再跑本件（"
                           "这类过期若留到分片里发现要多花 25 分钟）",
                   "wall": 0.0}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
              if args.json else "  ✗ 生成物过期 → 停止")
        if not args.json:
            for line in fresh.get("tail") or []:
                print(f"    {line}")
        return 1
    if supply_issues:
        payload = {"schema": "nf-release-conclusion/1", "ok": False,
                   "supply_chain": supply, "issues": supply_issues,
                   "note": "供应链核对未过：发布文案的数字来源不一致，先修再跑（"
                           "site: node site/tools/sync-numbers.mjs --write；"
                           "投影: python scripts/sync_llms.py --write）",
                   "wall": 0.0}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
              if args.json else "  ✗ 供应链核对未过 → 停止")
        return 1

    if not args.json:
        print("[3/5] 静态棘轮（风格 / 度量 / 耦合 / SAST）…", flush=True)
    ratchets = _step_ratchets(not args.json)
    ratchet_bad = ratchet_issues(ratchets)
    if ratchet_bad:
        payload = {"schema": "nf-release-conclusion/1", "ok": False,
                   "supply_chain": supply, "freshness": fresh, "ratchets": ratchets,
                   "issues": ratchet_bad,
                   "note": "静态棘轮未过：先按各脚本的修复指引收口，再跑本件"
                           "（这类红跑测试也变不绿）",
                   "wall": 0.0}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  ✗ 静态棘轮未过 → 停止")
            for line in ratchet_bad:
                print(f"    {line}")
        return 1

    if args.only_preflight:
        payload = {"schema": "nf-release-conclusion/1", "ok": True, "only_preflight": True,
                   "supply_chain": supply, "freshness": fresh,
                   "ratchets": ratchets, "issues": [],
                   "wall": 0.0}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
              if args.json else "  => 前置面全过（脏树 / payload / 供应链）")
        return 0

    checks_rc = 0
    if not args.skip_checks:
        checks_rc, _checks_wall = _step_checks_only(not args.json)
        if checks_rc != 0:
            payload = {"schema": "nf-release-conclusion/1", "ok": False,
                       "checks_only_rc": checks_rc,
                       "note": "checks-only 未过：结构性红不必再花时间跑测试",
                       "wall": 0.0}
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                  if args.json else "  ✗ checks-only 未过 → 停止")
            return 1

    if not args.json:
        print(f"[5/5] 分片 ×{shards}（并发 {concurrency}）…", flush=True)
    results: list[dict] = []
    drift = ""
    # 并发会话下「跑动中的树」会在分片途中把结论弄成垃圾：每片**之前**查一次 HEAD + 脏树，
    # 变了就停掉剩余分片（而不是等 25 分钟跑完再发现）。串行分片下这条最有效。
    def _drift_now() -> str:
        head_now = (_run(["git", "rev-parse", "HEAD"], 60).get("out") or "").strip()
        status = _run(["git", "status", "--porcelain"], 120).get("out") or ""
        return midrun_drift_guard(head, head_now,
                                  [ln for ln in status.splitlines() if ln.strip()],
                                  initial_dirty)

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {}
        for i in range(shards):
            futures[pool.submit(_shard_one, i, shards)] = i
        for fut in concurrent.futures.as_completed(futures):
            try:
                row = fut.result()
            except concurrent.futures.CancelledError:
                row = {"shard": f"{futures[fut]}/{shards}", "rc": 3, "wall": 0.0,
                       "tests": 0, "skipped": True, "note": "树在跑动中变化——已取消"}
            results.append(row)
            if not args.json:
                mark = "✓" if row["rc"] == 0 else "✗"
                print(f"  {mark} 分片 {row['shard']} · rc={row['rc']} · {row['wall']} s",
                      flush=True)
            if not drift:
                drift = _drift_now()
                if drift:
                    print(f"  ✗ {drift}", file=sys.stderr, flush=True)
                    for pending, idx in list(futures.items()):
                        if not pending.done():
                            pending.cancel()
                            results.append({"shard": f"{idx}/{shards}", "rc": 3,
                                            "wall": 0.0, "tests": 0,
                                            "skipped": True,
                                            "note": "树在跑动中变化——未执行"})
    summary = aggregate(results)
    head_end = (_run(["git", "rev-parse", "HEAD"], 60).get("out") or "").strip()
    moved = head_move_guard(head, head_end) or drift
    payload = {"schema": "nf-release-conclusion/1",
               "ok": summary["ok"] and checks_rc == 0 and not moved,
               "head_start": head, "head_end": head_end, "head_moved": bool(moved),
               "supply_chain": supply, "freshness": fresh, "ratchets": ratchets,
               "checks_only_rc": checks_rc,
               "shards": sorted(results, key=lambda r: r["shard"]),
               "failed": summary["failed"], "shard_wall_s": summary["wall"],
               "wall_s": round(time.perf_counter() - t0, 1)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        failed_rows = [r for r in results if r["rc"] != 0]
        if failed_rows:
            print("== 失败分片输出（末 40 行）==")
            for row in sorted(failed_rows, key=lambda r: r["shard"]):
                print(f"-- 分片 {row['shard']}（rc={row['rc']}）--")
                for line in row.get("tail") or []:
                    print(f"  {line}")
        print("== 发布结论 ==")
        print(f"  供应链核对：{len(supply)} 步 · 未过 {len(supply_issues)}")
        print(f"  生成物新鲜度：{fresh['wall']} s · rc={fresh['rc']}")
        print(f"  静态棘轮：{len(ratchets)} 条 · 未过 {len(ratchet_bad)}")
        print(f"  checks-only：rc={checks_rc}")
        print(f"  分片：{len(results)} 片 · 失败 {len(summary['failed'])} 片 · "
              f"分片墙钟合计 {summary['wall']} s · 总墙钟 {payload['wall_s']} s")
        verdict = "可发布（check1-42 测试侧与结构侧全过）" if payload["ok"] else "不可发布"
        print(f"  => {verdict}")
        if moved:
            print(f"  ✗ {moved}", file=sys.stderr)
    if moved:
        return 3
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    sys.exit(main())
