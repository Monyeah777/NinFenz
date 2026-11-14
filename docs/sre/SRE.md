# SRE / SLO（本地优先工具）

> ⛔ 操作指令：本件是运维目标与可观测口径；机读真源 `protocol/ops.json` 的 `slo` 段，判据 `desktop/tests/test_ops_contract.py`。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §15A.3/§15A.4
> 纪律：本仓是**本地优先**工具，不运营在线服务 ⇒ 不写「99.9% 可用性」这类不成立承诺；SLO 针对**正确性/可复现/离线**。

## SLO

| 编号 | 目标 | 口径 | 测量 | 证据 |
|---|---|---|---|---|
| SLO-01 | 门禁可复跑 | `bash verify.sh --checks-only` FAIL=0 | 每次提交与 CI | `verify.sh` |
| SLO-02 | 证据可复算 | 在盘报告 == 实时重算（freshness 4/4） | `scripts/freshness_check.py` | `scripts/freshness_check.py` |
| SLO-03 | 离线可用 | 核心路径不联网可跑；外部锚/网络动作显式可选 | 离线语义与测试 | `desktop/src/core/trust/public_anchor.py` |

## 错误预算（逻辑）

- 本仓没有「在线可用性」预算；等价物是**门禁宽松度**：任何一条 check 由红转绿必须给出修复证据，不允许靠降阈值/删判据「消费预算」。
- 质量债按 `docs/QUALITY_DEBT.md`（G5 建）与自审计 P1 owner 管理；超期债务进入下一 Gate 的退出条件。

## 可观测与恢复

- 机器可读出口：`protocol/verification_report.json`（判据表 + 声明 vs 实测）、`results/ops/drills.json`（演练）、`results/independence.json`（边界）。
- 日志纪律：不写秘密；门禁日志本地 `.nf-logs/`（gitignored、ephemeral，见 `docs/privacy/RETENTION.md`）。
- 失败可解释：错误消息须带修复指引（`purity_scan` 的 raise 面无指引即红）。
- 恢复流程见 `docs/sre/BCP_DR.md`；事件流程见 `docs/security/INCIDENT_RESPONSE.md`。

## 事件指标（逻辑口径）

| 指标 | 定义 | 用途 |
|---|---|---|
| MTTR（逻辑） | 从分级到修复入仓的步骤数/会话数，不记日历 | 趋势，不作承诺 |
| 变更失败率 | 回滚/热修提交占变更比例 | 质量趋势 |
| 演练通过率 | DR-01..DR-04 全过 | Gate 退出条件 |

## 局限

- 单维护者 + 本地运行：无 on-call 值守、无 7×24；对外部依赖（GitHub/TSA/公共日志/包源）只有退出计划与显式降级，不承诺外部可用性。
