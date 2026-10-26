"""M80 结构门 S4/S5（术语一致 / 无越层直写）——从 `quality_gate` 拆出的规则实现。

拆出原因（2026-10-26）：`quality_gate.py` 受**冻结外形基线**约束（模块行数 /
单函数行数 / 圈复杂度棘轮），两条新规则直接内联会越线；而新文件须 ≤800 行且
单函数 CC ≤25。故把判据实现搬到本模块，`quality_gate` 只保留 import 与规则表登记
（对外行为不变：`default_rules()` 仍返回 6 条，`_r_term_consistency` /
`_r_no_layer_bypass` 由 quality_gate 以同名 import 暴露）。

- S4 术语一致：读 M97 `term_synced` + DocState.terms（无数据不启用）；
- S5 无越层直写：读 M23 可见性裁剪结果（无数据不启用）。
"""
from __future__ import annotations

from typing import List

from .gate_types import Issue
from .ir import IRDocument

# ------------------------------------------------- 结构门 S4/S5（M80 §2.1 补齐）
def _all_content(ir: IRDocument) -> str:
    """IR 全文（标题 + 全部模块正文）——术语/可见性判据的共同取证面。"""
    parts: List[str] = [str(ir.title or "")]
    for layer in ir.layers:
        for m in layer.modules:
            parts.append(m.content or "")
    for m in ir.extra_modules:
        parts.append(m.content or "")
    return "\n".join(parts)


def _term_entry(raw) -> tuple:
    """术语条目归一 → (定义, 别名列表)。

    接受两种书写（M97 term_delta / DocState.terms）：
      - 字典形：{"definition"/"def": str, "aliases"/"variants": [str]}
      - 字符串形：直接就是定义
    """
    if isinstance(raw, dict):
        definition = str(raw.get("definition") or raw.get("def") or "").strip()
        raw_aliases = raw.get("aliases") or raw.get("variants") or []
        aliases = [str(a).strip() for a in raw_aliases if str(a).strip()]
        return definition, aliases
    return str(raw or "").strip(), []


def _term_meta(ir: IRDocument) -> tuple:
    """取 (terms, term_synced)。terms = DocState.terms / meta.terms；sync = M97 事件回执。"""
    meta = ir.meta or {}
    doc_state = meta.get("doc_state")
    terms = doc_state.get("terms") if isinstance(doc_state, dict) else None
    if terms is None:
        terms = meta.get("terms")
    return terms, meta.get("term_synced")


def _r_term_consistency(ir: IRDocument) -> List[Issue]:
    """S4 术语一致（M80 §2.1）：消费 M97 `term_synced` + DocState.terms。

    - 无术语域数据（terms 与 term_synced 都缺）→ 不启用（叙事装配零影响）；
    - term_synced 未通过（ok=False / status=conflict|pending_definition / 冲突非空）→ fail；
    - 术语在正文出现但定义为空（M97「首用未定义」）→ fail；
    - 规范术语与其别名在同一产物中并存（混用）→ fail。
    """
    terms, sync = _term_meta(ir)
    if terms is None and sync is None:
        return []
    issues: List[Issue] = []
    # ① M97 term_synced 回执：未同步即 fail（术语表未收敛时不得渲染）
    if isinstance(sync, dict):
        status = str(sync.get("status") or "").strip()
        ok = sync.get("ok")
        conflicts = sync.get("conflicts") or []
        if ok is False or status in ("conflict", "pending_definition") or conflicts:
            detail = str(sync.get("detail") or "")
            if not detail and conflicts:
                detail = "冲突术语：" + "、".join(str(x) for x in list(conflicts)[:5])
            issues.append(Issue(
                "fail", "术语表未同步（M97 term_synced 未通过）" + ("：" + detail if detail else ""),
                suggestion="先让 M97 补定义/消解冲突并发布 term_synced（DocState.terms 收敛）"
                           "再进 M80 渲染；或从装配中移除术语门数据"))
    elif sync is False:
        issues.append(Issue(
            "fail", "术语表未同步（term_synced=False）",
            suggestion="M97 术语管理未发布 term_synced：先补定义/消解冲突，再重跑术语层"))
    # ② 逐条术语：已使用须有定义；规范术语与别名不得混用
    if isinstance(terms, dict) and terms:
        content = _all_content(ir)
        for name, raw in terms.items():
            name = str(name).strip()
            if not name:
                continue
            definition, aliases = _term_entry(raw)
            used = name in content
            if used and not definition:
                issues.append(Issue(
                    "fail", "术语「%s」已在正文使用但无定义（M97 首用未定义）" % name,
                    suggestion="在术语表补该术语定义（definition），或改正文首用处为已定义术语；"
                               "M97 term_synced 要求每个已用术语有定义"))
            for alias in aliases:
                if alias != name and alias in content and used:
                    issues.append(Issue(
                        "fail", "术语混用：规范术语「%s」与其别名「%s」在同一产物中并存"
                        % (name, alias),
                        suggestion="统一为规范术语「%s」（术语表 aliases 只作检索等价，不作正文用词）"
                        % name))
    return issues


def _hidden_markers(ir: IRDocument) -> List[str]:
    """取 M23 可见性裁剪声明的隐藏域标记（多写入点归一）。"""
    meta = ir.meta or {}
    out: List[str] = []
    vis = meta.get("visibility")
    sources = [vis] if isinstance(vis, dict) else []
    sources.append(meta)
    for src in sources:
        for key in ("hidden", "hidden_terms", "hidden_domains", "hidden_slots"):
            val = src.get(key)
            if isinstance(val, (list, tuple)):
                out.extend(str(x).strip() for x in val if str(x).strip())
            elif isinstance(val, str) and val.strip():
                out.append(val.strip())
    return out


def _r_no_layer_bypass(ir: IRDocument) -> List[Issue]:
    """S5 无越层直写（M80 §2.1）：M23 隐藏域直述进呈现面 → fail。

    - 无可见性数据（IR.meta 无 visibility/hidden_*）→ 不启用（叙事装配零影响）；
    - 声明了隐藏域标记且正文逐字命中 → fail（隐藏域只可经可观察证据间接透出）。
    """
    hidden = _hidden_markers(ir)
    if not hidden:
        return []
    content = _all_content(ir)
    hits = [h for h in hidden if h in content]
    if not hits:
        return []
    shown = "、".join(hits[:5]) + ("…" if len(hits) > 5 else "")
    return [Issue(
        "fail", "隐藏域直述（M23 越层直写 / 可见性纪律违例）：" + shown,
        suggestion="前置 M23 可见性裁剪：隐藏域内容不得直接进输出，只能通过可见证据间接透出；"
                   "从输出素材移除隐藏域直述或改可见域表达")]
