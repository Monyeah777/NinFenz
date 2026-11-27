"""pack_combo 私有子模块 _base：基础层：按 root 画像缓存、内容键缓存、协议/模块契约/核心契约解析、包画像。

门面 core.pack_combo 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path

from core import json_doc
from core import conformance_scan as csc
from core import import_graph as _ig

from ._const import CORE13, CORE_CONTRACT_PATTERNS, INPUT_PATTERNS, MODULE_CONTRACT_PATTERNS, PROFILE_PATTERNS, _CACHE, _CACHE_MAX, _CONTENT_CACHE, _CONTENT_CACHE_MAX, _CONTRACTS_CACHE, _CONTRACTS_CACHE_MAX


def _root_cache(key: str) -> Dict[str, Any]:
    if key not in _CACHE and len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    return _CACHE.setdefault(key, {})


def _cache_key(root: str) -> str:
    """缓存键 = 绝对路径（`os.path.abspath`，**纯字符串运算，不碰文件系统**）。

    效率（实测，`nf score` / check32 广度证明）：此处原为 `Path(root).resolve()`，在
    Windows 上每次都要走 `nt._getfinalpathname` + `nt.stat` 系统调用（约 0.4–0.6 ms）。
    广度证明要跑 **6888 次**组合、每次组合都经 `indexes()` 取一次键——白花 **3.8 s**
    （占该证明总时 6.2 s 的 61%）。`abspath` 同样把相对/绝对 root 归一到同一个键
    （`normpath(join(cwd, root))`），但只在字符串层做。
    """
    return os.path.abspath(str(root))


def cache_clear() -> None:
    _CACHE.clear()


def _content_store(key: Any, value: Any) -> None:
    if key not in _CONTENT_CACHE and len(_CONTENT_CACHE) >= _CONTENT_CACHE_MAX:
        _CONTENT_CACHE.clear()
    _CONTENT_CACHE[key] = copy.deepcopy(value)


def _inputs_fingerprint(root: str = ".") -> str:
    """包画像 / 广度证明诸输入的**内容指纹**（键即内容；面见 `INPUT_PATTERNS`）。

    口径（2026-09-29 改，实测）：过去这里是 `Path.glob` + 逐件 `read_text_cached(...).encode()`
    ——**每次 57 ms**，而广度证明一次要调它**两遍**（进程内内容键一遍、落盘键一遍）⇒ **114 ms**，
    占 `pack_combo.scan` 的 **79%**（仪器化实测）。改走 `csc.content_fingerprint`（`iter_files`
    单遍枚举 + 常驻层**逐件摘要**）后 **2.3 ms（25×）**；口径仍是「相对路径 + 该件内容摘要」，
    且**枚举面逐件一致**由 `test_pack_combo.InputFaceTest` 在真仓库上逐模式守着。
    值本身换了一代 ⇒ 落盘缓存重键一次（一次性重算，无陈旧风险）。
    """
    return csc.face_fingerprint(root, INPUT_PATTERNS)


def _read_json(path: Path) -> Any:
    try:
        return json_doc.loads(csc.read_text_cached(path), None, what=str(path))
    except (OSError, ValueError):  # 件不可读/不可解析 ⇒ None（调用方按「无该面」处理）
        return None


def _core_ids() -> Set[str]:
    out = set(CORE13)
    for x in CORE13:
        out.add(x.split(":")[-1])
    return out


def _pack_dirs(root: str = ".") -> List[Path]:
    """有 `community/<包>/protocol.yaml` 的包目录（有序）。

    效率（实测 2026-09-29）：原实现 `Path.iterdir()` + 逐条 `d.is_dir()` + `protocol.yaml.is_file()`
    ——**每次 20 ms**（111 个目录 ⇒ 200+ 次 stat）；而守护**逐请求**清空按根缓存（`cache_clear`），
    于是一次新内容状态里 `profiles()` 重算时又要付一遍。改走共享枚举器（目录清单已在常驻层）
    后 **~0.5 ms**；面**逐件一致**由 `test_pack_combo.PackDirEnumerationTest` 用旧口径原样重算比对。
    """
    from core import conformance_scan as _csc
    base = Path(root)
    return [base / "community" / name for name in
            sorted({rel.split("/")[1]
                    for rel in _csc.iter_files(root, "community/*/protocol.yaml")})]


def _protocol_ids(text: str) -> List[str]:
    """模块 id 清单：行式（全限定 / 裸号，并集去重）→ 无则 flow 写法。"""
    ids = re.findall(r'(?m)^\s*-\s*"([^"]+:M\d{2,3})"\s*(?:#.*)?$', text)
    ids += re.findall(r'(?m)^\s*-\s*"?(M\d{2,3})"?\s*(?:#.*)?$', text)
    ids = list(dict.fromkeys(ids))          # 两种写法并集（旧包混用行式裸号与全限定）
    if ids:
        return ids
    m = re.search(r"(?m)^\s*module_id_range\s*:\s*\[([^\]]*)\]", text)
    if m:
        return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
    return []


def _protocol_layers(text: str) -> Dict[str, List[str]]:
    layers: Dict[str, List[str]] = {}
    for lm in re.finditer(r"(?m)^\s*(P\d{2})\s*[^:]*:\s*\{default:\s*\[([^\]]*)\]", text):
        mods = [x.strip().strip("'\"") for x in lm.group(2).split(",") if x.strip()]
        if mods:
            layers[lm.group(1)] = mods
    return layers


def _protocol_refs(text: str) -> List[Dict[str, str]]:
    refs = []
    for rm in re.finditer(r"(?ms)^\s*-\s*source_package:\s*(\S+)\s*\n\s*module_id:\s*(\S+)", text):
        refs.append({"source_package": rm.group(1).strip("'\""),
                     "module_id": rm.group(2).strip("'\"")})
    return refs


def _parse_protocol(path: Path) -> Dict[str, Any]:
    """极小读取：只取组合需要的键（id / pipeline / module_id_range / mount_layers）。"""
    text = csc.read_text_cached(path)
    out: Dict[str, Any] = {"dir": path.parent.name}
    m = re.search(r"(?m)^\s*id:\s*(\S+)\s*$", text)
    out["id"] = m.group(1) if m else path.parent.name
    m = re.search(r"(?m)^\s*pipeline:\s*(P\d{2,3})\s*$", text)
    out["pipeline"] = m.group(1) if m else ""
    # 行式清单：`    - "情感:M22"   # 注释` / `    - "M40"    # 注释`（注释须容忍）
    out["module_ids"] = _protocol_ids(text)
    out["mount_layers"] = _protocol_layers(text)
    out["references"] = _protocol_refs(text)
    return out


def _face_paths(root: str, pattern: str) -> List[Path]:
    """按模式枚举并还原成 `Path`（与 `Path(root).glob(pattern)` 同形态；有序）。

    效率（实测 2026-09-29）：`Path.glob` 在非末段用 `is_dir()` 逐条判——`community/*/modules/*.md`
    要判 **111 次** `is_dir`，一次新内容状态里这一笔独占 **~10 ms**（占该状态 stat 面的三分之一）；
    共享枚举器的目录清单已在常驻层里，同一张面 **~0.4 ms**。面**逐件一致**由
    `test_pack_combo.ContractEnumerationTest` 用旧口径原样重算比对。
    """
    base = Path(root)
    return [base.joinpath(*rel.split("/")) for rel in csc.iter_files(root, pattern)]


def _event_names(mc: Dict[str, Any], key: str) -> List[str]:
    return [str(x) for x in ((mc.get("events") or {}).get(key) or [])]


def _fence_mc(text: str) -> Dict[str, Any] | None:
    """`machine_contract` 围栏块 → dict；缺块/非对象/空块返回 None。"""
    mc = (csc._fence_yaml(text, "machine_contract") or {}).get("machine_contract") or {}
    if not isinstance(mc, dict) or not mc:
        return None
    return mc


def _module_rec(p: Path, mc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(mc.get("id") or p.stem.split("_")[0]),
        "stem": p.stem.split("_")[0],
        "pack": p.parents[1].name,
        "layer": str(mc.get("layer") or ""),
        "inputs": [str(x) for x in (mc.get("inputs") or [])],
        "outputs": [str(x) for x in (mc.get("outputs") or [])],
        "publish": _event_names(mc, "publish"),
        "subscribe": _event_names(mc, "subscribe"),
        "path": p.as_posix(),
    }


def _module_rec_from_text(p: Path, text: str) -> Dict[str, Any] | None:
    mc = _fence_mc(text)
    if mc is None:
        return None
    return _module_rec(p, mc)


def _module_contracts(root: str = ".") -> Dict[str, Dict[str, Any]]:
    """community/*/modules/*.md → {module id（全限定与裸号均可查）: 契约摘要}。"""
    key = _cache_key(root)
    cached = _root_cache(key)
    if cached.get("contracts"):
        return cached["contracts"]
    fp = csc.face_fingerprint(root, MODULE_CONTRACT_PATTERNS)
    hit = _CONTRACTS_CACHE.get("mod:" + fp)
    if hit is not None:
        cached.update({"contracts": hit})
        _CACHE[key] = cached
        return hit
    out: Dict[str, Dict[str, Any]] = {}
    for p in _face_paths(root, "community/*/modules/*.md"):
        try:
            text = csc.read_text_cached(p)
        except OSError:  # 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁另行报出（见 AUD-0016）
            continue
        rec = _module_rec_from_text(p, text)
        if rec is None:
            continue
        out[rec["id"]] = rec
        out.setdefault(rec["stem"], rec)
        out.setdefault(rec["id"].split(":")[-1], rec)
    if len(_CONTRACTS_CACHE) >= _CONTRACTS_CACHE_MAX:
        _CONTRACTS_CACHE.clear()
    _CONTRACTS_CACHE["mod:" + fp] = out
    cached.update({"contracts": out})
    _CACHE[key] = cached
    return out


def _core_rec(p: Path, mc: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": str(mc.get("id") or p.stem.split("_")[0]),
            "stem": p.stem.split("_")[0],
            "publish": _event_names(mc, "publish"),
            "subscribe": _event_names(mc, "subscribe"),
            "path": p.as_posix()}


def _core_rec_from_text(p: Path, text: str) -> Dict[str, Any] | None:
    mc = _fence_mc(text)
    if mc is None:
        return None
    return _core_rec(p, mc)


def _core_contracts(root: str = ".") -> Dict[str, Dict[str, Any]]:
    """官方核心 13 件（04_模块库/*/*.md）的契约摘要。

    必要性（2026-09-23 实测）：`core_only: true` 意味着**核心模块永远随任意组合装载**，
    故事件闭包必须把核心的 publish 计入；否则 chaos_event / minute_tick 这类核心事件
    会被误报为「未桥」。
    """
    fp = csc.face_fingerprint(root, CORE_CONTRACT_PATTERNS)
    hit = _CONTRACTS_CACHE.get("core:" + fp)
    if hit is not None:
        return hit
    out: Dict[str, Dict[str, Any]] = {}
    for p in _face_paths(root, "04_模块库/*/*.md"):
        try:
            text = csc.read_text_cached(p)
        except OSError:  # 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁另行报出（见 AUD-0016）
            continue
        rec = _core_rec_from_text(p, text)
        if rec is None:
            continue
        out[rec["id"]] = rec
        out.setdefault(rec["stem"], rec)
    if len(_CONTRACTS_CACHE) >= _CONTRACTS_CACHE_MAX:
        _CONTRACTS_CACHE.clear()
    _CONTRACTS_CACHE["core:" + fp] = out
    return out


def indexes(root: str = ".") -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]],
                                      Set[str]]:
    """组合闭包用的三类索引（一次构建、供广度证明复用）：
    module id → 契约、事件 → 发布方列表、核心发布事件集。"""
    key = _cache_key(root)
    cached = _root_cache(key)
    if cached.get("by_id") is not None:
        return cached["by_id"], cached["pub_index"], cached["core_pub"]
    contracts = _module_contracts(root)
    by_id: Dict[str, Dict[str, Any]] = {}
    pub_index: Dict[str, List[Dict[str, Any]]] = {}
    for r in contracts.values():
        if not r.get("path"):
            continue
        by_id.setdefault(r["id"], r)
        for e in r.get("publish") or []:
            pub_index.setdefault(e, []).append(r)
    core_pub = {e for r in _core_contracts(root).values() for e in r.get("publish", [])}
    prof = profiles(root)
    cached.update({"prof": prof, "contracts": contracts, "by_id": by_id,
                   "pub_index": pub_index, "core_pub": core_pub})
    _CACHE[key] = cached
    return by_id, pub_index, core_pub


def _pack_assets(root: str, pkg_dir: str) -> List[Dict[str, str]]:
    doc = _read_json(Path(root) / "community" / pkg_dir / "assets" / "provenance.json") or {}
    return [{"key": str(a.get("key") or ""), "file": str(a.get("file") or ""),
             "module": str(a.get("module") or ""), "source_package": pkg_dir}
            for a in (doc.get("assets") or [])]


def _asset_index(root: str = ".") -> Dict[Tuple[str, str], Dict[str, Any]]:
    """(包名, 资产键) → 资产记录；一次构建、供全部组合复用。

    效率（实测）：过去在 `combine()` 里每次现扫 `prof` 的 111 个包资产表（6885 次 /
    0.44 s）。它只依赖 `profiles(root)`，故随同一份 `_CACHE` 缓存。
    """
    key = _cache_key(root)
    cached = _root_cache(key)
    if cached.get("asset_index") is not None:
        return cached["asset_index"]
    out = {(pr["package"], a["key"]): a
           for pr in profiles(root).values() for a in pr["assets"]}
    cached.update({"asset_index": out})
    _CACHE[key] = cached
    return out


def _own_modules(proto: Dict[str, Any],
                 contracts: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    own = []
    for mid in proto["module_ids"]:
        rec = contracts.get(str(mid)) or contracts.get(str(mid).split(":")[-1])
        own.append(rec or {"id": str(mid), "layer": "", "inputs": [], "publish": [],
                           "subscribe": [], "pack": proto["id"]})
    return own


def _layers_of(own: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    layers: Dict[str, List[str]] = {}
    for rec in own:
        lay = str(rec.get("layer") or "")
        if lay:
            layers.setdefault(lay, [])
            if rec["id"] not in layers[lay]:
                layers[lay].append(rec["id"])
    return layers


def _pack_profile(root: str, d: Path, proto: Dict[str, Any],
                  contracts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    own = _own_modules(proto, contracts)
    layers = _layers_of(own)
    return {
        "package": proto["id"], "pipeline": proto.get("pipeline", ""),
        "modules": [r["id"] for r in own], "module_recs": own,
        "references": proto.get("references") or [],
        "layers": {k: sorted(set(v)) for k, v in sorted(layers.items())},
        "assets": _pack_assets(root, d.name),
        "publishes": sorted({e for r in own for e in r.get("publish", [])}),
        "subscribes": sorted({e for r in own for e in r.get("subscribe", [])}),
    }


def profiles(root: str = ".") -> Dict[str, Dict[str, Any]]:
    """每个包的组合画像（一次解析，供广度证明复用）。

    两层缓存：本次扫描按 root（`_CACHE`，守护逐请求清空）→ 跨调用按**内容指纹**
    （`_CONTENT_CACHE`，输入没变就直接复用；输入一变指纹就变，故无陈旧风险）。
    """
    key = _cache_key(root)
    cached = _root_cache(key)
    if cached.get("prof"):
        return cached["prof"]
    fp = csc.face_fingerprint(root, PROFILE_PATTERNS)          # 只按**真读面**取键（见其常量说明）
    hit = _CONTENT_CACHE.get(("prof", fp))
    dkey = None
    if hit is None:                        # 进程内没命中 → 再看**持久**层（新进程也免付这笔账）
        from core import disk_cache
        dkey = disk_cache.key("pack-prof", fp, root=root,
                              code_scope=_ig.code_scope_fingerprint(root, ("core.pack_combo",)))
        got_disk = disk_cache.load("pack-prof", dkey,
                                   validate=lambda v: isinstance(v, dict) and bool(v))
        if got_disk is not None:
            hit = got_disk
            _content_store(("prof", fp), got_disk)
    if hit is not None:
        got = copy.deepcopy(hit)
        _CACHE.setdefault(key, {})["prof"] = got      # 顺手回填本次扫描的缓存，供 indexes() 复用
        return got
    contracts = _module_contracts(root)
    out: Dict[str, Dict[str, Any]] = {}
    for d in _pack_dirs(root):
        proto = _parse_protocol(d / "protocol.yaml")
        out[proto["id"]] = _pack_profile(root, d, proto, contracts)
    cached.update({"prof": out, "contracts": contracts})
    _CACHE[key] = cached
    _content_store(("prof", fp), out)
    if dkey is not None:
        disk_cache.store("pack-prof", dkey, out)
    return out


def _digest(obj: Dict[str, Any]) -> str:
    blob = json.dumps({k: v for k, v in obj.items() if k != "digest"},
                      ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:32]
