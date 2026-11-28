"""evidence · _primitives（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from core import attest, receipts
from core.transparency_log import NODE_PREFIX

from ._const import (
    GUIDE,
)


def canonical(obj: Any) -> bytes:
    """规范化 JSON 编码——与 attest.canonical 同一口径（摘要稳定的前提）。"""
    return attest.canonical(obj)




def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()




class UnsafeBundleError(ValueError):
    """证据包含不安全/歧义结构（路径穿越、重名成员、超限膨胀）。"""




def _safe_rel(rel: str) -> str:
    """仓相对路径的安全闸门 → 归一后的 POSIX 路径；不安全就抛 UnsafeBundleError。

    为什么必须在这里拦（2026-11-05 实测）：成员路径来自**不可信包**，而验证过程会把它拼进
    临时目录落盘（信封主体摘要要对文件算）。不拦两点号段就等于给了「验证即任意写」——这是
    验证器最不该有的洞：它的全部价值建立在「敢拿去验敌意输入」上。
    """
    clean = _norm(str(rel or ""))
    if not clean:
        raise UnsafeBundleError("成员路径为空（修复指引：成员必须有仓相对路径）")
    parts = clean.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise UnsafeBundleError(f"成员路径不安全：{clean}（修复指引：路径段不许是空串 / "
                                    "单点 / 双点，这一条防的是解包越界写）")
        if ":" in part:
            raise UnsafeBundleError(f"成员路径含盘符/备用流写法：{clean}（修复指引：只接受仓内 "
                                    "POSIX 相对路径）")
        if part != part.strip():
            raise UnsafeBundleError(f"成员路径含首尾空白：{clean!r}（修复指引：请去掉不可见字符）")
    return clean




def _norm(rel: str) -> str:
    """仓相对路径归一成 POSIX 形态：zip 成员名与回执 id 都用正斜杠。"""
    return rel.replace("\\", "/").lstrip("/")




def _leaf(path: str, digest: str) -> str:
    """回执叶定义（与 receipts.build_scope 逐字一致：sha256(0x00 || canonical{id,digest})）。

    这里不重写公式的「主意」，只复算同一表达式——两份实现不一致会被
    test_evidence.py::test_leaf_matches_receipts 当场钉住。
    """
    payload = json.dumps({"id": path, "digest": digest}, sort_keys=True,
                         ensure_ascii=False, separators=(",", ":")).encode()
    return receipts.leaf_hash(payload).hex()




def _chain_prefix_head(entries: Sequence[dict[str, Any]], upto: int) -> str:
    """前 upto 条折叠出的链头（锚点核对用：外部锚点记的是「当时那条链的链头」）。"""
    prev = "0" * 64
    for e in entries[:max(0, upto)]:
        h = hashlib.sha256()
        h.update(NODE_PREFIX)
        for part in (prev.encode("ascii"), str(e.get("leaf") or "").encode("ascii")):
            h.update(b"|")
            h.update(part)
        prev = h.hexdigest()
    return prev




def check_anchor(entries: Sequence[dict[str, Any]], meta: dict[str, Any],
                 anchor: dict[str, Any] | None, res: dict[str, Any]) -> None:
    """外部锚点核对（G1：防「整链被截断成更早版本」）。

    语义：锚点 = 某个**外部可核**的（条目数 count, 链头 head）二元组，例如上一次发布的链头、
    外部日志的序号+摘要。核对三件事：
      1) 本包的链必须包含锚点声称的那一段前缀（count 条）——少于它即**被截断**；
      2) 该前缀折叠出的链头必须等于锚点记录（否则历史被改写/分叉）；
      3) 包内声明的 anchor 与外部锚点材料必须一致（声称与证据不得互相矛盾）。
    没提供锚点材料时：不判死、不判 ok —— 只在 warnings 里写明「无法证明未被截断」，
    并且**不**提升 level（缺证据不等于证据成立）。
    """
    declared = meta.get("anchor")
    if isinstance(declared, dict) and declared:
        res["anchor_ref"] = {"count": declared.get("count"), "head": declared.get("head")}
    ctx = _anchor_precheck(anchor, res)
    if ctx is None:
        return
    cnt, head = ctx
    if res["anchor_ref"] and _anchor_ref_mismatch(res["anchor_ref"], cnt, head):
        res["issues"].append("包内 anchor 与外部锚点不一致（" + GUIDE +
                             "声称的锚点与证据互相矛盾——请以外部锚点为准重新打包）")
        return
    _anchor_chain(entries, cnt, head, res)


def _anchor_precheck(anchor, res: dict[str, Any]):
    """锚点材料形状校验 → (count, head) 或 None（不判死，已写 issue/warning）。"""
    if anchor is None:
        if res["anchor_ref"]:
            res["warnings"].append("包声明了外部锚点但未提供锚点材料（" + GUIDE +
                                   "无法证明未被截断：请向发布方索要锚点文件并加 --anchor）")
        return None
    cnt = anchor.get("count")
    head = str(anchor.get("head") or "")
    if not isinstance(cnt, int) or cnt < 0 or not head:
        res["issues"].append("锚点材料形状不对（" + GUIDE +
                             "需要 {count: 非负整数, head: 非空字符串}）")
        return None
    return cnt, head


def _anchor_ref_mismatch(ref: dict[str, Any], cnt: Any, head: str) -> bool:
    """包内声明的 anchor 与外部锚点材料是否矛盾。"""
    return ref.get("count") != cnt or ref.get("head") != head


def _anchor_chain(entries: Sequence[dict[str, Any]], cnt: int, head: str,
                  res: dict[str, Any]) -> None:
    """截断检查 + 链头一致性（通过则标记 verified）。"""
    if len(entries) < cnt:
        res["issues"].append(f"证据包被截断：包只有 {len(entries)} 条，锚点记录 {cnt} 条"
                             f"（{GUIDE}截断的历史不能当现在——请索要完整包）")
        return
    if _chain_prefix_head(entries, cnt) != head:
        res["issues"].append("与外部锚点不符：该位置的链头不一致（" + GUIDE +
                             "历史被改写或来自另一条链，二者只能有一个是真的）")
        return
    res["anchor_verified"] = True




def _chain_head(entries: Sequence[dict[str, Any]]) -> str:
    """透明日志链头：H(NODE_PREFIX | prev | leaf) 逐节折叠（公式同 transparency_log）。"""
    prev = "0" * 64
    for e in entries:
        h = hashlib.sha256()
        h.update(NODE_PREFIX)
        for part in (prev.encode("ascii"), str(e.get("leaf") or "").encode("ascii")):
            h.update(b"|")
            h.update(part)
        prev = h.hexdigest()
    return prev




def _json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode()
