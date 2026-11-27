"""core.disk_cache 私有实现分片 1/2（对外只经 core.disk_cache 门面导入）：ENV_OFF、ENV_DIR 等"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from core import json_doc

ENV_OFF = "NF_NO_DISK_CACHE"


#: C1（2026-10-22 安全审计）：缓存根显式覆盖（最高优先级）。
ENV_DIR = "NF_CACHE_DIR"


#: 仓内回退目录的所有权标记：无标记的预置缓存目录**不收养**（防被审仓库预置伪造判定）。
MARKER = ".nf-cache-owner"


#: 缓存根裁决结果与「全不可用」禁用标记（进程内一次记忆；测试用 _reset_root_state 清）。
_ROOT: dict[str, Any] = {}


KEEP = 16


#: 大集合标签（每份文件一条的那种，如 AST 事实）裁剪频次：每 N 次写入裁一次。
#: 为什么不一写一裁：一写一裁＝每次都要把目录整个 scandir+stat 一遍，**每份文件一条**的标签
#: 会变成 O(n²)（250 条 × 250 次 = 6 万次 stat，实测吃掉几百毫秒，把收益全抵消）。
PRUNE_EVERY_BIG = 128


#: **小集合标签**同样按批裁（2026-09-29 实测更正）：「小集合每次写都裁」不成立——一次新内容状态里
#: 11 次 `store` 花 33–42 ms，其中 **20–23 ms 是 11 次 `prune`**（每次 `glob("*.json")` + 逐件
#: `stat`）。按批后调用降到 1/8；代价是每标签最多多留 `PRUNE_EVERY_SMALL` 份（仍有界，判据在册）。
PRUNE_EVERY_SMALL = 8


# : 参与「代码面」的路径（改了算法即换键；不含 tests）。**别写 `scripts/**/*`**（2026-09-29 实测坑）
# ：它连
#: `scripts/__pycache__/*.pyc`（Python 自生成）一起收 ⇒ 一导入就改指纹 ⇒ 宽面派生缓存反复 miss。
CODE_FACE = ("desktop/src/**/*.py", "scripts/**/*.py", "scripts/*.sh",
             "scripts/nf", "scripts/nf.cmd")


_CODE_FP: dict = {}                      # root → 代码面指纹（**按根记忆**：换根不得串味）


_RUNTIME: Optional[str] = None


def runtime_tag() -> str:
    """运行时标签：软依赖与解释器在场与否**会改变结果**，故必须进键。"""
    global _RUNTIME
    if _RUNTIME is None:
        import sys

        from core import lazy_yaml as _ly
        ver = _ly.dist_version("PyYAML")               # 不导入 yaml 就取版本（实测 34.5 → 0.7 ms）
        if not ver:                                    # 装法异常（vendored 等）→ 退回真导入，语义不变
            try:
                import yaml
                ver = getattr(yaml, "__version__", "?")
            except Exception:                          # noqa: BLE001 - 缺 PyYAML 是合法状态
                ver = ""
        yaml_bit = ("yaml=%s" % ver) if ver else "yaml=none"
        _RUNTIME = "%d.%d.%d|%s|%s" % (sys.version_info[0], sys.version_info[1],
                                       sys.version_info[2], os.name, yaml_bit)
    return _RUNTIME


def code_fingerprint(root: str = ".") -> str:
    """代码面内容指纹（**按根**进程内记忆；实测 41 ms）。

    按根记忆是必须的：早先写成单变量时，换一棵树会拿回上一棵树的指纹——判据当场抓住
    （`test_code_fingerprint_tracks_code_content`）。守护在**判定代码已换版**时要调
    `reset_code_fingerprint()`，否则会拿旧算法的键去命中盘上旧算法的账。
    """
    rkey = os.path.normcase(os.path.abspath(str(root)))
    hit = _CODE_FP.get(rkey)
    if hit is None:
        from core import content_face as _cf  # 叶子件：持久层不反向依赖校验层
        hit = _cf.code_face_digest(str(root), CODE_FACE)
        _CODE_FP[rkey] = hit
    return hit


def key(tag: str, *parts: str, root: str = ".", code_scope: Optional[str] = None) -> str:
    """算缓存键：标签 + 代码面 + 运行时 + 调用方给的各段。

    `code_scope` 是调用方算好的**导入闭包指纹**（`import_graph.code_scope_fingerprint`；闭包算不出
    /含动态导入时给 `None`）——于是改别的模块不再换键（整块代码面 100+ 件，多数派生只依赖 3–21 件）。
    闭包解析**不再由持久层自己做**（2026-09-29 拆环：`disk_cache → import_graph` 与
    `import_graph → disk_cache` 组成模块级环；零环是硬判据）。`code_scope=None` ⇒ 退回整块代码面
    （宁可多算，不可拿旧算法的账当新账）。
    """
    code_bit = code_scope or code_fingerprint(root)
    h = hashlib.sha256()
    for piece in ("v1", str(tag), code_bit, runtime_tag()) + tuple(
            str(p) for p in parts):
        h.update(piece.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


_KEEP: dict = {}                         # tag → 上限（给大集合标签用）


_PRUNE_COUNT: dict = {}


#: **总量上限**（2026-10-19 实测）：按标签裁剪只保证"单标签有界"，标签一多总量仍会失控
#: （现场：~/.NinFenz/cache 涨到 1.1 万文件后，新建文件的 open() 在杀软/ACL 下开始卡住，
#: 表现成整条判据"挂死"）。这里再加一道全局闸：超过上限就按 mtime 淘汰最旧的整份缓存。
ENV_MAX_TOTAL = "NF_CACHE_MAX_TOTAL"


MAX_TOTAL_DEFAULT = 20000


#: 每多少次 store 检查一次总量（全量 scandir 有代价，按批做）
ENFORCE_EVERY = 200


def max_total() -> int:
    """全局文件数上限（可由 NF_CACHE_MAX_TOTAL 覆盖；非法值退回默认）。"""
    try:
        got = int(os.environ.get(ENV_MAX_TOTAL) or MAX_TOTAL_DEFAULT)
    except (TypeError, ValueError):
        return MAX_TOTAL_DEFAULT
    return got if got > 0 else MAX_TOTAL_DEFAULT


def canonical(value: Any) -> Any:
    """把「刚算出来的值」规范化到与**落盘再读回**完全相同的形状（键序固定）。

    为什么（2026-10-01 取证）：`store` 落盘时用 `sort_keys=True`，而**未命中路径**是把内存里的
    值直接交回调用方 ⇒ 同一份派生账，首跑按插入序打印、第二跑（命中）按字典序打印：
    `nf layers --json` 实测首跑 sha `d265f466…` / 次跑 `4acfa0a3…`（**同长不同序**），
    守护路径与直跑路径也因此逐字节不一致——「同一输入两次运行逐字节一致」这条口径
    在**带缓存的机器面**上此前是假真。规范化一次（小对象往返，微秒级）就把两条路径收成一条，
    且对**所有** `memo_pair` / `scan` 站点同时生效（不必逐个打印面排序）。
    """
    return json_doc.loads(json.dumps(value, ensure_ascii=False, sort_keys=True),
                        None, what="cache 规范化")


def _user_cache_base() -> Path:
    """用户级缓存根（跨平台，C1）：Windows `%LOCALAPPDATA%
infenz`，其余 `~/.cache/ninfenz`。"""
    if os.name == "nt":
        env_name, parts = "LOCALAPPDATA", ("AppData", "Local")
    else:
        env_name, parts = "XDG_CACHE_HOME", (".cache",)
    base = os.environ.get(env_name) or os.path.join(os.path.expanduser("~"), *parts)
    return Path(base) / "ninfenz"


def _repo_tag() -> str:
    """被审仓库分段：当前工作目录真实路径的短哈希（同仓多次运行稳定、跨仓不串味）。"""
    try:
        where = str(Path.cwd().resolve())
    except OSError:                            # cwd 已消失等异常状态：退回未解析形态（不抛）
        where = os.getcwd()
    return hashlib.sha256(where.encode("utf-8")).hexdigest()[:16]


def _probe_writable(d: Path) -> bool:
    """真实可写判据：建目录 → 写探针 → 读回（临时目录出块自清，不留残留）。

    失败语义：探针失败＝该候选不可用（**不抛**；由 `_resolve_root` 汇总后降级/回退）。
    """
    try:
        d.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".nf_write_probe.", dir=str(d)) as td:
            probe = Path(td) / "p"
            probe.write_text("ok", encoding="utf-8")
            return probe.read_text(encoding="utf-8") == "ok"
    except OSError:  # 建目录/写探针失败＝候选不可用（语义见 docstring：降级而非抛）
        return False


def _adopt_fallback(d: Path) -> bool:
    """仓内回退目录的收养闸门（C1 第二道闸）：只收养**空目录**或**带所有权标记**的目录。

    为什么：回退目录落在被审仓库里——若仓库预置了一份伪造缓存（含假的 PASS 判定），
    直接收养等于把 C1 原样复活。无标记的非空目录一律拒绝（宁可关缓存，也不拿可疑判定）。
    """
    mark = d / MARKER
    try:
        if mark.is_file():
            return True
        d.mkdir(parents=True, exist_ok=True)
        if any(d.iterdir()):
            return False
        mark.write_text(str(Path.cwd().resolve()), encoding="utf-8")
        return True
    except OSError:  # 建目录/写标记失败＝回退不可用（调用方据此禁用缓存，fail-closed）
        return False


def _root_key() -> tuple:
    """缓存根的**环境指纹**：任一来源变化（测试/守护会在同进程里换 NF_HOME/cwd）都要重裁决。"""
    return (os.environ.get(ENV_DIR), os.environ.get("NARRATIVE_FORGE_HOME"),
            os.environ.get("LOCALAPPDATA"), os.environ.get("XDG_CACHE_HOME"),
            os.getcwd(), os.name)
