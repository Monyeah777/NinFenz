# Assembly Runtime（`nf agent run --assembly`，WP-21）

> ⛔ 操作指令：本件是 WP-21 装配运行时的人读说明；实现 `desktop/src/core/assembly_runtime.py`，判据 `desktop/tests/test_assembly_runtime_contract.py`，样例记录 `results/assembly/sample-document.assembly.json`。只走 core-only 链路，不依赖治理平面。
> 状态：v1（G2 · 2026-11-14）· 依据：PR-02/PR-07、QG2（core-only E2E / 2 adapter 可移植 / 输出校验）

## 用法

```bash
python scripts/nf.py agent run --adapter mock --intent spec/intents/sample-document.json --assembly
python scripts/nf.py agent run --adapter local-template --intent spec/intents/sample-document.json --assembly --json
```

## 链路（P00 黄金路径）

`intent → spec → task → context pack → agent adapter → output 校验 → gate → export 记录`

| 步骤 | 组件 | 判据 |
|---|---|---|
| S01 spec | `core/spec_compiler` | spec ref+digest |
| S02 task | `core/spec_compiler` | slot 有界/refs |
| S03 context | `core/context_packer` | citation_rate=100% |
| S04 adapter | `core/agent_adapter` | 两 adapter 均可跑 |
| S05 output | `core/agent_adapter` | `nf-adapter-output/1` |
| S06 gate | `core/assembly_runtime` | K-001…K-004 全绿 |
| S07 export | 记录（正文由 WP-23 Delivery） | 只存 digest/相对路径 |

## 产物两层

- `assembly`：**严格** `nf-assembly/1`（`protocol/production/assembly.schema.json`，additionalProperties=false）；
- `run`：`nf-assembly-run/1` 信封（status/adapter/checks/output digest/steps trace/error）。

## 失败语义

- 任一步失败 → `run.status=blocked` + `run.error`（code+修复指引），**不留 export 步骤**、不静默放行；
- 未知 adapter / 坏 intent / 输出不合契约 / 超预算都被判红并记录（K-001…K-004）。

## 边界

- 本件是 core-only 运行时；治理/证据链属 G3，Delivery（pack/元数据/sidecar）属 WP-23。
- 真实外部模型/外部发布属外部操作（OPEN）。
