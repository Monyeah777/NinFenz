"""判据注册表（nf-criteria-registry/1）：三层判据 + 硬纪律。

为什么单独一层：文档里「质量标准」「评审」「盲评」经常混成一句，结果就变成打分表。
本层把判据写成**三层**并强制三条铁律：
- craft（可计算/可自检）：融贯、证据充分性、可证伪性；
- standard（可机检）：GB 条款、证据包格式——判定以策略引擎输出为准，本层只登记映射；
- review（外部盲评）：内部**永不**产出 pass（只能 unknown 或引用外部评审件）。

铁律（校验时强制执行）：
① 不出聚合分：任何判据对象里出现 score/grade/rating 键 → 校验失败；
② 不许角色升级：source_role 不得超过该判据的 max_role（外部意见变不成 local-trusted）；
③ 没有 witness 不出 pass：判定函数在缺 witness 时只能给 unknown。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "nf-criteria-registry/1"
REL = "protocol/criteria/registry.json"
GUIDE = "修复指引："
LAYERS = ("craft", "standard", "review")
KINDS = ("computable", "machine-check", "external-blind")
ROLES = ("external-blind", "external-advisory", "local-trusted")   # 权限从低到高
FORBIDDEN_KEYS = ("score", "grade", "rating", "points", "weighted_score")


def _load(root: str) -> Any:
    path = Path(root) / REL
    if not path.is_file():
        raise ValueError("判据注册表不在场：" + str(path)
                         + "（" + GUIDE + "确认 protocol/criteria/）")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("判据注册表不可读：" + str(exc) + "（" + GUIDE + "修 JSON 语法）") from exc


def _walk_keys(obj: Any, hits: list[str], path: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                hits.append(path + "/" + str(key))
            _walk_keys(value, hits, path + "/" + str(key))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            _walk_keys(value, hits, path + "/" + str(i))


def validate(doc: Any) -> list[str]:
    """注册表校验 → 问题列表（空 = 合法）。"""
    issues: list[str] = []
    if not isinstance(doc, dict) or str(doc.get("schema") or "") != SCHEMA:
        return ["注册表 schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）"]
    layers = doc.get("layers")
    if not isinstance(layers, dict):
        return ["缺 layers（" + GUIDE + "需要 craft/standard/review 三层）"]
    forbidden: list[str] = []
    _walk_keys(doc, forbidden)
    if forbidden:
        issues.append("出现聚合分键 " + str(forbidden[:3])
                      + "（" + GUIDE + "判据只输出 pass/fail/unknown + witness）")
    seen: set[str] = set()
    for layer in LAYERS:
        items = layers.get(layer)
        if not isinstance(items, list) or not items:
            issues.append("层 " + layer + " 为空（" + GUIDE + "每层至少一条判据）")
            continue
        for item in items:
            if not isinstance(item, dict):
                issues.append(layer + " 里有非对象判据（" + GUIDE + "改写成对象）")
                continue
            cid = str(item.get("id") or "")
            if not cid:
                issues.append(layer + " 里有判据缺 id（" + GUIDE + "给唯一 id）")
                continue
            if cid in seen:
                issues.append("判据 id 重复：" + cid)
            seen.add(cid)
            if not cid.startswith(layer + ":"):
                issues.append("判据 id 前缀与层不符：" + cid + "（" + GUIDE + "应为 "
                              + layer + ":…）")
            if item.get("kind") not in KINDS:
                issues.append(cid + " 的 kind 非法：" + str(item.get("kind")))
            if not item.get("how") or not item.get("witness"):
                issues.append(cid + " 缺 how/witness（" + GUIDE + "判据必须写清怎么判、留什么）")
            role = str(item.get("source_role") or "")
            max_role = str(item.get("max_role") or "")
            if role not in ROLES or max_role not in ROLES:
                issues.append(cid + " 的 source_role/max_role 非法（" + GUIDE + "见 ROLES）")
            elif ROLES.index(role) > ROLES.index(max_role):
                issues.append(cid + " 角色升级：" + role + " 高于 " + max_role
                              + "（" + GUIDE + "外部意见不能变成本地可信）")
            if layer == "review" and item.get("kind") != "external-blind":
                issues.append(cid + " 在 review 层但 kind 不是 external-blind")
    return issues


def load(root: str = ".") -> dict[str, Any]:
    doc = _load(root)
    issues = validate(doc)
    if issues:
        raise ValueError("判据注册表不合法：" + "；".join(issues[:3]))
    return doc


def list_criteria(root: str = ".", layer: str = "") -> list[dict[str, Any]]:
    doc = load(root)
    out: list[dict[str, Any]] = []
    for name in ((layer,) if layer else LAYERS):
        for item in doc["layers"].get(name, []):
            out.append({"layer": name, **item})
    return out


def get(root: str, criterion_id: str) -> dict[str, Any]:
    for item in list_criteria(root):
        if item["id"] == criterion_id:
            return item
    raise ValueError("未知判据：" + criterion_id + "（" + GUIDE + "见 nf cog criteria）")


def evaluate(root: str, criterion_id: str, witness: Any) -> dict[str, Any]:
    """按判据评估一次 → {criterion, verdict, witness_ok, reason}。

    verdict 只有 pass/fail/unknown；缺 witness → unknown（**不给 pass**）；
    review 层判据在本仓内永远 unknown（内部不能自证外部盲评）。
    """
    item = get(root, criterion_id)
    res: dict[str, Any] = {"criterion": criterion_id, "layer": item["layer"],
                           "verdict": "unknown", "witness_ok": False, "reason": ""}
    if not isinstance(witness, dict) or not witness:
        res["reason"] = "没有 witness——按铁律③ 只能是 unknown（" + GUIDE + "补证据）"
        return res
    need = [str(x) for x in item.get("witness") or []]
    missing = [x for x in need if x not in witness]
    res["witness_ok"] = not missing
    if item["layer"] == "review":
        res["verdict"] = "unknown"
        res["reason"] = ("外部盲评不能由本仓产出 pass（" + GUIDE + "只能用 review 件引用，"
                         "见 review:blind-review-protocol）")
        return res
    if missing:
        res["verdict"] = "unknown"
        res["reason"] = "witness 缺项：" + "、".join(missing) + "（" + GUIDE + "补齐后重评）"
        return res
    ok = bool(witness.get("ok", True))
    res["verdict"] = "pass" if ok else "fail"
    res["reason"] = str(witness.get("reason") or "按判据 how 执行并通过" if ok else "判据不通过")
    return res
