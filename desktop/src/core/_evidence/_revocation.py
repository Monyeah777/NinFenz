"""evidence · _revocation（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core import json_doc
from core import revocations as revoc

from ._const import (
    GUIDE,
    REVOCATION_SCHEMA,
    REVOCATIONS_ENTRY,
)
from ._primitives import (
    _norm,
)
from ._reader import (
    _Reader,
)

#: `--revocations` 形状不对时的统一文案（M11）：坏形状 fail-closed，不许静默不命中
_BAD_REVOCATIONS = ("--revocations 既不是 nf-revocation/1 表也不是 nf-revocation-feed/1"
                    "（" + GUIDE + "给表或签名 feed；传 feed 时本仓会取 table 并读其有效期）")




def _revocation_source(rev: dict[str, Any] | None,
                       ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    """吊销来源归一化 → (表, feed 信封, 错误文本)。

    `--revocations` 现在**同时吃**普通 `nf-revocation/1` 表与签名 `nf-revocation-feed/1`
    （此前只认表：传签名 feed 会静默不命中、已吊销的证据照样判 ok——那是缺陷，不是特性）。
    吃 feed 时取里面的表并读它的有效期；裸表没有信封可读有效期 → freshness=unknown。
    **坏形状一律 fail-closed**：坏件不能当「无吊销」，也不能静默放过。
    """
    if not isinstance(rev, dict):
        return None, None, _BAD_REVOCATIONS
    schema = str(rev.get("schema") or "")
    if schema == REVOCATION_SCHEMA:
        table, feed = rev, None
    elif schema == revoc.FEED_SCHEMA:
        table = revoc.table_of(rev)
        feed = rev
        if table is None:
            return None, None, ("--revocations 的 feed 缺 nf-revocation/1 表（" + GUIDE +
                                "只放条目不算；请用签发方 feed 或先 revocations merge）")
    else:
        return None, None, _BAD_REVOCATIONS
    revoked = table.get("revoked")
    if not isinstance(revoked, list) or not all(isinstance(i, dict) for i in revoked):
        return None, None, ("--revocations 的 revoked 必须是对象数组（" + GUIDE +
                            "给合法的 nf-revocation/1 表或签名 feed）")
    return table, feed, ""




def _apply_revocation(rd: _Reader, entries: Sequence[dict[str, Any]],
                      revocations: dict[str, Any] | None,
                      res: dict[str, Any], fresh: dict[str, Any],
                      at: str = "") -> bool:
    """吊销判定：命中即 revoked（压过 expired/新鲜度，也压过 ok）。返回是否已定案。

    来源优先级：外部 `--revocations`（表或签名 feed）> 包内嵌（只认表）。
    未命中时**只记录新鲜度**（写进 `fresh` 与 res），不在这里判死——严格判定在时效之后。
    """
    if revocations is not None:
        table, feed, err = _revocation_source(revocations)
        res["revocations_source"] = "external"
    else:
        table, err = _embedded_revocations(rd)
        feed = None
        res["revocations_source"] = "embedded" if (table is not None or err) else "none"
    if err:
        res["issues"].append(err)
        return True                       # 坏吊销表 = 定案 invalid（不是「无吊销」）
    if table is None:
        return False                      # 没做吊销检查：不是「陈旧」，严格开关也不判死
    fresh.update(revoc.freshness(feed, at) if feed is not None
                 else {"state": "unknown", "expires_at": "", "basis": "none"})
    res["revocations_fresh"] = fresh["state"]
    res["revocations_basis"] = fresh["basis"]
    hit = _revocation_hit(table, entries)
    if hit is None:
        return False
    res["verdict"] = "revoked"
    res["revoked_by"] = hit
    why = hit.get("reason") or hit.get("path") or hit.get("digest") or "未给理由"
    res["issues"].append(f"证据已被吊销：{why}（{GUIDE}吊销是不可逆判定——请向签发方确认是否"
                         "曾发生错签或内容下架，不要把它当临时失败重试）")
    return True




def _embedded_revocations(rd: _Reader) -> tuple[dict[str, Any] | None, str]:
    """包内吊销表 → (表 或 None, 错误文本)。

    **坏件不能当「无吊销」**（2026-11-04 实测）：旧实现把解析失败折成 None，于是「把吊销表
    写坏」就能让已吊销的证据判 ok——坏件冒充合格。现在坏件/形状不符一律返回错误，判定 invalid。
    """
    raw = rd.read(REVOCATIONS_ENTRY)
    if raw is None:
        return None, ""
    try:
        doc = json_doc.loads(raw.decode(), dict, what="吊销表")
    except (ValueError, UnicodeDecodeError) as exc:
        return None, (f"包内吊销表不可解析：{exc}（{GUIDE}吊销表坏件不能当「无吊销」——"
                      "请重新打包，或提供合法的 nf-revocation/1）")
    if str(doc.get("schema") or "") != REVOCATION_SCHEMA:
        got = doc.get("schema")
        return None, (f"包内吊销表 schema 不匹配（期望 {REVOCATION_SCHEMA}，实得 {got!r}）"
                      f"（{GUIDE}形状不对的吊销表不能当「无吊销」）")
    return doc, ""




def _revocation_hit(rev: dict[str, Any] | None,
                    entries: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    """吊销表命中判定（按摘要或仓相对路径）；表形状不对一律不认（宁可 invalid 也不放过）。"""
    if not rev or str(rev.get("schema") or "") != REVOCATION_SCHEMA:
        return None
    revoked = rev.get("revoked") or []
    if not isinstance(revoked, list):
        return None
    digests = {str(e.get("digest") or "") for e in entries}
    paths = {_norm(str(e.get("path") or "")) for e in entries}
    for item in revoked:
        if not isinstance(item, dict):
            continue
        dig = str(item.get("digest") or "")
        pat = _norm(str(item.get("path") or ""))
        if (dig and dig in digests) or (pat and pat in paths):
            return item
    return None




def _apply_revocation_doc(revocations: dict[str, Any] | None,
                          entries: Sequence[dict[str, Any]],
                          res: dict[str, Any], fresh: dict[str, Any],
                          at: str = "") -> bool:
    """无容器形态的吊销判定（吊销表由调用方给，不内嵌；同样吃表或签名 feed）。"""
    if revocations is None:
        return False
    table, feed, err = _revocation_source(revocations)
    res["revocations_source"] = "external"
    if err:
        res["issues"].append(err)
        return True
    fresh.update(revoc.freshness(feed, at) if feed is not None
                 else {"state": "unknown", "expires_at": "", "basis": "none"})
    res["revocations_fresh"] = fresh["state"]
    res["revocations_basis"] = fresh["basis"]
    hit = _revocation_hit(table, entries)
    if hit is None:
        return False
    why = hit.get("reason") or hit.get("path") or hit.get("digest") or "未给理由"
    res["verdict"] = "revoked"
    res["revoked_by"] = hit
    res["issues"].append(f"证据已被吊销：{why}（{GUIDE}吊销是不可逆判定——请向签发方确认"
                          "是否曾发生错签或内容下架，不要当临时失败重试）")
    return True
