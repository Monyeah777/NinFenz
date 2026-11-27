"""43 A2 —— Conformance 一致性分级扫描（声明 ≤ 可证级别，防虚标）。

分级定义见 01 §1.2：L0 结构可读 / L1 机读契约 / L2 装配可执行 / L3 外部互操作。

扫描对象：
- 模块文档 machine_contract.conformance（23 件机读块，check28 约束必带）
- community/*/protocol.yaml package.conformance（5 协议包，在册 = L2）
- protocol/export_conformance.json（导出契约面 manifest，L3 = 导出门禁锁定面）

用法：conformance_scan.scan('.') -> (issues, stats)
"""

# 读点：围栏 YAML / registry 读取在 _conformance._fence 里仍走 json_doc.loads（N11）。

from __future__ import annotations

import copy
import os

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
import sys as _sys
import types as _types
from dataclasses import dataclass

# 导入闭包指纹：由调用方算（持久层不再反向依赖解析层，见 2026-09-29 拆环）
from typing import Any, Dict, List, Tuple

from core import (
    atomic_write,
    disk_cache,
    json_doc,
)
from core import (
    content_face as _cf,
)
from core import (
    import_graph as _ig,
)

# 依赖面：逐字保留原模块 import 面（含函数内 core import 的边）——
# 耦合图/纯度面按模块级 import 计算，勿删（见 re-export 说明）。
from core import (
    lazy_yaml as _lyaml,
)

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade

from ._conformance import _fence, _memo, _resident
from ._conformance._export import (
    _GATE_FAIL_TOKENS,
    _gate_calls,
    _gate_defs,
    export_manifest_issues,
)
from ._conformance._fence import (
    _BODY_CACHE,
    _BODY_CACHE_BYTES,
    _BODY_CACHE_MAX,
    _BODY_CACHE_MAX_BYTES,
    _FENCE_CACHE,
    _FENCE_CACHE_MAX,
    _FENCE_CACHE_MAX_BYTES,
    _T,
    FENCE,
    _evidence_ids,
    _fence_yaml,
    _fence_yaml_cached,
    _fence_yaml_opt,
    _parse_fence_yaml,
    _read_json,
    load_yaml,
    load_yaml_cached,
)
from ._conformance._memo import (
    read_memo,
)
from ._conformance._read import (
    _decode_text,
    _payload_digest,
    _raw_bytes,
    content_fingerprint,
    fingerprint_of,
    read_bytes_cached,
    read_text_cached,
)
from ._conformance._resident import (
    _KEY_CACHE,
    _KEY_CACHE_MAX,
    _RESIDENT_DIR_MAX,
    _RESIDENT_RAW_MAX_BYTES,
    _RESIDENT_TEXT_MAX,
    _Entry,
    _resident_key,
    _resident_under,
    adopt_resident,
    changed_paths,
    clear_changes,
    clear_resident,
    drop_resident,
    install_resident,
    note_changes,
    resident_active,
    resident_stats,
    take_resident,
)
from ._conformance._scan import (
    scan,
)
from ._conformance._walk import (
    NON_REPO_DIRS,
    _compiled_parts,
    _enumerate_rel,
    _fast_glob_supported,
    _fixed_prefix,
    _match_parts,
    _module_docs,
    _scandir_list,
    _segment_regex,
    _tree_hit,
    iter_files,
    match_rel,
    matches_any,
    tree_files,
)


def _FACADE_GETATTR(name):
    if name in ("yaml", "SAFE_LOADER"):
        return _lyaml.module() if name == "yaml" else _lyaml.safe_loader()
    raise AttributeError(name)

_install_live_facade(__name__, {
    "_READ_MEMO": _memo,
    "_DIR_MEMO": _memo,
    "_DIGEST_MEMO": _memo,
    "_PAT_MEMO": _memo,
    "_TREE_MEMO": _memo,
    "_RESIDENT": _resident,
    "_FENCE_CACHE_BYTES": _fence,
}, _FACADE_GETATTR)


#: **面指纹**缓存（键 = (绝对 root, 模式元组)）：确知这批变更没一件落在该面内就整个复用（不枚举、
#: 不摘要），说不清一律重算。条目 `{"rels", "index", "digests", "fp"}`；两级复用见 `face_digests`。
_FACE_CACHE: Dict[Any, Any] = {}
_FACE_FP_MAX = 1024
#: 观测位：**整面重算** / **增量更新** 各多少次（复用不算）。判据 `FaceReuseBudgetTest` 用它把
#: 「确知没变就复用」变成**确定性**数字——不能靠数 `content_fingerprint`（那是 0，实测踩过）。
_FACE_FP_STATS: Dict[str, int] = {"recomputes": 0, "incremental": 0}


def _hash_face(rels, digests) -> str:
    """面指纹 = 逐件「相对路径 + \\x00 + 摘要 + \\x01」流式哈希（委托叶子件 `content_face`，避免两份帧）。"""
    from core import content_face as _cf
    return _cf.hash_face(rels, digests)


def face_fingerprint(root: str, patterns) -> str:
    """`content_fingerprint` 的**带确知变更面复用**版本（值逐位相同，只在确知没变时省掉重算）。"""
    return face_digests(root, patterns)[0]


def face_digests(root: str, patterns):
    """`(面指纹, {相对路径: 逐件摘要})`——一次枚举 + 一次摘要**服务两种口径**。

    `face_fingerprint` 就是本函数的第一个返回值（两者值**逐位相同**）。
    依据（实测 2026-09-29）：`asset_density.usage_scan` 的内容键要按**同一张语料面**取指纹，而它随后
    又要给 2815 份语料各取一次逐件摘要当**逐件缓存键**——同一批摘要算了两遍（~5.6 ms）。这个入口把
    「枚举 + 摘要」一次做完，指纹与逐件摘要一起交出。
    """
    pats = tuple(str(p) for p in patterns)
    key = (os.path.normcase(os.path.abspath(str(root))), pats)
    ent = _FACE_CACHE.get(key)
    if ent is not None:
        known, changed = changed_paths()
        if known:
            relevant = [c for c in changed if matches_any(c, pats)]
            if not relevant:
                return ent["fp"], ent["digests"]          # ① 确知没变：连哈希都不算
            # ② 只改内容 ⇒ 增量（成员集合不变）。比对必须**大小写不敏感**：监听的相对路径是小写，
            # `iter_files` 是真实大小写（`M00_数据槽总线.md`）⇒ 否则一律误判成新增件、增量形同虚设。
            members = [ent["index"].get(str(c).lower()) for c in relevant]
            if all(rel and os.path.isfile(os.path.join(str(root), *rel.split("/")))
                   for rel in members):
                for rel in members:
                    ent["digests"][rel] = _payload_digest(root, rel)
                ent["fp"] = _hash_face(ent["rels"], ent["digests"])
                _FACE_FP_STATS["incremental"] += 1
                return ent["fp"], ent["digests"]
    rels: List[str] = []                                      # ③ 首次 / 成员集合变了：整面重建
    for pat in patterns:
        rels.extend(iter_files(root, str(pat)))
    digests = {rel: _payload_digest(root, rel) for rel in rels}
    fp = _hash_face(rels, digests)
    _FACE_FP_STATS["recomputes"] += 1
    if len(_FACE_CACHE) >= _FACE_FP_MAX:
        _FACE_CACHE.clear()
    _FACE_CACHE[key] = {"rels": rels, "digests": digests, "fp": fp,
                        "index": {rel.lower(): rel for rel in rels}}
    return fp, digests


#: `scan()` 派生结果的跨调用缓存（键 = 输入内容指纹）。输入面见 `SCAN_INPUTS`——**穷举**，
#: 所以「输入一变必然换键」，不需要随请求清空。
_SCAN_CACHE: Dict[str, Tuple[List[str], Dict[str, int]]] = {}
#: `scan()` 的全部输入（逐一对照实现枚举：证据 id 的 registry + 模块文档 + 协议包声明 +
#: 导出契约 manifest + 门禁脚本里的证据名）。
SCAN_INPUTS = ("desktop/src/core/registry.json",
               "04_模块库/*/*.md",
               "community/*/modules/*.md",
               "community/*/protocol.yaml",
               "protocol/export_conformance.json",
               "verify.sh")


def result_pair_ok(value) -> bool:
    """持久缓存读回值的形状校验：`{"issues": [...], "stats": {...}}`（否则当未命中）。"""
    return (isinstance(value, dict) and set(value) == {"issues", "stats"}
            and isinstance(value["issues"], list) and isinstance(value["stats"], dict))


#: 通用「内容键派生结果」缓存的**进程内**层：tag → {输入面指纹: {"issues":…, "stats":…}}。
#: 与各派生自己的专用缓存同一条纪律（键即内容），只是把「指纹 → 缓存 → 落盘 → 校验 → 深拷贝」
#: 这套骨架收成一处，新派生接入只需三行（见 `memo_pair` 的调用示例）。
_DERIVED_MEMO: Dict[str, Dict[str, Any]] = {}


@dataclass(frozen=True)
class MemoOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    keep: int = 8
    fp: Optional[str] = None


def memo_pair(
    tag: str,
    patterns,
    impl,
    root: str = '.',
    code_modules = None,
    opts: MemoOptions | None = None,
):
    """`(issues, stats)` 形状的派生结果缓存（**进程内 + 持久**两层；键即内容）。

    纪律与 `scan()` 一致：输入面（`patterns`，须穷举）变 ⇒ 指纹变 ⇒ 必重算；持久层键另含代码面 +
    运行时（`disk_cache.key`）；读回必过 `result_pair_ok`；一切 IO 尽力而为。

    `code_modules`（如 `("core.schema_lint",)`）把**代码面**缩到「这段派生自己的导入闭包」——改别的
    模块不再换键（闭包算不出/含动态导入时自动退回整块代码面，见 `disk_cache.key`）。

    `fp` 可传**已经算好的指纹**（口径须与 `content_fingerprint(root, patterns)` 一致）：调用方若有
    更省的取键方式（例如把两张面各自的指纹组合起来），就不必在这里把面再枚举一遍。

    **没有「只在常驻层在位时才缓存」这档开关了**（2026-09-29 删，实测）：那条规矩建立在「冷进程里
    宽面指纹比直接重算更贵」上——今天不成立，冷进程本来就要为别的站点读整棵语料（逐件摘要在同一
    只读作用域内共享），指纹近乎白拿，而重算派生账贵得多。删掉后冷进程首跑 **4481 → 2188 ms**、
    稳态 **1585 → 1183 ms**（结论逐位相同）。
    """

    opts = opts if opts is not None else MemoOptions()
    keep = opts.keep
    fp = opts.fp
    if fp is None:
        # 走**面指纹**（带「确知没变就复用」）：各站点的面宽窄不一，这一改把「确知变更面」这条
        # 信息铺到**所有** `memo_pair` 站点，而不只是逐包键那一处。
        fp = face_fingerprint(root, patterns)
    mem = _DERIVED_MEMO.setdefault(tag, {})
    hit = mem.get(fp)
    if hit is None:
        from core import disk_cache
        from core import import_graph as _ig
        _scope = _ig.code_scope_fingerprint(root, code_modules) if code_modules else None
        dkey = disk_cache.key(tag, fp, root=root, code_scope=_scope)
        packed = disk_cache.load(tag, dkey, validate=result_pair_ok)
        if packed is None:
            got = impl(root)
            # 未命中也要与命中**逐字节一致**：落盘走 `sort_keys` 规范化 ⇒ 新算的这份同过一道
            # （否则首跑/次跑换序；见 `disk_cache.canonical` 的实证）。
            packed = disk_cache.canonical({"issues": list(got[0]), "stats": got[1]})
            disk_cache.store(tag, dkey, packed)
        if len(mem) >= keep:
            mem.clear()
        mem[fp] = packed
        hit = packed
    return copy.deepcopy(list(hit["issues"])), copy.deepcopy(dict(hit["stats"]))


def _scan_impl(root: str = ".") -> Tuple[List[str], Dict[str, int]]:
    issues: List[str] = []
    if _lyaml.module() is None:
        issues.append("PyYAML 不在（conformance_scan 依赖仓库既有 yaml 依赖）")
        return issues, {"modules_mc": 0, "packages": 0, "export_items": 0}

    # registry.json 只读一次：过去它在**每个社区包的循环体里**被重读一遍（实测 112 次
    # ≈ 0.09 s，纯重复 IO + JSON 解析），现在提到扫描开头，两个用处共用同一份。
    reg, _ = _read_json(os.path.join(root, "desktop", "src", "core", "registry.json"))
    evidence = set(_evidence_ids(root, reg))
    reg_ids = {p.get("id") for p in (reg or {}).get("protocols") or []}

    modules_mc = 0
    #: 模块 id 全局唯一（01 §1.6.11）——登记面由 check14 ⑤b 管；但**两个模块文件声明同一 mc.id**
    #: 此前无判据，运行时索引 first-wins 静默择一（`mcp_runtime` / `pipelinerun`）会让编号指向不确定
    #: 的模块。此处补文件级唯一判据（极端渗透 D3）。
    seen_mc_id: dict = {}
    for doc in _module_docs(root):
        rel = os.path.relpath(doc, root).replace(os.sep, "/")
        try:
            text = read_text_cached(doc)      # 共享语料：同一份模块文档一次只读一遍
        except Exception as exc:
            issues.append(f"{rel}: 读取失败 {exc}")
            continue
        parsed = _fence_yaml(text, "machine_contract")
        if "machine_contract" not in parsed:
            continue
        mc = parsed["machine_contract"]
        mid = str((mc or {}).get("id") or "")
        if mid:
            if mid in seen_mc_id:
                issues.append("%s: 模块 id 与 %s 重复（mc.id=%s）——编号是全局寻址面，"
                              "运行时索引会静默择一，须改号"
                              "（修复指引：按 01 §1.6.11 换类内段号或 M91-M99 段号）"
                              % (rel, seen_mc_id[mid], mid))
            else:
                seen_mc_id[mid] = rel
        modules_mc += 1
        declared = mc.get("conformance")
        if declared not in ("L1", "L2", "L3"):
            issues.append(f"{rel}: machine_contract 缺/非法 conformance 声明 {declared!r}")
            continue
        mid = mc.get("id")
        provable = 2 if isinstance(mid, str) and mid in evidence else 1
        order = {"L1": 1, "L2": 2, "L3": 3}
        if order[declared] > provable:
            issues.append(
                f"{rel}: conformance 虚标 {declared} > 可证 L{provable}"
                f"（{mid!r} 不在装配在册证据）"
            )

    # community 协议包
    packages = 0
    # 走共享枚举器（目录清单已在常驻层）：实测 2026-09-29，`glob.glob(community/*/protocol.yaml)`
    # 一次 **9–13 ms**（占该状态 stat 面的三分之一），同一张面走 `iter_files` 后 **~0.4 ms**。
    for rel in iter_files(root, "community/*/protocol.yaml"):
        proto = os.path.join(root, *rel.split("/"))
        try:
            # 共享语料 + 内容键解析（同一份 protocol.yaml 一轮只读一次、只解析一次）
            data = load_yaml_cached(read_text_cached(proto))
        except Exception as exc:
            issues.append(f"{rel}: protocol.yaml 解析失败 {exc}")
            continue
        packages += 1
        pkg = (data or {}).get("package") or {}
        declared = pkg.get("conformance")
        pid = pkg.get("id")
        if declared not in ("L1", "L2", "L3"):
            issues.append(f"{rel}: package 缺/非法 conformance 声明 {declared!r}")
            continue
        provable = 2 if isinstance(pid, str) and pid in reg_ids else 1
        order = {"L1": 1, "L2": 2, "L3": 3}
        if order[declared] > provable:
            issues.append(f"{rel}: conformance 虚标 {declared} > 可证 L{provable}（包不在 registry p"
                f"rotocols[]）")

    # 导出契约面 manifest（L3 = 导出契约门禁锁定面）
    manifest_path = os.path.join(root, "protocol", "export_conformance.json")
    manifest, err = _read_json(manifest_path)
    export_items = 0
    if not isinstance(manifest, dict):
        issues.append(f"protocol/export_conformance.json 缺失/解析失败：{err}")
    else:
        verify_txt = ""
        verify_path = os.path.join(root, "verify.sh")
        if os.path.isfile(verify_path):
            with open(verify_path, encoding="utf-8") as fh:
                verify_txt = fh.read()
        man_issues, export_items = export_manifest_issues(root, verify_txt, manifest)
        issues.extend(man_issues)

    stats = {
        "modules_mc": modules_mc,
        "packages": packages,
        "export_items": export_items,
    }
    return issues, stats
