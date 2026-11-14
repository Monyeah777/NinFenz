# 事件响应与漏洞披露（INCIDENT RESPONSE）

> ⛔ 操作指令：本件是事故处理 runbook；通道权威在 `SECURITY.md`，机读登记在 `protocol/ops.json`，演练判据 `desktop/tests/test_ops_contract.py`。改步骤必须同步真源，否则判据红。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §15A.4（NIST SP 800-61 思想）
> 纪律：不写日历修复 SLA；「确认/协调披露」是流程口径，不是保证；不把 S0/S1 写成已解决。

## 这份文件管什么

- 出事了按什么分级、谁做什么、证据怎么保、什么时候披露、怎么复盘。
- 披露通道与窗口以 `SECURITY.md` 为唯一权威（GitHub Security Advisories 私密通道）；本件只定义流程衔接。
- 演练：桌面演练（DR-01）+ 披露演练（DR-03），命令见文末。

## 严重度分级

| 编号 | 定义 | 响应 | 披露义务 |
|---|---|---|---|
| S0 | 密钥/证据泄露、越权、可伪造、可静默篡改 | 立即隔离 + 取证 + 撤销/轮换密钥 + 阻断发布 | 必须（协调披露） |
| S1 | 安全/信任判定错误、证据链断裂、默认放行 | 阻断发布 + 最小修复 + 回归测试 | 必须 |
| S2 | 功能错误、契约不满足、不可复现 | 常规修复；影响面进质量债 | 按需（涉信任/用户数据升级） |
| S3 | 质量、性能、兼容、文档问题 | 进质量债/文档修复 | 通常不需要 |

## 角色

报告人 · 受理人（maintainer）· 修复人 · 复核人（非唯一作者；高风险需独立复核）。

## Runbook

| 编号 | 步骤 | 动作 | 证据/入口 |
|---|---|---|---|
| IR-01 | 发现/受理 | 经 `SECURITY.md` 私密通道或门禁/CI 告警进入；记录时间线与事件编号 | `SECURITY.md` |
| IR-02 | 分级 | 按上表定 S0-S3；S0/S1 立即升级并阻断发布 | `protocol/ops.json` |
| IR-03 | 隔离 | 停止相关写盘/发布；撤销或轮换受影响凭据 | `CONTRIBUTING.md` |
| IR-04 | 取证 | 保全只读证据（digest/回执/日志），不覆盖现场 | `desktop/src/core/evidence.py` |
| IR-05 | 修复 | 最小修复 + 回归测试 + 冻结链按序重跑 | `verify.sh` |
| IR-06 | 披露 | 按 `SECURITY.md` 协调披露；修复优先于披露，不单方面公开 | `SECURITY.md` |
| IR-07 | 复盘 | postmortem 记根因/行动项/owner，行动项进质量债 | `postmortems/` |

## 披露口径（逻辑，不承诺 SLA）

- 通道：**GitHub Security Advisories（私密）**；确认目标 ≤ **7 天**、协调披露目标 ≤ **90 天**（从确认受理起；修复已发布可提前）。
- 天数是流程口径，**不是修复 SLA**；不单方面公开；需要 CVE 时经 GitHub（CNA）请求。
- 凭据类问题一律按已泄露处理：立即撤销重建（见 `CONTRIBUTING.md` Token 轮换 SOP）。

## 演练与判据

- 桌面演练（DR-01）：按严重度输出每步 required/skipped + 披露义务，确定性映射，不"看情况"。
- 披露演练（DR-03）：私密通道存在、确认/披露窗口有序。
- 命令：`python scripts/ops_drill.py --check`、`python -m pytest desktop/tests/test_ops_contract.py -q`；报告 `results/ops/drills.json`。

## 不承诺

- 不承诺修复时限/无中断；不声称合规或认证；演练是**桌面/静态**层面，真实渗透与外部协调属外部操作。
