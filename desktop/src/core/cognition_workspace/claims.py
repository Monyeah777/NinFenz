"""主张编译（nf-cog-claim/1）：把「主张」编译成「必须交的证据义务清单」。

这是方法包真正生效的地方：
- 方法包给 evidence_standards（这个领域什么算证据）；
- 判据注册表给 criteria（怎么判、留什么 witness、什么角色）；
- 本模块把两者编成一张**义务清单**，并支持按清单核对已有证据（缺项/未知分列）。

纪律：清单只列「要交什么」，不评分；核对结果只给 satisfied/missing/unknown 三态。
"""
from __future__ import annotations

import json
from typing import Any

from core.cognition_workspace import criteria as cr
from core.method_pack import compose, load_pack
from core.method_pack import obligations as pack_obligations

SCHEMA = "nf-cog-claim/1"
CHECK_SCHEMA = "nf-cog-claim-check/1"
GUIDE = "修复指引："


def _digest(obj: Any) -> str:
    import hashlib
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compile_claim(root: str, claim: str, claim_kind: str,
                  pack_ids: list[str], criterion_ids: list[str] | None = None,
                  role: str = "local-trusted") -> dict[str, Any]:
    """编译主张 → 义务清单。缺包/缺 claim_kind/未知判据 → ValueError（带指引）。"""
    if not str(claim).strip():
        raise ValueError("主张不能为空（" + GUIDE + "写一句能被反驳的话）")
    if not pack_ids:
        raise ValueError("至少要一个方法包（" + GUIDE + "nf cognition --packs-list 看可用包）")
    packs = [load_pack(root, pid) for pid in pack_ids]
    per_pack = []
    without_kind: list[str] = []
    for pack in packs:
        kinds = [std.get("claim_kind") for std in pack.get("evidence_standards") or []]
        if claim_kind not in kinds:
            without_kind.append(str(pack.get("id")))
            continue
        per_pack.append(pack_obligations(pack, claim_kind))
    if not per_pack:
        available = sorted({str(std.get("claim_kind")) for pack in packs
                            for std in pack.get("evidence_standards") or []})
        raise ValueError("所选方法包都没有 claim_kind=" + str(claim_kind)
                         + " 的证据标准（修复指引：可选 " + "、".join(available) + "）")
    composed = compose(packs)
    ids = list(criterion_ids or [])
    if not ids:
        ids = [item["id"] for item in cr.list_criteria(root)
               if claim_kind in (item.get("applies_to") or ["claim"])] or \
              ["craft:evidence_sufficiency"]
    resolved = []
    for cid in ids:
        item = next((c for c in cr.list_criteria(root) if c["id"] == cid), None)
        if item is None:
            raise ValueError("未知判据：" + cid + "（" + GUIDE + "见 nf cog criteria）")
        if cr.ROLES.index(role) > cr.ROLES.index(item["max_role"]):
            raise ValueError("角色升级：以 " + role + " 身份使用判据 " + cid
                             + "（" + GUIDE + "外部判据只能用 external-advisory/ blind 身份）")
        resolved.append({"id": cid, "layer": item["layer"], "kind": item["kind"],
                         "witness": list(item.get("witness") or [])})
    payload = {"schema": SCHEMA, "claim": str(claim), "claim_kind": str(claim_kind),
               "packs": [pack["id"] for pack in packs],
               "role": role,
               "obligations": per_pack,
               "packs_without_kind": without_kind,
               "criteria": resolved,
               "common_failures": composed["common_failures"]}
    payload["digest"] = _digest(payload)
    return payload


def _evidence_index(evidence: Any) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        return {}
    return evidence


def check_claim(doc: dict[str, Any], evidence: Any) -> dict[str, Any]:
    """按义务清单核对证据 → {ready, satisfied, missing, unknown}（三态，不评分）。"""
    if not isinstance(doc, dict) or str(doc.get("schema") or "") != SCHEMA:
        raise ValueError("主张文件 schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）")
    ev = _evidence_index(evidence)
    satisfied: list[str] = []
    missing: list[str] = []
    unknown: list[str] = []
    for block in doc.get("obligations") or []:
        for standard in block.get("standards") or []:
            for need in standard.get("required") or []:
                entry = ev.get(str(need))
                if entry is None:
                    missing.append(str(need))
                elif isinstance(entry, dict) and entry.get("status") == "unknown":
                    unknown.append(str(need))
                else:
                    satisfied.append(str(need))
    total = len(satisfied) + len(missing) + len(unknown)
    return {"schema": CHECK_SCHEMA, "ready": bool(total and not missing and not unknown),
            "total": total, "satisfied": satisfied, "missing": missing,
            "unknown": unknown,
            "note": "unknown ≠ pass；ready 只在 missing 与 unknown 都为空时为真"}

SHEET_SCHEMA = "nf-cog-claim-sheet/1"


def claim_sheet(doc: dict[str, Any]) -> dict[str, Any]:
    """把主张义务清单翻成**证据作业单**：每个 required 一条空槽，status 一律 unknown。

    为什么要有它：check_claim 说「差哪些证据」，但人/agent 拿到的是散落清单；
    作业单让「取证」变成逐个填空，且默认 unknown（unknown != pass，必须显式改成 ok）。
    """
    if not isinstance(doc, dict) or str(doc.get("schema") or "") != SCHEMA:
        raise ValueError("主张文件 schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）")
    slots = []
    for block in doc.get("obligations") or []:
        for standard in block.get("standards") or []:
            kind = str(standard.get("claim_kind") or "")
            for need in standard.get("required") or []:
                slots.append({"need": str(need), "claim_kind": kind,
                              "status": "unknown", "evidence": "",
                              "how_to_check": "给出可复算的路径/命令/断言（不接受口头结论）"})
    return {"schema": SHEET_SCHEMA, "claim": doc.get("claim"),
            "claim_kind": doc.get("claim_kind"),
            "packs": list(doc.get("packs") or []),
            "digest": doc.get("digest"),
            "slots": slots,
            "note": "unknown != pass：全部槽位改成 ok 后，check_claim 才会 ready"}
