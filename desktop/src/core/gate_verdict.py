"""判定缓存：把「某节点在某输入状态下的判定」按内容寻址存起来（秒级 check 的省算面）。

三条来自实测的纪律（缺一条就会「看起来该命中却永远不命中」）：
  1. **缺席清单也要进键**：测试会故意打开不存在的路径；verify 把缺件一律判失效，
     若缺席者不进键，该节点永久 miss。缺席清单进键后：文件后来出现 ⇒ 键变 ⇒ 该跑；
     始终不出现 ⇒ 键稳定 ⇒ 可命中。
  2. **按节点分标签**：disk_cache 每标签只留最近 KEEP 份；共用一个标签时，
     写到第 KEEP+1 个节点就会把前面的条目裁掉（实测命中率长期卡在 ~60%）。
  3. **计划期定键**：键必须在「没有别的测试在跑」时算（plan-then-execute），
     否则并行期的瞬态文件会让 exists/absent 抖动，键跟着抖。

安全边界：只缓存可序列化判定；命中前一律 verify（缺件/内容变即失效）。
调用方对「读面不可信」的节点**不应调用本模块**（见 gate_select.cacheable）。

判据：tests/test_gate_verdict.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core import disk_cache
from core import gate_cache as gc

#: 标签前缀：真正的标签按节点再切一刀（见纪律 2）。
TAG_PREFIX = "gate-verdict"


def tag_for(node_id: str) -> str:
    """按节点分标签（disk_cache 每标签只留 KEEP 份，共用标签会互相裁剪）。"""
    safe = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in str(node_id))[:60]
    return f"{TAG_PREFIX}/{safe}"


def _split_existing(root: str, files) -> tuple[list, list]:
    """读面一分为二：**存在**的进内容键，**缺失**的单独成缺席清单（见纪律 1）。"""
    exists, absent = [], []
    for f in files:
        if gc.file_digest(Path(root) / f):
            exists.append(f)
        else:
            absent.append(f)
    return exists, sorted(absent)


def _absent_digest(absent: list) -> str:
    return hashlib.sha256(json.dumps(absent, ensure_ascii=False).encode("utf-8")).hexdigest()


def key_and_entry(node_id: str, files, root: str = ".", code_files=None) -> tuple:
    """→ (内容键, 校验用 entry, 标签)。**必须在没有别的测试在跑时调用**（纪律 3）。"""
    code = gc.CODE_FILES if code_files is None else tuple(code_files)
    read_exists, read_absent = _split_existing(root, files)
    code_exists, code_absent = _split_existing(root, code)
    # 缺席者**读面与代码面都要**进键：verify 把缺件判失效，漏掉任何一类都会永久 miss
    # （合成根 / 改名后的测试件都踩过这一条）。
    absent = sorted(read_absent) + sorted(code_absent)
    nid = node_id if not absent else f"{node_id}|absent={_absent_digest(absent)}"
    ckey = gc.key_for(str(root), nid, read_exists, code_files=code_exists)
    entry = {"reads": gc.face_digest(str(root), read_exists),
             "code": gc.face_digest(str(root), code_exists)}
    return ckey, entry, tag_for(node_id)


def _shape(value) -> bool:
    return isinstance(value, dict) and "value" in value and isinstance(value.get("entry"), dict)


def lookup(node_id: str, files, root: str = ".", code_files=None) -> tuple:
    """计划期查缓存 → ((命中?, 值), 键, entry, 标签)。命中前 verify，不可信即当未命中。"""
    ckey, entry, tag = key_and_entry(node_id, files, root, code_files)
    packed = disk_cache.load(tag, ckey, validate=_shape)
    if packed:
        ok, _why = gc.verify(str(root), packed.get("entry") or entry)
        if ok:
            return (True, packed.get("value")), ckey, entry, tag
    return (False, None), ckey, entry, tag


def store(tag: str, ckey: str, entry: dict, value) -> None:
    """按**计划期钉住的键**落盘（执行后不再重算键，避免并行期抖动）。"""
    disk_cache.store(tag, ckey, {"value": value, "entry": entry})


def verdict(node_id: str, files, compute, root: str = ".", code_files=None) -> tuple:
    """一步式：命中即返回 (值, True)，否则 compute() 后落盘并返回 (值, False)。"""
    (hit, value), ckey, entry, tag = lookup(node_id, files, root, code_files)
    if hit:
        return value, True
    value = compute()
    store(tag, ckey, entry, value)
    return value, False

