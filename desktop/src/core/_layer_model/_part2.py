"""core.layer_model 私有实现分片 2/3（对外只经 core.layer_model 门面导入）：_rule_l2 等"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from core import conformance_scan as csc
from core import json_doc

from ._part1 import (
    _CHECK_DEF,
    _JUDGE_ASSERTION,
    _JUDGE_CHECK,
    ASSERTIONS_REL,
    DOC_REL,
    MARK_BEGIN,
    MARK_END,
    VERIFY_REL,
    _arr,
    _derived_files,
    _entry_imports,
    _exists,
    _expand_many,
    _obj,
    _rule_l1,
)


def _rule_l2(root: str, tiers: list, tier_ids: List[str], derived: set, cache: dict,
             issues: List[str]) -> Dict[str, set]:
    """L2 归属互斥（派生物已扣除）→ 各阶真源面。"""
    faces = {tid: _expand_many(root, _obj(t.get("source")).get("globs"), cache) - derived
             for t, tid in zip(tiers, tier_ids, strict=True)}
    for i, a in enumerate(tier_ids):
        for b in tier_ids[i + 1:]:
            overlap = sorted(faces.get(a, set()) & faces.get(b, set()))
            if overlap:
                issues.append("L2 阶 %s 与阶 %s 真源面重叠：%s（修复指引：把件归给唯一一阶，"
                              "或把派生物登记进 derived）"
                              % (a, b, "、".join(overlap[:3])))
    return faces


def _rule_l3(root: str, tiers: list, faces: Dict[str, set], derived: set, cache: dict,
             issues: List[str]) -> None:
    """L3 接口面 ⊆ 真源面。"""
    for tier in tiers:
        tid = str(tier.get("id"))
        iface = _expand_many(root, _obj(tier.get("interface")).get("globs"), cache)
        if not iface:
            issues.append("L3 阶 %s 未声明接口面（修复指引：在 interface.globs 写明跨阶可依赖面）"
                          % tid)
        stray = sorted(iface - faces.get(tid, set()) - derived)
        if stray:
            issues.append("L3 阶 %s 接口面超出真源面：%s（修复指引：接口必须是真源面的子集）"
                          % (tid, "、".join(stray[:3])))


@dataclass(frozen=True)
class _WalkContext:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    graph: Dict[str, list]
    order: Dict[str, int]
    walked: set
    reported_cycles: set
    issues: List[str]


def _walk_cycle(tid: str, stack: list, opts: _WalkContext) -> None:
    """依赖图 DFS：成环即报（同一路径只报一次）。"""

    graph = opts.graph
    order = opts.order
    walked = opts.walked
    reported_cycles = opts.reported_cycles
    issues = opts.issues
    if tid in stack:
        path = " → ".join(list(stack) + [tid])
        if path not in reported_cycles:
            reported_cycles.add(path)
            issues.append("L4 依赖图存在环：%s（修复指引：断开上行依赖）" % path)
        return
    if tid in walked:
        return
    for dep in graph.get(tid, []):
        if dep in order:
            _walk_cycle(
                dep,
                stack + [tid],
                opts=_WalkContext(
                    graph=graph,
                    order=order,
                    walked=walked,
                    reported_cycles=reported_cycles,
                    issues=issues,
                ),
            )
    walked.add(tid)


def _rule_l4(root: str, tiers: list, tier_ids: List[str], issues: List[str]) -> None:
    """L4 依赖向下无环。"""
    order = {str(t.get("id")): int(t.get("order", 99)) for t in tiers}
    for tier in tiers:
        tid = str(tier.get("id"))
        for dep in _arr(tier.get("depends_on")):
            dep = str(dep)
            if dep not in order:
                issues.append("L4 阶 %s 依赖了不存在的阶：%s（修复指引：改成真实阶 id）"
                              % (tid, dep))
            elif order[dep] >= order[tid]:
                issues.append("L4 阶 %s 依赖方向不向下：%s（order %d ≥ 自身 %d；"
                              "修复指引：依赖只能指向更下位的阶）"
                              % (tid, dep, order[dep], order[tid]))
    graph = {str(t.get("id")): [str(d) for d in _arr(t.get("depends_on"))]
             for t in tiers}
    walked: set = set()
    reported_cycles: set = set()
    for tid in tier_ids:
        _walk_cycle(
            tid,
            [],
            opts=_WalkContext(
                graph=graph,
                order=order,
                walked=walked,
                reported_cycles=reported_cycles,
                issues=issues,
            ),
        )


def _rule_l5(doc: Dict[str, Any], tier_ids: List[str], issues: List[str]) -> None:
    """L5 入口面只登记角色。"""
    for sf in _arr(doc.get("surfaces")):
        if sf.get("is_source_of_truth") is not False:
            issues.append("L5 入口面 %s 的 is_source_of_truth 必须为 false"
                          "（修复指引：入口是角色，真源只能是四阶）" % sf.get("id"))
        for served in _arr(sf.get("serves")):
            if str(served) not in tier_ids:
                issues.append("L5 入口面 %s 的 serves 指向不存在的阶：%s"
                              "（修复指引：改成真实阶 id）" % (sf.get("id"), served))


def _rule_l6(root: str, cache: dict, issues: List[str]) -> None:
    """L6 引擎不反向 import 入口面。"""
    for rel in sorted(_expand_many(root, ["desktop/src/core/*.py"], cache)):
        try:
            src = csc.read_text_cached(Path(root) / rel)   # 与 purity 的 core/*.py 读同一份语料
        except OSError:
            continue
        # 事实按**正文**缓存（entry_imports）：文本预筛 + AST 只在「这一件没算过」时付。
        for lineno, name in _entry_imports(src):
            issues.append("L6 引擎阶反向 import 入口面件：%s:%d import %s"
                          "（修复指引：入口可替换，core 不得依赖它——改由 CLI 层注入）"
                          % (rel, lineno, name))


def _rule_l7(doc: Dict[str, Any], tiers: list, issues: List[str]) -> None:
    """L7 退役阶不被依赖。"""
    retired = {str(t.get("id")) for t in tiers if str(t.get("status")) == "retired"}
    for tier in tiers:
        if str(tier.get("status")) == "retired":
            continue
        for dep in _arr(tier.get("depends_on")):
            if str(dep) in retired:
                issues.append("L7 在役阶 %s 依赖了退役阶 %s（修复指引：把该能力改依赖重分派后的阶）"
                              % (tier.get("id"), dep))
        if str(tier.get("status")) not in _arr(_obj(doc.get("vocabulary")).get("status")):
            issues.append("L7 阶 %s 的 status 越词表：%s" % (tier.get("id"), tier.get("status")))


def _collect_judged_refs(doc: Dict[str, Any], tiers: list) -> List[tuple]:
    """收集 (owner, judged_by 原值) 引用对（阶 / 资产子级 / 纵切件三面）。"""
    refs: List[tuple] = []
    for tier in tiers:
        refs += [(str(tier.get("id")), r) for r in _arr(tier.get("judged_by"))]
    for lv in _arr(doc.get("asset_levels")):
        refs += [(str(lv.get("id")), r) for r in _arr(lv.get("judged_by"))]
    for comp in _arr(_obj(doc.get("crosscut")).get("components")):
        refs += [(str(comp.get("id")), r) for r in _arr(comp.get("judged_by"))]
    return refs


def _rule_l8(root: str, doc: Dict[str, Any], tiers: list, issues: List[str]) -> None:
    """L8 judged_by 可解析（checkN 或在册 assertion）。"""
    checks = set(_CHECK_DEF.findall(csc.read_text_cached(Path(root, VERIFY_REL)))) \
        if _exists(root, VERIFY_REL) else set()
    a_path = Path(root, ASSERTIONS_REL)
    assertion_ids = set()
    if a_path.is_file():
        assertion_ids = {str(a.get("id")) for a in
                         _arr(json_doc.loads(csc.read_text_cached(a_path),
 dict,
 what=str(a_path)).get("assertions"))}
    for owner, raw in _collect_judged_refs(doc, tiers):
        ref = str(raw)
        m = _JUDGE_CHECK.match(ref)
        if m:
            if m.group(1) not in checks:
                issues.append("L8 %s 的判据 %s 在 %s 中不存在（修复指引：改指向真实 check）"
                              % (owner, ref, VERIFY_REL))
        elif ref.startswith(_JUDGE_ASSERTION):
            if ref[len(_JUDGE_ASSERTION):] not in assertion_ids:
                issues.append("L8 %s 的判据 %s 未登记（修复指引：在 %s 补该断言）"
                              % (owner, ref, ASSERTIONS_REL))
        else:
            issues.append("L8 %s 的判据形式不合法：%s（修复指引：写成 checkN 或 assertion:<id>）"
                          % (owner, ref))


def _rule_l9(root: str, doc: Dict[str, Any], cache: dict, issues: List[str]) -> None:
    """L9 豁免诚实：derived 条目须命中文件。"""
    for pattern in _arr(doc.get("derived")):
        # 走**快路径**（子树索引 + 正则）：等价性由 test_expand_fast_path_matches_reference 逐 patte
        # rn
        # 守着；原先是逐 pattern 的 Path.glob（本仓 6 条 derived），与别处的展开两套口径（实测）。
        if not _expand_many(root, [pattern], cache):
            issues.append("L9 derived 条目命中零文件：%s（修复指引：删掉该豁免或修正 glob）"
                          % pattern)


def _region_of(text: str):
    """取生成区正文；缺标记返回 None。"""
    if MARK_BEGIN not in text or MARK_END not in text:
        return None
    return text.split(MARK_BEGIN, 1)[1].split(MARK_END, 1)[0]


def _table(rows: List[List[str]], header: List[str]) -> List[str]:
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return out


def render_markdown(doc: Dict[str, Any]) -> str:
    """把阶梯真源渲染成 markdown 生成区（确定性；`nf layers --write` 写它）。"""
    lines: List[str] = []
    lines.append("### 抽象轴：四阶")
    lines.append("")
    rows = _render_tier_rows(doc)
    lines += _table(rows, ["阶", "真源面", "接口面（跨阶唯一可依赖）", "既有判据", "状态 / 变更档"])
    lines.append("")
    lines.append("### 资产阶五子级（同一格内异质，分开看代价）")
    lines.append("")
    rows = _render_level_rows(doc)
    lines += _table(rows, ["子级", "真源面", "既有判据", "口径"])
    lines.append("")
    lines.append("### 入口面（只登记角色，永不作为真源）")
    lines.append("")
    rows = _render_surface_rows(doc)
    lines += _table(rows, ["面", "入口件", "服务阶", "口径"])
    lines.append("")
    lines.append("### 验证纵切（贯穿四阶，不是层）")
    lines.append("")
    rows = _render_cross_rows(doc)
    lines += _table(rows, ["件", "落点", "既有判据"])
    lines.append("")
    lines.append("> 本区由 `nf layers --write` 渲染，禁止手改；真源 = `protocol/LAYERS.json`。")
    return "\n".join(lines)


def _render_tier_rows(doc):
    rows = []
    for t in doc.get("tiers") or []:
        rows.append([
            "**%s**" % t.get("name"),
            "、".join("`%s`" % g for g in (t.get("source") or {}).get("globs") or []),
            "、".join("`%s`" % g for g in (t.get("interface") or {}).get("globs") or []),
            "、".join(t.get("judged_by") or []),
            "%s（%s）" % (t.get("status"), t.get("change_tier")),
        ])
    return rows


def _render_level_rows(doc):
    rows = []
    for lv in doc.get("asset_levels") or []:
        rows.append(["**%s**" % lv.get("name"),
                     "、".join("`%s`" % g for g in lv.get("globs") or []),
                     "、".join(lv.get("judged_by") or []),
                     str(lv.get("note") or "")])
    return rows


def _render_surface_rows(doc):
    rows = []
    for sf in doc.get("surfaces") or []:
        rows.append(["**%s**" % sf.get("name"),
                     "、".join("`%s`" % e for e in sf.get("entries") or []),
                     "、".join(sf.get("serves") or []),
                     str(sf.get("note") or "")])
    return rows


def _render_cross_rows(doc):
    cross = doc.get("crosscut") or {}
    rows = []
    for comp in cross.get("components") or []:
        rows.append(["**%s**" % comp.get("id"), "`%s`" % comp.get("artifact"),
                     "、".join(comp.get("judged_by") or [])])
    return rows


def _rule_l10(root: str, doc: Dict[str, Any], issues: List[str]) -> None:
    """L10 生成区 == 实时渲染。"""
    if not _exists(root, DOC_REL):
        issues.append("L10 缺阶梯文档 %s（修复指引：补件并跑 nf layers --write）" % DOC_REL)
        return
    body = csc.read_text_cached(Path(root, DOC_REL))
    got = _region_of(body)
    want = render_markdown(doc)
    if got is None:
        issues.append("L10 %s 缺生成区标记 %s / %s（修复指引：补标记后跑 nf layers --write）"
                      % (DOC_REL, MARK_BEGIN, MARK_END))
    elif got.strip() != want.strip():
        issues.append("L10 %s 生成区与实时渲染不一致（修复指引：跑 nf layers --write 刷新）"
                      % DOC_REL)


def _rule_issues(root: str, doc: Dict[str, Any]) -> List[str]:
    """L1-L10 逐面校验 → 违例清单（每面一个校验器，见各 _rule_lN）。"""
    issues: List[str] = []
    tiers = _arr(doc.get("tiers"))
    tier_ids = [str(t.get("id")) for t in tiers]
    cache: dict = {}                       # 本次扫描的 glob 展开缓存（见 _expand_many）
    derived = _derived_files(root, doc, cache)

    _rule_l1(root, doc, tier_ids, cache, issues)
    faces = _rule_l2(root, tiers, tier_ids, derived, cache, issues)
    _rule_l3(root, tiers, faces, derived, cache, issues)
    _rule_l4(root, tiers, tier_ids, issues)
    _rule_l5(doc, tier_ids, issues)
    _rule_l6(root, cache, issues)
    _rule_l7(doc, tiers, issues)
    _rule_l8(root, doc, tiers, issues)
    _rule_l9(root, doc, cache, issues)
    _rule_l10(root, doc, issues)
    return issues
