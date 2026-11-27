"""evidence · _freshness（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import os
from typing import Any

from core import attest
from core import revocations as revoc

from ._const import (
    GUIDE,
)


def _apply_freshness(res: dict[str, Any], require_fresh: bool, at: str,
                     fresh: dict[str, Any]) -> bool:
    """吊销表新鲜度：默认只 WARN；`--require-fresh-revocations` 才把 stale/unknown 定案。

    插在**时效之后、ok 之前**：`expired` 是更具体的正向判定，不该被「表陈旧」这种数据
    质量问题遮蔽；而「命中吊销」是事实，已在 `_apply_revocation` 里立即定案。
    **完全没有吊销来源时不算 unknown**——那是「没做吊销检查」，不是「陈旧」，严格开关下
    也不得判死（否则不传吊销表的离线复验会全红）。
    """
    if str(res.get("revocations_source") or "none") == "none":
        return False
    state = str(res.get("revocations_fresh") or "unknown")
    if state not in revoc.FRESH:
        state = "unknown"      # 来源给出词表外状态：按未知处理（绝不因错误状态放行）
    if state == "fresh":
        return False
    exp = str(fresh.get("expires_at") or "")
    if not require_fresh:
        if state == "stale":
            res["warnings"].append(f"吊销表已过期（expires_at={exp}）：未开 "
                                   "--require-fresh-revocations，本次判定不受影响（" + GUIDE +
                                   "需要「新鲜」保证时加上该开关）")
        else:
            res["warnings"].append("吊销表未给有效期，无法判新鲜（" + GUIDE +
                                   "签发时加 --expires-at/--ttl；本次判定不受影响）")
        return False
    now = at or attest.issue_stamp()
    if state == "stale":
        res["issues"].append(f"吊销表已过期（expires_at={exp}，判定时点={now}）：无法证明"
                             "「当前未吊销」（" + GUIDE + "向签发方取 seq 更大的新 feed 重跑；"
                             "或去掉 --require-fresh-revocations 接受「新鲜度未知」）")
    else:
        res["issues"].append("吊销表未给有效期（无 expires_at/ttl）："
                             "--require-fresh-revocations 下无法证明新鲜（" + GUIDE +
                             "签发方补 --expires-at 或 --ttl 重签；或去掉开关）")
    res["verdict"] = "invalid"
    return True




def _apply_time_token(res: dict[str, Any], bundle: str, record: dict[str, Any],
                      ca_file: str, untrusted: str) -> str | None:
    """校验外部 RFC 3161 token 并把判定时点锚到 genTime。

    → 成功返回锚定时刻（ISO）；失败返回 None 并把原因写进 issues（fail-closed）。
    语义边界：token 证的是「该字节在该时刻已存在」，所以**有效期判定用 genTime**——
    我们仍然不知道「现在」的真实时间，只把「已过期」上的时钟依赖换成可验证的锚点。
    """
    from core import timestamp as ts
    if not isinstance(record, dict) or str(record.get("schema") or "") != ts.SCHEMA:
        res["issues"].append("时间锚记录 schema 不匹配（" + GUIDE
                             + "给 nf-time-token/1 记录 JSON）")
        return None
    subject = record.get("subject") or {}
    try:
        with open(bundle, "rb") as fh:
            want = ts.subject_digest(fh.read())
    except OSError as exc:
        res["issues"].append(f"读不到证据包：{exc}（{GUIDE}确认路径）")
        return None
    got = str(subject.get("sha256") or "")
    if got != want:
        res["issues"].append(f"时间锚与被证对象不符（记录={got[:16]} 实测={want[:16]}）"
                             f"（{GUIDE}token 必须盖在同一份字节上——换包必须重新申请）")
        return None
    base = os.path.dirname(os.path.abspath(bundle))
    record_dir = str(record.get("_dir") or base)
    token = os.path.join(record_dir, str((record.get("token") or {}).get("path") or ""))
    query = os.path.join(record_dir, str((record.get("query") or {}).get("path") or ""))
    checked = ts.verify(token, query, ca_file=ca_file, untrusted=untrusted)
    if not checked["ok"]:
        res["issues"].extend(["时间锚不可信：" + i for i in checked["issues"]])
        return None
    res["time_proof"] = "tsa"
    res["time_basis"] = checked["gen_time"]
    res["time_token"] = {"gen_time": checked["gen_time"], "serial": checked["serial"],
                         "tsa": checked["tsa"]}
    return checked["gen_time"]




def _apply_expiry(res: dict[str, Any], at: str) -> bool:
    """时效判定：有效期早于判定时点即 expired。返回是否已定案。

    同时标注**时间可证性**（G3）：本仓没有可信时间源，所以只能说「这个判定用的是哪个时点」，
    不能说「那个时点是真的」。调用方给 --at 时记 pinned（可复现/可对账），否则记 none 并
    在包带有效期时给 warning——**不假装已经证明了时间**。
    """
    exp = res["expires_at"]
    if res.get("time_proof") != "tsa":      # 已有 TSA 锚：不要覆盖成 pinned/none
        res["time_proof"] = "pinned" if at else "none"
        res["time_basis"] = at or ("本机时钟 " + attest.issue_stamp())
    if not exp:
        return False
    if not at and res.get("time_proof") != "tsa":
        res["warnings"].append("时间不可证（G3）：本判定用本机时钟判有效期，回拨时钟即可改变 "
                               "expired 结论（修复指引：需要可对账时给 --at 固定时点，"
                               "或用 nf evidence timestamp 申请 TSA token 后再判）")
    now = at or attest.issue_stamp()
    if now <= exp:
        return False
    res["verdict"] = "expired"
    res["issues"].append(f"证据已过期：有效期至 {exp}，判定时点 {now}（{GUIDE}过期须重签——"
                         "请用 nf evidence pack 配新的 --expires-at 重新签发）")
    return True
