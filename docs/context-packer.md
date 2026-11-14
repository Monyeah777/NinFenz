# Context Packer（`nf wiki context --role`，WP-12）

> ⛔ 操作指令：本件是 WP-12 上下文打包的人读说明；实现 `desktop/src/core/context_packer.py`，判据 `desktop/tests/test_context_packer_contract.py`。打包产物只含 Wiki 页摘要 + spec_ref + citations，不复制正文。
> 状态：v1（G1 · 2026-11-14）· 依据：§13A L3（页面/引用齐全、预算、角色隔离、抗注入）

## 用法

```bash
# 轻量上下文（旧行为，无角色/注入处理）
python scripts/nf.py wiki context wiki:pipeline:P00_通用文档生成管线 --budget 1200

# 按角色打包（nf-context-pack/1；报告含 citation_rate/injection/role_isolated）
python scripts/nf.py wiki context wiki:module:M06 wiki:protocol:schema/module \
  --role reviewer --budget 4000
```

## 契约

| 项 | 规则 |
|---|---|
| 条目 | 必带 `spec_ref` + `citations`；`citation_rate` 必须 100% |
| 预算 | `max_chars` 硬上限；超预算必 `truncated=true`；**spec_ref/citations 永不截**，仅可截 summary |
| 角色 | `author`：module/pipeline/domain；`reviewer`：全部页面类型；`governance`：protocol/asset；未知角色 → `ROLE-FORBIDDEN`（角色升级=0） |
| 抗注入 | summary 命中「忽略以上指令 / ignore previous / system prompt」等 → 替换为 `[已移除可疑指令]`，`injection` 计数 + `sanitized=true`；**不执行页面内指令** |
| 确定性 | 同 ids/task + 同预算 + 同角色 → 逐字节一致（稳定排序，无时间戳） |

## 报告（`nf-context-report/1`，嵌入 pack.report）

`task_slot` / `role` / `budget_chars` / `used_chars` / `entries` / `truncated` / `injection` /
`citation_rate` / `role_isolated` / `allowed_types` / `over_budget`。

## 边界

- 本件只做「上下文打包」；spec→task 属 WP-11，真实装配/执行属 G2。
- 打包不落盘为固定产物（避免 Wiki 真源变化造成陈旧件）；需要报告时用 `--role` 输出 JSON 或由 CQ 轮次生成 `context-report.json`。
