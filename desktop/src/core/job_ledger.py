"""作业账本（nf-job/1 + nf-job-ledger/1）：K1 作业模型 + K4 事件总线最小实现。

为什么（2026-11-08，方案 §2.4）：现在每次调用只有命令级证据，没有 job id 贯穿，
于是「同一件事的多次调用」无法归集、无法整体复算、无法判断「这个 job 结束没」。
本模块给 cc_*/cog_* 调用一个 6 态作业对象与只追加事件流，证据按 job 归集。

状态机（OS 语义补全 L41-42）：created → queued → running → succeeded|failed|canceled|timeout
终态之后不得再追加事件或回执（真终止，不是记个日志）。

纪律：
- 只追加：事件/回执都进同一条 append-only 链（prev digest），改一处即断；
- 可复算：replay() 从事件流重算最终状态与 digest；
- 作业 digest 用于和证据绑定（job_digest = 状态 + 事件链头），可进 commitment。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA = "nf-job/1"
LEDGER_SCHEMA = "nf-job-ledger/1"
EVENT_SCHEMA = "nf-job-event/1"
GUIDE = "修复指引："
STATES = ("created", "queued", "running", "succeeded", "failed", "canceled", "timeout")
TERMINAL = ("succeeded", "failed", "canceled", "timeout")
TRANSITIONS = {
    "created": ("queued", "canceled", "failed"),
    "queued": ("running", "canceled", "timeout", "failed"),
    "running": ("succeeded", "failed", "canceled", "timeout"),
    "succeeded": (),
    "failed": (),
    "canceled": (),
    "timeout": (),
}


def digest_of(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {"schema": LEDGER_SCHEMA, "jobs": {}, "chain": []}
    ledger["digest"] = digest_of(ledger)
    return ledger


def _bump(ledger: dict[str, Any]) -> None:
    ledger["digest"] = digest_of({k: v for k, v in ledger.items() if k != "digest"})


def _append(ledger: dict[str, Any], job_id: str, kind: str, body: dict[str, Any]) -> dict[str, Any]:
    prev = ledger["chain"][-1]["digest"] if ledger["chain"] else ""
    event = {"schema": EVENT_SCHEMA, "seq": len(ledger["chain"]) + 1, "job": job_id,
             "kind": kind, "body": body, "prev": prev}
    event["digest"] = digest_of(event)
    ledger["chain"].append(event)
    return event


def create(ledger: dict[str, Any], job_id: str, kind: str, contract_digest: str = "",
           inputs_digest: str = "") -> dict[str, Any]:
    """建一个作业（created）。重复 id / 空 id → 拒绝。"""
    if not str(job_id).strip():
        raise ValueError("job_id 不能为空（" + GUIDE + "给稳定 id，如 job-2026-11-08-1）")
    if job_id in ledger.get("jobs", {}):
        raise ValueError("作业已存在：" + job_id + "（" + GUIDE + "换 id 或复用已有作业）")
    if not str(kind).strip():
        raise ValueError("作业缺 kind（" + GUIDE + "写清是 check/label/evidence-verify 哪类）")
    new = json.loads(json.dumps(ledger))
    new["jobs"][job_id] = {"schema": SCHEMA, "id": str(job_id), "kind": str(kind),
                           "state": "created", "contract_digest": str(contract_digest),
                           "inputs_digest": str(inputs_digest),
                           "events": [], "receipts": []}
    event = _append(new, job_id, "created",
                    {"kind": str(kind), "contract_digest": str(contract_digest),
                     "inputs_digest": str(inputs_digest)})
    new["jobs"][job_id]["events"].append(event["digest"])
    _bump(new)
    return new


def transition(ledger: dict[str, Any], job_id: str, to_state: str,
               witness: dict[str, Any] | None = None) -> dict[str, Any]:
    """状态迁移（必须合法；终止后不得再迁移）。"""
    job = (ledger.get("jobs") or {}).get(job_id)
    if job is None:
        raise ValueError("未知作业：" + job_id + "（" + GUIDE + "先 nf cog job create）")
    if to_state not in STATES:
        raise ValueError("未知状态：" + str(to_state) + "（" + GUIDE + "见 STATES）")
    if job["state"] in TERMINAL:
        raise ValueError("作业已终止（" + job["state"] + "），不能再迁移（" + GUIDE + "新开作业）")
    if to_state not in TRANSITIONS[job["state"]]:
        raise ValueError("非法迁移：" + job["state"] + " → " + to_state
                         + "（" + GUIDE + "允许："
                         + "、".join(TRANSITIONS[job["state"]]) + "）")
    new = json.loads(json.dumps(ledger))
    new["jobs"][job_id]["state"] = to_state
    event = _append(new, job_id, "transition",
                    {"from": job["state"], "to": to_state, "witness": witness or {}})
    new["jobs"][job_id]["events"].append(event["digest"])
    _bump(new)
    return new


def attach_receipt(ledger: dict[str, Any], job_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
    """把一条调用回执挂到作业上（终止后拒绝）。"""
    job = (ledger.get("jobs") or {}).get(job_id)
    if job is None:
        raise ValueError("未知作业：" + job_id + "（" + GUIDE + "先 create）")
    if job["state"] in TERMINAL:
        raise ValueError("作业已终止，不能再挂回执（" + GUIDE + "回执必须在作业内产生）")
    if not isinstance(receipt, dict) or not str(receipt.get("digest") or ""):
        raise ValueError("回执缺 digest（" + GUIDE + "用 mcp_manifest.receipt 生成）")
    new = json.loads(json.dumps(ledger))
    new["jobs"][job_id]["receipts"].append(str(receipt["digest"]))
    event = _append(new, job_id, "receipt", {"receipt": str(receipt["digest"])})
    new["jobs"][job_id]["events"].append(event["digest"])
    _bump(new)
    return new


def job_digest(ledger: dict[str, Any], job_id: str) -> str:
    """作业摘要 digest（状态 + 事件链项），用于和证据/commitment 绑定。"""
    job = (ledger.get("jobs") or {}).get(job_id)
    if job is None:
        raise ValueError("未知作业：" + job_id + "（" + GUIDE + "先 create）")
    return digest_of({"id": job["id"], "kind": job["kind"], "state": job["state"],
                      "events": job["events"], "receipts": job["receipts"],
                      "contract_digest": job["contract_digest"],
                      "inputs_digest": job["inputs_digest"]})


def replay(ledger: dict[str, Any]) -> dict[str, Any]:
    """从事件链重放 → {ok, ledger, issues}（校验链、迁移合法性、终态后无追加）。"""
    res: dict[str, Any] = {"ok": False, "ledger": None, "issues": []}
    if not isinstance(ledger, dict) or str(ledger.get("schema")) != LEDGER_SCHEMA:
        res["issues"].append("账本 schema 不匹配（" + GUIDE + "需要 " + LEDGER_SCHEMA + "）")
        return res
    fresh = new_ledger()
    prev = ""
    for item in ledger.get("chain") or []:
        if str(item.get("prev") or "") != prev:
            res["issues"].append("事件链断在第 " + str(item.get("seq")) + " 条")
            return res
        if digest_of({k: v for k, v in item.items() if k != "digest"}) != item.get("digest"):
            res["issues"].append("第 " + str(item.get("seq")) + " 条事件 digest 不符")
            return res
        kind, job_id, body = str(item.get("kind")), str(item.get("job")), item.get("body") or {}
        try:
            if kind == "created":
                fresh = create(fresh, job_id, str(body.get("kind") or ""),
                               contract_digest=str(body.get("contract_digest") or ""),
                               inputs_digest=str(body.get("inputs_digest") or ""))
            elif kind == "transition":
                fresh = transition(fresh, job_id, str(body.get("to")),
                                   witness=body.get("witness") or {})
            elif kind == "receipt":
                fresh = attach_receipt(fresh, job_id, {"digest": body.get("receipt")})
            else:
                res["issues"].append("未知事件类型：" + kind)
                return res
        except ValueError as exc:
            res["issues"].append("第 " + str(item.get("seq")) + " 条无法重放：" + str(exc))
            return res
        prev = str(item["digest"])
    res.update({"ok": True, "ledger": fresh})
    return res
