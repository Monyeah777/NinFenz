"""domain_pack · _catalog（自 domain_pack.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from ._const import (
    _STD_BY_CODE,
    _STD_KEYWORD,
    _STD_SECTION_DEFAULT,
    _STD_SUPPORT_KEYWORD,
    _STD_SUPPORT_SECTION,
    AUTHENTICITY_THRESHOLD,
    SUB_COUNT,
)


def _std_reachable(catalog: Dict[str, Dict[str, Any]], sid: str) -> bool:
    """该标准是否有**本机实测可达**证据（false 一律如实计入不可达）。"""
    return bool(((catalog.get(sid) or {}).get("evidence") or {}).get("reachable"))




def _std_probe_date(catalog: Dict[str, Dict[str, Any]], sid: str) -> str:
    return str(((catalog.get(sid) or {}).get("evidence") or {}).get("probe_date") or "")




def _std_layer(catalog: Dict[str, Dict[str, Any]], sid: str) -> str:
    return str((catalog.get(sid) or {}).get("layer") or "")




def _reachable_first(ids: List[str], catalog: Dict[str, Dict[str, Any]]) -> List[str]:
    """可达优先排序（真实证据优先，不改变候选集合）。"""
    return sorted(ids, key=lambda x: (not _std_reachable(catalog, x), ids.index(x)))




def _keyword_standard_binding(
        name: str, catalog: Dict[str, Dict[str, Any]]
) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    """关键词命中：返回 (可达命中, 不可达兜底)；无命中时首项为 ("", "")。"""
    fallback: Tuple[str, str] = ("", "")
    for pat, sid in _STD_KEYWORD:
        if re.search(pat, name) and sid in catalog:
            why = "关键词「%s」命中" % pat
            if _std_reachable(catalog, sid):
                return (sid, why), fallback
            if not fallback[0]:
                fallback = (sid, why + "（本机实测不可达，如实记录）")
    return ("", ""), fallback


def bind_standard(spec: Dict[str, Any], sub: Dict[str, Any],
                  catalog: Dict[str, Dict[str, Any]],
                  index: int = 0) -> Tuple[str, str]:
    """给一条细分选标准：关键词命中 → 域码默认 → 段默认（都取目录内第一条命中）。

    返回 (standard_id, rationale)。不猜：目录里没有的 id 一律跳过。
    段默认候选按 `index` 轮换——保证单包**至少贴 3 条不同标准**（check32 门槛），
    同时让同一域内的细分不至于全挤在一条标准上。
    可达优先：同一命中位若有**本机实测可达**的候选，先取可达者（数据真实性口径）。
    """
    name = str(sub.get("name") or "")
    hit, fallback = _keyword_standard_binding(name, catalog)
    if hit[0]:
        return hit
    code_pool = [x for x in _STD_BY_CODE.get(spec["code"], []) if x in catalog]
    if code_pool:
        pool = _reachable_first(code_pool, catalog)
        return pool[index % len(pool)], "域码 %s 专属绑定（轮换 %d）" % (spec["code"],
                                                                       index % len(pool))
    sec = str(spec.get("section", "")).split(" · ")[0]
    pool = _reachable_first([x for x in _STD_SECTION_DEFAULT.get(sec, []) if x in catalog], catalog)
    if pool:
        return pool[index % len(pool)], "%s 段默认绑定（轮换 %d）" % (sec, index % len(pool))
    return fallback




def _support_keyword_hit(name: str, catalog: Dict[str, Dict[str, Any]],
                         primary: str) -> Tuple[str, str]:
    """产出形态关键词命中（要求「在目录内 + ≠ 主锚」）；无命中返回 ("", "")。"""
    for pat, sid in _STD_SUPPORT_KEYWORD:
        if sid in catalog and sid != primary and re.search(pat, name):
            return sid, "载体锚：产出形态「%s」的承载标准" % pat.split("|")[0]
    return "", ""


def _support_pool(sec: str, catalog: Dict[str, Dict[str, Any]],
                  primary: str) -> List[str]:
    """段载体池：在目录内且 ≠ 主锚的标准 id（保持目录顺序）。"""
    return [x for x in _STD_SUPPORT_SECTION.get(sec, [])
            if x in catalog and x != primary]


def bind_support(spec: Dict[str, Any], sub: Dict[str, Any],
                 catalog: Dict[str, Dict[str, Any]],
                 index: int, primary: str) -> Tuple[str, str]:
    """给一条细分选**载体锚**（辅锚）：产出形态的承载/交换标准，与主锚异层优先。

    规则：关键词（产出形态）→ 段载体池轮换；候选一律要求「在目录内 + ≠ 主锚」，
    可达优先，并优先取与本条主锚**不同层**的标准（口径锚与承载锚分属不同层才有信息量）。
    """
    name = str(sub.get("name") or "")
    hit = _support_keyword_hit(name, catalog, primary)
    if hit[0]:
        return hit
    sec = str(spec.get("section", "")).split(" · ")[0]
    pool = _support_pool(sec, catalog, primary)
    if not pool:
        return "", ""
    pool = _reachable_first(pool, catalog)
    pl = _std_layer(catalog, primary)
    for k in range(len(pool)):
        sid = pool[(index + k) % len(pool)]
        if _std_layer(catalog, sid) != pl:
            return sid, "%s 段载体锚（轮换 %d；与主锚异层）" % (
                sec, (index + k) % len(pool))
    return pool[index % len(pool)], "%s 段载体锚（轮换 %d）" % (sec, index % len(pool))




def bindings_full(spec: Dict[str, Any],
                  catalog: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Tuple[str, str]]]:
    """整包**双锚**绑定：主锚（域口径）+ 辅锚（产出承载）。单一入口，判据与文档同源。"""
    prim = bindings_for(spec, catalog)
    out: Dict[str, Dict[str, Tuple[str, str]]] = {}
    for i, s in enumerate(spec["subdivisions"]):
        p_sid, p_why = prim[s["id"]]
        s_sid, s_why = bind_support(spec, s, catalog, i, p_sid)
        out[s["id"]] = {"primary": (p_sid, p_why), "support": (s_sid, s_why)}
    return out




def concept_index(spec: Dict[str, Any], catalog: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """概念图索引（单源）：概念节点 + 主/辅锚标准节点 + **标准依赖边**（depends_on）。

    边三类：① 细分前置边（spec.edges）；② 概念 → 主锚；③ 概念 → 辅锚；④ 标准依赖边
    （被依赖 → 依赖；依赖目标亦入图，保证「有边必有端点」）。
    """
    bd = bindings_full(spec, catalog)
    prim = {k: v["primary"][0] for k, v in bd.items()}
    supp = {k: v["support"][0] for k, v in bd.items()}
    stds = set(filter(None, list(prim.values()) + list(supp.values())))
    dep_edges: List[Tuple[str, str]] = []
    for sid in sorted(stds):
        for dep in (catalog.get(sid) or {}).get("depends_on") or []:
            if dep in catalog:
                dep_edges.append((dep, sid))
                stds.add(dep)
    nodes = len(spec["subdivisions"]) + len(stds)
    edges = (len(spec["edges"]) + len(list(filter(None, prim.values())))
             + len(list(filter(None, supp.values()))) + len(dep_edges))
    return {"primary": prim, "support": supp, "std_ids": sorted(stds),
            "dep_edges": sorted(dep_edges), "nodes": nodes, "edges": edges,
            "density": round(edges / max(1, nodes), 4), "bindings": bd}




def _std_cell(catalog: Dict[str, Dict[str, Any]], sid: str) -> str:
    """标准单元格（人读面）：id + 标题 + 层 + 实测状态。"""
    if not sid:
        return "—"
    std = catalog.get(sid) or {}
    ev = std.get("evidence") or {}
    mark = "✓" if ev.get("reachable") else "✗"
    return "`%s` %s（%s｜%s）" % (sid, std.get("title", ""), std.get("layer", ""), mark)




def _bound_refs(bd: Dict[str, Dict[str, Tuple[str, str]]]) -> List[str]:
    """双锚引用清单（主锚/辅锚，非空者按条目顺序）。"""
    refs: List[str] = []
    for v in bd.values():
        for role in ("primary", "support"):
            if v[role][0]:
                refs.append(v[role][0])
    return refs


def _probe_evidence_ok(catalog: Dict[str, Dict[str, Any]], sid: str) -> bool:
    """实测记录齐备：探针日期 + 取样指纹都在。"""
    return bool(_std_probe_date(catalog, sid)
                and str(((catalog[sid].get("evidence") or {}).get("sha256_sample") or "")))


def authenticity(spec: Dict[str, Any], catalog: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """数据真实性（单源口径，落 DOMAIN_SPEC.json 与名录，check32 硬判）。

    三要素（每包逐条复算，不抽样）：
    1. `in_catalog_ratio`：绑定标准在 `protocol/standards_catalog.json` 在册率（须 1.0）；
    2. `reachable_ratio`：绑定标准**本机实测可达**率（bot 防护/付费墙如实计入不可达）；
    3. `probe_evidence_ratio`：绑定标准的实测记录（探针日期 + 取样指纹）齐备率（须 1.0）。
    复合分 `score` = 在册 × (0.5 + 0.5 × 可达) × 证据齐备（乘法口径：任一环缺即降分，
    不用加权和掩盖缺口），门槛见 AUTHENTICITY_THRESHOLD。
    """
    bd = bindings_full(spec, catalog)
    refs = _bound_refs(bd)
    total = len(refs)
    in_cat = [r for r in refs if r in catalog]
    reach = [r for r in in_cat if _std_reachable(catalog, r)]
    ev_ok = [r for r in in_cat if _probe_evidence_ok(catalog, r)]
    anchors = [s.get("anchor_status") for s in spec["subdivisions"]]
    probed = list(filter(None, anchors))
    r_in = round(len(in_cat) / max(1, total), 4)
    r_reach = round(len(reach) / max(1, total), 4)
    r_ev = round(len(ev_ok) / max(1, total), 4)
    r_anchor = round(len(probed) / max(1, len(anchors)), 4)
    score = round(r_in * (0.5 + 0.5 * r_reach) * r_ev, 4)
    return {"standard_bindings": total, "in_catalog_ratio": r_in,
            "reachable_ratio": r_reach, "probe_evidence_ratio": r_ev,
            "anchor_probed_ratio": r_anchor, "score": score,
            "threshold": AUTHENTICITY_THRESHOLD,
            "bound_standards": sorted(set(refs)),
            "reachable_standards": sorted(set(reach))}




def _distinct_primaries(out: Dict[str, Tuple[str, str]]) -> int:
    return len({v[0] for v in out.values() if v[0]})


def _diversity_pool(spec: Dict[str, Any], sec: str,
                    catalog: Dict[str, Dict[str, Any]]) -> List[str]:
    """多样性补位候选池：域码专属 + 段默认，去重保序。"""
    pool = [x for x in (_STD_BY_CODE.get(spec["code"], []) +
                        _STD_SECTION_DEFAULT.get(sec, [])) if x in catalog]
    return list(dict.fromkeys(pool))


def bindings_for(spec: Dict[str, Any],
                 catalog: Dict[str, Dict[str, Any]]) -> Dict[str, Tuple[str, str]]:
    """整包绑定（**单一入口**）：关键词 → 专属/段默认轮换，并保证**至少 3 条不同标准**。

    多样性后处理：若关键词命中把整包挤到 1–2 条标准上，按顺序把部分细分改绑段默认池里的
    其它标准，直到不同标准数 ≥3（check32 门槛）；改写理由如实写「多样性补位」。
    """
    out: Dict[str, Tuple[str, str]] = {}
    for i, s in enumerate(spec["subdivisions"]):
        out[s["id"]] = bind_standard(spec, s, catalog, i)
    sec = str(spec.get("section", "")).split(" · ")[0]
    pool = _diversity_pool(spec, sec, catalog)
    if _distinct_primaries(out) >= 3 or not pool:
        return out
    k = 0
    for sid in list(out):
        if _distinct_primaries(out) >= 3:
            break
        cand = pool[k % len(pool)]
        k += 1
        if cand != out[sid][0]:
            out[sid] = (cand, "多样性补位（段默认池轮换）")
    return out




def _meta_field_issues(spec: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    for k in ("code", "section", "name", "pack_name", "category", "metric_family",
              "module_titles", "subdivisions"):
        if not spec.get(k):
            issues.append("缺字段 %s" % k)
    return issues


def _code_issues(spec: Dict[str, Any]) -> List[str]:
    code = str(spec.get("code") or "")
    if not re.fullmatch(r"[A-F]\d{2}", code):
        return ["code 形态应为 <A-F><两位数>，实为 %r" % code]
    return []


def _pack_name_issues(spec: Dict[str, Any]) -> List[str]:
    # `pack_name` 直接拼进 `community/<pack_name>/…` 的**全部写盘路径**——形状必须先定死
    # （实测形态：写成 `../x` 即写到仓库外；与 `pack_combo` 的组合包名同一条判据）。
    pack = str(spec.get("pack_name") or "")
    if pack and not re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9_-]{2,40}", pack):
        return ["pack_name 写法定形失败：%r（须 2–40 位中英文/数字/-/_，不含路径分隔符）"
                % pack]
    return []


def _missing_subdivision_fields(s: Dict[str, Any], sub_id: Any) -> List[str]:
    issues: List[str] = []
    for k in ("name", "definition", "anchor", "check", "pitfall"):
        if not str(s.get(k) or "").strip():
            issues.append("%s 缺 %s" % (sub_id, k))
    return issues


def _subdivision_issues(spec: Dict[str, Any], subs: List[Dict[str, Any]],
                        code: str) -> List[str]:
    issues: List[str] = []
    seen = set()
    for i, s in enumerate(subs, 1):
        want = "%s-%02d" % (code, i)
        if s.get("id") != want:
            issues.append("第 %d 条 id 应为 %s，实为 %r" % (i, want, s.get("id")))
        if s.get("id") in seen:
            issues.append("细分 id 重复：%s" % s.get("id"))
        seen.add(s.get("id"))
        issues.extend(_missing_subdivision_fields(s, s.get("id")))
        if not str(s.get("anchor") or "").startswith(("http://", "https://")):
            issues.append("%s anchor 须为绝对 URL" % s.get("id"))
        if len(str(s.get("check") or "")) < 10:
            issues.append("%s 可机验判据过短（<10 字）" % s.get("id"))
    return issues


def _edge_issues(spec: Dict[str, Any], subs: List[Dict[str, Any]]) -> List[str]:
    issues: List[str] = []
    edges = spec.get("edges") or []
    ids = {s.get("id") for s in subs}
    node_ids = {str(x) for x in (spec.get("node_ids") or ids)}
    for e in edges:
        if len(e) != 2 or str(e[0]) not in node_ids or str(e[1]) not in node_ids:
            issues.append("边 %r 端点不在节点表" % (e,))
    if not edges:
        issues.append("须至少声明一条前置边（概念图非空偏序）")
    return issues


def spec_issues(spec: Dict[str, Any]) -> List[str]:
    """域规格结构自检（内容质量由作者负责，结构由这里判）。"""
    issues: List[str] = []
    issues.extend(_meta_field_issues(spec))
    issues.extend(_code_issues(spec))
    issues.extend(_pack_name_issues(spec))
    code = str(spec.get("code") or "")
    subs = spec.get("subdivisions") or []
    if len(subs) != SUB_COUNT:
        issues.append("细分条目须 %d 条，实为 %d" % (SUB_COUNT, len(subs)))
    issues.extend(_subdivision_issues(spec, subs, code))
    if len(spec.get("module_titles") or []) != 2:
        issues.append("module_titles 须 2 条（P40 口径层 / P60 收口层）")
    issues.extend(_edge_issues(spec, subs))
    return issues
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
