# 质量债登记（QUALITY DEBT）

> ⛔ 操作指令：本件登记 CQ 审查发现的存量债/接受风险（CQ0/CQ1 起）；每条必须有 owner、状态与复审点；棘轮=只增不减。判据 `desktop/tests/test_cq_scan_contract.py`（结构）与 `scripts/cq_scan.py --check`（新鲜度）。
> 状态：v1（G0 · 2026-11-14）· 依据：`docs/CQ_REPORT.md`、`NF-Final-方案-2026-11-13.md` §13B.7

## 债务表

| 编号 | 来源 | 严重度 | 内容 | owner | 状态 | 复审 |
|---|---|---|---|---|---|---|
| QD-01 | radon-cc | P2 | 核心面 CC>15 存量 **302** 个函数（max CC 99）；已由 `code_metrics_baseline` 棘轮冻结，新增必红 | maintainers | baseline-frozen | 每阶段 / CQ6 |
| QD-02 | bandit | P2 | medium **4** 条（无 high）；逐条人工复核后修或登记 ACCEPTED-RISK | security | open | CQ2 |
| QD-03 | bandit | P3 | low **35** 条（多为 subprocess 等允许面）；人工确认后白名单或修 | maintainers | open | CQ2 |
| QD-04 | vulture | P3 | 未使用变量 2 处（`eval_collapse.py:32`、`chain_vertical.py:164`） | maintainers | open | CQ3 |
| QD-05 | toolchain | P1（流程） | `cosign` / `gitleaks` 不在场 → 外部签名锚/秘密扫描在本机 **BLOCKED**；`dotnet` 命令不可用（不冒充 .NET 门禁） | maintainers | blocked | 环境修复后复跑 |
| QD-06 | 测试质量 | P2 | 全仓 mutation score 未测（当前只有关键面抽样；`OPEN-MUT`） | qa | open | CQ3 / G5 |
| QD-07 | 人工审查 | P2 | CQ2 人工高危审查（信任/治理/生产/密钥/路径/MCP）未做；CQ1 仅自动扫描 | maintainers | open | CQ2 |
| QD-08 | 跨语言 | P2 | cargo/dotnet 构建门禁本轮未跑（`cargo` 可用但未构建；`dotnet` BLOCKED） | engine | open | CQ4 |
| QD-09 | CQ6 | P2 | CQ6 复审签署未完成（AI 不代签，评分卡 signoff=pending-human） | author | open | 人工复审 |
| QD-10 | CQ6 | P2 | 核心覆盖率/全仓 mutation score 未测（评分卡 D4 扣分；coverage 工具在，未接线） | qa | open | CQ3 / G5 |
| QD-11 | CQ6 | P2 | Go↔Python parity 与离线验证未做（评分卡 D5=2；WP-51） | maintainers | open | WP-51 |

## 规则

- 新发现先入本表再修；`P0` 阻断下一 Gate，`P1` 须有 owner 与期限逻辑（当前 Gate 内），`P2/P3` 进棘轮只许收敛。
- `ACCEPTED-RISK` 必须写理由、owner、复审点；不得静默消失。
