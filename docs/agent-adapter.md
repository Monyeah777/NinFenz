# Agent Adapter（`nf agent`，WP-20）

> ⛔ 操作指令：本件是 WP-20 Agent Adapter 协议的人读说明；实现 `desktop/src/core/agent_adapter.py`，判据 `desktop/tests/test_agent_adapter_contract.py`，报告 `results/adapter/adapter-report.json`。Adapter 只接有界任务，不得自由生成整篇。
> 状态：v1（G2 · 2026-11-14）· 依据：PR-03/PR-05、§13A L4（2 adapter parity、超时、输出合规、编造引用=0）

## 用法

```bash
python scripts/nf.py agent list
python scripts/nf.py agent run --adapter mock --intent spec/intents/sample-document.json --json
python scripts/nf.py agent run --adapter local-template --intent spec/intents/sample-document.json --report
```

## 契约

- **输入**：`nf-task/1`（slot 有界；spec_refs/context_refs/acceptance/budget 必填）。
- **输出**：`nf-adapter-output/1`（adapter/task_slot/output/citations/usage）：
  - citations 必须是 context_refs（或 context pack entries）子集 → **编造引用=0**；
  - content 长度 ≤ `budget.max_tokens × 4`；kind 必须等于 task.output_schema.kind；
  - usage.tokens ≤ budget。
- **Adapter**：
  - `mock`：进程内确定性桩（按上下文页 summary 拼装 slot 内容）；
  - `local-template`：本地子进程桩（同 spec 的独立实现，用于 parity 对照；不联网）。
- **Parity**：两 adapter 同 task 跑，citations 集与 kind 一致 → `parity=true`；报告 `nf-adapter-report/1` 提交入仓（`results/adapter/adapter-report.json`），测试断言 committed == 实时重算。

## 失败语义（exit 2）

| 码 | 触发 |
|---|---|
| `TASK-INVALID` | 不是 nf-task/1 / schema 不符 / 缺 slot 或 context_refs |
| `ADAPTER-UNKNOWN` | 未知 adapter id |
| `ADAPTER-TIMEOUT` | 子进程超时（>10s） |
| `ADAPTER-FAILED` | 子进程失败/输出不是单个 JSON |
| `OUTPUT-INVALID` | 编造引用 / 超预算 / kind 不符 / 空内容 |
| `CONTEXT-EMPTY` | 空上下文无法产出 |

## 边界

- `local-template` 是**本地子进程桩，不是真实外部模型**；真实外部 adapter 需要外部 API/额度，属外部操作（OPEN），不冒充。
- 真实装配/导出 E2E 属 WP-21 Assembly Runtime。
