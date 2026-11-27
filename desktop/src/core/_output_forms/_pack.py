"""output_forms 私有子模块 _pack：逐包内容键与产出面校验的进程内缓存（确知变更面复用 + 按包切片）。

门面 core.output_forms 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Dict

from core import conformance_scan as _csc
from core import import_graph as _ig

from ._const import REGISTRY_INPUT
from core import output_forms as _dm



#: **逐包**产出面校验的内容键缓存：键 = (该包目录内容指纹, registry 内容指纹)。
#: 为什么按包切：一次「改一页模块文档」只会让**那一个包**的键变，其余包直接命中——
#: 实测（稀疏常驻层的新进程里）`index_verify` 713 ms → 改一包之后只剩那一个包的钱。
#: 键即内容 ⇒ 无陈旧风险；`_DIGEST_MEMO` 让「外层输入面指纹已经算过的件」在这里近乎白拿。
_PACK_VERIFY_CACHE: Dict[Any, Any] = {}

_PACK_VERIFY_MAX = 4096



#: 逐包键里「属于该包」的那几条（**必须 ⊆ `INDEX_INPUTS`**，否则「读盘面 ⊆ 输入面」判据会红）。
_PACK_FACE_SLICE = ("outputs/**/*", "assets/*", "protocol.yaml", "modules/*.md")

#: 逐包键里「所有包共享」的那几条。**2026-09-29 用读追踪补齐**：`_verify_pack` 的 T4 复算会经
#: `pack_combo.combine/profiles` 读到**别的包的声明 / 资产台账 / 模块契约**（实测越面读 225 件）——
#: 这些不写进键，就会「子扫描器失效、外层键没变」⇒ 逐包缓存命中旧判决（**陈旧/假绿**）。
#: 只有**产物切片**（`_PACK_FACE_SLICE`）是「谁改谁重算」；声明面一变，所有包的判决都可能变。
#: **核心模块文档按「解析后的契约」进键**（见 `shared_face_key`）：正文改动不该重算 106 个包。
#: 判据：`test_output_forms.PackKeyReadCoverageTest`。
_PACK_FACE_SHARED = ("community/*/modules/*.md", "community/*/protocol.yaml",
                     "community/*/assets/provenance.json", REGISTRY_INPUT)

# : 逐包键里「按**解析后**契约进键」的那条（`04_模块库`）：正文改动不换键、`machine_contract` 变才换
# 。
_PACK_FACE_PARSED = ("04_模块库/*/*.md",)



def shared_face_key(root: str = ".") -> str:
    """逐包键里**所有包共享**的那一半（跨包模块面 + registry）——**每个内容状态只算一遍**。

    为什么单拎出来（2026-09-29 仪器化实测）：`index_verify` 要为 111 个包各取一次内容键，
    而每个键都把 235 份 `community/*/modules/*.md` 重新枚举 + 摘要一遍 ⇒ **111 遍同一条共享面**，
    实测占 `index_verify` 185 ms 里的大头。切出来之后共享面一次算好、逐包只算自己那一份切片。
    正确性：键仍覆盖**同一批件**（共享面 ∪ 该包切片），任一侧内容一变键必变。
    **核心模块（`04_模块库`）按解析后的契约进键**（`pack_combo.core_contracts_fingerprint`）：
    `combine` 只消费核心模块的 `publish`（`core_pub`），所以正文改动不影响任何判决——按正文取键
    会让 106 个包在白改正文时全重算（实测 **+800 ms/条命令**）。判据：`PackKeyReadCoverageTest`
    （读覆盖）与 `PackVerifyCacheTest`（面内/面外换键）。
    """
    raw = _csc.face_fingerprint(root, _PACK_FACE_SHARED)
    from core import pack_combo as pc            # 惰性导入：避免模块级环
    core = pc.core_contracts_fingerprint(root)
    return hashlib.sha256(("%s\x00%s" % (raw, core)).encode("utf-8")).hexdigest()



_PACK_KEY_MEMO: Dict[str, Any] = {}

_PACK_KEY_MEMO_MAX = 4096



def _pack_key_reusable(_root: str, pkg: str, shared: str) -> Any:
    """**确知变更面**驱动的键复用：本包切片确知没变 ⇒ 复用上一次的键（返回该键；否则 None）。

    依据（实测 2026-09-29）：`index_verify` 要为 106 个包各算一次切片指纹（合计 ~15 ms），而最常见的
    改动（改 `04_模块库` 正文、改文档、改协议声明外的件）**一件都不落在任何包的切片里**——算完 106 次
    才发现全都没变。读层早就在用「确知变更路径」精确失效（`drop_resident`），键层过去没用。

    fail-closed：`conformance_scan.changed_paths()` 说「不知道」（没装常驻层 / 监听说不清 / 刚装层）
    时**一律不复用**；只有「确知这一批变更里没有一件落在本包切片模式内」才复用。
    """
    prev = _PACK_KEY_MEMO.get(pkg)
    if not prev or prev[0] != shared:
        return None
    known, changed = _csc.changed_paths()
    if not known:
        return None
    if any(_matches_any(rel, _pack_slice_patterns(pkg)) for rel in changed):
        return None                              # 本包切片里有确知变更 → 老老实实重算
    return prev[1]



def _pack_slice_patterns(pkg: str):
    return tuple("community/%s/%s" % (pkg, rel) for rel in _PACK_FACE_SLICE)



def _matches_any(rel: str, patterns) -> bool:
    """仓库相对路径是否落在任一模式内（语义与 `iter_files` 同源：`**` 跨目录、`*` 不跨）。

    两侧都按 `lower()` 归一：① 监听给的是**小写**相对路径，而模式里有 `INDEX.json` 这种大写；
    ② 归一后若「本该不匹配却被判成匹配」，后果只是**多算一次**（安全方向）——反过来才会陈旧。
    """
    segs = [s.lower() for s in str(rel).replace("\\", "/").split("/")]
    for pat in patterns:
        if _csc._match_parts(segs, _csc._compiled_parts(str(pat).replace("\\", "/").lower())):
            return True
    return False



def pack_slice_index(root: str) -> Dict[str, List[str]]:
    """**一次枚举**四条包面，按包切成 `{包名: [该包的相对路径…]}`（每条面内有序）。

    依据（实测 2026-09-29）：`pack_content_key` 过去按包拼模式（106 包 × 4 条 = 424 个不同模式），
    一次 `nf score` 里 `iter_files` 因此被调 **619 次（35.5 ms）**，其中 ~424 次是「同一批面按包切」。
    一次枚举 + 内存切片后只剩 4 次枚举（实测 ~8 ms），**键值逐位不变**（同一条路径清单、同一顺序），
    由 `test_output_forms.PackSliceIndexTest` 在真仓库上逐包比对守着。
    """
    out: Dict[str, List[str]] = {}
    for rel_pat in _PACK_FACE_SLICE:
        for rel in _csc.iter_files(root, "community/*/" + rel_pat):
            out.setdefault(rel.split("/")[1], []).append(rel)
    return out



def pack_content_key(root: str, pkg: str, shared: str = "", rels=None) -> str:
    """一个包的**内容键** = `(共享面指纹, 该包切片指纹)` 两者的组合（见 `shared_face_key`）。

    为什么要按切片而不是整棵包树：判据（`DerivedResultCacheTest.test_reads_stay_inside_declared_input_face`）
    要求**读盘面 ⊆ 声明输入面**——用整棵包树会把 `pipelines/**` 也读进来，而它不在 `INDEX_INPUTS` 里，
    当场红（实测）。切片 = 声明面里属于该包的那几条 + `community/*/modules/*.md`（组合包会借阅别包模块，
    保守起见每包都计入）+ registry。

    **边界（如实记）**：因为把「全体包的 modules」都算进每个包的键，**改一页模块文档仍会换掉所有包的键**
    （这是保守代价）。改 `docs/**`、协议件、包外资产等**不在包切片里**的件时，只有外层整块键变、
    **逐包键全不变** ⇒ 逐包缓存全命中（实测 `index_verify` 533 → 11 ms）。要连模块文档也精确到包，
    得按 `protocol.yaml` 的 `references` 求「被借阅包」闭包——属下一步。
    """
    if not shared:                        # 单调用方（如单测）自己用时不强求外部先算
        shared = shared_face_key(root)
    reused = _pack_key_reusable(root, pkg, shared)
    if reused is not None:
        return reused
    if rels is None:                      # 单独调用（如单测）时仍按包枚举，结果与切片路线**逐位相同**
        rels = [r for rel_pat in _PACK_FACE_SLICE
                for r in _csc.iter_files(root, "community/%s/%s" % (pkg, rel_pat))]
    per_pack = _csc.fingerprint_of(root, rels)
    key = hashlib.sha256(("%s\x00%s" % (shared, per_pack)).encode("utf-8")).hexdigest()
    if len(_PACK_KEY_MEMO) >= _PACK_KEY_MEMO_MAX:
        _PACK_KEY_MEMO.clear()
    _PACK_KEY_MEMO[pkg] = (shared, key)
    return key



def _pack_verify_ok(value) -> bool:
    """逐包校验结果的形状校验：`{"issues": [...], "rows": [...]}`（否则当未命中）。"""
    return (isinstance(value, dict) and set(value) == {"issues", "rows"}
            and isinstance(value["issues"], list) and isinstance(value["rows"], list))



def _verify_pack_cached(root: str, pkg: str, shared: str = "", rels=None):
    """按包内容键取校验结果：进程内一层 + **落盘**一层（新进程也能免付未变包的账）。"""
    key = pack_content_key(root, pkg, shared, rels)
    hit = _PACK_VERIFY_CACHE.get(key)
    if hit is None:
        hit = _verify_pack_io(root, pkg, key)
        if len(_PACK_VERIFY_CACHE) >= _PACK_VERIFY_MAX:
            _PACK_VERIFY_CACHE.clear()
        _PACK_VERIFY_CACHE[key] = hit
    return hit



def _verify_pack_io(root: str, pkg: str, key: str):
    """`_verify_pack_cached` 的落盘层（可被 A/B 关掉：`NF_NO_PACK_DISK=1`）。"""
    if os.environ.get("NF_NO_PACK_DISK"):
        issues, rows = _dm._verify_pack(root, pkg)
        return list(issues), list(rows)
    from core import disk_cache
    dkey = disk_cache.key("pack-verify", key, root=root,
                          code_scope=_ig.code_scope_fingerprint(root, ("core.output_forms",)))
    packed = disk_cache.load("pack-verify", dkey, validate=_pack_verify_ok)
    if packed is None:
        issues, rows = _dm._verify_pack(root, pkg)
        packed = {"issues": list(issues), "rows": list(rows)}
        disk_cache.store("pack-verify", dkey, packed, keep=512)
    return list(packed["issues"]), list(packed["rows"])
