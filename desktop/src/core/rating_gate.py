"""内容分级门（挂账收口：原触发条件 = 「馆藏出现分级消费方」）。

内部差距实证：`library/INDEX.md` 登记表有「形态 / 许可 / 状态」列，**没有分级列**；
条目的 frontmatter 也没有 `rating` 字段——投稿须知里连「分级」二字都没出现。
后果：消费方（家长控制、平台分级、检索过滤）**无从判断**一件馆藏适龄与否，
只能读了才知道；而 NF 的门禁对此完全沉默（`license_gate` 只管许可）。

设计纪律（与 `license_gate` 同源，不另造标准）：
- **真源 = 条目 frontmatter**（`rating:`），投影 = INDEX「分级」列（由 `nf library reindex` 生成）；
- 取值 = 声明件 `library/intake.json: rating.vocabulary` 词表（general / teen / mature / unrated），
  词表以**声明**为准——改词表 = 改声明件，门禁自动跟随（不写死在代码里）；
- `unrated` 是**显式声明未分级**，不是缺省：缺字段 = FAIL（分级是消费方选择的前提，不许沉默）；
- 本门只判「声明在场且合规」，**不替投稿人做适龄判断**（那是内容责任，不是机器责任）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple
from core import json_doc

INTAKE_REL = "library/intake.json"
DEFAULT_VOCAB = ("general", "teen", "mature", "unrated")
#: 「显式未定级」的默认记号（声明件可用 rating.undecided 覆盖）。
UNDECIDED = "unrated"


def _decl(root: str = ".") -> Dict[str, Any]:
    """读投稿闸门声明件 → dict（缺件/坏件返回 {}，由各判据分别如实报出）。"""
    path = Path(root) / INTAKE_REL
    if not path.is_file():
        return {}
    try:
        return json_doc.load(path, dict, what=INTAKE_REL)
    except ValueError:
        return {}


def vocabulary(root: str = ".") -> List[str]:
    """分级词表真源 = library/intake.json 的 rating.vocabulary（缺失即用默认值）。"""
    vocab = ((_decl(root).get("rating") or {}).get("vocabulary") or [])
    return [str(v) for v in vocab] or list(DEFAULT_VOCAB)


def undecided_token(root: str = ".") -> str:
    """「未定级」记号的声明真源（rating.undecided，缺省 unrated）。"""
    return str((_decl(root).get("rating") or {}).get("undecided") or UNDECIDED)


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """馆藏分级声明体检 → (issues, stats)。"""
    from core import library  # 延迟导入：避免与 library↔rating 形成导入环

    issues: List[str] = []
    vocab = vocabulary(root)
    rows = library.entries(root)
    counts: Dict[str, int] = {}
    for e in rows:
        fm = e["fm"]
        rating = str(fm.get("rating") or "").strip()
        if not rating:
            issues.append("%s 缺 frontmatter `rating`（修复指引：取值为 %s；未定级写 unrated "
                          "而非留空——分级是消费方选择的前提）" % (e["id"], "/".join(vocab)))
            continue
        if rating not in vocab:
            issues.append("%s 的 rating 越词表：%s（允许：%s；词表真源 = %s）"
                          % (e["id"], rating, "/".join(vocab), INTAKE_REL))
            continue
        counts[rating] = counts.get(rating, 0) + 1
    # 声明面须在场（词表可声明，才谈得上「按声明判」）
    doc = _decl(root)
    if not doc:
        issues.append("缺 %s（修复指引：投稿闸门声明件须在场）" % INTAKE_REL)
    elif not ((doc.get("rating") or {}).get("vocabulary")):
        issues.append("%s 缺 rating.vocabulary 声明（修复指引：分级词表须成文，"
                      "门禁按声明判而不写死）" % INTAKE_REL)
    tok = undecided_token(root)
    n_unrated = counts.get(tok, 0)
    # Z3：把「声明在场」与「真被定级」拆成两个数——100% 覆盖不再等于内容已定级。
    stats: Dict[str, Any] = {"entries": len(rows), "vocabulary": vocab, "counts": counts,
                             "decided": len(rows) - n_unrated, "unrated": n_unrated,
                             "undecided_token": tok, "issues": len(issues)}
    return issues, stats


def decided(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """内容是否真被定级（审计 Z3：rating_gate 100% 覆盖拆穿）。

    scan() 判的是「声明在场且合词表」——显式 unrated 也算合格，于是覆盖率恒 100%；
    本判据判第二层：只声明未定级的件算不算数。策略真源 = library/intake.json 的
    rating.allow_unrated（缺省 false ⇒ fail-closed）：要允许未定级，必须成文写清，
    否则「100% 覆盖」这个词就名不副实（审计 §11ai N9 的原话）。
    """
    from core import library  # 延迟导入：避免与 library↔rating 导入环

    decl = _decl(root)
    rating_decl = decl.get("rating") or {}
    allow = bool(rating_decl.get("allow_unrated"))
    tok = undecided_token(root)
    rows = library.entries(root)
    unrated_ids = [e["id"] for e in rows
                   if str((e["fm"].get("rating") or "")).strip() == tok]
    issues: List[str] = []
    if unrated_ids and not allow:
        issues.append("馆藏 %d 件只声明「未定级」（%s）：%s（修复指引：给出真实分级；"
                      "确需允许未定级，则在 %s 的 rating.allow_unrated=true 成文说明，"
                      "不要用 100%% 覆盖掩盖未定级）"
                      % (len(unrated_ids), tok, "、".join(unrated_ids[:5]), INTAKE_REL))
    stats = {"entries": len(rows), "decided": len(rows) - len(unrated_ids),
             "unrated": len(unrated_ids), "undecided_token": tok, "allow_unrated": allow}
    return issues, stats


def summary(stats: Dict[str, Any]) -> str:
    parts = "、".join("%s=%d" % (k, v) for k, v in sorted((stats.get("counts") or {}).items()))
    tail = ""
    if "decided" in stats or "unrated" in stats:
        # Z3：摘要也分开报「已定级 / 未定级」，避免读者把覆盖率读成内容已定级。
        tail = " · 已定级 %d / 未定级 %d" % (stats.get("decided", 0), stats.get("unrated", 0))
    return "馆藏 %d 件 · 分级 %s · 词表 %s%s" % (
        stats.get("entries", 0), parts or "—", "/".join(stats.get("vocabulary") or []), tail)
