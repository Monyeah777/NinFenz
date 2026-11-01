#!/usr/bin/env python3
# nf-io: inputs=- outputs=-
"""**子 check 缓存**：把「一条 check 的判定」按内容寻址缓存起来。

为什么需要（实测）
------------------
门禁的成本形状是**一元巨步**：check12 一个 check 就占全量门禁 ~96%（串行 1255 s / 3042 个
测试）。改一行 `desktop/src/core/*` 就要整条重跑。要谈「缓存粒度」，得先把判据切到
**子 check**（一条 check = 一个可独立缓存、独立失效的单元）。

本模块只做**机制**（观测读面 / 快照 / 取存 / 复核），不含任何具体 check 的知识——
于是 `nf verify`、`verify_parallel.py`、check12 三处共用同一套语义。

键 = 内容寻址，且必须 fail-closed
---------------------------------
本仓 `ADR-0002-门禁不注水` 的硬线：**宁可重算，不可错答**。故全部分支都朝
「**可能假命中 ⇒ 一律重跑**」收：

1. **读面靠观测，不靠声明**。实测 22 条已迁入 check 的 `reads` **全是空元组**——拿声明面
   当键等于键里什么都没有，必然假命中。故用 `gate_faces` 的 audit hook **实收**本次执行
   真正 `open` 过的文件（与实现无关，谁读都记）。
2. **目录项也进快照**。「目录里多出一个文件」会改变 `glob` 类判据，而它**不产生 `open`
   事件**（只 `listdir`）。故对每个被读文件的各级祖先目录，记**目录项集合的哈希**。
3. **读面为空 ⇒ 不缓存**。什么都没读到却给出结论，说明输入在别处（环境/时间/网络）。
4. **读到仓外路径 ⇒ 不缓存**。仓外内容不在内容寻址的管辖内。
5. **取回必复核**：任一输入**缺席**（Tup：缺失即失效）或**内容已变** ⇒ 当未命中。
6. **值里带 `trusted` 与理由**：`trusted=False` 的条目留档，但 `try_hit` 永不采信。
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core import disk_cache as dc
from core import gate_faces as gf

#: 缓存标签（落点 `<NF_HOME>/cache/<tag>/…`；**不在仓库内**，不影响仓库纯净与门禁）。
TAG = "subcheck.v1"
#: 先验读面表标签：`ident → 上次观测到的仓内读面`（有了它才能「先查后跑」）。
FACE_TAG = "subcheck.face.v1"
#: 快照结构版本：形状一变即换键（旧条目自然失效，不需要手工清理）。
SCHEMA = 1

#: 「未命中」哨兵——把「没缓存」与「缓存值本身是 None」分开。
MISS = object()

#: 解释器自身的地盘（stdlib / site-packages / 解释器根）。这些读取**与判据语义无关**：
#: 它们是「这段 Python 跑起来」的固定开销，同一台机器上恒定，且改它们不属于本仓内容变更。
#: 不过滤的实测后果（2026-10-16）：check33 报 **948** 条仓外读（全是 `csv.pyc`/`calendar.pyc`
#: 这类字节码），check39 报 86 条（`DLLs`/`Lib`）⇒ 两条都因「读到仓外」被永久判为不可缓存。
#: 注意：**用户 home / 临时目录 / 仓库外数据**仍算仓外（那些才可能真影响判定）。
_RUNTIME_ROOTS = tuple(
    Path(p).resolve() for p in {sys.prefix, sys.base_prefix, sys.exec_prefix}
    if p and Path(p).exists()
)


def _is_runtime_path(p: Path) -> bool:
    for base in _RUNTIME_ROOTS:
        try:
            p.relative_to(base)
            return True
        except ValueError as _exc:      # 不在这个 base 之下 ⇒ 正常分支（换下一个 base 试），非静默吞错
            _ = _exc
            continue
    return False


def _digest_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def file_digest(path: Path) -> str:
    """文件内容 sha256；缺席/不可读 → 空串（调用方据此判失效）。"""
    try:
        return _digest_bytes(path.read_bytes())
    except OSError:
        return ""


def dir_digest(path: Path) -> str:
    """目录**项集合**哈希（只含名字与类型，不含内容）。见模块 docstring 第 2 条。"""
    try:
        names = sorted(n.name + ("/" if n.is_dir() else "") for n in os.scandir(str(path)))
    except OSError:
        return ""
    return _digest_bytes("\x00".join(names).encode("utf-8", "surrogatepass"))


#: **为什么不按目录 mtime 记忆条目哈希**（2026-10-16 实测否决）：
#: 大 check 的命中复核成本确实全在重算目录项哈希（check39 目录面 24718 ⇒ 复核 10.6 s，
#: 而重算 10.12 s，缓存近乎无意义），于是「用目录 mtime 当廉价失效键」看起来是显然的解。
#: **但它不安全**：判据 `test_dir_entry_change_is_detected_despite_memo` 实测——在同一个
#: 瞬时内新增条目，**目录 mtime 可能不变**（Windows/NTFS 实测复现），记忆就会返回旧哈希
#: ⇒ **假命中**。按本仓 `ADR-0002-门禁不注水`（宁可重算，不可错答），此处**不记忆**，
#: 每次老实重算目录项集合。代价是 check39 这类超大目录面命中收益仅 1×（如实记账，
#: 不靠一个不可靠的失效键把它做成纸面上的赢）。


def _ancestors(rel: str) -> List[str]:
    """仓内相对路径的各级祖先目录（含 '.'），去重且顺序稳定。"""
    out = ["."]
    cur = Path(".")
    for p in Path(rel).parts[:-1]:
        cur = cur / p
        out.append(cur.as_posix())
    return sorted(set(out))


def snapshot(root: str, rels: Iterable[str], dirs: Iterable[str] = (),
             with_ancestors: bool = False) -> Dict[str, Any]:
    """读面 → 可复核快照 `{files, dirs}`（内容寻址的键材料）。

    `files`：内容哈希；`dirs`：**目录项集合**哈希。

    `dirs` 只收 `observe` **实际列举过**的目录（`os.listdir`/`os.scandir` 的 audit 事件）。
    为什么不默认把被读文件的**各级祖先目录**也塞进来（2026-10-16 实测）：那会让
    check39 的目录面从「实际列举数」膨胀到 **24718** 个（几乎整棵树），
    于是**命中时的复核成本 ≈ 重算成本**，缓存净亏。而祖先目录的信息是**冗余**的——
    目录里多出一个文件，只有当它**被读**或**被列举**时才可能影响判定，这两种情况都已分别
    落在 `files` 与 `dirs` 里。`with_ancestors=True` 仅供诊断/对照。
    """
    base = Path(root)
    files = {r: file_digest(base / r) for r in sorted(set(rels))}
    dirset = set(dirs)
    if with_ancestors:
        for r in files:
            dirset.update(_ancestors(r))
    return {"files": files, "dirs": {d: dir_digest(base / d) for d in sorted(dirset)}}


def equiv(root: str, snap: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """复核快照 → (是否等价, 理由)。任一输入缺席或内容已变即不等价。"""
    base = Path(root)
    files, dirs = snap.get("files"), snap.get("dirs")
    if not isinstance(files, dict) or not isinstance(dirs, dict):
        return False, ["快照结构不可信"]
    reasons: List[str] = []
    for rel, want in sorted(files.items()):
        got = file_digest(base / rel)
        if not got:
            reasons.append("输入缺席：%s（Tup 规则：缺失即失效）" % rel)
        elif got != want:
            reasons.append("输入已变：%s（内容寻址：须重算）" % rel)
    for rel, want in sorted(dirs.items()):
        if dir_digest(base / rel) != want:
            reasons.append("目录项已变：%s（glob 类输入：须重算）" % rel)
    return (not reasons), reasons


def _key(root: str, ident: str, snap: Dict[str, Any]) -> str:
    """内容键：根 + 标识 + 读面内容 + 目录项（顺序稳定）。"""
    h = hashlib.sha256()
    h.update(str(Path(root).resolve()).encode("utf-8"))
    for piece in (TAG, str(SCHEMA), str(ident)):
        h.update(b"\x00")
        h.update(piece.encode("utf-8"))
    for rel, dig in sorted((snap.get("files") or {}).items()):
        h.update(b"\x00F")
        h.update(rel.encode("utf-8", "surrogatepass"))
        h.update(b"\x00")
        h.update(str(dig).encode("ascii"))
    for rel, dig in sorted((snap.get("dirs") or {}).items()):
        h.update(b"\x00D")
        h.update(rel.encode("utf-8", "surrogatepass"))
        h.update(b"\x00")
        h.update(str(dig).encode("ascii"))
    return h.hexdigest()


def observe(root: str, runner: Callable[[], Any]) -> Tuple[Any, List[str], List[str], List[str]]:
    """跑一次 runner → (返回值, 仓内文件读面, 仓内目录读面, 仓外绝对读面)。

    为什么**不能用** `gate_faces.rel_face` 判仓界（2026-10-16 实测抓到）：
    它按 `normcase(abspath)` 做前缀比较，而 `gate_faces` 的 audit hook 收集器里是
    **原始 open 路径**（相对当前 cwd）。仓库根在盘符大小写/`cd` 之后与 `abspath(root)`
    不同形时，`03_管线库/…` 这类**明明在仓内**的路径会被判成仓外 ⇒ 该 check 永远不缓存
    （实测 check33/39/40 全因此永久 miss）。

    处置：仓界一律按 **resolve() 之后的真实路径**判，与 `gate_faces` 的形状无关。
    另外**目录列举事件单独收**（`os.listdir`/`os.scandir` 会触发 audit）——「目录里多出一个
    文件」不产生 `open` 事件，只快照文件内容会漏掉它（glob 类判据的假命中来源）。
    """
    gf._ensure_hook()                                   # noqa: SLF001 - 有意复用（见 docstring）
    seen, listed = set(), set()
    gf._COLLECTORS.append(seen)                         # noqa: SLF001
    gf._DIR_COLLECTORS.append(listed)
    try:
        value = runner()
    finally:
        for reg, item in ((gf._COLLECTORS, seen), (gf._DIR_COLLECTORS, listed)):  # noqa: SLF001
            for i, s in enumerate(reg):
                if s is item:
                    del reg[i]
                    break
    base = Path(root).resolve()
    files_in, dirs_in, outside = [], [], []

    def _classify(raw: Any) -> Optional[str]:
        """仓内 → 相对 posix；仓外 → None（并记进 outside，由调用方 fail-closed）。"""
        try:
            p = Path(os.fsdecode(raw))
        except (TypeError, ValueError) as _exc:
            # 路径解不出（audit 事件参数形状异常）⇒ **按仓外处理**：调用方见 outside 非空即
            # 判不可缓存（fail-closed）。不外抛、也不当成「仓内已核对」。
            outside.append("unresolvable:%s:%s" % (type(raw).__name__, _exc))
            return None
        ap = p if p.is_absolute() else (Path.cwd() / p)
        try:
            rp = ap.resolve()
        except OSError:
            outside.append(str(ap))          # 解不出真实路径 ⇒ 保守当仓外
            return None
        if _is_runtime_path(rp):
            return None                       # 解释器自己的地盘：与判据语义无关（见 _RUNTIME_ROOTS）
        try:
            rel = rp.relative_to(base)
        except ValueError:
            outside.append(str(rp))
            return None
        if not rel.parts or rel.parts[0] == ".git":     # .git 内容不参与判据
            return None
        return rel.as_posix()

    for raw in seen:
        rel = _classify(raw)
        if rel:
            files_in.append(rel)
    for raw in listed:
        rel = _classify(raw)
        if rel:
            dirs_in.append(rel)
    return value, sorted(set(files_in)), sorted(set(dirs_in)), sorted(set(outside))


def _validate(v: Any) -> bool:
    return (isinstance(v, dict) and isinstance(v.get("trusted"), bool)
            and isinstance(v.get("files"), dict) and isinstance(v.get("dirs"), dict)
            and "value" in v)


def lookup(root: str, ident: str, snap: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """取回并复核 → 命中且 `trusted` 返回条目；否则 None。"""
    got = dc.load(TAG, _key(root, ident, snap), validate=_validate)
    if not isinstance(got, dict) or got.get("trusted") is not True:
        return None
    ok, _why = equiv(root, got)
    return got if ok else None


def _face_key(root: str, ident: str) -> str:
    h = hashlib.sha256()
    h.update(str(Path(root).resolve()).encode("utf-8"))
    for piece in (FACE_TAG, str(SCHEMA), str(ident)):
        h.update(b"\x00")
        h.update(piece.encode("utf-8"))
    return h.hexdigest()


def read_face(root: str, ident: str) -> Optional[Dict[str, List[str]]]:
    """读回该 ident 上次观测到的读面 `{files, dirs}`（无/不可信 → None）。"""
    def _ok(v: Any) -> bool:
        return (isinstance(v, dict) and isinstance(v.get("files"), list)
                and isinstance(v.get("dirs"), list)
                and all(isinstance(x, str) for x in v["files"] + v["dirs"]))

    got = dc.load(FACE_TAG, _face_key(root, ident), validate=_ok)
    return got if isinstance(got, dict) else None


def write_face(root: str, ident: str, files: Iterable[str], dirs: Iterable[str] = ()) -> None:
    dc.store(FACE_TAG, _face_key(root, ident),
             {"files": sorted(set(files)), "dirs": sorted(set(dirs))})


def try_hit(root: str, ident: str) -> Any:
    """**先查后跑**：用先验读面复核，等价则直接回上次的值（判据本体不跑）。未命中 → `MISS`。

    这是唯一可能造假命中的路径，故每一步都 fail-closed：
    没有先验读面 / 读面为空 / `trusted=False` / 任一输入变或缺 ⇒ `MISS`。
    """
    face = read_face(root, ident)
    if not face or not face.get("files"):
        return MISS
    got = lookup(root, ident, snapshot(root, face["files"], face.get("dirs") or ()))
    return MISS if got is None else got.get("value")


def run_cached(root: str, ident: str, runner: Callable[[], Any]) -> Tuple[Any, str]:
    """**一条子 check 的带缓存执行** → (结果, 状态)。

    状态 ∈ `{"hit" | "run" | "untrusted"}`：
      - `hit`：先验读面复核通过，**未跑**判据本体，值是上次的；
      - `run`：跑了，且读面可用 ⇒ 已存结果 + 先验表（下一轮可 hit）；
      - `untrusted`：跑了，但读面为空/含仓外/值不可序列化 ⇒ **只回结果，不存**。

    诚实说明：`run` 路径**不省读**（要观测读面就得跑一遍）。省的是下一轮——
    命中时判据本体完全不跑。
    """
    hit = try_hit(root, ident)
    if hit is not MISS:
        return hit, "hit"

    value, files, dirs, outside = observe(root, runner)
    if not files or outside:
        return value, "untrusted"
    try:
        encoded = dc.canonical(value)
    except (TypeError, ValueError):          # 值不可序列化 ⇒ 不当可缓存件（fail-closed）
        return value, "untrusted"
    snap = snapshot(root, files, dirs)
    dc.store(TAG, _key(root, ident, snap), {
        "schema": SCHEMA, "ident": str(ident), "trusted": True,
        "why": "", "files": snap["files"], "dirs": snap["dirs"], "value": encoded,
    })
    write_face(root, ident, files, dirs)
    return encoded, "run"


# --------------------------------------------------- Verdict 形状的子 check（引擎专用）

#: 缓存里**只存**这些稳定字段。`seconds` 是墙钟（每跑必不同）、`cached` 是本次运行态——
#: 二者**绝不入缓存**，否则「同一输入两次运行逐字节一致」这条口径会当场破。
STABLE_FIELDS = ("name", "status", "verdicts", "stats", "note")


def stable_payload(verdict: Any) -> Dict[str, Any]:
    """Verdict → 只含稳定字段的字典（可安全落盘）。"""
    return {k: getattr(verdict, k) for k in STABLE_FIELDS}


def run_payload_cached(root: str, num: int, impl: Callable[[Path], Any],
                       root_path: Path) -> Tuple[Dict[str, Any], str]:
    """跑一条 check 并缓存 → (**只含稳定字段的字典**, 状态)。

    为什么返回字典而不是 `Verdict`（2026-10-16，被 `test_coupling_metrics` 的「零环」判据抓出）：
    原先这里**延迟 import** `core.gate_engine.Verdict`，而 `gate_engine.run_checks` 又延迟 import
    本模块 ⇒ 静态依赖图上成了 `gate_engine ↔ subcheck_cache` **一个真环**（基线里记着）。
    改成**依赖倒置**：本模块只懂「稳定字段字典」，由调用方（`gate_engine`）自己把字典装成
    `Verdict`。于是本模块**不依赖** gate_engine，环消失，职责也更干净
    （缓存机制不该知道 `Verdict` 是什么）。
    """
    got, state = run_cached(root, "check%d" % num, lambda: stable_payload(impl(root_path)))
    return dict(got), state
