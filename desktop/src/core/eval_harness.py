"""预注册评测 harness（nf-eval-protocol/1 + nf-eval-run/1）：先冻结协议，再录数据。

纪律（写进校验，不靠自觉）：
- 协议必须 frozen_before_run: true 才允许录 run；
- 维度只有三类 kind：count（可数）/ blind-rank（只能外部盲评给）/ ratio；
  **不许出现 score/grade/rating 键**（递归查）；
- run 的 source 只有 measured（真测）与 synthetic（夹具/演练）两种；
  synthetic 的 run **不得**被当成证据（compare 会直接拒）；
- compare 只给计数差与中位数，不给 p 值、不做显著性宣称；
- 反窄化指标 table_external_mechanisms：产出里不在菜单/方法包表内的机制数，越低 = 越被窄化。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core import json_doc

from ._eval_harness._base import GUIDE
from ._eval_harness._compare import (
    COMPARE_SCHEMA,
    _diffs,
    _medians,
    _value_table,
    compare,
)

PROTOCOL_SCHEMA = "nf-eval-protocol/1"
RUN_SCHEMA = "nf-eval-run/1"
REL = "protocol/eval/protocol.json"
KINDS = ("count", "blind-rank", "ratio")
SOURCES = ("measured", "synthetic")
FORBIDDEN_KEYS = ("score", "grade", "rating", "points", "weighted_score")


def _walk_forbidden(obj: Any, hits: list[str], path: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                hits.append(path + "/" + str(key))
            _walk_forbidden(value, hits, path + "/" + str(key))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            _walk_forbidden(value, hits, path + "/" + str(i))


def load_protocol(root: str = ".") -> dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise ValueError("评测协议不在场：" + REL + "（" + GUIDE + "确认 protocol/eval/）")
    try:
        doc = json_doc.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(REL + " 不是合法 JSON：" + str(exc)) from exc
    issues = validate_protocol(doc)
    if issues:
        raise ValueError("评测协议不合法：" + "；".join(issues[:3]))
    return doc


def _dim_issues(dim: Any) -> list[str]:
    """单个维度条目 → 问题清单。"""
    if not isinstance(dim, dict):
        return ["dimensions 里有非对象条目"]
    out: list[str] = []
    if str(dim.get("kind")) not in KINDS:
        out.append(str(dim.get("id")) + " 的 kind 非法：" + str(dim.get("kind")))
    if not str(dim.get("how") or "").strip():
        out.append(str(dim.get("id")) + " 缺 how（" + GUIDE + "写清怎么计）")
    return out


def _protocol_conditions_issues(doc: dict[str, Any]) -> list[str]:
    """对照组判据：≥2 组、id 不重复、必须有 free 基线。"""
    conds = doc.get("conditions")
    if not isinstance(conds, list) or len(conds) < 2:
        return ["至少两个对照组（" + GUIDE + "free 作为基线）"]
    out: list[str] = []
    ids = [str(c.get("id")) for c in conds if isinstance(c, dict)]
    if len(ids) != len(set(ids)):
        out.append("对照组 id 重复")
    if "free" not in ids:
        out.append("缺 free 基线（" + GUIDE + "必须有自由推理对照）")
    return out


def _protocol_dimensions_issues(doc: dict[str, Any]) -> list[str]:
    """维度判据：逐维 kind/how，且必须有反窄化指标。"""
    dims = doc.get("dimensions")
    if not isinstance(dims, list) or not dims:
        return ["缺 dimensions（" + GUIDE + "至少一个维度）"]
    out: list[str] = []
    for dim in dims:
        out.extend(_dim_issues(dim))
    ids = {str(d.get("id")) for d in dims if isinstance(d, dict)}
    if "table_external_mechanisms" not in ids:
        out.append("缺反窄化指标 table_external_mechanisms"
                   "（" + GUIDE + "没有它就无法发现「被菜单窄化」）")
    return out


def _protocol_fields_issues(doc: dict[str, Any]) -> list[str]:
    """必填文本字段判据。"""
    out: list[str] = []
    for field in ("version", "registered_at", "question"):
        if not str(doc.get(field) or "").strip():
            out.append("协议缺 " + field)
    return out


def _protocol_tail_issues(doc: dict[str, Any]) -> list[str]:
    """samples / 分析计划 / 禁止项判据。"""
    out: list[str] = []
    samples = doc.get("samples_per_task")
    if not isinstance(samples, int) or samples < 1:
        out.append("samples_per_task 必须是 ≥1 的整数")
    plan = doc.get("analysis_plan")
    if not isinstance(plan, dict) or "statistic" not in plan:
        out.append("缺 analysis_plan.statistic（" + GUIDE + "写清怎么比）")
    if not isinstance(doc.get("prohibitions"), list) or not doc.get("prohibitions"):
        out.append("缺 prohibitions（" + GUIDE + "写清不允许做什么）")
    return out


def validate_protocol(doc: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(doc, dict) or str(doc.get("schema")) != PROTOCOL_SCHEMA:
        return ["协议 schema 不匹配（" + GUIDE + "需要 " + PROTOCOL_SCHEMA + "）"]
    banned: list[str] = []
    _walk_forbidden(doc, banned)
    if banned:
        issues.append("协议出现打分键 " + str(banned[:3])
                      + "（" + GUIDE + "只计数，不打分）")
    if doc.get("frozen_before_run") is not True:
        issues.append("协议必须先冻结（frozen_before_run: true），否则不得录数据")
    issues.extend(_protocol_fields_issues(doc))
    issues.extend(_protocol_conditions_issues(doc))
    tasks = doc.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        issues.append("缺 tasks（" + GUIDE + "至少一个任务）")
    issues.extend(_protocol_dimensions_issues(doc))
    issues.extend(_protocol_tail_issues(doc))
    return issues


def _run_head(run: Any) -> str:
    """run 头部校验（对象/无打分键/source 在词表）→ source。"""
    if not isinstance(run, dict):
        raise ValueError("run 必须是对象（" + GUIDE + "见 nf-eval-run/1）")
    banned: list[str] = []
    _walk_forbidden(run, banned)
    if banned:
        raise ValueError("run 出现打分键 " + str(banned[:3]) + "（" + GUIDE + "只计数）")
    source = str(run.get("source") or "")
    if source not in SOURCES:
        raise ValueError("run.source 必须是 measured 或 synthetic（" + GUIDE + "别把演练当测量）")
    return source


def _check_item(item: Any, cond_ids: set, task_ids: set, dim_ids: set,
                samples: int) -> tuple[str, str, int]:
    """单条 run item 的形状校验 → (cond, task, sample)。"""
    if not isinstance(item, dict):
        raise ValueError("items 里有非对象条目（" + GUIDE + "每条一个对象）")
    cond = str(item.get("condition") or "")
    task = str(item.get("task") or "")
    sample = item.get("sample")
    if cond not in cond_ids:
        raise ValueError("未知对照组：" + cond + "（" + GUIDE + "见 protocol.conditions）")
    if task not in task_ids:
        raise ValueError("未知任务：" + task + "（" + GUIDE + "见 protocol.tasks）")
    if not isinstance(sample, int) or not 1 <= sample <= samples:
        raise ValueError("sample 必须是 1.." + str(samples) + "（" + GUIDE + "按协议取样）")
    values = item.get("values")
    if not isinstance(values, dict):
        raise ValueError("第 " + str(sample) + " 条缺 values")
    missing = dim_ids - set(values)
    if missing:
        raise ValueError("缺维度值 " + str(sorted(missing)) + "（" + GUIDE + "七维都要计）")
    return cond, task, sample


def record_run(protocol: dict[str, Any], run: Any) -> dict[str, Any]:
    """校验一次 run 是否符合预注册协议 → 规范化 run。"""
    source = _run_head(run)
    cond_ids = {str(c.get("id")) for c in protocol["conditions"]}
    task_ids = {str(t.get("id")) for t in protocol["tasks"]}
    dim_ids = {str(d.get("id")) for d in protocol["dimensions"]}
    samples = int(protocol["samples_per_task"])
    items = run.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("run 缺 items（" + GUIDE + "每个 task×sample 一条）")
    seen: set[tuple[str, str, int]] = set()
    for item in items:
        cond, task, sample = _check_item(item, cond_ids, task_ids, dim_ids, samples)
        key = (cond, task, sample)
        if key in seen:
            raise ValueError("重复记录：" + str(key))
        seen.add(key)
    out = {"schema": RUN_SCHEMA, "protocol_version": str(protocol.get("version")),
           "source": source, "items": items,
           "note": "synthetic 只能用于演练；measured 才是证据"}
    raw = json.dumps(out, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    out["digest"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return out





def validate(record: Any) -> list[str]:
    """校验一条评测用例记录（能力契约 eval-harness 的入口）→ 问题列表。

    契约口径：合法记录（含 case_id/ok/at/trigger 等）→ 空列表；缺关键字段 → 非空。
    """
    issues: list[str] = []
    if not isinstance(record, dict):
        return ["评测记录必须是对象（" + GUIDE + "见 nf-eval-run/1 的 items 条目）"]
    for field in ("case_id", "ok", "at", "trigger"):
        if field not in record:
            issues.append("评测记录缺 " + field + "（" + GUIDE + "补该字段）")
    if "ok" in record and not isinstance(record.get("ok"), bool):
        issues.append("ok 必须是布尔（" + GUIDE + "别用字符串）")
    cost = record.get("cost_usd")
    if cost is not None and not isinstance(cost, (int, float)):
        issues.append("cost_usd 必须是数字（" + GUIDE + "无成本写 0）")
    return issues

CHECKLIST_SCHEMA = "nf-eval-checklist/1"


def eval_run_checklist(root: str = ".") -> dict[str, Any]:
    """生成采集检查单（真实测量的作业面）：**只排格子、不填数**。

    为什么在 core：检查单是「协议 + 方法包」的纯派生，脚本只负责打印/落盘。
    纪律：values 必须为空、status 必须是 planned——先有格子再有数，
    否则事后无法分辨哪些数是采集的、哪些是编的。
    """
    from core import method_pack as mp  # 局部导入：避免模块级循环

    protocol = load_protocol(root)
    pack = mp.load_pack(root, "evaluation-design")
    samples = int(protocol["samples_per_task"])
    cells = []
    for cond in protocol["conditions"]:
        for task in protocol["tasks"]:
            for sample in range(1, samples + 1):
                cells.append({
                    "condition": cond["id"], "task": task["id"], "sample": sample,
                    "status": "planned",
                    "values": {},
                    "cost": {"latency_s": None, "cost_usd": None},
                    "review": {"reviewer": None, "verdict": None},
                })
    return {
        "schema": CHECKLIST_SCHEMA,
        "protocol": {"version": protocol["version"],
                     "registered_at": protocol["registered_at"],
                     "frozen_before_run": protocol["frozen_before_run"],
                     "samples_per_task": samples,
                     "dimensions": [d["id"] for d in protocol["dimensions"]],
                     "prohibitions": protocol["prohibitions"]},
        "pack": {"id": pack["id"],
                 "guards": list(pack["common_failures"]),
                 "evidence_kinds": [st["claim_kind"] for st in pack["evidence_standards"]]},
        "cells": cells,
        "negative_control": {
            "kind": "label-shuffle",
            "how": "把条件标签打乱后重跑同一批样本；判据：该对照不得出现显著优于 free 的差异",
            "status": "planned"},
        "blind_review": {"reviewers_per_task": 2,
                         "how": "评审者只见样本内容与维度量表，不见条件标签；每任务至少两名",
                         "conflict_declaration_required": True,
                         "status": "planned"},
        "cost_accounting": {"per_cell": ["latency_s", "cost_usd"],
                            "aggregate": ["wall_clock_s", "total_cost_usd", "review_hours"],
                            "status": "planned"},
        "measurement": {"status": "not-run",
                        "why": "真实测量只由作者显式触发；本检查单不填任何数"},
    }

COLLECT_STATUSES = ("planned", "collected", "reviewed")


def _check_sheet_binding(sheet: dict[str, Any], protocol: dict[str, Any]) -> None:
    """① 协议绑定：版本/注册时间必须与当前冻结协议一致（防悄悄换协议）。"""
    bound = sheet.get("protocol") or {}
    if str(bound.get("version") or "") != str(protocol["version"]):
        raise ValueError("采集单绑定的协议版本 " + str(bound.get("version"))
                         + " ≠ 当前 " + str(protocol["version"])
                         + "（" + GUIDE + "协议变更须重新生成检查单）")
    if str(bound.get("registered_at") or "") != str(protocol["registered_at"]):
        raise ValueError("采集单的注册时间与冻结协议不一致（" + GUIDE
                         + "协议被改动过，须重跑 --checklist）")


def _value_blockers(label: str, status: str, cell: dict[str, Any],
                    dims: list[str]) -> list[str]:
    """③ collected/reviewed 的维度数值判据。"""
    values = cell.get("values") or {}
    out: list[str] = []
    if status != "planned" and set(dims) - set(values):
        out.append(label + " 缺维度值：" + ",".join(sorted(set(dims) - set(values))))
    if status != "planned":
        for dim in dims:
            if dim in values and not isinstance(values[dim], (int, float)):
                out.append(label + " 维度 " + dim + " 不是数字（"
                           + GUIDE + "别填空串/说明文字）")
    return out


def _review_blockers(label: str, status: str, cell: dict[str, Any]) -> list[str]:
    """③ reviewed 必须有评审者与判定。"""
    review = cell.get("review") or {}
    if status == "reviewed" and not (review.get("reviewer") and review.get("verdict")):
        return [label + " reviewed 但缺评审者或判定"]
    return []


def _cell_blockers(cell: Any, dims: list[str]) -> tuple[list[str], str]:
    """单格 → (blockers, status)；状态未知返回空 status（不计入 counts）。"""
    label = (str(cell.get("condition")) + "/" + str(cell.get("task"))
             + "#" + str(cell.get("sample")))
    status = str(cell.get("status") or "")
    if status not in COLLECT_STATUSES:
        return [label + " 状态未知：" + status
                + "（" + GUIDE + "只用 planned/collected/reviewed）"], ""
    out = _value_blockers(label, status, cell, dims)
    out.extend(_review_blockers(label, status, cell))
    return out, status


def _cells_blockers(cells: list, expected: int, counts: dict[str, int]) -> list[str]:
    """② 格子数量与采集完成度判据。"""
    out: list[str] = []
    if len(cells) < expected:
        out.append("格子不足：" + str(len(cells)) + " < " + str(expected)
                   + "（" + GUIDE + "补齐或重新生成检查单）")
    if cells and counts["reviewed"] != len(cells):
        out.append("采集未完成：planned " + str(counts["planned"])
                   + " / collected " + str(counts["collected"])
                   + " / reviewed " + str(counts["reviewed"])
                   + "（" + GUIDE + "全部格都要到 reviewed 才能进比较）")
    return out


def _control_blockers(sheet: dict[str, Any]) -> list[str]:
    """④ 负对照 + 盲评判据。"""
    out: list[str] = []
    nc = sheet.get("negative_control") or {}
    if str(nc.get("status") or "") == "planned":
        out.append("负对照未做（" + GUIDE + "负对照失败时任何差异都不能算证据）")
    blind = sheet.get("blind_review") or {}
    per_task = int(blind.get("reviewers_per_task") or 0)
    if per_task < 2:
        out.append("盲评人数不足：" + str(per_task) + " < 2（" + GUIDE + "每任务至少两名）")
    if str(blind.get("status") or "") == "planned":
        out.append("盲评未做（" + GUIDE + "改 status 并把逐格 review 填上）")
    return out


def validate_collection(root: str, sheet: Any) -> dict[str, Any]:
    """校验采集单（checklist 填好后的形态）→ {ok, ready, blockers, counts}。

    为什么要有这一层：检查单只是格子，填完之后必须有一道**fail-closed 的验收**，
    否则「跑完了」和「填了数」无法区分，实测数据会带着空洞进比较。规则：
    ① 协议绑定：sheet.protocol.version/registered_at 必须与当前冻结协议一致（防悄悄换协议）；
    ② 状态机：planned → collected → reviewed 单向；未知状态直接拒；
    ③ collected 必须有全部维度的数值；reviewed 必须有评审者与判定；
    ④ ready（可进比较）额外要求：所有格 reviewed + 负对照出了结论 + 盲评至少每任务 2 人。
    """
    protocol = load_protocol(root)
    if not isinstance(sheet, dict):
        raise ValueError("采集单必须是对象（" + GUIDE + "用 --checklist 生成模板）")
    if str(sheet.get("schema") or "") != CHECKLIST_SCHEMA:
        raise ValueError("采集单 schema 不符（" + GUIDE + "需要 " + CHECKLIST_SCHEMA + "）")
    _check_sheet_binding(sheet, protocol)
    dims = [str(d["id"]) for d in protocol["dimensions"]]
    cells = sheet.get("cells") or []
    expected = (len(protocol["conditions"]) * len(protocol["tasks"])
                * int(protocol["samples_per_task"]))
    blockers: list[str] = []
    counts = dict.fromkeys(COLLECT_STATUSES, 0)
    for cell in cells:
        cell_blockers, status = _cell_blockers(cell, dims)
        blockers.extend(cell_blockers)
        if status:
            counts[status] += 1
    blockers.extend(_cells_blockers(cells, expected, counts))
    blockers.extend(_control_blockers(sheet))
    ready = not blockers and counts["reviewed"] == len(cells)
    return {"ok": True, "ready": ready, "counts": counts,
            "cells": len(cells), "expected_cells": expected,
            "blockers": blockers[:20], "blockers_total": len(blockers)}
