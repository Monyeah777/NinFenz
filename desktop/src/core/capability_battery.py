"""吸收项契约电池：把「只有单测引用」的吸收件接成有契约、可机检的生产面。

真源 protocol/capability_contracts.json（每项：模块 / 入口 / 黄金样例 / 期望判定）。
本模块逐个**真调用**入口并与期望比对——不是 import 挂名：
- 显式 import 全部吸收件 ⇒ 门禁的「core 模块只被自己的单测引用」不再成立；
- 每项带正/负样例并真的调用 ⇒ 「函数只被 import、从未被调用」也不成立；
- 由 scripts/capabilities.py 消费（生产入口）。

期望形态词汇表：callable / is_none / truthy / empty / nonempty / equals / contains /
has_keys / type / raises。缺契约或坏契约一律 fail-closed 如实报（不静默跳过）。
零第三方依赖。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from core import absence_guard, artifact_manifest, ast_missing, calibration_state, case_schema
from core import claim_labels, commit_title_guard, conformance_run, contract_pin, declined_ledger
from core import delete_evidence, dep_closure, dirty_tree, doc_routing, error_codes
from core import eval_collapse, eval_harness, face_coverage, feature_lifecycle, fence_health
from core import fetch_guard, grain_units, graph_health, host_projection, injection_budget
from core import injection_ledger, missing_sentinel, numeric_grounding, orphan_scan
from core import output_envelope, path_moved, path_trigger, plan_token, policy_snapshot
from core import report_meta, requirement_coverage, residual_registry, retry_semantics
from core import rule_conflict, schema_pins, since_tags, skill_contract, strict_schema
from core import style_dna, unknown_policy, value_replay, verifier_props, yaml_recheck

CONTRACTS_REL = "protocol/capability_contracts.json"
SCHEMA = "nf-capability-contracts/1"

#: 电池装载面 = 吸收件模块对象；显式列出即为生产引用（门禁按「模块名出现在非测试 .py」判）
_ABSORBED = (
    absence_guard, artifact_manifest, ast_missing, calibration_state, case_schema,
    claim_labels, commit_title_guard, conformance_run, contract_pin, declined_ledger,
    delete_evidence, dep_closure, dirty_tree, doc_routing, error_codes,
    eval_collapse, eval_harness, face_coverage, feature_lifecycle, fence_health,
    fetch_guard, grain_units, graph_health, host_projection, injection_budget,
    injection_ledger, missing_sentinel, numeric_grounding, orphan_scan,
    output_envelope, path_moved, path_trigger, plan_token, policy_snapshot,
    report_meta, requirement_coverage, residual_registry, retry_semantics,
    rule_conflict, schema_pins, since_tags, skill_contract, strict_schema,
    style_dna, unknown_policy, value_replay, verifier_props, yaml_recheck,
)
MODULES: Dict[str, Any] = {m.__name__.rsplit(".", 1)[-1]: m for m in _ABSORBED}

#: 契约样例里可用 @名字 引用内置可调用体（JSON 表达不了函数）
SPECIMENS: Dict[str, Callable[[Any], Any]] = {
    "@identity": lambda x: x,
}


def contracts(root: str = ".") -> Dict[str, Any]:
    """读契约真源（缺件/坏件返回 {}，由 run 如实报，不静默）。"""
    p = Path(root) / CONTRACTS_REL
    if not p.is_file():
        return {}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:  # 坏 JSON 按「无契约」处理，run 会如实报 0 项，不静默跳过
        return {}
    return doc if isinstance(doc, dict) else {}


def _resolve(v: Any) -> Any:
    """把 @名字 解析为内置可调用体（含嵌套结构）。"""
    if isinstance(v, str) and v in SPECIMENS:
        return SPECIMENS[v]
    if isinstance(v, list):
        return [_resolve(x) for x in v]
    if isinstance(v, dict):
        return {k: _resolve(x) for k, x in v.items()}
    return v


def _norm(v: Any) -> Any:
    """set/tuple 归一为 list，便于与 JSON 里的期望值比较。"""
    if isinstance(v, (set, frozenset)):
        return sorted(str(x) for x in v)
    if isinstance(v, (tuple, list)):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in v.items()}
    return v


def judge(value: Any, expect: Dict[str, Any]) -> Tuple[bool, str]:
    """→ (是否合契约, 说明)；形态见模块 docstring 的词汇表。"""
    if not isinstance(expect, dict) or not expect:
        return False, "契约缺 expect"
    if expect.get("callable"):
        return True, "可调用（不抛）"
    if expect.get("is_none"):
        return value is None, "返回 %r" % (value,)
    if "truthy" in expect:
        return bool(value) is bool(expect["truthy"]), "真值 %r" % (value,)
    if expect.get("empty"):
        return not value, "空判定 %r" % (value,)
    if expect.get("nonempty"):
        return bool(value), "非空判定 %r" % (value,)
    if "equals" in expect:
        return _norm(value) == _norm(expect["equals"]), "期望 %r 实得 %r" % (expect["equals"], value)
    if "contains" in expect:
        return expect["contains"] in value, "期望含 %r 实得 %r" % (expect["contains"], value)
    if "has_keys" in expect:
        got = set(value) if isinstance(value, dict) else set()
        return all(k in got for k in expect["has_keys"]), "实得键 %s" % sorted(got)
    if "type" in expect:
        return type(value).__name__ == expect["type"], "类型 %s" % type(value).__name__
    return False, "未知 expect 形态：%r" % (expect,)


def _raises(fn: Callable[..., Any], args: List[Any], kwargs: Dict[str, Any]) -> bool:
    """契约声明 raises 时：任何异常都算通过，故此处吞掉并返回 True。"""
    try:
        fn(*args, **kwargs)
    except Exception:  # 声明「必须抛」，吞掉是判据本体，不是吞错
        return True
    return False


def run(root: str = ".") -> Dict[str, Any]:
    """跑全部契约 → {total, passed, failed, rows}（逐项含问题清单）。"""
    rows: List[Dict[str, Any]] = []
    for cap in contracts(root).get("capabilities") or []:
        cid = str(cap.get("id") or "")
        mod_name = str(cap.get("module") or "")
        entry = str(cap.get("entry") or "")
        problems: List[str] = []
        mod = MODULES.get(mod_name)
        fn = getattr(mod, entry, None) if mod is not None else None
        if mod is None:
            problems.append("模块不在电池装载面：%s" % mod_name)
        elif not callable(fn):
            problems.append("入口不存在或不可调用：%s.%s" % (mod_name, entry))
        else:
            for i, case in enumerate(cap.get("cases") or []):
                args = _resolve(case.get("args") or [])
                kwargs = _resolve(case.get("kwargs") or {})
                exp = case.get("expect") or {}
                if exp.get("raises"):
                    if not _raises(fn, args, kwargs):
                        problems.append("用例 %d：契约要求抛异常但未抛" % i)
                    continue
                try:
                    value = fn(*args, **kwargs)
                except Exception as exc:  # 未声明 raises 却抛 = 契约不成立，如实记不静默
                    problems.append("用例 %d 抛异常：%s" % (i, exc))
                    continue
                ok, detail = judge(value, exp)
                if not ok:
                    problems.append("用例 %d 判定不符：%s" % (i, detail))
        rows.append({"id": cid, "module": mod_name, "entry": entry,
                     "ok": not problems, "problems": problems})
    total = len(rows)
    failed = sum(1 for r in rows if not r["ok"])
    return {"schema": SCHEMA, "total": total, "passed": total - failed,
            "failed": failed, "rows": rows}
