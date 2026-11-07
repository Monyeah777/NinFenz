"""法规文本 → 意图草稿 v0（cc_check 语义层的诚实半边）。

现状（2026-11-07 前）：意图必须人写（nf-check-intent/1），工具只做编译与校验。缺口是
「法规原文 → 意图」这一步。真正的自然语言理解不在本仓能力内，所以这里做的是**规则抽取**：

- 按条切分（「第X条」/数字编号/破折号），逐条匹配**封闭的**关键词模式（显式标识/水印/元数据/
  禁止/字数/时限…），套到 check_compile 的可编译规则上；
- 能从原文里抽到的参数（引号里的文字、数字）就抽，抽不到就留缺失标记让人补；
- 抽不到规则的条目进 uncovered，需要能力才判的进 unsupported——**绝不静默丢弃**；
- 每条都带 confidence 与 needs_human 标记：这是**草稿**，不是法律意见。

纪律：纯函数、无时间戳（同输入逐字节一致）；输出可直接喂 nf check --compile 走编译面。
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA = "nf-check-intent-draft/1"
INTENT_SCHEMA = "nf-check-intent/1"
GUIDE = "修复指引："
MAX_TEXT_BYTES = 2 * 1024 * 1024

#: 条分割：中文条号 / 数字编号 / 圆点编号
CLAUSE_RE = re.compile(
    r"(?:^|\n)\s*(?:(第[一二三四五六七八九十百零〇\d]+条)|(\d{1,3})[.、]|[-•·])\s*")
#: 引号里的字面值（中文引号/直角引号/英文引号）
QUOTE_RE = re.compile(r"[「『\"'“]([^」』\"'”]{1,40})[」』\"'”]")
NUM_RE = re.compile(r"(?<!\d)(\d{1,6})\s*(?:个)?(?:字节|B|字符|字)")

#: 关键词 → (规则, 说明, 需要人补的参数)；顺序即优先级
KEYWORDS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("显式标识", "explicit_notice", "要求出现显式标识文字", ("text",)),
    ("显著标识", "explicit_notice", "要求出现显著标识文字", ("text",)),
    ("文字提示", "explicit_notice", "要求文字提示", ("text",)),
    ("标注", "explicit_notice", "要求标注提示", ("text",)),
    ("水印", "carrier_watermark", "要求数字水印", ()),
    ("隐式标识", "carrier_watermark", "要求隐式标识", ()),
    ("元数据", "require_metadata", "要求元数据字段", ("key",)),
    ("信息项", "require_metadata", "要求信息字段", ("key",)),
    ("不得", "forbidden_tokens", "禁止出现某些内容", ("patterns",)),
    ("禁止", "forbidden_tokens", "禁止出现某些内容", ("patterns",)),
    ("字节", "min_bytes", "规定最小字节/字数", ("n",)),
    ("字数", "min_bytes", "规定最小字数", ("n",)),
    ("时限", "time_window", "规定发布时限", ()),
    ("期限内", "time_window", "规定发布期限", ()),
    ("资质", "owner_signature", "要求主体资质", ()),
    ("许可", "owner_signature", "要求许可", ()),
)


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def split_clauses(text: str) -> list[dict[str, Any]]:
    """按条切分 → [{label, body, line}]（label 缺省给 序号）。"""
    matches = list(CLAUSE_RE.finditer(text))
    out: list[dict[str, Any]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        label = (match.group(1) or match.group(2) or "").strip() or f"#{len(out) + 1}"
        out.append({"label": label, "body": body,
                    "line": text[:match.start()].count("\n") + 1})
    if not out and text.strip():
        out.append({"label": "#1", "body": text.strip(), "line": 1})
    return out


def _params(rule: str, body: str) -> dict[str, Any]:
    """从条文里抽可编译参数（抽不到就留空，由 missing_params 交给人工）。"""
    quoted = QUOTE_RE.findall(body)
    nums = NUM_RE.findall(body)
    if rule == "explicit_notice":
        return {"text": quoted[0]} if quoted else {}
    if rule == "forbidden_tokens":
        return {"patterns": [re.escape(q) for q in quoted]} if quoted else {}
    if rule == "min_bytes":
        return {"n": int(nums[0])} if nums else {}
    if rule == "require_metadata":
        return {"key": quoted[0]} if quoted else {}
    return {}


def draft(text: str, source: str = "") -> dict[str, Any]:
    """法规文本 → 意图草稿（含覆盖/不可表达/未覆盖三张账）。"""
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("法规文本超过 2 MiB（" + GUIDE + "按章/节拆分后再跑）")
    clauses = split_clauses(text)
    if not clauses:
        raise ValueError("没有可识别的条文（" + GUIDE + "给带条号/编号的文本，或至少一段正文）")
    from core import check_compile
    items: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    covered: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []
    for clause in clauses:
        hits = [kw for kw in KEYWORDS if kw[0] in clause["body"]]
        if not hits:
            uncovered.append({"clause": clause["label"], "line": clause["line"],
                              "why": "没有匹配到任何封闭规则关键词"})
            continue
        seen_rules: set[str] = set()
        for _word, rule, why, needs in hits:
            if rule in seen_rules:
                continue
            seen_rules.add(rule)
            params = _params(rule, clause["body"])
            missing = [n for n in needs if n not in params]
            if rule in check_compile.UNSUPPORTED:
                unsupported.append({"clause": clause["label"], "line": clause["line"],
                                    "rule": rule,
                                    "why": check_compile.UNSUPPORTED[rule]["why"],
                                    "needs": check_compile.UNSUPPORTED[rule]["needs"],
                                    "evidence": clause["body"][:80]})
                continue
            if missing:
                pending.append({"clause": clause["label"], "rule": rule,
                                "missing_params": missing, "line": clause["line"],
                                "source": clause["body"][:120]})
            else:
                req = {"id": f"R{len(items) + 1}", "rule": rule,
                       "clause": clause["label"], "source": clause["body"][:120]}
                req.update(params)
                items.append(req)
            covered.append({"clause": clause["label"], "rule": rule, "why": why,
                            "confidence": 0.9 if not missing else 0.55,
                            "needs_human": bool(missing), "missing_params": missing,
                            "line": clause["line"]})
    return {"schema": SCHEMA,
            "source": {"path": source,
                       "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                       "clauses": len(clauses)},
            "intent": {"schema": INTENT_SCHEMA, "object": "<待填：被检对象路径>",
                       "requirements": items},
            "covered": covered, "pending": pending,
            "unsupported": unsupported, "uncovered": uncovered,
            "needs_human": sum(1 for c in covered if c["needs_human"]),
            "note": "这是**规则抽取草稿**：参数抽不全的条目请人工补齐；未覆盖/不可表达项"
                    "必须人工裁决——不丢账，也不假装理解法律条文"}
