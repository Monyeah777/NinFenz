"""临时/scratch 区的唯一裁决点：谁用临时目录、用哪个、能不能用，只在这里判。

## 为什么需要它（三次事故同一根因，2026-10-19 实测）

1. 宿主把 /tmp 与 %TEMP% 设为不可写时，Python tempfile 会静默回退到 os.getcwd()：
   atomic_write / disk_cache 于是把临时件写进仓库根——工作树被污染、
   repo_clean 判据红、全仓扫描把 scratch 当仓库内容扫（单次判据从 2 s 涨到 >10 min）。
2. 反过来，一些受限会话里唯一可写的地方就是仓内 .rivet/tmp，一律拒绝会让
   "会话状态落盘"这类判据在此环境必红。
3. 没有单一裁决点 ⇒ 每个组件各自 tempfile.mkstemp()，行为随环境漂移、无法测试。

## 契约（fail-closed）

- resolve() 按固定优先级挑候选：NF_SCRATCH → NF_HOME/scratch → 系统临时区 →
  （仅在显式 NF_ALLOW_REPO_SCRATCH=1 时）仓内 .rivet/tmp。
- 候选必须真实可写（建目录 + 探针写入 + 删除）；不可写就换下一个。
- 仓内候选默认拒绝：宁可抛 ScratchUnavailable，也不静默落到仓库里。
- 全部候选不可用 ⇒ 抛 ScratchUnavailable（带修复指引），绝不返回 cwd。
- ensure_process_tempdir() 把裁决结果写进 tempfile.tempdir 与 TEMP/TMP/TMPDIR，
  让第三方库也不再回退到 cwd（本模块唯一允许的全局副作用，且幂等）。

## 边界

零外部依赖（只用标准库）；不 import core.*，避免被判据链反向依赖；进程内记忆结果，
测试用 reset_cache() 隔离。
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

ENV_ROOT = "NF_SCRATCH"
ENV_ALLOW_REPO = "NF_ALLOW_REPO_SCRATCH"
ENV_TTL_HOURS = "NF_SCRATCH_TTL_HOURS"
DEFAULT_TTL_HOURS = 24.0
PROBE_NAME = ".nf_write_probe"

_CACHE: dict = {}


class ScratchUnavailable(RuntimeError):
    """没有任何可写的临时区。调用方必须处理：要么显式失败，要么显式降级。"""


def _repo_root() -> Path:
    """仓库根：本文件位于 <repo>/desktop/src/core/，故 parents[3]。"""
    return Path(__file__).resolve().parents[3]


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:  # 不在其下是**正常答案**（不是错误）：返回 False，由调用方决定语义
        return False


def in_repo(path: Path) -> bool:
    """该路径是否落在仓库内（仓内候选必须显式 opt-in 这条边界的实现）。"""
    return _is_within(Path(path).resolve(), _repo_root().resolve())


def _probe_writable(d: Path) -> bool:
    """真实可写判据：建目录 → 写探针 → 读回 → 删探针。任何一步失败即不可用。"""
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / (PROBE_NAME + "." + uuid.uuid4().hex[:8])
        probe.write_text("ok", encoding="utf-8")
        got = probe.read_text(encoding="utf-8")
        probe.unlink()
        return got == "ok"
    # 探针失败＝该候选不可用（不抛：由 resolve() 汇总全部候选原因后统一 fail-closed）
    except OSError:
        return False


def _candidates() -> list:
    out = []
    explicit = os.environ.get(ENV_ROOT)
    if explicit:
        out.append(Path(explicit).expanduser())
    home = os.environ.get("NARRATIVE_FORGE_HOME") or os.path.join(
        os.path.expanduser("~"), ".NinFenz")
    out.append(Path(home) / "scratch")
    with suppress(Exception):              # gettempdir 自身也可能炸
        out.append(Path(tempfile.gettempdir()) / "nf-scratch")
    out.append(_repo_root() / ".rivet" / "tmp")
    return out


def resolve() -> Path:
    """裁决 scratch 根（进程内记忆）。不可用抛 ScratchUnavailable，绝不回退 cwd。"""
    if "root" in _CACHE:
        return _CACHE["root"]
    allow_repo = os.environ.get(ENV_ALLOW_REPO) == "1"
    tried = []
    for cand in _candidates():
        if not cand.is_absolute():
            tried.append(f"{cand}（非绝对路径，忽略）")
            continue
        if in_repo(cand) and not allow_repo:
            tried.append(f"{cand}（在仓库内，需 {ENV_ALLOW_REPO}=1）")
            continue
        if not _probe_writable(cand):
            tried.append(f"{cand}（不可写）")
            continue
        _CACHE["root"] = cand
        return cand
    raise ScratchUnavailable(
        "没有可写的临时区。候选逐个失败：" + "; ".join(tried) +
        "。修复指引：设 NF_SCRATCH 指向可写目录；受限环境可设 " +
        ENV_ALLOW_REPO + "=1 允许落在 <repo>/.rivet/tmp。")


def reset_cache() -> None:
    """清进程内记忆（测试隔离用）。"""
    _CACHE.clear()


def ensure_process_tempdir() -> Path | None:
    """把裁决结果写进 tempfile 与 TEMP/TMP/TMPDIR（幂等）。

    这是必要的全局副作用：tempfile.gettempdir() 在坏环境下返回 cwd，第三方库
    （含本仓的 atomic_write/disk_cache）会把临时件写进仓库。统一改写后，
    任何库都拿不到 cwd 这个伪临时区。
    """
    root = resolve()
    os.environ["TEMP"] = os.environ["TMP"] = os.environ["TMPDIR"] = str(root)
    tempfile.tempdir = str(root)
    return root


def gc() -> int:
    """按 TTL 清理本区下的 nf* 子目录（不碰别人的），返回删掉的目录数。"""
    root = resolve()
    ttl_h = float(os.environ.get(ENV_TTL_HOURS) or DEFAULT_TTL_HOURS)
    cutoff = time.time() - ttl_h * 3600.0
    removed = 0
    try:
        entries = list(root.iterdir())
    # 区根读不到＝没有可清理项（scratch 不是事实；清了只是省空间，不为此报错）
    except OSError:
        return 0
    for entry in entries:
        if not entry.is_dir() or not entry.name.startswith("nf"):
            continue
        try:
            if entry.stat().st_mtime > cutoff:
                continue
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
        except OSError:  # 单条 stat/删失败＝跳过它继续（GC 是尽力而为，不因一条失败中断）
            continue
    return removed


def new_dir(prefix: str = "nf") -> Path:
    """在 scratch 根下新建唯一子目录（长期件用这个，不自动清理）。"""
    root = resolve()
    d = root / f"{prefix}-{uuid.uuid4().hex[:12]}"
    d.mkdir(parents=True, exist_ok=False)
    return d


@contextmanager
def scratch_dir(prefix: str = "nf") -> Iterator[Path]:
    """with scratch_dir() as d: 出块即删（删不掉也不影响结果，交给 gc()）。"""
    d = new_dir(prefix)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
