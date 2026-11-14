# Output / Validation（WP-22）

> ⛔ 操作指令：本件是 WP-22 产物校验的人读说明；实现 `desktop/src/core/output_validation.py`，判据 `desktop/tests/test_output_validation_contract.py`，样例报告 `results/output/output-report.json`。失败必须拒收，不静默放行。
> 状态：v1（G2 · 2026-11-14）· 依据：PR-07、§13A L6（形态合规/可 diff/失败拒收）

## 用法

```python
from core import output_validation as ov
report = ov.validate(output, task, pack, root)   # 不抛：返回 nf-output-report/1
report = ov.accept(output, task, pack, root)     # 红项 → OutputRejected（code+修复指引）
```

## 校验项

| 项 | 规则 | 失败码 |
|---|---|---|
| adapter 契约 | citations ⊆ context_refs（编造=0）/ budget / kind / slot | `ADAPTER-CONTRACT` |
| contract | 产物生成 `nf-contract/1` 并过 schema（id/artifact digest/constraints/acceptance/status） | `CONTRACT-INVALID` |
| output form | md 需标题、行宽 ≤400；json 必须可解析；禁控制字符；禁占位符（TODO/TBD/待补） | `FORM-*` |
| 拒收 | 任一红项 → 不落交付，Assembly Runtime gate 停链 | `OUTPUT-REJECTED` |

## 报告（`nf-output-report/1`）

`ok` / `form` / `tier`（对齐 `protocol/output_forms.json` 的 T0–T4 口径）/ `digest` /
`contract` / `issues[]` / `metrics`（chars/tokens/citations/citation_rate/control_chars/violations）。
committed 样例 `results/output/output-report.json` 必须 == 实时重算。

## 与 Assembly Runtime 的关系

WP-21 的 S05/K-002 直接复用本模块：产物被拒 → `status=blocked` + `error.code=OUTPUT-INVALID`，
**不留 export 步骤**；失败原因落 `run.validation`（form/tier/digest/metrics）。

## 边界

- 本件只判「形态/契约/引用」；内容质量与 rubric 抽样属后续 CQ/评测线，不在此冒充。
- `file` 形态只做路径/大小/控制字符边界校验；深度格式（PDF/DOCX）不在 core-only 范围。
