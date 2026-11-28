"""管线抽象执行（dry-run）→ 执行图（机制借鉴 Pipelex `dry_run_pipeline` → GraphSpec）。

NF 此前只能回答「管线**声明**自洽吗」（静态 check），回答不了「这条管线**跑得通**吗」。
本模块补这一层：**不调模型、不动状态、不写盘**，只用声明跑一遍。

判决分层（关键：把「真错」与「NF 执行模型决定的待裁决项」分开，避免噪声门禁）：

- **hard**（真缺陷）：模块在仓库找不到；依赖落在**严格更后的层**。
- **advisory**（不判死，据实标注）：同层内依赖序（NF 的 I5 明确「最终执行顺序以注册表
  合并为准，禁止硬编码」）；事件订阅方在本执行集内无发布方（可能由 references 跨包
  闭包或外部域包提供）。

执行集 = 官方核心基座（registry.json `modules[]`，随每次装配恒执行）∪ 管线各层模块。
纪律：纯标准库；只读；不执行任何生成。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from core import json_doc

from core.models import fid_key
from core.pipeline_loader import load_pipeline_file

_MODULE_GLOBS = ("04_模块库/*/*.md", "community/*/modules/*.md")


def _module_files(root: str = ".") -> Dict[str, Dict[str, Any]]:
    """仓库模块索引：文件名即 id（全限定由类别限定补），机读契约在场则挂上。"""
    from core import conformance_scan as csc

    out: Dict[str, Dict[str, Any]] = {}
    r = Path(root)
    seen = set()
    for pat in _MODULE_GLOBS:
        for p in sorted(r.glob(pat)):
            rel = p.relative_to(r).as_posix()
            if rel in seen or p.name == "README.md":
                continue
            seen.add(rel)
            stem = p.stem.split("_", 1)[0]
            cat = p.parent.name.replace("类", "")
            rec = _module_record(p, rel, stem, cat, csc)
            for key in (stem, rec["cat_id"], fid_key(rec["cat_id"])):
                out.setdefault(key, rec)
    return out


def _module_record(p: Path, rel: str, stem: str, cat: str,
                   csc) -> Dict[str, Any]:
    """单个模块文件的索引记录（机读契约在场时挂摘要）。"""
    rec: Dict[str, Any] = {"id": stem, "cat_id": "%s:%s" % (cat, stem),
                           "path": rel, "has_contract": False,
                           "inputs": [], "outputs": [],
                           "publish": [], "subscribe": []}
    try:
        text = p.read_text(encoding="utf-8")
        parsed = csc._fence_yaml(text, "machine_contract")
        mc = parsed.get("machine_contract") if isinstance(parsed, dict) else None
        if isinstance(mc, dict):
            _apply_contract(rec, mc, text)
    except OSError:  # 件不可读 ⇒ 该模块无契约摘要（跳过，不伪造）
        pass
    return rec


def _apply_contract(rec: Dict[str, Any], mc: Dict[str, Any], text: str) -> None:
    """把机读契约摘要挂到索引记录上。"""
    rec["has_contract"] = True
    rec["inputs"] = _str_list(mc.get("inputs"))
    rec["outputs"] = _str_list(mc.get("outputs"))
    ev = mc.get("events") or {}
    rec["publish"] = _str_list(ev.get("publish"))
    rec["subscribe"] = _str_list(ev.get("subscribe"))
    if mc.get("id"):
        rec["cat_id"] = str(mc["id"])
    from core import io_types as _iot
    rec["io_types"] = _iot.parse_io_types(text) or {}


def _str_list(value) -> List[str]:
    """契约里的字符串列表字段（缺省空列表）。"""
    return [str(x) for x in (value or [])]


def _core_ids(root: str = ".") -> List[str]:
    """官方核心基座 id（registry.json modules[]）。"""
    path = Path(root) / "desktop" / "src" / "core" / "registry.json"
    try:
        reg = json_doc.load(path, dict, what=str(path))
    except (OSError, ValueError):  # 扫描失败 ⇒ 空集（下游按「无核心件」处理）
        return []
    return [str(m.get("id")) for m in (reg.get("modules") or []) if m.get("id")]


def _resolve(ref: str, index: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return index.get(ref) or index.get(fid_key(ref)) or index.get(ref.split(":")[-1])


def graph(pipeline_path: str, root: str = ".",
          overrides: Optional[Dict[str, List[str]]] = None,
          index: Optional[Dict[str, Dict[str, Any]]] = None,
          core: Optional[List[str]] = None) -> Dict[str, Any]:
    """跑一遍管线声明 → 执行图 JSON（hard/issues 与 advisory/notes 分列）。

    index / core 可由调用方注入：全仓 sweep 下二者对每条管线都是同一份，逐条重建即
    重复读盘（见 sweep）。缺省仍各自现算，单条调用与既有测试行为不变。
    """
    abs_path = (pipeline_path if os.path.isabs(pipeline_path)
                else os.path.join(root, pipeline_path))
    pl = load_pipeline_file(abs_path)
    if pl is None:
        raise ValueError("管线解析失败：%s（修复指引：检查 frontmatter 与代码围栏闭合）"
                         % pipeline_path)
    if index is None:
        index = _module_files(root)
    if core is None:
        core = _core_ids(root)
    st: Dict[str, Any] = {"issues": [], "notes": [], "steps": [], "edges": [],
                          "tokens": [], "published": {}, "subscribed": {},
                          "layer_of": {}, "executed": [], "done": _done_set(core)}
    # 基座先跑：官方核心的产出/事件进入池
    _base_pool(core, index, st)
    for idx, layer in enumerate(pl.layers, 1):
        refs = list((overrides or {}).get(layer.id) or layer.default_modules or [])
        st["steps"].append(_run_layer(idx, layer, refs, index, st))
    _event_notes(st)
    # 类型面（io_types）：仅在本执行集内判**可证**事项（未收窄不判死）
    type_issues_before = len(st["issues"])
    kind_of_token = _collect_kinds(st["executed"], index, st["issues"])
    _check_input_types(st["executed"], index, st["issues"])
    stats = _graph_stats(st, pl, core, kind_of_token, type_issues_before)
    return {"schema": "nf-graphspec/1",
            "pipeline": {"id": pl.id, "name": pl.name,
                         "structure_type": pl.structure_type,
                         "path": str(pipeline_path).replace("\\\\", "/")},
            "steps": st["steps"], "edges": st["edges"], "tokens": st["tokens"],
            "events": {"published": sorted(st["published"])},
            "issues": st["issues"], "notes": st["notes"], "stats": stats}


def _done_set(core: List[str]) -> set:
    return set(core) | {fid_key(x) for x in core} | {x.split(":")[-1] for x in core}


def _base_pool(core: List[str], index: Dict[str, Dict[str, Any]],
               st: Dict[str, Any]) -> None:
    """基座先跑：官方核心的产出/事件进入池。"""
    for ref in core:
        rec = _resolve(ref, index)
        if rec:
            _record_events(rec["cat_id"], rec, st)


def _run_layer(idx: int, layer, refs: List[str],
               index: Dict[str, Dict[str, Any]], st: Dict[str, Any]) -> Dict[str, Any]:
    """跑一层声明 → step 记录。"""
    # 本层成员集合（先算出来：同层依赖是「顺序由注册表裁决」，不判死）
    lctx: Dict[str, Any] = {
        "idx": idx, "layer": layer,
        "same_layer": {str(r) for r in refs},
        "step": {"index": idx, "layer": layer.id, "layer_name": layer.name,
                 "optional": bool(layer.optional), "modules": [], "missing": []}}
    for ref in refs:
        _run_layer_ref(ref, lctx, index, st)
    return lctx["step"]


def _run_layer_ref(ref: str, lctx: Dict[str, Any],
                   index: Dict[str, Dict[str, Any]], st: Dict[str, Any]) -> None:
    """处理一层里的单个模块引用。"""
    step = lctx["step"]
    rec = _resolve(str(ref), index)
    if rec is None:
        step["missing"].append(str(ref))
        st["issues"].append("模块未在仓库找到：%s（层 %s）"
                            "（修复指引：核对 04_模块库/community/*/modules 的文件名与类别限定）"
                            % (ref, lctx["layer"].id))
        return
    mid = rec["cat_id"]
    st["executed"].append(mid)
    step["modules"].append({"id": mid, "path": rec["path"],
                            "has_contract": rec["has_contract"]})
    st["layer_of"][mid] = lctx["idx"]
    for dep in rec["inputs"]:
        _dep_edge(dep, mid, lctx, index, st)
    _mark_done(mid, rec, st)
    _record_events(mid, rec, st)


def _dep_edge(dep: str, mid: str, lctx: Dict[str, Any],
              index: Dict[str, Dict[str, Any]], st: Dict[str, Any]) -> None:
    """判一条依赖：已执行 / 同层 / 违约 / 跨包外部。"""
    done = st["done"]
    rec_dep = _resolve(dep, index)
    dep_id = rec_dep["cat_id"] if rec_dep else dep
    bare = dep_id.split(":")[-1]
    if _contains(done, dep_id, dep, bare):
        st["edges"].append({"from": dep_id, "to": mid, "kind": "input"})
        return
    if _contains(lctx["same_layer"], dep, dep_id, bare):
        st["notes"].append({"category": "同层依赖序",
                            "detail": "%s ← %s（以注册表合并顺序为准）" % (mid, dep_id)})
        st["edges"].append({"from": dep_id, "to": mid, "kind": "input"})
        return
    dep_layer = st["layer_of"].get(dep_id, st["layer_of"].get(bare))
    if _orders_before(dep_layer, lctx["idx"]):
        st["issues"].append("依赖序违约：%s 依赖 %s，但 %s 未在其之前执行"
                            "（修复指引：前移提供方层位，或把该模块移出本层 default）"
                            % (mid, dep_id, dep_id))
        return
    # 既不在本执行集、也不在更后层：可能由 references 跨包闭包或外部域包提供
    st["notes"].append({"category": "跨包/外部依赖",
                        "detail": "%s ← %s（可能由 references 闭包或外部域包提供）"
                                  % (mid, dep_id)})


def _contains(coll, *values) -> bool:
    return any(v in coll for v in values)


def _orders_before(dep_layer, idx: int) -> bool:
    return dep_layer is not None and dep_layer > idx


def _mark_done(mid: str, rec: Dict[str, Any], st: Dict[str, Any]) -> None:
    """把模块的四种 id 形态记入已执行集。"""
    done = st["done"]
    done.add(mid)
    done.add(fid_key(mid))
    done.add(mid.split(":")[-1])
    done.add(rec["id"])


def _record_events(mid: str, rec: Dict[str, Any], st: Dict[str, Any]) -> None:
    """模块的产出 token 与发布/订阅事件进入池。"""
    for tok in rec["outputs"]:
        if tok not in st["tokens"]:
            st["tokens"].append(tok)
    for ev in rec["publish"]:
        st["published"].setdefault(ev, mid)
    for ev in rec["subscribe"]:
        st["subscribed"].setdefault(ev, []).append(mid)


def _event_notes(st: Dict[str, Any]) -> None:
    """订阅了但无人发布的事件 → advisory note。"""
    for ev, subs in sorted(st["subscribed"].items()):
        if ev not in st["published"]:
            st["notes"].append({"category": "跨包/外部事件",
                                "detail": "%s ← %s（可能由 references 跨包闭包或外部域包提供）"
                                          % ("、".join(sorted(set(subs))), ev)})


def _io_map(rec: Dict[str, Any], side: str) -> Dict[str, str]:
    """模块 io_types 的某一面（inputs/outputs）。"""
    return (rec.get("io_types") or {}).get(side) or {}


def _merge_kind(kind_of_token: Dict[str, str], tok: str, kind: str,
                issues: List[str]) -> None:
    """登记 token 的输出类型；冲突记 issue。"""
    if kind == "untyped":
        return
    prev = kind_of_token.get(tok)
    if prev and prev != kind:
        issues.append("类型冲突：token %s 同时被声明为 %s 与 %s"
                      "（修复指引：对齐各模块 io_types.outputs）"
                      % (tok, prev, kind))
    kind_of_token.setdefault(tok, kind)


def _collect_kinds(executed: List[str], index: Dict[str, Dict[str, Any]],
                   issues: List[str]) -> Dict[str, str]:
    """收集执行集内各 token 的输出类型。"""
    kind_of_token: Dict[str, str] = {}
    for mid in executed:
        rec = _resolve(mid, index)
        if not rec:
            continue
        for tok, kind in _io_map(rec, "outputs").items():
            _merge_kind(kind_of_token, tok, kind, issues)
    return kind_of_token


def _got_types(dep: str, index: Dict[str, Dict[str, Any]]) -> List[str]:
    """依赖方声明可提供的输出类型集合。"""
    dep_rec = _resolve(dep, index)
    if not dep_rec:
        return []
    return sorted({v for v in _io_map(dep_rec, "outputs").values() if v != "untyped"})


def _check_input_types(executed: List[str], index: Dict[str, Dict[str, Any]],
                       issues: List[str]) -> None:
    """输入类型面：期望类型是否被依赖方声明。"""
    for mid in executed:
        rec = _resolve(mid, index)
        if not rec:
            continue
        for dep, want in _io_map(rec, "inputs").items():
            if want in ("untyped", "state"):
                continue
            got = _got_types(dep, index)
            if got and want not in got:
                issues.append("类型不匹配：%s 期望 %s 提供 %s，而 %s 声明输出类型 %s"
                              "（修复指引：对齐 io_types 或调整依赖）"
                              % (mid, dep, want, dep, got))


def _graph_stats(st: Dict[str, Any], pl, core: List[str],
                 kind_of_token: Dict[str, str], type_issues_before: int) -> Dict[str, Any]:
    """执行图统计段。"""
    steps = st["steps"]
    issues = st["issues"]
    return {"layers": len(pl.layers),
            "modules": sum(len(s["modules"]) for s in steps),
            "missing": sum(len(s["missing"]) for s in steps), "core_base": len(core),
            "tokens": len(st["tokens"]), "events_published": len(st["published"]),
            "typed_tokens": len(kind_of_token),
            "issues": len(issues), "type_issues": len(issues) - type_issues_before,
            "notes": len(st["notes"])}


def discover(root: str = ".") -> List[str]:
    """仓库内全部管线文件（03_管线库 + community/*/pipelines）。"""
    hits: List[str] = []
    for pat in ("03_管线库/*.md", "community/*/pipelines/*.md"):
        hits += [Path(p).as_posix() for p in sorted(Path(root).glob(pat))]
    return hits


def sweep(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """全仓管线扫一遍 → (hard issues, stats)（供门禁聚合）。

    效率（实测）：228 条管线若各自建索引，就是 228 × 248 份模块文档的 glob + 读 + YAML
    解析（约 5.6 万次读盘），`nf conformance` 里这一项独占 **40 s**。模块索引在一次 sweep
    内**只建一次**、逐条复用。刻意**不做进程级常驻**：同进程里「先写模块再扫描」会读到
    陈旧索引，故共享范围只在本函数这一次调用内。
    """
    issues: List[str] = []
    total: Dict[str, Any] = {"pipelines": 0, "notes": 0, "modules": 0, "core_base": 0}
    buckets: Dict[str, int] = {}
    items: List[Dict[str, str]] = []
    index = _module_files(root)
    core = _core_ids(root)
    for p in discover(root):
        g = graph(p, root, index=index, core=core)
        total["pipelines"] += 1
        total["notes"] += g["stats"]["notes"]
        total["modules"] += g["stats"]["modules"]
        total["core_base"] = max(total["core_base"], g["stats"]["core_base"])
        issues += ["%s：%s" % (g["pipeline"]["id"], i) for i in g["issues"]]
        for n in g["notes"]:
            cat = n.get("category", "未分类") if isinstance(n, dict) else "未分类"
            buckets[cat] = buckets.get(cat, 0) + 1
            items.append({"pipeline": g["pipeline"]["id"], "category": cat,
                          "detail": n.get("detail", "") if isinstance(n, dict) else str(n)})
    total["advisory_buckets"] = buckets
    total["advisory_items"] = items
    return issues, total


def advisory_report(root: str = ".", write: bool = False) -> Dict[str, Any]:
    """advisory 分类台账：把「不判死的提示」按类别计数落盘（可归档、可追踪收敛）。"""
    issues, total = sweep(root)
    doc = {"schema": "nf-pipeline-advisory/1",
           "note": ("管线抽象执行的 advisory（同层顺序 / 跨包依赖 / 跨包事件）——"
                    "不判死，但需分类可见；类别计数下降即缺口收敛。"),
           "pipelines": total["pipelines"], "counts": total["advisory_buckets"],
           "total": total["notes"], "items": total["advisory_items"]}
    if write:
        from core import atomic_write          # 在仓协议件：原子落盘（2026-10-01）
        p = Path(root) / "protocol" / "pipeline_advisory.json"
        atomic_write.write_text(p, json.dumps(doc, ensure_ascii=False, indent=2,
                                              sort_keys=True) + "\n")
    return doc


def verify_advisory(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """台账与实时重算一致（类别计数不得悄悄变）。"""
    live = advisory_report(root)
    issues: List[str] = []
    p = Path(root) / "protocol" / "pipeline_advisory.json"
    if not p.is_file():
        issues.append("缺 advisory 台账 protocol/pipeline_advisory.json"
                      "（修复指引：nf pipeline dryrun --all --write-advisory）")
        return issues, {"total": live["total"]}
    try:
        committed = json_doc.load(p, dict, what=p.name)
        if committed.get("counts") != live["counts"]:
            issues.append("advisory 台账过期：记录 %s ≠ 实测 %s"
                          "（修复指引：重建台账）"
                          % (committed.get("counts"), live["counts"]))
    except ValueError:
        issues.append("advisory 台账 JSON 不可解析")
    return issues, {"total": live["total"], "counts": live["counts"]}
