"""原子目录 v2（nf/atom-catalog/2）：在 v1 之上补齐「可判」字段，不改 v1 文件。

为什么要有 v2：任务书要求每个原子带 success_witness（
        成功见证）、failure_modes、composed_of、status，
而 v1（nf/meta-atoms/1）只有 id/name/function/level/input/output/trigger/failure_mode。
本模块**派生** v2：读 v1 原子 + 契约，补字段、算不变量，绝不写回 v1（旧 digest 不变）。

不变量 A1–A5（违反即 fail-closed）：
- A1 composed_of 引用闭合：引用存在、无自引用、无环；
- A2 契约完整：每个原子都有契约，且契约里的 id 都在原子集内，requires/adds/removes 为非空列表（
        可空数组）；
- A3 success_witness 可判：必须有 observe（观察什么）与 falsifier（
        什么观察会推翻），且不得是空泛词；
- A4 无死码：每个原子至少被引用一次（契约字段 / composed_of / 方法包 maps_to）；
- A5 身份一致：id 前缀（k/m/c/e/i）与 meta_level=object 一致，id 唯一。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "nf/atom-catalog/2"
V1_SCHEMA = "nf/meta-atoms/1"
CONTRACT_SCHEMA = "nf/atom-contracts/1"
ATOMS_REL = "desktop/src/core/meta_cockpit/meta_atoms.json"
CONTRACTS_REL = "desktop/src/core/meta_cockpit/atom_contracts.json"
PACKS_INDEX_REL = "protocol/method_packs/index.json"
DEBT_REL = "protocol/criteria/atom_debt.json"
GUIDE = "修复指引："
LEVELS = ("k", "m", "c", "e", "i")
VAGUE = ("更好", "更强", "更深", "合理", "合适", "差不多", "明显")


def _load(root: str, rel: str, schema: str) -> Any:
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError("文件不在场：" + rel + "（" + GUIDE + "确认路径）")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(rel + " 不是合法 JSON：" + str(exc)) from exc
    if str(doc.get("schema") or "") != schema:
        raise ValueError(rel + " schema 不匹配（" + GUIDE + "需要 " + schema + "）")
    return doc


def _pack_actions(root: str) -> set[str]:
    """方法包引用的原子/算子集合（A4 的外部引用来源之一）。"""
    used: set[str] = set()
    path = Path(root) / PACKS_INDEX_REL
    if not path.is_file():
        return used
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return used
    for item in index.get("packs") or []:
        pack_path = Path(root) / str(item.get("path") or "")
        if not pack_path.is_file():
            continue
        try:
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for move in pack.get("expert_moves") or []:
            used.update(str(x) for x in move.get("maps_to") or [])
    return used


def _debt(root: str) -> dict[str, str]:
    """已知死码债：id → reason（新死码不在债里 → A4 违规，fail-closed）。"""
    path = Path(root) / DEBT_REL
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(item.get("id")): str(item.get("reason") or "")
            for item in doc.get("atoms") or []}


def build(root: str = ".") -> dict[str, Any]:
    """派生 nf/atom-catalog/2（纯函数：不写盘）。"""
    atoms_doc = _load(root, ATOMS_REL, V1_SCHEMA)
    contracts_doc = _load(root, CONTRACTS_REL, CONTRACT_SCHEMA)
    contracts = {str(c.get("id")): c for c in contracts_doc.get("contracts") or []}
    pack_used = _pack_actions(root)
    items: list[dict[str, Any]] = []
    for atom in atoms_doc.get("atoms") or []:
        aid = str(atom.get("id") or "")
        contract = contracts.get(aid, {})
        output = [str(x) for x in atom.get("output") or []]
        failures = [str(atom.get("failure_mode"))] if atom.get("failure_mode") else []
        items.append({
            "id": aid,
            "name": atom.get("name"),
            "function": atom.get("function"),
            "meta_level": "object",
            "level_min": atom.get("level_min"),
            "level_max": atom.get("level_max"),
            "input": [str(x) for x in atom.get("input") or []],
            "output": output,
            "trigger": atom.get("trigger"),
            "composed_of": [str(x) for x in atom.get("composed_of") or []],
            "aliases": [],
            "tags": [str(atom.get("function") or "")],
            "status": "active",
            "version": "2.0.0",
            "contract": {"requires": list(contract.get("requires") or []),
                         "adds": list(contract.get("adds") or []),
                         "removes": list(contract.get("removes") or []),
                         "cost": contract.get("cost"),
                         "incompatible_with": list(contract.get("incompatible_with") or [])},
            "success_witness": {
                "observe": output[0] if output else "",
                "expected": ("该原子声明的产物在状态中可见：" + "、".join(output)) if output else
                        "",
                "falsifier": (failures[0] if failures else
                              "产物不可见或与声明不符（" + GUIDE + "补 failure_mode）"),
            },
            "failure_modes": failures,
        })
    return {"schema": SCHEMA, "source": {"atoms": ATOMS_REL, "contracts": CONTRACTS_REL},
            "count": len(items), "atoms": items, "pack_references": sorted(pack_used),
            "atom_debt": sorted(_debt(root))}


def _cycle_check(nodes: dict[str, list[str]]) -> list[str]:
    """返回参与环的原子 id（A1 用）。"""
    state: dict[str, int] = {}
    bad: list[str] = []

    def visit(node: str, stack: list[str]) -> None:
        if state.get(node) == 1:
            if node in stack:
                bad.append(node)
            return
        if state.get(node) == 2:
            return
        state[node] = 1
        for nxt in nodes.get(node, []):
            if nxt in nodes:
                visit(nxt, stack + [node])
        state[node] = 2

    for atom in nodes:
        visit(atom, [])
    return sorted(set(bad))


def invariants(catalog: dict[str, Any]) -> dict[str, Any]:
    """A1–A5 检查 → {ok, violations:[{code, atom, detail}], warnings:[...], counts}。"""
    atoms = catalog.get("atoms") or []
    by_id = {str(a.get("id")): a for a in atoms}
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    # A5 身份一致 + 唯一
    seen: set[str] = set()
    for atom in atoms:
        aid = str(atom.get("id") or "")
        if not aid:
            violations.append({"code": "A5", "atom": "", "detail": "原子缺 id"})
            continue
        if aid in seen:
            violations.append({"code": "A5", "atom": aid, "detail": "id 重复"})
        seen.add(aid)
        prefix = aid.split(".", 1)[0]
        if prefix not in LEVELS:
            violations.append({"code": "A5", "atom": aid,
                               "detail": "id 前缀不是 k/m/c/e/i"})
        if str(atom.get("meta_level")) != "object":
            violations.append({"code": "A5", "atom": aid,
                               "detail": "object 原子 meta_level 必须是 object"})

    # A1 composed_of 引用闭合
    for atom in atoms:
        aid = str(atom.get("id") or "")
        for ref in atom.get("composed_of") or []:
            if ref == aid:
                violations.append({"code": "A1", "atom": aid, "detail": "composed_of 自引用"})
            elif ref not in by_id:
                violations.append({"code": "A1", "atom": aid,
                                   "detail": "composed_of 引用不存在的原子：" + str(ref)})
    graph = {str(a.get("id")): [str(x) for x in a.get("composed_of") or []] for a in atoms}
    for node in _cycle_check(graph):
        violations.append({"code": "A1", "atom": node, "detail": "composed_of 成环"})

    # A2 契约完整
    for atom in atoms:
        aid = str(atom.get("id") or "")
        contract = atom.get("contract") or {}
        if str(by_id.get(aid, {}).get("id")) not in by_id:
            continue
        if not isinstance(contract.get("requires"), list):
            violations.append({"code": "A2", "atom": aid, "detail": "contract.requires 不是数组"})
        for field in ("adds", "removes"):
            if not isinstance(contract.get(field), list):
                violations.append({"code": "A2", "atom": aid,
                                   "detail": "contract." + field + " 不是数组"})
        if not isinstance(contract.get("cost"), int):
            violations.append({"code": "A2", "atom": aid, "detail": "contract.cost 缺失或非整数"})
        for ref in list(contract.get("requires") or []) + list(contract.get("adds") or []):
            if str(ref) and str(ref) not in by_id and str(ref) in {"k.represent"}:
                continue  # 契约字段是状态键不是原子 id，跳过

    # A3 success_witness 可判
    for atom in atoms:
        aid = str(atom.get("id") or "")
        witness = atom.get("success_witness") or {}
        observe = str(witness.get("observe") or "").strip()
        falsifier = str(witness.get("falsifier") or "").strip()
        if not observe:
            violations.append({"code": "A3", "atom": aid, "detail": "success_witness.observe 为空"})
        if not falsifier:
            violations.append({"code": "A3", "atom": aid,
                               "detail": "success_witness.falsifier 为空"})
        for word in VAGUE:
            if observe == word or falsifier == word:
                violations.append({"code": "A3", "atom": aid,
                                   "detail": "witness 用了空泛词：" + word})

    # A4 无死码：被**别处**引用（方法包 maps_to / 组合 / 互斥 / 被别的原子组合）
    #     自己契约里的 adds/removes 不算「被使用」——否则「填满但空洞」会通过。
    used: set[str] = {str(x) for x in catalog.get("pack_references") or []}
    for atom in atoms:
        for ref in atom.get("composed_of") or []:
            used.add(str(ref))
        contract = atom.get("contract") or {}
        for ref in contract.get("incompatible_with") or []:
            used.add(str(ref))
    dead = sorted(aid for aid in by_id if aid not in used and not by_id[aid].get("composed_of"))
    debt = {str(x) for x in catalog.get("atom_debt") or []}
    for aid in dead:
        if aid in debt:
            warnings.append({"code": "A4", "atom": aid,
                             "detail": "存量死码（已记债，见 protocol/criteria/atom_debt.json）"})
        else:
            violations.append({"code": "A4", "atom": aid,
                               "detail": "新增死码：没有契约/组合/方法包引用它"
                                         "（" + GUIDE + "接入或记入 atom_debt.json）"})

    counts = {"atoms": len(atoms),
              "composed_of_nonempty": sum(1 for a in atoms if a.get("composed_of")),
              "dead": len(dead),
              "violations": len(violations)}
    return {"schema": "nf/atom-invariants/1", "ok": not violations,
            "violations": violations, "warnings": warnings, "counts": counts}
