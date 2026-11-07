"""活体认知驾驶舱：每轮读 need → 组合 1-3 个原子 → 想一步 → 重新读 need。

无评分、无固定全程计划、无回执驱动。评分/审计属于外部质量门，不参与驾驶。
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

from . import calibration_ledger as cal_ledger
from . import calibration_store as cal_store
from . import coherence, domain_sources, epistemic_agenda, method_memory, task_profile
from . import live_selector as ls
from . import meta_atom_runtime as atoms
from . import metacognitive_control as control

REQ_KEYS = ("生存", "经济", "战斗", "死亡重生", "失败成本", "回滚", "风险", "对比")
REL_MAP = {
    "生存": ["P03 §1", "M10"],
    "经济": ["P03 §5", "M11"],
    "战斗": ["P03 §2", "M04"],
    "死亡重生": ["P03 §6", "生存:M10"],
    "失败成本": ["P03 §6", "M80"],
    "回滚": ["techdoc", "M00"],
    "风险": ["techdoc", "M00"],
    "对比": ["P03", "NF-1"],
}
TECH_TERMS = (
    "回滚",
    "发布",
    "数据库",
    "技术",
    "系统",
    "状态快照",
    "文档",
    "迁移",
    "停机",
    "切换",
    "校验",
    "失败",
    "恢复",
    "故障",
    "检测",
)
BUSINESS_TERMS = ("市场", "商业", "成本", "供给", "信任", "用户", "增长", "平台", "决策")
GAME_TERMS = ("游戏", "玩法", "生存流", "西幻", "战斗", "死亡重生", "刷怪")


def select_references(prompt: str) -> list[dict]:
    domain = domain_sources.select_for_text(prompt, limit=2, include_adjacent=True)
    domain_refs = (
        [
            {
                "source": item["id"],
                "ref": "README",
                "keywords": item["keywords"],
                "context_only": item["match_tier"] == "adjacent",
            }
            for item in domain
        ]
        if domain
        else []
    )
    if domain_refs:
        if any(term in prompt for term in GAME_TERMS):
            return domain_refs + [{"source": "P03", "ref": "§1"}]
        if any(term in prompt for term in TECH_TERMS):
            return domain_refs + [{"source": "techdoc", "ref": "§1"}]
        return domain_refs
    if any(term in prompt for term in TECH_TERMS) and not any(
        term in prompt for term in GAME_TERMS
    ):
        return [{"source": "techdoc", "ref": "§1"}, {"source": "NF-1", "ref": "§2"}]
    if any(term in prompt for term in BUSINESS_TERMS) and not any(
        term in prompt for term in GAME_TERMS
    ):
        return [{"source": "NF-1", "ref": "§2"}, {"source": "techdoc", "ref": "§1"}]
    if any(term in prompt for term in GAME_TERMS):
        return [
            {"source": "P03", "ref": "§1"},
            {"source": "NF-1", "ref": "§2"},
            {"source": "techdoc", "ref": "§1"},
        ]
    return [{"source": "NF-1", "ref": "§2"}]


def initial_state(prompt: str) -> dict:
    state = {
        "goal": prompt,
        "reference": select_references(prompt),
        "artifact": {
            "representation": "",
            "parts": [],
            "definitions": [],
            "relations": [],
            "trace": [],
            "risks": [],
            "resolutions": [],
            "abstract": "",
            "plan": [],
            "evidence": [],
            "verified": False,
        },
        "open_questions": [],
        "budget": {"envelope": 3},
        "budget_state": {"remaining": 3},
        "fallback": {"action": "stop"},
        "context_units_spent": 0,
        "turn": 0,
        "history": [],
        "error": "",
    }
    profile = task_profile.build(prompt)
    if set(profile["modes"]) & {"audit", "decide"}:
        state["frame"] = {
            "source": "task-profile",
            "rows": [
                {
                    "dimension": facet,
                    "primitive": "invariant",
                    "unit": "invariant",
                    "threshold": True,
                    "granularity": 1,
                }
                for facet in profile["required_facets"]
            ],
        }
    if "decide" in profile["modes"]:
        state["options"] = [
            {"id": "maintain"},
            {"id": "change"},
            {"id": "defer"},
        ]
    state["history_root"] = method_memory.core_signature(state)
    return state


def parts_from(prompt: str) -> list[str]:
    found = [k for k in REQ_KEYS if k in prompt]
    clauses = [x.strip() for x in re.split(r"[，。；、,;]", prompt) if x.strip()]
    if len(found) >= 2:
        return found
    if found:
        parts = list(clauses)
        parts += [term for term in found if not any(term in clause for clause in clauses)]
        return parts or found
    return clauses or ["目标"]


def infer_need(s: dict) -> str:
    a = s["artifact"]
    if s["open_questions"]:
        return "resolve"
    if not a["parts"]:
        return "understand"
    if not a["relations"]:
        return "relate"
    if not a["risks"]:
        return "challenge"
    if not a["plan"]:
        return "synthesize"
    if not a["verified"]:
        return "ground"
    return "done"


def compose(s: dict, ledger: dict | None = None) -> list[str]:
    d = control.decide_compiled(s, ledger)
    if d is None:
        d = control.decide(s, ledger)
    s["_last_decision"] = d
    return d["cluster"]


def _payload(s: dict) -> dict:
    payload = copy.deepcopy(s["artifact"])
    for key, value in s.items():
        if key in ("artifact", "history") or key.startswith("_"):
            continue
        if value not in ("", [], {}, None, False):
            payload[key] = copy.deepcopy(value)
    payload["target"] = s.get("target", s["goal"])
    payload["reference"] = s.get("reference") or select_references(s["goal"])
    unmet = ls.unmet(s)
    if len(unmet) >= 2:
        payload["options"] = [{"id": need} for need in unmet]
    return payload


def _met(s: dict) -> dict:
    a = s["artifact"]
    return {
        "structure": bool(a["parts"]),
        "relations": bool(a["relations"]),
        "risks": bool(a["risks"]),
        "synthesis": bool(a["plan"]),
        "grounding": bool(a["verified"]),
        "resolve": not bool(s["open_questions"]),
    }


def _enrich(s: dict, atom_id: str, output: dict | None = None) -> None:
    a = s["artifact"]
    parts = a["parts"] or parts_from(s["goal"])
    if atom_id == "k.represent":
        a["representation"] = s["goal"]
    elif atom_id == "k.partition":
        a["parts"] = parts
    elif atom_id == "k.define":
        a["definitions"] = [f"{part}：目标中的边界、状态与验收条件。" for part in parts]
    elif atom_id == "k.relate":
        rels = [f"{left} → {right}" for left, right in zip(parts, parts[1:], strict=False)]
        for p in parts:
            rels += [f"{p} → {ref}" for ref in REL_MAP.get(p, [])]
        if len(parts) == 1:
            rels.append("{} → {}".format(s["goal"], parts[0]))
        a["relations"] = sorted(set(rels))
    elif atom_id == "m.trace":
        a["trace"] = sorted(
            {
                item["source"]
                for item in _payload(s)["reference"]
                if not item.get("context_only", False)
            }
        )
    elif atom_id == "e.falsify":
        risks = [f"若「{part}」缺少可观察状态或回退路径，相关结论不可验证。" for part in parts]
        risks.append("若各部分之间的约束相互冲突，组合结构会在执行阶段断裂。")
        a["risks"] = risks
    elif atom_id == "i.reconcile":
        q = s["open_questions"].pop(0) if s["open_questions"] else "未命名缺口"
        a["resolutions"].append({"question": q, "resolution": "把缺口转成可观察状态与回退路径。"})
    elif atom_id == "k.abstract":
        a["abstract"] = "目标由 {} 组成；各部分的约束、反馈与失败成本必须闭合。".format(
            "、".join(parts)
        )
    elif atom_id == "i.compose":
        a["plan"] = [
            "1. 明确目标边界、输入与验收状态。",
            "2. 定义 {} 的约束与相互作用。".format("、".join(parts)),
            "3. 为每个部分建立可观察机制与反馈回路。",
            "4. 设计反例、失败成本、停止条件与回退路径。",
            "5. 用 NF 证据核验结构完整性与可执行性。",
        ]
    elif atom_id == "e.verify":
        a["evidence"] = list(a["trace"] or select_references(s["goal"]))
        a["verified"] = True
    # 其余原子按契约把执行器输出投影到共享状态；已有语义值不覆盖。
    contract = ls.CONTRACTS.get(atom_id)
    if contract and output:
        for key in contract["adds"]:
            if key in output and not a.get(key):
                value = output[key]
                if key == "definitions" and isinstance(value, str):
                    value = [value]
                a[key] = copy.deepcopy(value)
        spec_out = atoms.SPECS[atom_id]["out"]
        missing_adds = [key for key in contract["adds"] if not a.get(key)]
        if spec_out in output and len(missing_adds) == 1:
            a[missing_adds[0]] = copy.deepcopy(output[spec_out])
        for key in contract["removes"]:
            if key == "open_questions":
                s["open_questions"] = []
            else:
                a.pop(key, None)


def execute_cluster(s: dict, cluster: list[str], thought_patch: dict | None = None) -> dict:
    """事务式执行一个 1-3 原子簇。

    先在状态副本上执行；任一原子失败则不提交任何前缀状态。
    返回的 state 是新副本，调用方可将其作为下一轮唯一合法状态。
    """
    if not 1 <= len(cluster) <= 3 or len(set(cluster)) != len(cluster):
        return {
            "status": "fail",
            "state": s,
            "resolved": [],
            "error": "cluster must contain 1-3 unique atoms",
            "atom_trace": [],
        }
    if thought_patch is not None:
        issues = epistemic_agenda.validate_thought_patch({"cluster": cluster}, thought_patch)
        if issues:
            return {
                "status": "fail",
                "state": s,
                "resolved": [],
                "error": "thought patch: " + "; ".join(issues),
                "atom_trace": [],
            }
    before_keys = ls.available_keys(s)
    before = _met(s)
    work = copy.deepcopy(s)
    atom_trace = []
    for atom_id in cluster:
        res = atoms.execute_atom(atom_id, _payload(work))
        atom_trace.append(
            {
                "atom_id": atom_id,
                "status": res["status"],
                "input_digest": res["input_digest"],
                "output_digest": res["output_digest"],
            }
        )
        if res["status"] != "pass":
            return {
                "status": "fail",
                "state": s,
                "resolved": [],
                "error": "{}: {}".format(atom_id, res["error"]),
                "atom_trace": atom_trace,
            }
        _enrich(work, atom_id, res["output"])
        if thought_patch:
            for key in ls.CONTRACTS[atom_id]["adds"]:
                if key in thought_patch:
                    work["artifact"][key] = copy.deepcopy(thought_patch[key])
    after_keys = ls.available_keys(work)
    after = _met(work)
    resolved = [k for k in before if not before[k] and after[k]]
    unresolved = epistemic_agenda.unresolved_after(work, resolved)
    if unresolved:
        return {
            "status": "fail",
            "state": s,
            "resolved": [],
            "error": "thought patch did not close: " + ",".join(unresolved),
            "atom_trace": atom_trace,
        }
    if thought_patch is not None:
        regressions = coherence.new_issue_ids(s, work)
        if regressions:
            return {
                "status": "fail",
                "state": s,
                "resolved": [],
                "error": "thought patch introduced incoherence: " + ",".join(regressions),
                "atom_trace": atom_trace,
            }
    return {
        "status": "pass",
        "state": work,
        "resolved": resolved,
        "error": "",
        "atom_trace": atom_trace,
        "changed_keys": sorted(after_keys - before_keys),
    }


def think(
    prompt: str,
    injections: dict | None = None,
    max_turns: int = 8,
    store_path: str | Path | None = None,
) -> tuple[dict, list[dict]]:
    s = initial_state(prompt)
    store_file = Path(store_path) if store_path is not None else None
    if store_file is not None:
        store, status = cal_store.load(store_file)
        ledger = store["atoms"]
        s["store_status"] = status
        if status.startswith("tampered:"):
            s["error"] = "calibration store: " + status
            return s, []
    else:
        store = None
        ledger = cal_ledger.initial_ledger()
    injections = injections or {}
    trace = []
    while s["turn"] < max_turns:
        if s["turn"] in injections:
            s["open_questions"].append(injections[s["turn"]])
        need = infer_need(s)
        if need == "done":
            break
        cluster = compose(s, ledger)
        d = s.get("_last_decision", {})
        if d.get("action") == "stop":
            trace.append(
                {
                    "turn": s["turn"] + 1,
                    "need": need,
                    "goal": None,
                    "cluster": [],
                    "resolved": [],
                    "calibration_error": 0,
                    "action": "stop",
                    "reason": d.get("reason"),
                    "changed": False,
                    "reliability_band": "n/a",
                }
            )
            break
        before_keys = ls.available_keys(s)
        applied = execute_cluster(s, cluster)
        if applied["status"] != "pass":
            s["error"] = applied["error"]
            break
        after_keys = ls.available_keys(applied["state"])
        actual = applied["resolved"]
        cal = control.calibration(d.get("resolves", []), actual)
        if cal["error"] > 0:
            s["error"] = f"calibration mismatch: {cal}"
            break
        s = applied["state"]
        cal_ledger.observe(ledger, cluster, after_keys)
        rel_band = cal_ledger.band(cal_ledger.avg_reliability(ledger, cluster))
        trace.append(
            {
                "turn": s["turn"] + 1,
                "need": need,
                "cluster": cluster,
                "goal": d.get("goal"),
                "resolved": actual,
                "calibration_error": cal["error"],
                "reliability_band": rel_band,
                "action": d.get("action", "continue"),
                "changed": before_keys != after_keys,
            }
        )
        s["turn"] += 1
        if before_keys == after_keys and not s["open_questions"]:
            break
    if store is not None and store_file is not None:
        saved = cal_store.save(store_file, store)
        s["calibration_rounds"] = saved["rounds"]
    return s, trace
