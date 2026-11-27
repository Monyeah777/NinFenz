"""双向锚定对齐面：反向量化「项目对已收集标准的内化度」，正向按词汇找标准交叉候选。

内部差距（2026-10-09 实测）：protocol/standards_catalog.json 收集 370 条可扩展标准，但
protocol/standards_binding.json 的 100 包 × 1200 条绑定只实际引用 68 条 —— 302 条（81.6%）
从未被任何域包绑定。现有判据（check32 domain_packs）只判「每条细分都有 standard_ref」这一侧，
不判「收集来的标准被用得怎么样」。本模块把两侧打通：

- stats(root)：反向量化内化度（目录利用率 / 各 layer 已绑定与未绑定数 / 包与绑定总数）；
- unbound(root, layer)：未绑定标准清单（可按 layer 过滤）；
- intersect(root, term)：正向按词汇在（未）绑定标准里找交叉候选（id/title/body 词面命中，确定性）。

纪律：纯标准库；只读；无网络；同输入同输出；缺件/坏件返回零值，不裸崩。
"""
from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import Any, Dict, List

CATALOG_REL = "protocol/standards_catalog.json"
BINDING_REL = "protocol/standards_binding.json"
_TOKEN = re.compile(r"[a-z0-9_]+")
#: 标准目录的五个层（口径同 protocol/standards_catalog.json 的 coverage.by_layer）
LAYERS = ("data", "eng", "form", "gov", "iface")
_HAN = re.compile("[一-龥]+")


def _read(root: str, rel: str) -> Dict[str, Any]:
    p = Path(root) / rel
    if not p.is_file():
        return {}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:  # 坏件按缺件处理：不打断报告，消费方据 stats 全 0 自证
        return {}
    return doc if isinstance(doc, dict) else {}


def catalog(root: str = ".") -> List[Dict[str, Any]]:
    """标准目录条目（缺件/坏件返回空表）。"""
    return [s for s in (_read(root, CATALOG_REL).get("standards") or []) if isinstance(s, dict)]


def bound_ids(root: str = ".") -> set:
    """被任一域包绑定引用过的标准 id 集合（standard / standard_ref 两种键名都认）。"""
    out: set = set()
    for p in (_read(root, BINDING_REL).get("packs") or []):
        if not isinstance(p, dict):
            continue
        for b in (p.get("bindings") or []):
            sid = (b.get("standard") or b.get("standard_ref")) if isinstance(b, dict) else b
            if sid:
                out.add(str(sid))
    return out


def _by_layer(rows: List[Dict[str, Any]], bound: set) -> Dict[str, Dict[str, int]]:
    by_layer: Dict[str, Dict[str, int]] = {}
    for s in rows:
        cell = by_layer.setdefault(str(s.get("layer") or "(未声明)"),
                                   {"total": 0, "bound": 0, "unbound": 0})
        cell["total"] += 1
        if str(s.get("id")) in bound:
            cell["bound"] += 1
        else:
            cell["unbound"] += 1
    return by_layer


def _valid_packs(root: str) -> List[Dict[str, Any]]:
    return [p for p in (_read(root, BINDING_REL).get("packs") or []) if isinstance(p, dict)]


def _bindings_total(packs: List[Dict[str, Any]]) -> int:
    return sum(len(p.get("bindings") or []) for p in packs)


def _layer_map(by_layer: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
    return {k: by_layer[k] for k in sorted(by_layer)}


def stats(root: str = ".") -> Dict[str, Any]:
    """反向：目录利用率总览（确定性）。"""
    rows = catalog(root)
    ids = [str(s.get("id")) for s in rows if s.get("id")]
    bound = bound_ids(root) & set(ids)
    by_layer = _by_layer(rows, bound)
    packs = _valid_packs(root)
    total = len(ids)
    return {
        "standards": total,
        "bound": len(bound),
        "unbound": total - len(bound),
        "utilization": round(len(bound) / total, 4) if total else 0.0,
        "packs": len(packs),
        "bindings": _bindings_total(packs),
        "by_layer": _layer_map(by_layer),
    }


def unbound(root: str = ".", layer: str = "") -> List[Dict[str, Any]]:
    """未绑定标准清单（可按 layer 过滤；按 id 排序）。"""
    b = bound_ids(root)
    want = str(layer).strip()
    rows = [s for s in catalog(root)
            if str(s.get("id")) not in b and (not want or str(s.get("layer")) == want)]
    return sorted(rows, key=lambda s: str(s.get("id")))


@functools.lru_cache(maxsize=1024)
def _terms_cached(text: str) -> tuple:
    """词元：英文 [a-z0-9_] 词 + 中文整段与 2-gram（中英混排口径，同 core.library 检索精神）。"""
    s = text.lower()
    out = _TOKEN.findall(s)
    for h in _HAN.findall(s):
        out.append(h)
        if len(h) > 1:
            out.extend(h[i:i + 2] for i in range(len(h) - 1))
    return tuple(out)


def _terms(text: Any) -> List[str]:
    return list(_terms_cached(str(text or "")))


def _intersect_row(s: Dict[str, Any], sid: str, want: set,
                    b: set) -> Dict[str, Any] | None:
    hay = set(_terms_cached(sid) + _terms_cached(str(s.get("title") or ""))
              + _terms_cached(str(s.get("body") or "")))
    hit = sum(1 for t in want if t in hay)
    if not hit:
        return None
    return {"id": sid, "layer": str(s.get("layer") or ""),
            "body": str(s.get("body") or ""),
            "title": str(s.get("title") or ""), "hits": hit,
            "bound": sid in b}


def _intersect_candidates(root: str, want: set, b: set, look: str,
                          include_bound: bool) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for s in catalog(root):
        sid = str(s.get("id"))
        if not include_bound and sid in b:
            continue
        if look and str(s.get("layer")) != look:
            continue
        row = _intersect_row(s, sid, want, b)
        if row is not None:
            rows.append(row)
    return rows


def intersect(root: str = ".", term: str = "", layer: str = "",
              limit: int = 0, include_bound: bool = False) -> List[Dict[str, Any]]:
    """正向：按词汇在标准里找交叉候选（命中数降序，同分按 id 升序）。

    词面 = term 的 [a-z0-9_] 词元与「id + title + body」词元的交集大小；0 命中不进表。
    """
    want = {t for t in _terms(term) if len(t) > 1}
    if not want:
        return []
    b = bound_ids(root)
    look = str(layer).strip()
    rows = _intersect_candidates(root, want, b, look, include_bound)
    rows.sort(key=lambda r: (-int(r["hits"]), str(r["id"])))
    return rows[:limit] if limit and limit > 0 else rows


def _s(value: Any) -> str:
    return str(value or "")


def _pack_binds(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [b for b in (p.get("bindings") or []) if isinstance(b, dict)]


def _pack_layers(binds: List[Dict[str, Any]]) -> Dict[str, int]:
    layers: Dict[str, int] = {}
    for b in binds:
        lay = _s(b.get("standard_layer")) or "(未声明)"
        layers[lay] = layers.get(lay, 0) + 1
    return layers


def _pack_row(p: Dict[str, Any]) -> Dict[str, Any]:
    binds = _pack_binds(p)
    layers = _pack_layers(binds)
    return {
        "code": _s(p.get("code")),
        "package": _s(p.get("package")),
        "category": _s(p.get("category")),
        "subdivisions": int(p.get("subdivisions") or 0),
        "bindings": len(binds),
        "distinct_standards": len({str(b.get("standard")) for b in binds if b.get("standard")}),
        "layers": {k: layers[k] for k in sorted(layers)},
        "layer_breadth": len(layers),
        "missing_layers": [x for x in LAYERS if x not in layers],
    }


def pack_stats(root: str = ".") -> List[Dict[str, Any]]:
    """逐域包标准对齐概览（按层覆盖宽度升序）：绑定数 / 标准数 / 各层计数 / 层覆盖宽度。"""
    rows: List[Dict[str, Any]] = []
    for p in _valid_packs(root):
        rows.append(_pack_row(p))
    return sorted(rows, key=lambda r: (int(r["layer_breadth"]), int(r["distinct_standards"]),
                                       str(r["code"])))


def shallow_packs(root: str = ".", max_breadth: int = 2) -> List[Dict[str, Any]]:
    """层覆盖宽度 ≤ max_breadth 的域包（反向对齐的优先补强清单，按宽度升序）。"""
    limit = max(0, int(max_breadth))
    return [r for r in pack_stats(root) if int(r["layer_breadth"]) <= limit]


def depends(root: str = ".") -> Dict[str, List[str]]:
    """标准依赖图（id → depends_on 在册项，去重排序；悬空引用剔除）。"""
    ids = {str(s.get("id")) for s in catalog(root)}
    out: Dict[str, List[str]] = {}
    for s in catalog(root):
        sid = str(s.get("id"))
        out[sid] = sorted({str(d) for d in (s.get("depends_on") or []) if str(d) in ids})
    return out


def dependents(root: str = ".") -> Dict[str, List[str]]:
    """反向依赖图（id → 依赖它的 id 列表，按 id 排序）。"""
    rev: Dict[str, List[str]] = {}
    for sid, ds in depends(root).items():
        for d in ds:
            rev.setdefault(d, []).append(sid)
    return {k: sorted(v) for k, v in rev.items()}


def _seed_node(s: Dict[str, Any], term: str) -> tuple:
    sid = str(s["id"])
    return sid, {"id": sid, "layer": str(s.get("layer") or ""),
                 "title": str(s.get("title") or ""), "hits": int(s["hits"]),
                 "depth": 0, "via": str(term)}


def _expand_node(nb: str, s: Dict[str, Any], level: int, via: str) -> Dict[str, Any]:
    return {"id": nb, "layer": str(s.get("layer") or ""),
            "title": str(s.get("title") or ""), "hits": 0,
            "depth": level, "via": via}


def _expand_frontier(frontier: List[str], fwd: Dict[str, List[str]],
                     rev: Dict[str, List[str]], by_id: Dict[str, Dict[str, Any]],
                     nodes: Dict[str, Dict[str, Any]], level: int) -> List[str]:
    nxt: List[str] = []
    for sid in sorted(frontier):
        for nb in sorted(set(fwd.get(sid, []) + rev.get(sid, []))):
            if nb in nodes:
                continue
            s = by_id.get(nb) or {}
            nodes[nb] = _expand_node(nb, s, level, sid)
            nxt.append(nb)
    return nxt


def bootstrap(root: str = ".", term: str = "", depth: int = 1,
              limit: int = 0) -> List[Dict[str, Any]]:
    """正向自举：词汇命中标准（种子）→ 沿依赖与反向依赖各扩 depth 层。

    返回 [{id, layer, title, hits, depth, via}]，按（depth 升、hits 降、id 升）排序；
    hits 只在种子非零；via = 带入者（种子记 term，扩展节点记父标准 id）。depth=0 只回种子。
    """
    seeds = intersect(root, term, include_bound=True)
    if not seeds:
        return []
    by_id = {str(s.get("id")): s for s in catalog(root)}
    fwd, rev = depends(root), dependents(root)
    nodes: Dict[str, Dict[str, Any]] = {}
    frontier: List[str] = []
    for s in seeds:
        sid, node = _seed_node(s, term)
        nodes[sid] = node
        frontier.append(sid)
    for level in range(1, max(0, int(depth)) + 1):
        frontier = _expand_frontier(frontier, fwd, rev, by_id, nodes, level)
        if not frontier:
            break
    rows = sorted(nodes.values(), key=lambda r: (int(r["depth"]), -int(r["hits"]), str(r["id"])))
    return rows[:limit] if limit and limit > 0 else rows


def report(root: str = ".") -> str:
    """人读报告（反向利用率 + 各 layer 未绑定数）。"""
    st = stats(root)
    out = ["# 双向锚定对齐报告", "",
           "标准目录 %d 条 · 已绑定 %d · 未绑定 %d · 利用率 %.1f%% · 域包 %d · 绑定 %d"
           % (st["standards"], st["bound"], st["unbound"], st["utilization"] * 100.0,
              st["packs"], st["bindings"]), "",
           "| layer | 总 | 已绑定 | 未绑定 |", "|---|---|---|---|"]
    for lay, c in st["by_layer"].items():
        out.append("| %s | %d | %d | %d |" % (lay, c["total"], c["bound"], c["unbound"]))
    return "\n".join(out) + "\n"
