"""nf-process/1 流程步骤与 prev 链（FR-A2-01 / FR-A2-02 / FR-A2-03）。

冻结依据：ADR-006 域分隔规则 + 向量集 process 族（schema 形状）。

规则（与向量集 rules.process 逐字对应）：
- step 摘要 = `domain_digest("nf:process:v1:step", canonical_bytes(step 去 digest))`：
  schema / process_id / step / prev / actor / authorization / input_refs / output_refs /
  state_digest / type **全部进摘要**；
- prev = 上一步摘要；创世步 prev = 64 个 0（不接受空串/缺省）；step 从 1 连续；
- 链验证顺序固定：PREV-FORMAT → SEQ-ORDER → PREV-MISMATCH（与向量族 expected 一致）；
- step 记录本身不存 digest（schema additionalProperties=false），验证方按链重算——存 digest
  会让「删尾重算」有第二个可篡改面。

边界：本地可重建自洽链（自洽≠不可篡改）；链头签名/外部锚在 G2。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core import json_doc, json_schema
from core.trust.canonical import canonical_bytes, domain_digest, is_digest

GUIDE = "修复指引："
SCHEMA = "nf-process/1"
SCHEMA_REL = "protocol/trust/process.schema.json"
DOMAIN_TAG = "nf:process:v1:step"
#: 创世步的 prev：64 个 0（不是空串；空串会被 schema pattern 拒）。
ZERO_DIGEST = "0" * 64
#: step 必填字段（与冻结 schema 的 required 对齐；digest 计算前先确认在场）。
STEP_FIELDS = ("schema", "process_id", "step", "prev", "actor", "authorization",
               "input_refs", "output_refs", "state_digest", "type")


def load_schema(root: str = ".", rel: str = SCHEMA_REL) -> dict:
    """读冻结的 process schema（缺件/坏 JSON 直接抛，不静默降级）。"""
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺 process schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    doc = json_doc.load(path, dict, what=rel)
    const = str((doc.get("properties") or {}).get("schema", {}).get("const"))
    if const != SCHEMA:
        raise ValueError(f"{rel} 不是 {SCHEMA} 定义（{GUIDE}核对 properties.schema.const）")
    return doc


def step_digest(step: Any) -> str:
    """单步摘要：canonical(step 去 digest) 经域分隔。缺必填字段即抛（不猜、不补默认值）。"""
    if not isinstance(step, dict):
        raise ValueError(f"step 必须是对象（{GUIDE}见 nf-process/1 定义）")
    missing = [field for field in STEP_FIELDS if field not in step]
    if missing:
        raise ValueError(f"step 缺必填字段 {missing}（{GUIDE}按 nf-process/1 required 补齐）")
    body = {key: value for key, value in step.items() if key != "digest"}
    return domain_digest(DOMAIN_TAG, canonical_bytes(body))


def validate_steps(steps: Any, schema: dict | None = None) -> list:
    """结构校验：schema（若给）+ 链序/prev 格式。返回问题清单（空 = 结构合法）。"""
    issues: list[str] = []
    if not isinstance(steps, list):
        return ["steps 必须是数组（" + GUIDE + "按 nf-process/1 顺序存放 step）"]
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            issues.append(f"steps[{index}] 不是对象")
            continue
        if schema is not None:
            issues += [f"steps[{index}]: {msg}"
                       for msg in json_schema.json_schema_check(step, schema)]
        prev = step.get("prev")
        if not is_digest(prev):
            issues.append(f"steps[{index}] 的 prev 非 64 位小写 hex")
        if step.get("step") != index + 1:
            issues.append(f"steps[{index}] 的 step 应为 {index + 1}，实为 {step.get('step')!r}")
    return issues


def append_step(steps: list, process_id: str, actor: dict, authorization: dict,
                state_digest: str, type_: str,
                input_refs: list | None = None,
                output_refs: list | None = None) -> dict:
    """向合法链追加一步：自动封 seq = len+1 与 prev = 当前链头。"""
    if not isinstance(steps, list):
        raise ValueError(f"steps 必须是数组（{GUIDE}从 [] 开始）")
    head = chain_head(steps)
    if not isinstance(state_digest, str) or not is_digest(state_digest):
        raise ValueError(f"state_digest 须为 64 位小写 hex（{GUIDE}用 canonical.digest_of 生成）")
    return {
        "schema": SCHEMA,
        "process_id": str(process_id),
        "step": len(steps) + 1,
        "prev": head,
        "actor": actor,
        "authorization": authorization,
        "input_refs": list(input_refs or []),
        "output_refs": list(output_refs or []),
        "state_digest": state_digest,
        "type": str(type_),
    }


def verify_chain(steps: Any) -> dict:
    """按 prev 链规则重算。

    返回与向量约定一致的两种形状：
      通过 → {"valid": True, "digests": [...], "head": "..."}
      失败 → {"valid": False, "reason": "PREV-FORMAT|SEQ-ORDER|PREV-MISMATCH|STEP-NOT-OBJECT"}
    """
    if not isinstance(steps, list) or not steps:
        return {"valid": False, "reason": "STEPS-EMPTY"}
    digests = []
    head = ZERO_DIGEST
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            return {"valid": False, "reason": "STEP-NOT-OBJECT"}
        prev = step.get("prev")
        if not is_digest(prev):
            return {"valid": False, "reason": "PREV-FORMAT"}
        if step.get("step") != index + 1:
            return {"valid": False, "reason": "SEQ-ORDER"}
        if prev != head:
            return {"valid": False, "reason": "PREV-MISMATCH"}
        head = step_digest(step)
        digests.append(head)
    return {"valid": True, "digests": digests, "head": head}


def chain_head(steps: Any) -> str:
    """链头摘要；空链返回创世基（64 个 0）；链无效则抛（带原因与修复指引）。"""
    if not isinstance(steps, list):
        raise ValueError(f"steps 必须是数组（{GUIDE}从 [] 开始）")
    if not steps:
        return ZERO_DIGEST
    result = verify_chain(steps)
    if not result["valid"]:
        raise ValueError(f"链条无效：{result['reason']}（{GUIDE}先修链再取链头）")
    return result["head"]
