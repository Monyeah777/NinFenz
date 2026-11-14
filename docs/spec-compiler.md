# Spec Compiler（`nf spec compile`，WP-11）

> ⛔ 操作指令：本件是 WP-11 Spec Compiler 的人读说明；契约 `protocol/production/{spec,task}.schema.json`；判据 `desktop/tests/test_spec_compiler_contract.py`。编译只引用 Wiki 页（id+digest）与 spec（ref+digest），不复制正文。
> 状态：v1（G1 · 2026-11-14）· 纪律：确定性 / 拒绝未知 / 有界任务 / 任务图无环

## 用法

```bash
python scripts/nf.py spec compile --intent spec/intents/sample-document.json --json
python scripts/nf.py spec ls   # 旧：Spec Registry 版本清单（不变）
```

intent 格式（`nf-intent/1`，未知字段即拒）：

```json
{"schema": "nf-intent/1", "kind": "output", "goal": "…",
 "wiki_ids": ["wiki:module:M06", "wiki:protocol:schema/module"],
 "constraints": ["硬约束 1", "硬约束 2"],
 "budget": {"max_tokens": 1200, "max_steps": 3}}
```

## 编译产物（`nf-spec-bundle/1`）

- `spec`（`nf-spec/1`）：kind / ref / digest（intent+refs 的 canonical sha256）/ constraints / version。
- `tasks[]`（`nf-task/1`）：每个 Wiki 页一个任务——slot（有界）、spec_refs（ref+digest）、context_refs（页 id+digest）、output_schema、acceptance（A-001/A-002）、budget（必填）。
- `graph`：选中页之间的 relations 图；编译前做拓扑检查，**有环即拒**。
- `intent_digest`：输入指纹；同输入同字节。

## 错误码（exit 2 + 修复指引）

| 码 | 触发 |
|---|---|
| `SPEC-KIND-UNKNOWN` | kind 不在 protocol/module/pipeline/asset/domain/output |
| `WIKI-ID-UNKNOWN` | wiki_ids 指向不在场页面（或 Wiki 未编译） |
| `INTENT-INVALID` | 坏 JSON / 缺字段 / 未知字段 / budget 非法 |
| `TASK-GRAPH-CYCLE` | 选中页 relations 成环 |

## 边界

- 本件只到「spec+task 计划」；真实装配/执行属 G2（WP-21 Assembly Runtime）。
- check44（Spec 编译门禁）在 WP-13 接入 verify.sh；当前由判据模块与 CLI 自检承担。
