"""core.pack_combo 私有实现分片：组合（combine）与产物化（materialize）的真算。

对外只经 core.pack_combo 门面（经 _part1 重新导出）导入；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from core import atomic_write
from core._pack_combo._base import (
    _asset_index,
    _core_ids,
    _digest,
    _module_contracts,
    _read_json,
    indexes,
    profiles,
)
from core._pack_combo._const import CORE13
from core._pack_combo._materialize import _flatten_sources, combo_outputs, prof_get_module
from core._pack_combo._readme import combo_assets_readme, combo_pipeline, combo_readme


# ---------------------------------------------------------------- combine
def _chosen(packs: Sequence[str], prof: Dict[str, Any]
            ) -> Tuple[List[str], List[Dict[str, Any]]]:
    """未知包名 + 已选包档（顺序同 packs）。"""
    unknown = [p for p in packs if p not in prof]
    chosen = [prof[p] for p in packs if p in prof]
    return unknown, chosen


def _seed_modules(chosen: List[Dict[str, Any]], extra_modules: Sequence[str],
                  contracts: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """包内模块 + 组件级自由点选 → 初始模块表。"""
    mods: Dict[str, Dict[str, Any]] = {}
    for pr in chosen:
        for rec in pr["module_recs"]:
            mods[rec["id"]] = rec
    for mid in extra_modules:                 # 组件级自由：直接点模块名（可跨包）
        rec = contracts.get(str(mid)) or contracts.get(str(mid).split(":")[-1])
        if rec:
            mods[rec["id"]] = rec
    return mods


def _add_borrowed(mods: Dict[str, Dict[str, Any]], borrowed: List[Dict[str, str]],
                  rec: Dict[str, Any], why: str, by: str) -> bool:
    """借入一个模块（去重）；返回是否真的新增。"""
    if rec["id"] in mods:
        return False
    mods[rec["id"]] = rec
    borrowed.append({"module": rec["id"], "from": str(rec.get("pack")),
                     "by": by or "<组件级>", "mode": "closure_pull", "why": why})
    return True


def _reference_borrows(chosen: List[Dict[str, Any]], contracts: Dict[str, Any],
                       mods: Dict[str, Dict[str, Any]],
                       borrowed: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """references 自动借入（跨包引用白名单语义）→ 未解析引用清单。"""
    unresolved_refs: List[Dict[str, str]] = []
    for pr in chosen:
        for ref in pr.get("references") or []:
            src, mid = ref.get("source_package", ""), ref.get("module_id", "")
            rec = contracts.get(mid) or contracts.get(str(mid).split(":")[-1])
            if rec and str(rec.get("pack")) == src:
                if rec["id"] not in mods:
                    mods[rec["id"]] = rec
                    borrowed.append({"module": rec["id"], "from": src,
                                     "by": pr["package"], "mode": "module_borrow"})
            elif rec:
                if rec["id"] not in mods:
                    mods[rec["id"]] = rec
                    borrowed.append({"module": rec["id"], "from": str(rec.get("pack")),
                                     "by": pr["package"], "mode": "module_borrow"})
            else:
                unresolved_refs.append({"by": pr["package"], "source_package": src,
                                        "module_id": mid})
    return unresolved_refs


def _dep_closure_round(mods: Dict[str, Dict[str, Any]], borrowed: List[Dict[str, str]],
                       by_id: Dict[str, Dict[str, Any]], core: Any) -> bool:
    """依赖 inputs 闭包一轮 → 是否有新增。"""
    grew = False
    for m, r in list(mods.items()):
        for dep in r.get("inputs", []):
            if dep in core or dep in mods or dep.split(":")[-1] in core:
                continue
            rec = by_id.get(dep) or by_id.get(str(dep).split(":")[-1])
            if rec and _add_borrowed(mods, borrowed, rec,
                                     "依赖 %s 的 inputs 需要 %s" % (m, dep), m):
                grew = True
    return grew


def _event_closure_round(mods: Dict[str, Dict[str, Any]], borrowed: List[Dict[str, str]],
                         core_pub: Any, pub_index: Any) -> bool:
    """事件发布方闭包一轮 → 是否有新增。"""
    grew = False
    published_now = ({e for x in mods.values() for e in x.get("publish", [])} | core_pub)
    for m, r in list(mods.items()):
        for ev in r.get("subscribe", []):
            if ev in published_now:
                continue
            recs = pub_index.get(ev) or []
            if not recs:
                continue                      # 无人发布 → 由 unpublished 面报告
            for rec in recs:
                if _add_borrowed(mods, borrowed, rec,
                                 "事件 %s 需要发布方（%s 订阅）" % (ev, m), m):
                    grew = True
    return grew


def _closure(mods: Dict[str, Dict[str, Any]], borrowed: List[Dict[str, str]],
             by_id: Dict[str, Dict[str, Any]], pub_index: Any) -> None:
    """不动点闭包：依赖 inputs ∪ 事件发布方（递归），直到不再新增。"""
    core = _core_ids()
    for _round in range(12):
        grew = _dep_closure_round(mods, borrowed, by_id, core)
        if _event_closure_round(mods, borrowed, core, pub_index):
            grew = True
        if not grew:
            break


def _dangling(mods: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
    """悬空依赖（既非核心也非在场模块）。"""
    core = _core_ids()
    out: List[Dict[str, str]] = []
    for m, r in sorted(mods.items()):
        for dep in r.get("inputs", []):
            if dep in core or dep in mods or dep.split(":")[-1] in core:
                continue
            out.append({"module": m, "needs": dep})
    return out


def _published_faces(mods: Dict[str, Dict[str, Any]], core_pub: Any) -> Any:
    """已发布事件集合（模块 publish ∪ 核心发布面）。"""
    published = {e for r in mods.values() for e in r.get("publish", [])}
    published |= core_pub
    return published


def _unbridged_faces(mods: Dict[str, Dict[str, Any]], published: Any) -> List[str]:
    """订阅了但未被任何在场模块/核心发布的事件。"""
    return sorted({e for r in mods.values() for e in r.get("subscribe", [])
                   if e not in published})


def _unpublished_faces(mods: Dict[str, Dict[str, Any]], published: Any,
                       pub_index: Any) -> List[str]:
    """全仓无发布方的事件（由 unpublished 面报告）。"""
    return sorted({e for r in mods.values() for e in r.get("subscribe", [])
                   if e not in published and not (pub_index.get(e) or [])})


def _event_faces(mods: Dict[str, Dict[str, Any]], core_pub: Any, pub_index: Any
                 ) -> Tuple[Any, List[str], List[str]]:
    """事件闭包三面 → (published, unbridged, unpublished)。"""
    published = _published_faces(mods, core_pub)
    return (published, _unbridged_faces(mods, published),
            _unpublished_faces(mods, published, pub_index))


def _pack_layers(chosen: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """包声明层栈 → {层: [模块]}（保序去重）。"""
    stacks: Dict[str, List[str]] = {}
    for pr in chosen:
        for lay, ms in pr["layers"].items():
            stacks.setdefault(lay, [])
            for m in ms:
                if m not in stacks[lay]:
                    stacks[lay].append(m)
    return stacks


def _merge_module_layers(stacks: Dict[str, List[str]],
                         mods: Dict[str, Dict[str, Any]]) -> None:
    """把模块自带 layer 并入层栈（追加在包声明之后）。"""
    for m, r in sorted(mods.items()):
        lay = str(r.get("layer") or "")
        if lay and m not in stacks.get(lay, []):
            stacks.setdefault(lay, []).append(m)


def _order_stacks(stacks: Dict[str, List[str]], mods: Dict[str, Dict[str, Any]],
                  packs: Sequence[str]) -> List[Dict[str, Any]]:
    """规范序（按排序后的包名定序）+ 列表形态。"""
    canon = sorted(set(packs))
    order = {p: i for i, p in enumerate(canon)}
    ordered = {k: sorted(set(v), key=lambda x: (order.get(
        str((mods.get(x) or {}).get("pack")), 99), x))
        for k, v in sorted(stacks.items())}
    return [{"layer": k, "modules": v} for k, v in sorted(ordered.items())]


def _layer_stacks(chosen: List[Dict[str, Any]], mods: Dict[str, Dict[str, Any]],
                  packs: Sequence[str]) -> List[Dict[str, Any]]:
    """层栈 → 对外列表形态（[{layer, modules}]）。"""
    stacks = _pack_layers(chosen)
    _merge_module_layers(stacks, mods)
    return _order_stacks(stacks, mods, packs)


def _asset_borrows(chosen: List[Dict[str, Any]], mods: Dict[str, Dict[str, Any]],
                   extra_assets: Sequence[str], asset_index: Any
                   ) -> Tuple[List[Dict[str, str]], List[str]]:
    """资产只读借阅 → (borrow, unresolved)。"""
    borrow: List[Dict[str, str]] = []
    unresolved: List[str] = []
    for pr in chosen:
        for a in pr["assets"]:
            if a["module"] and a["module"] not in mods:
                borrow.append({"key": a["key"], "from": pr["package"],
                               "for_module": a["module"], "mode": "asset_readonly"})
    for spec in extra_assets:
        pkg, _, key = str(spec).partition(":")
        if (pkg, key) in asset_index:
            borrow.append({"key": key, "from": pkg, "for_module": "",
                           "mode": "asset_readonly"})
        else:
            unresolved.append(str(spec))
    return borrow, unresolved


def _certificate(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """组合证书（五条不变量的机读面）。"""
    mods = ctx["mods"]
    dangling = ctx["dangling"]
    unresolved_refs = ctx["unresolved_refs"]
    unbridged = ctx["unbridged"]
    missing_contracts = ctx["missing_contracts"]
    unresolved = ctx["unresolved"]
    cert: Dict[str, Any] = {
        "schema": "nf-combo/1",
        "packs": ctx["canon"],
        "unknown_packs": sorted(ctx["unknown"]),
        "extra_modules": sorted(set(ctx["extra_modules"])),
        "modules": sorted(mods),
        "module_count": len(mods),
        "layer_stacks": ctx["stack_list"],
        "dependency_closure": {
            "core": sorted(_core_ids()),
            "explicit": sorted({d for r in mods.values() for d in r.get("inputs", [])
                                if d in mods}),
            "dangling": dangling},
        "event_closure": {"published": sorted(ctx["published"]), "unbridged": unbridged},
        "events_unpublished": ctx["unpublished"],
        "assets_borrowed": sorted(ctx["borrow"], key=lambda x: (x["from"], x["key"])),
        "modules_borrowed": sorted(ctx["borrowed"], key=lambda x: (x["by"], x["module"])),
        "references_unresolved": sorted(unresolved_refs,
                                        key=lambda x: (x["by"], x["module_id"])),
        "assets_unresolved": sorted(unresolved),
        "module_missing_contract": missing_contracts,
    }
    cert["legal"] = not (ctx["unknown"] or dangling or unbridged or missing_contracts
                         or unresolved or unresolved_refs)
    return cert


def combine(root: str = ".", packs: Sequence[str] = (), extra_modules: Sequence[str] = (),
            extra_assets: Sequence[str] = (), _prof: Any = None,
            _contracts: Any = None) -> Dict[str, Any]:
    """组合一个（纯读、不落盘）：返回组合证书 + 五条不变量判定。"""
    prof = _prof if _prof is not None else profiles(root)
    contracts = _contracts if _contracts is not None else _module_contracts(root)
    unknown, chosen = _chosen(packs, prof)
    mods = _seed_modules(chosen, extra_modules, contracts)
    borrowed: List[Dict[str, str]] = []
    by_id, pub_index, core_pub = indexes(root)
    unresolved_refs = _reference_borrows(chosen, contracts, mods, borrowed)
    _closure(mods, borrowed, by_id, pub_index)
    missing_contracts = sorted(m for m, r in mods.items() if not r.get("path"))
    dangling = _dangling(mods)
    published, unbridged, unpublished = _event_faces(mods, core_pub, pub_index)
    stack_list = _layer_stacks(chosen, mods, packs)
    borrow, unresolved = _asset_borrows(chosen, mods, extra_assets, _asset_index(root))
    canon = sorted(set(packs))
    cert = _certificate({"canon": canon, "unknown": unknown,
                         "extra_modules": extra_modules, "mods": mods,
                         "stack_list": stack_list, "dangling": dangling,
                         "published": published, "unbridged": unbridged,
                         "unpublished": unpublished, "borrow": borrow,
                         "borrowed": borrowed, "unresolved_refs": unresolved_refs,
                         "unresolved": unresolved,
                         "missing_contracts": missing_contracts})
    cert["digest"] = _digest(cert)
    return cert
