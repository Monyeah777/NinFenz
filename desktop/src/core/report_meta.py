"""报告元数据：分母 + 输入指纹 + 三态置信 + basis（机制借鉴 instar 诚实分母 / basis）。

「完成了」不是证据：任何度量/评测报告必须自带 **输入指纹（sha256）、分母 n、
置信三态（confident / tentative / unjudged）与理由、以及计量依据 basis**；
样本不足返回 unjudged 而非推断。本模块提供构造与校验（纯函数，零依赖）。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

CONFIDENCE = ("confident", "tentative", "unjudged")


def input_digest(obj: Any) -> str:
    """规范 JSON（sort_keys、ensure_ascii=False）→ sha256（与 CONFORMANCE 口径同向）。"""
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_meta(basis: str, inputs: Any, denominator: int,
              confidence: str = "confident", reason: str = "") -> Dict[str, Any]:
    """构造一条报告元数据。"""
    return {"basis": basis, "input_digest": input_digest(inputs),
            "denominator": int(denominator), "confidence": confidence,
            "reason": reason}


def validate(meta: Dict[str, Any]) -> List[str]:
    """校验：字段齐 / 置信在封闭词表 / 非 confident 必带理由 / 空分母只许 unjudged。"""
    issues: List[str] = []
    for k in ("basis", "input_digest", "denominator", "confidence"):
        if not meta.get(k) and meta.get(k) != 0:
            issues.append("报告元数据缺字段 %s（修复指引：补 %s 后重跑）" % (k, k))
    conf = meta.get("confidence")
    if conf not in CONFIDENCE:
        issues.append("confidence 越词表：%r（修复指引：取 %s 之一）" % (conf, "/".join(CONFIDENCE)))
    if conf in ("tentative", "unjudged") and not str(meta.get("reason") or "").strip():
        issues.append("非 confident 缺 reason（修复指引：写明为何不能给 confident）")
    if int(meta.get("denominator") or 0) == 0 and conf == "confident":
        issues.append("空分母不得报 confident（修复指引：改 unjudged 或补齐样本）")
    return issues
