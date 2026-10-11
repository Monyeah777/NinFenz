# -*- coding: utf-8 -*-
"""复合路由（W-05 首片）：变化闭包选专家，UNSAFE 永不被裁，休眠必带理由。

策略 S（§1）：本次实跑 = dense(生效级别 UNSAFE) ∪ routed(读面命中变化闭包)；
其余记 dormant + 理由。纪律：
  - 生效级别 = 声明与**源码推导**取更严者（声明不得下调推导，fail-closed）；
  - UNSAFE 一律进 dense（INV-10：先证不丢）；
  - dormant 无理由即 issue（INV-5：无静默跳过）；
  - 路由表必须覆盖每个专家（既未路由也不休眠 = 不完整）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from core import gate_cache as gc
from core import gate_faces as gf
from core import gate_graph as gg

#: 级别严宽序（数值越大越严）。
_ORDER = {"SAFE": 0, "CONDITIONAL": 1, "UNSAFE": 2}


def effective_level(root: str, expert: Dict[str, Any]) -> Tuple[str, List[str]]:
    """生效级别 = max(声明, 源码推导)；未声明按 CONDITIONAL（保守中档）。"""
    declared = str(expert.get("skip_safety") or "")
    level = declared if declared in _ORDER else "CONDITIONAL"
    derived, why = gf.derive_skip_safety(root, expert)
    if derived in _ORDER and _ORDER[derived] > _ORDER[level]:
        level = derived
    return level, list(why)


def route(root: str, changed: Sequence[str], experts: Optional[Dict[str, Any]] = None,
          mode: str = "S") -> Tuple[List[str], Dict[str, Any], Dict[str, Any]]:
    """→ (issues, plan, stats)。changed 为仓库相对路径（或前缀）。"""
    decl = experts if experts is not None else gf.load_manifest(root)
    changed_n = [str(c).replace("\\", "/") for c in (changed or [])]
    dense: List[str] = []
    routed: List[Dict[str, Any]] = []
    dormant: List[Dict[str, str]] = []
    # W-08：受影响集走内容寻址缓存（键含根 + 变更 + 声明面 + 代码面；命中前 verify）
    akey = gc.key_for(root, "affected:" + "|".join(changed_n), [gf.MANIFEST_REL])
    affected, cached = gc.memo("gate-affected", akey,
                               lambda: gg.affected_experts(root, changed_n, experts=decl),
                               root=root, reads=[gf.MANIFEST_REL])
    for eid, e in sorted(decl.items()):
        level, _why = effective_level(root, e)
        if level == "UNSAFE" or not e.get("face_verified", True):
            dense.append(eid)
            via = "dense(UNSAFE)" if level == "UNSAFE" else "dense(读面未验证)"
            routed.append({"id": eid, "level": level, "via": via})
        elif eid in affected:
            routed.append({"id": eid, "level": level, "via": affected[eid]})
        else:
            dormant.append({"id": eid, "reason": "读面与变更闭包不相交（level=%s）" % level})
    plan = {"mode": mode, "changed": changed_n, "dense": dense,
            "routed": routed, "dormant": dormant}
    stats = {"experts": len(decl), "changed": len(changed_n), "dense": len(dense),
             "routed": len(routed), "dormant": len(dormant), "affected_cached": bool(cached)}
    return [], plan, stats


def audit_route(root: str, plan: Dict[str, Any],
                experts: Optional[Dict[str, Any]] = None) -> List[str]:
    """路由表自检：覆盖完整、休眠有理由、UNSAFE 未被裁（三条硬纪律）。"""
    decl = experts if experts is not None else gf.load_manifest(root)
    issues: List[str] = []
    routed_ids = {str(r.get("id")) for r in (plan.get("routed") or [])}
    dormant_ids = {str(d.get("id")) for d in (plan.get("dormant") or [])}
    dense_ids = {str(x) for x in (plan.get("dense") or [])}
    for d in (plan.get("dormant") or []):
        if not str(d.get("reason") or "").strip():
            issues.append("休眠缺理由：%s（INV-5：无静默跳过）" % d.get("id"))
    for eid, e in sorted(decl.items()):
        if eid not in routed_ids and eid not in dormant_ids:
            issues.append("专家既未路由也不休眠：%s（路由表不完整）" % eid)
        level, _why = effective_level(root, e)
        must_dense = (level == "UNSAFE") or (not e.get("face_verified", True))
        if must_dense and eid not in dense_ids:
            why = "UNSAFE 专家被裁（INV-10：先证不丢）" if level == "UNSAFE" \
                else "读面未验证的专家被裁（M2：声明面须由观测面生成）"
            issues.append("%s：%s" % (why, eid))
    return issues


def audit(root: str = ".", changed: Optional[Sequence[str]] = None
          ) -> Tuple[List[str], Dict[str, Any]]:
    """仓库面入口：对声明面全体求路由并自检 → (issues, stats)。

    入口命名 audit 而非 scan：本模块的产出是**路由表**（给调度器），不是又一条
    门禁自检——避开 judgement_coverage 的 scan 名额（与 gate_faces 同口径）。
    """
    experts = gf.load_manifest(root)
    issues, plan, stats = route(root, changed or [], experts=experts)
    issues += audit_route(root, plan, experts)
    stats["plan"] = plan
    return issues, stats
