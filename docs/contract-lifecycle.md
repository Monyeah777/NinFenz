# 契约生命周期与义务（WP-30，G3）

> ⛔ 操作指令：本件是 WP-30 契约生命周期/义务的人读说明；机读真源 `protocol/contract_lifecycle.json`（`nf-contract-lifecycle/1`），判据 `desktop/tests/test_contract_lifecycle_contract.py`，实现 `desktop/src/core/contract_lifecycle.py`。不新增 `nf-contract/1` schema 字段（additionalProperties=false）。
> 状态：v1（G3 · 2026-11-15）· 依据：G3 WP-30（契约生命周期/义务/证据要求）

## 状态与义务

| 状态 | 可消费 | 可被引用 | evidence 下限 | acceptance | 义务 |
|---|---|---|---|---|---|
| `draft` | ✗ | ✗ | 0 | 否 | 不得被其它契约/产物引用 |
| `active` | ✓ | ✓ | ≥1 | 是 | constraints 每条可核；证据/验收可解析 |
| `deprecated` | ✗ | 仅既有 | ≥1 | 是 | 既有引用可读、**禁止新增引用**；证据保留 |
| `retired` | ✗ | ✗ | ≥1 | 是 | 证据不得静默删除；不得进入新装配/引用 |

## API

```python
from core import contract_lifecycle as cl
issues = cl.check_contract(contract_doc)          # 按状态义务校验（不抛）
ok = cl.can_reference("deprecated", new_reference=True)  # False（existing-only）
cl.check_registry()                                # 义务表自检
```

## 义务 → 既有门禁映射

- `evidence-presence` / `acceptance-presence`：本模块 `check_contract`；
- `lifecycle-gate`：check35 一致性报告 + check38 发布体检（按状态使用）；
- `module-lifecycle`：check24 模块生命周期（同纪律：deprecated/retired 不得被引用）。

## 边界

- 本件只定义状态义务与引用策略；治理 verify 适配（WP-31）、Attachment 模式（WP-32）、治理报告/审计包（WP-33）不在此件。
- 契约实例的 evidence/acceptance 引用解析属治理面校验，避免把「引用存在」与「引用有效」混为一谈。
