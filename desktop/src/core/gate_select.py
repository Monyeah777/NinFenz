"""门禁选择器：由「改动件」选出该跑的测试模块（秒级 check 的第一半）。

定位：选择只负责「少跑」，**不产生任何结论**——所以它的失败方向必须是「多跑」。
读面数据 faces.json 是**可再生的环境相关缓存**（含本机路径与耗时），落
`<NF_HOME>/cache/gate-observe/`，**不入库**；缺失/损坏 ⇒ 全部模块按「未观测」处理，一律常跑，
绝不静默跳过。

三条 fail-closed 规则（宁可多跑）：
  1. 观测状态非 ok（超时 / 导入失败 / 测试红）；
  2. 读面不可信（原生工具子进程看不见、或子进程读面未捕获）；
  3. 改动件就是该模块自身。
其余模块：观测读面与改动集相交才跑。

判据：tests/test_gate_select.py（合成面逐条钉住规则与可缓存性闸门）。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from core import disk_cache, json_doc

#: 读面数据格式版本（升级即旧数据自然失效，退回「全跑」）。
SCHEMA = "nf-gate-faces/1"
FACES_TAG = "gate-observe"
FACES_NAME = "faces.json"
#: 会 spawn 子进程的记号（子进程读面默认不可见）。
SPAWN_MARKS = ("subprocess", "Popen", "os.system", "multiprocessing", "CreateProcess")
#: 原生工具痕迹（**只认被引号包住的命令名**：裸词会把注释里的 git/node 也算进来）。
#: 这些子进程不是 Python，观测钩子注入不进去 ⇒ 读面必然不完整。
NATIVE_MARKS = ('"ruff"', "'ruff'", '"bandit"', "'bandit'", '"node"', "'node'",
                '"npm"', "'npm'", '"cargo"', "'cargo'", '"dotnet"', "'dotnet'",
                '"git"', "'git'", '.exe"', ".exe'")
#: 慢车道阈值（秒）：单模块实测超过它 ⇒ 默认路径让位给定时/发布车道（**不跳**，只挪）。
SLOW_SECONDS = 30


def faces_path() -> Path:
    """读面数据落点（缓存区，不入库）。"""
    return disk_cache.dir_for(FACES_TAG) / FACES_NAME


def _posix(p: object) -> str:
    return str(p).replace("\\", "/")


#: 跨平台绝对路径形态：Windows 盘符（`C:\…` / `C:/…`）与 UNC（`\\server\share`）。
#: 为什么单独判：`os.path.isabs("C:/x")` 在 Linux 上是 **False**，若按"相对路径"处理
#: 就会把它当成仓内读面（CI 2026-10-23 run#42 实测：Windows 绿、Linux 红）。
_WIN_ABS = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")


def _rel(root: str, p: object) -> str | None:
    """路径 → 仓库相对 posix；不在根内（临时目录等）→ None。

    两种口径都收：观测器落盘的是**仓库相对**；早期/私有数据是**绝对**路径。
    相对路径**不能**拿 cwd 去 abspath——那会按调用者所在目录解析（曾因此把读面清空）。
    盘符/UNC 形态先判：它们在任何平台都**不可能**落在 POSIX 根内 ⇒ 直接 None（跨平台一致）。
    """
    raw = str(p)
    # 仅在 POSIX 上把盘符/UNC 判为仓外：Windows 上它们就是**正常绝对路径**，
    # 要走下面的前缀比较（否则会把本仓自身的 `C:\…` 读面全丢掉）。
    if os.name != "nt" and _WIN_ABS.match(raw):
        return None
    if not os.path.isabs(raw):
        return _posix(raw).lstrip("/")
    rp = os.path.normcase(os.path.abspath(str(root)))
    n = os.path.normcase(os.path.abspath(str(p)))
    if n == rp or n.startswith(rp + os.sep):
        return _posix(n[len(rp):]).lstrip("/")
    return None


def load_faces(root: str = ".", path: Path | None = None) -> dict:
    """读并归一读面；**任何不可信**（缺件 / 坏 JSON / schema 不符）→ 空 dict（上层全跑）。"""
    try:
        doc = json_doc.loads((path or faces_path()).read_text(encoding="utf-8"), dict,
                             what="门禁读面数据")
    except (OSError, ValueError):
        return {}
    if doc.get("schema") != SCHEMA or not isinstance(doc.get("modules"), dict):
        return {}
    out: dict = {}
    for mod, rec in doc["modules"].items():
        if not isinstance(rec, dict):
            continue
        reads = [r for r in (_rel(root, p) for p in (rec.get("reads") or []))
                 if r and not r.startswith((".rivet/", ".git/", "__pycache__/"))
                 and not r.endswith((".pyc", ".pyo"))]
        out[str(mod)] = {"status": rec.get("status"),
                         "seconds": rec.get("seconds") or 0,
                         "reads": reads,
                         "child_reads_captured": rec.get("child_reads_captured"),
                         "unobservable_children": rec.get("unobservable_children")}
    return out


def spawn_risk(mod: str, tests_dir: Path | None = None,
               rec: dict | None = None) -> bool:
    """子进程读面是否**不可信** ⇒ 常跑。静态优先：原生工具永远不可观测。"""
    p = (tests_dir or Path("desktop") / "tests") / f"{mod}.py"
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return True
    if any(m in text for m in NATIVE_MARKS):
        return True
    if rec is not None:
        if rec.get("unobservable_children"):
            return True
        captured = rec.get("child_reads_captured")
        if captured is not None:
            return captured == 0
    return any(m in text for m in SPAWN_MARKS)


def cacheable(mod: str, rec: dict | None, tests_dir: Path | None = None) -> bool:
    """能不能走判定缓存（健全性闸门）：读面不完整的模块**绝不缓存**，否则会命中旧绿。"""
    rec = rec or {}
    if rec.get("status") != "ok" or not rec.get("reads"):
        return False
    return not spawn_risk(mod, tests_dir, rec)


def lane_of(rec: dict | None) -> str:
    """quick | slow：秒数达到阈值即让位；**成本说不清（观测非 ok）也一律让位**。

    为什么非 ok 要让位：那类记录没有可信秒数（实测有 observe_error 记 0s、真跑 137s 的），
    留在快车道会让「秒级」变成谎话。让位不等于跳过——名单照打，慢车道/--all 照跑。
    """
    rec = rec or {}
    if rec.get("status") != "ok":
        return "slow"
    return "slow" if (rec.get("seconds") or 0) >= SLOW_SECONDS else "quick"


def _covered(changed: list, reads: list) -> bool:
    for r in reads:
        rl = _posix(r).lower()
        for c in changed:
            cl = _posix(c).lower()
            if rl == cl or rl.startswith(cl.rstrip("/") + "/"):
                return True
    return False


def select(changed: list, doc: dict | None = None, tests_dir: Path | None = None,
           root: str = ".") -> dict:
    """→ {run, skip, quick, slow, uncacheable}。

    run 是 (模块, 理由) 列表，skip 是模块名列表；quick/slow 按车道再切一刀。
    """
    mods: dict = dict(doc if doc is not None else load_faces(root))
    tdir = tests_dir or Path("desktop") / "tests"
    for p in sorted(tdir.glob("test_*.py")):
        mods.setdefault(p.stem, {"status": "unobserved", "reads": []})
    changed_n = [_posix(c) for c in (changed or [])]
    run: list = []
    skip: list = []
    for mod, rec in sorted(mods.items()):
        status = (rec or {}).get("status")
        if status != "ok":
            run.append((mod, "观测非 ok（fail-closed）"))
            continue
        if spawn_risk(mod, tdir, rec):
            run.append((mod, "读面不可信（fail-closed）"))
            continue
        own = _posix(f"desktop/tests/{mod}.py").lower()
        if any(own == c.lower() for c in changed_n):
            run.append((mod, "本模块自身被改"))
            continue
        if _covered(changed_n, rec.get("reads") or []):
            run.append((mod, "读面命中"))
        else:
            skip.append(mod)
    quick = [(m, w) for m, w in run if lane_of(mods.get(m)) == "quick"]
    slow = [(m, w) for m, w in run if lane_of(mods.get(m)) == "slow"]
    uncacheable = [m for m, _w in run if not cacheable(m, mods.get(m), tdir)]
    return {"run": run, "skip": skip, "quick": quick, "slow": slow,
            "uncacheable": uncacheable}

