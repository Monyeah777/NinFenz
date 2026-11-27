"""conformance_scan 私有子模块 _resident：常驻语料层：目录条目 / 正文 / 字节 / 摘要 + 确知变更面与逐路径失效。

门面 core.conformance_scan 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple


#: **常驻层**（`_RESIDENT`）：跨调用、跨请求活着的一份「语料正文 + 目录条目」（依据：改一件后守护
#: 第一条重命令要 1.6–2.0 s，作用域缓存出口即清）。不比响应缓存多信任任何东西：只在守护带监听且
#: 监听健康时安装、只按**确知路径**失效、说不清即整批作废；只缓存监听根之下的件。
_RESIDENT: Optional[Dict[str, Any]] = None

#: 常驻层的容量上界（目录条数与正文条数）：超出即停止收录（不影响正确性，只是退回按需读）。
_RESIDENT_DIR_MAX = 8192

_RESIDENT_TEXT_MAX = 16384

_RESIDENT_RAW_MAX_BYTES = 64 * 1024 * 1024



class _Entry:
    """常驻目录索引里的一条：只提供 `os.DirEntry` 被用到的那五个成员。"""

    __slots__ = ("name", "path", "_is_dir", "_is_file", "_is_link")

    def __init__(self, name: str, path: str, is_dir: bool, is_file: bool, is_link: bool):
        self.name = name
        self.path = path
        self._is_dir = is_dir
        self._is_file = is_file
        self._is_link = is_link

    def is_dir(self) -> bool:
        return self._is_dir

    def is_file(self) -> bool:
        return self._is_file

    def is_symlink(self) -> bool:
        return self._is_link



def install_resident(root) -> None:
    """安装常驻层（**只在守护带监听且监听健康时调用**）。"""
    global _RESIDENT
    root_abs = os.path.normcase(os.path.abspath(str(root)))
    _RESIDENT = {"root": root_abs, "dirs": {}, "text": {}, "bytes": {}, "digest": {}, "raw": {},
                 "raw_bytes": 0,
                 #: **确知变更面**（见 `changed_paths`）：装层时为空且**未确知**（fail-closed——
                 #: 新装的层不知道装之前发生过什么，任何「跳过重算」的推理都不许建立在这上面）。
                 "changed": set(), "changed_known": False}



#: 「确知变更面」的用途：读层一直用它精确失效（`drop_resident`）；**键层**过去没用——于是「改一件、
#: 106 个键都要重算」才发现全没变。有了它，「确知没变」的面直接复用上次的键；说不清就整批作废。
def note_changes(paths) -> None:
    """记下这一批**确知**变更的仓库相对路径（由守护的监听给出；`drop_resident` 会顺手调用）。"""
    if _RESIDENT is None:
        return
    _RESIDENT["changed_known"] = True
    _RESIDENT["changed"].update(str(p) for p in (paths or ()))



def changed_paths() -> Tuple[bool, set]:
    """`(known, paths)`：本进程**确知**自上次取用以来变过哪些仓库相对路径。

    `known=False`（没装层 / 监听说不清 / 刚装层）表示**不许做任何「没变」的推理**——调用方必须按
    「全都可能变了」处理（fail-closed）。
    """
    if _RESIDENT is None or not _RESIDENT.get("changed_known"):
        return False, set()
    return True, set(_RESIDENT["changed"])



def clear_changes() -> None:
    """**请求结束**时清空确知变更面（`daemon.execute` 的收尾调用）。

    为什么必须清（实测 2026-09-29 踩到）：`note_changes` 是**累加**的，而早先没有清空点 ⇒ 变更集会
    单调增长，几条命令之后**每个面都「沾到变更」**，键层复用直接退化成全量重算（探针里四种改动位置
    都报「重算 5 个面」就是这个 bug）。语义与读层一致：确知变更只在**当次请求**内有效。
    """
    if _RESIDENT is None:
        return
    _RESIDENT["changed"] = set()
    _RESIDENT["changed_known"] = False



def resident_active() -> bool:
    return _RESIDENT is not None



def resident_stats() -> Dict[str, int]:
    """常驻层规模（观测 + 判据用）：目录条数 / 正文条数 / 二进制条数。"""
    if _RESIDENT is None:
        return {"dirs": 0, "text": 0, "bytes": 0, "digest": 0, "raw": 0}
    return {"dirs": len(_RESIDENT["dirs"]), "text": len(_RESIDENT["text"]),
            "bytes": len(_RESIDENT["bytes"]), "digest": len(_RESIDENT["digest"]),
            "raw": len(_RESIDENT["raw"])}



def clear_resident() -> None:
    """整批作废（监听说不清 / 不再健康时调用）。"""
    global _RESIDENT
    _RESIDENT = None



def take_resident():
    """**取走**常驻层并返回（供「代码换版时把它搬到新模块」用）；本来没装 → None。

    背景：守护判定代码换版时会把 `core.*` 整块摘掉重载（保证不跑旧代码），于是新的
    `conformance_scan` 会是一个**空层**——不把它搬回来，改一行代码就要让下一条重命令把整棵语料
    重读一遍（实测 ~2 s）。常驻层装的是**仓库事实**（正文 / 目录条目 / 逐件摘要），与代码无关，
    所以跨代码换版保住它是安全的：它的失效仍然只由监听给出的变更路径驱动。
    """
    global _RESIDENT
    res, _RESIDENT = _RESIDENT, None
    return res



def adopt_resident(res) -> None:
    """接手一份常驻层（同一份仓库事实，换的只是装着它的模块对象）。"""
    global _RESIDENT
    _RESIDENT = res



def _resident_key(path) -> str:
    """路径 → 归一化键（`normcase(abspath)`）——**带记忆**。

    依据（实测，2026-09-29 profile）：一次 `evaluate` 里本函数被调 **17628 次**、单独花掉 **71 ms**，
    而它只是 `abspath + normcase`（各约 2 µs）。热路径（`read_text_cached` / `_payload_digest` /
    常驻层的每次查表）都按**同一批路径**反复调它，所以按 `(cwd, 传入写法)` 记忆是安全的：
    `abspath` 只依赖 cwd，而 cwd 在**一次只读调用内**不变（守护逐请求 chdir，不在一段中途改）。
    """
    raw = str(path)
    memo_key = (os.getcwd(), raw)
    hit = _KEY_CACHE.get(memo_key)
    if hit is not None:
        return hit
    key = os.path.normcase(os.path.abspath(raw))
    if len(_KEY_CACHE) >= _KEY_CACHE_MAX:
        _KEY_CACHE.clear()
    _KEY_CACHE[memo_key] = key
    return key



#: `_resident_key` 的记忆表（见其说明）：到上限整批清，避免无界增长。
_KEY_CACHE: Dict[Tuple[str, str], str] = {}

_KEY_CACHE_MAX = 65536



def _resident_under(key: str) -> bool:
    """这个（已 normcase 的绝对）路径是否落在常驻层的监听根之下。"""
    res = _RESIDENT
    if res is None:
        return False
    root = res["root"]
    return key == root or key.startswith(root + os.sep)



def drop_resident(paths) -> None:
    """按**确知变更**的路径精确失效：正文按件删；目录条目按**父目录**删（增删都会改父目录清单）。

    `paths` 是监听给出的仓库相对路径（`/` 分隔、小写）；解析不过来的路径直接忽略。

    顺带把这一批**确知变更**记进 `changed`（见 `note_changes`）——键层据此判断「哪些面确知没变，
    可以复用上一次的键」。
    """
    res = _RESIDENT
    if res is None:
        return
    note_changes(paths)
    root = res["root"]
    for rel in paths or ():
        key = os.path.normcase(os.path.join(root, str(rel).replace("/", os.sep)))
        res["text"].pop(key, None)
        res["bytes"].pop(key, None)
        res["digest"].pop(key, None)
        old_raw = res["raw"].pop(key, None)
        if old_raw is not None:
            res["raw_bytes"] = max(0, int(res.get("raw_bytes") or 0) - len(old_raw))
        res["dirs"].pop(os.path.dirname(key), None)
        res["dirs"].pop(key, None)          # 路径本身也可能是目录（整棵子树增删）
