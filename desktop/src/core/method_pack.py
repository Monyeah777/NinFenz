"""方法包（Method Pack）v0：把「专业领域的专家动作 + 证据标准」做成可校验、可组合的数据。

为什么单独一层（2026-11-08）：认知核的 15 meta moves 与 33 对象原子是领域中立的——它们知道
「要验证」「要拆分」，但不知道「这个领域什么算证据」。LLM 元认知研究把这类知识分成
陈述性（是什么）/ 程序性（怎么做）/ 条件性（何时用），领域专业性正落在后两项；通用原子给不了。
方法包就是这两项的可执行载体：expert_moves（怎么做）+ evidence_standards（什么算证据）+
common_failures（常见错法）+ examples（范例）。

纪律（与仓内一致）：
- 包是数据：新增领域 = 加一个 JSON，不改代码；schema 校验失败即拒（fail-closed）；
- 每个 expert move 必须 maps_to 到已存在的原子/算子 id（防「包里的词没人能执行」）；
- evidence_standards 必须给 claim_kind 与 required 列表（防「只说重要不说要交什么」）；
- 组合（compose）只做并集去重，序稳定，不评分、不排序优先级（避免把专业变成打分）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core import json_doc

SCHEMA = "nf-method-pack/1"
INDEX_SCHEMA = "nf-method-pack-index/1"
INDEX_REL = "protocol/method_packs/index.json"
GUIDE = "修复指引："

#: 可被 maps_to 引用的动作 id（对象面 33 原子 + 元面 11 算子 + 15 meta moves）
OBJECT_ATOMS = (
    "k.represent", "k.partition", "k.relate", "k.abstract", "k.define", "k.instantiate",
    "k.classify", "k.quantify", "k.criterion", "k.standard",
    "m.observe", "m.compare", "m.check", "m.estimate", "m.detect", "m.trace",
    "c.select", "c.sequence", "c.allocate", "c.switch", "c.stop",
    "e.verify", "e.falsify", "e.adjudicate", "e.audit", "e.calibrate", "e.benchmark",
    "i.merge", "i.reconcile", "i.cluster", "i.hierarchy", "i.compose", "i.transfer",
)
META_OPERATORS = ("observe", "estimate", "detect", "calibrate", "allocate", "switch",
                  "stop", "abstain", "revise", "request_context", "audit")
META_MOVES = ("reframe", "bracket", "conceptual_analysis", "dialectic", "thought_experiment",
              "counterexample", "analogy", "perspective_shift", "value_conflict", "genealogy",
              "reductio", "boundary_case", "steelman", "meta_question", "decomposition")
KNOWN_ACTIONS = set(OBJECT_ATOMS) | set(META_OPERATORS) | set(META_MOVES)


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise ValueError("文件不存在：" + str(path)
                         + "（" + GUIDE + "确认路径，或先恢复 protocol/method_packs/）")
    try:
        return json_doc.load(path, dict, what=str(path))
    except (OSError, ValueError) as exc:
        raise ValueError(str(path) + " 不可读或不是合法 JSON：" + str(exc)
                         + "（" + GUIDE + "修好语法后重跑）") from exc


def _pack_head_issues(doc: dict[str, Any]) -> list[str]:
    """包头三字段（id/version/domain）必填。"""
    issues: list[str] = []
    for field in ("id", "version", "domain"):
        if not str(doc.get(field) or "").strip():
            issues.append("包缺 " + field + "（" + GUIDE + "补齐后重跑）")
    return issues


def _move_maps_issues(mv: dict[str, Any], label: str) -> list[str]:
    """expert_move 的 maps_to：非空且只能引用已知动作。"""
    issues: list[str] = []
    maps = mv.get("maps_to")
    if not isinstance(maps, list) or not maps:
        issues.append("expert_move " + label + " 缺 maps_to（" + GUIDE +
                      "必须映射到已知动作）")
        return issues
    unknown = [str(x) for x in maps if str(x) not in KNOWN_ACTIONS]
    if unknown:
        issues.append("expert_move " + label + " 的 maps_to 含未知动作：" +
                      str(unknown)
                      + "（" + GUIDE + "只能引用 33 原子 / 11 算子 / 15 meta move）")
    return issues


def _move_issues(mv: Any, i: int, seen: set[str]) -> list[str]:
    """单条 expert_move：对象化、id 唯一、name/why 非空、maps_to 可解析。"""
    if not isinstance(mv, dict):
        return ["第 " + str(i) + " 条 expert_move 不是对象（" + GUIDE + "改写成对象）"]
    issues: list[str] = []
    mid = str(mv.get("id") or "").strip()
    if not mid:
        issues.append("第 " + str(i) + " 条 expert_move 缺 id（" + GUIDE + "给唯一 id）")
    elif mid in seen:
        issues.append("expert_move id 重复：" + mid + "（" + GUIDE + "改成唯一 id）")
    else:
        seen.add(mid)
    label = mid or str(i)
    if not str(mv.get("name") or "").strip():
        issues.append("expert_move " + label + " 缺 name（" + GUIDE + "写清动作名）")
    if not str(mv.get("why") or "").strip():
        issues.append("expert_move " + label + " 缺 why（" + GUIDE +
                      "说明为何这一步必要）")
    issues.extend(_move_maps_issues(mv, label))
    return issues


def _standard_item_issues(st: Any, i: int) -> list[str]:
    """单条 evidence_standard：对象化、claim_kind 非空、required 非空。"""
    if not isinstance(st, dict):
        return ["第 " + str(i) + " 条 evidence_standard 不是对象（" + GUIDE +
                "改写成对象）"]
    issues: list[str] = []
    if not str(st.get("claim_kind") or "").strip():
        issues.append("第 " + str(i) + " 条 evidence_standard 缺 claim_kind（" + GUIDE +
                      "写清哪类主张）")
    need = st.get("required")
    if not isinstance(need, list) or not need:
        issues.append("第 " + str(i) + " 条 evidence_standard 的 required 为空（" + GUIDE +
                      "写清要交出什么）")
    return issues


def _standards_issues(stds: Any) -> list[str]:
    """evidence_standards：非空列表 + 逐条形状。"""
    if not isinstance(stds, list) or not stds:
        return ["包缺 evidence_standards（" + GUIDE + "至少一条：这个领域什么算证据）"]
    issues: list[str] = []
    for i, st in enumerate(stds, 1):
        issues.extend(_standard_item_issues(st, i))
    return issues


def validate_pack(doc: Any) -> list[str]:
    """单包形状校验 → 问题列表（空 = 合法）。"""
    issues: list[str] = []
    if not isinstance(doc, dict) or str(doc.get("schema") or "") != SCHEMA:
        return ["方法包 schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）"]
    issues.extend(_pack_head_issues(doc))
    moves = doc.get("expert_moves")
    if not isinstance(moves, list) or not moves:
        issues.append("包缺 expert_moves（" + GUIDE + "至少一条专家动作）")
        return issues
    seen: set[str] = set()
    for i, mv in enumerate(moves, 1):
        issues.extend(_move_issues(mv, i, seen))
    issues.extend(_standards_issues(doc.get("evidence_standards")))
    if not isinstance(doc.get("common_failures"), list) or not doc.get("common_failures"):
        issues.append("包缺 common_failures（" + GUIDE +
                "至少列一条常见错法——它比正确做法更能防错）")
    return issues


def load_index(root: str = ".") -> dict[str, Any]:
    doc = _load_json(Path(root) / INDEX_REL)
    if str(doc.get("schema") or "") != INDEX_SCHEMA:
        raise ValueError("索引 schema 不匹配（" + GUIDE + "需要 " + INDEX_SCHEMA + "）")
    packs = doc.get("packs")
    if not isinstance(packs, list) or not packs:
        raise ValueError("索引里没有 packs（" + GUIDE + "至少登记一个包）")
    return doc


def list_packs(root: str = ".") -> list[dict[str, Any]]:
    out = []
    for item in load_index(root)["packs"]:
        out.append({"id": str(item.get("id") or ""), "version": str(item.get("version") or ""),
                    "path": str(item.get("path") or "")})
    return out


def load_pack(root: str, pack_id: str) -> dict[str, Any]:
    for item in load_index(root)["packs"]:
        if str(item.get("id") or "") != pack_id:
            continue
        rel = str(item.get("path") or "")
        doc = _load_json(Path(root) / rel)
        issues = validate_pack(doc)
        if issues:
            raise ValueError("方法包 " + pack_id + " 不合法：" + "；".join(issues[:3]))
        if str(doc.get("id")) != pack_id:
            raise ValueError("索引 id 与包内 id 不一致（" + GUIDE + pack_id + " vs " +
                    str(doc.get("id")) +
                "）")
        doc["_path"] = rel
        return doc
    raise ValueError("未知方法包：" + pack_id + "（" + GUIDE + "可用见 nf cognition packs）")


def obligations(pack: dict[str, Any], claim_kind: str = "") -> dict[str, Any]:
    stds = list(pack.get("evidence_standards") or [])
    if claim_kind:
        hit = [st for st in stds if str(st.get("claim_kind")) == claim_kind]
        if not hit:
            raise ValueError("方法包 " + str(pack.get("id")) + " 没有 claim_kind=" +
                    repr(claim_kind)
                             + " 的证据标准（" + GUIDE + "可选："
                             + ", ".join(str(s.get("claim_kind")) for s in stds) + "）")
        stds = hit
    return {"schema": "nf-method-obligations/1", "pack": str(pack.get("id")),
            "claim_kind": claim_kind, "standards": [
                {"claim_kind": st.get("claim_kind"), "required": list(st.get("required") or [])}
                for st in stds]}


def _compose_moves(packs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """专家动作并集（按 id 去重，序稳定）。"""
    moves: list[dict[str, Any]] = []
    seen_moves: set[str] = set()
    for pack in packs:
        for mv in pack.get("expert_moves") or []:
            mid = str(mv.get("id") or "")
            if mid in seen_moves:
                continue
            seen_moves.add(mid)
            moves.append({"id": mid, "name": mv.get("name"),
                          "maps_to": list(mv.get("maps_to") or []),
                          "why": mv.get("why"), "from": str(pack.get("id"))})
    return moves


def _compose_standards(packs: list[dict[str, Any]]
                       ) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """证据标准按 claim_kind 归并（required 去重，from 记来源包，序稳定）。"""
    by_kind: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for pack in packs:
        for st in pack.get("evidence_standards") or []:
            kind = str(st.get("claim_kind") or "")
            if kind not in by_kind:
                by_kind[kind] = {"claim_kind": kind, "required": [], "from": []}
                order.append(kind)
            src = by_kind[kind]
            for item in st.get("required") or []:
                if item not in src["required"]:
                    src["required"].append(item)
            if str(pack.get("id")) not in src["from"]:
                src["from"].append(str(pack.get("id")))
    return by_kind, order


def _compose_failures(packs: list[dict[str, Any]]) -> list[str]:
    """常见错法并集（去重，序稳定）。"""
    failures: list[str] = []
    for pack in packs:
        for item in pack.get("common_failures") or []:
            if item not in failures:
                failures.append(item)
    return failures


def compose(packs: list[dict[str, Any]]) -> dict[str, Any]:
    """多包组合 → 去重后的专家动作与证据标准（序稳定，不评分不排序）。"""
    if not packs:
        raise ValueError("组合至少需要一个方法包（" + GUIDE + "给 --pack 一次或多次）")
    moves = _compose_moves(packs)
    by_kind, order = _compose_standards(packs)
    failures = _compose_failures(packs)
    return {"schema": "nf-method-compose/1",
            "packs": [str(p.get("id")) for p in packs],
            "expert_moves": moves,
            "evidence_standards": [by_kind[k] for k in order],
            "common_failures": failures}


CHECKLIST_SCHEMA = "nf-method-checklist/1"


def _checklist_items(moves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """动作 → 可执行清单条目（step 按包内顺序编号）。"""
    items = []
    for mv in moves:
        items.append({
            "step": len(items) + 1,
            "move": str(mv.get("id")),
            "do": str(mv.get("name")),
            "why": str(mv.get("why")),
            "kind": str(mv.get("kind") or "advisory"),
        })
    return items


def _checklist_stds(stds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """证据标准 → 清单附带的 claim_kind/required 投影。"""
    return [{"claim_kind": str(st.get("claim_kind")),
             "required": list(st.get("required") or [])} for st in stds]


def checklist(pack: dict[str, Any]) -> dict[str, Any]:
    """把一个方法包变成**可执行清单**：每个动作一条，附「为什么」与该类证据要求。

    为什么要这层（第 68 轮）：方法包此前只有两份用法——列出来看、编进主张义务；
    都不回答「现在这一步该做什么」。清单把包从「文档」变成「可照着做的东西」，
    仍然不评分、不排序，只按包内顺序输出。
    """
    bad = validate_pack(pack)
    if bad:
        raise ValueError("方法包不合法：" + "；".join(bad[:2]))
    moves = list(pack.get("expert_moves") or [])
    stds = list(pack.get("evidence_standards") or [])
    items = _checklist_items(moves)
    # 第 144 轮：清单带上「这个域怎么跑」（可跑入口），把包与命令接起来。
    runnable = [str(x) for x in (pack.get("runnable") or []) if str(x).strip()]
    return {"schema": CHECKLIST_SCHEMA, "pack": str(pack.get("id")),
            "domain": str(pack.get("domain") or ""),
            "items": items,
            "runnable": runnable,
            "evidence_standards": _checklist_stds(stds),
            "note": "按包内顺序；不评分不排序。每条动作要求的是「做一次并留证」，不是打卡"}


def vocabulary_mismatches(packs: list[dict[str, Any]],
                          registry: dict[str, Any]) -> dict[str, list[str]]:
    """claim_kind 词表核对：包用了未登记词 / 词表里有死词（两边都要报）。

    为什么单独成函数（第 72 轮）：判据需要**能被变异打死**——只有把核对逻辑抽出来，
    才可能用一份「故意改坏」的 registry 证明它真的会红，而不是只在真实数据上碰巧为空。
    """
    vocab = {str(x) for x in (registry.get("claim_kinds") or [])}
    used: set[str] = set()
    for pack in packs:
        for std in pack.get("evidence_standards") or []:
            used.add(str(std.get("claim_kind")))
    return {"unknown": sorted(used - vocab), "unused": sorted(vocab - used)}
