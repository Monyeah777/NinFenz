# 业务连续与灾难恢复（BCP / DR）

> ⛔ 操作指令：本件给资产备份/恢复与故障场景；恢复演练可跑（`python scripts/ops_drill.py --check`）。改流程必须同步 `protocol/ops.json`，否则判据红。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §15A.4（ISO 22301 思想）
> 纪律：RTO/RPO 是**逻辑口径**（步骤/提交边界），不是日历承诺；密钥丢失不伪造旧 key。

## 资产与备份

| 编号 | 资产 | 备份 | RTO（逻辑） | RPO（逻辑） | 恢复 |
|---|---|---|---|---|---|
| A-01 | 真源与代码 | git 历史 + 远端镜像 | 一个工作会话内 | 最后一次提交 | `git clone/fetch` + 回执校验 |
| A-02 | 证据/回执 | git 历史 + 每阶段重算 | 同上 | 最后一次冻结 | 重跑冻结链（conformance → approve → receipts） |
| A-03 | 密钥/信任材料 | 用户离线备份（不入仓） | 轮换后新证据 | 不适用（旧证据仍可验） | 新 key 签新证据；旧证据按历史验证，不伪造旧 key |

## 故障场景与恢复步骤

| 编号 | 触发 | 影响 | 步骤 | 期望 | 演练 |
|---|---|---|---|---|---|
| BCP-01 | 本机磁盘丢失/工作区损坏 | 工作区与未提交面丢失 | git clone 恢复真源 → 按序重跑冻结链 → `bash verify.sh --checks-only` | FAIL=0 且 freshness 4/4 | recovery（DR-02） |
| BCP-02 | 密钥丢失或泄露 | 旧签名不可再用于新证据 | 撤销/轮换 → 旧证据按历史验证 → 新证据用新 key | 旧证据可验、新证据新 key；不伪造旧 key | tabletop（DR-01） |
| BCP-03 | TSA/公共日志不可达 | T2/T4 外部锚不可得 | 显式降级 → 报告写缺项 → 不冒充等级 | 缺锚 exit 2 / 不声称 T3/T4 | tabletop（DR-01） |

## 恢复演练（DR-02，可执行）

`core.ops.recovery_drill` 做真实闭环（不写仓、不联网）：

1. 用 claim bundle 构建受保护对象并验证通过（= 有备份）；
2. 篡改备份副本的一个 claim 摘要 → Merkle 根重算不一致（= 损坏被检出）；
3. 从备份恢复 → 再次验证通过（= 恢复有效）。

机检：`python scripts/ops_drill.py --check`（在盘 `results/ops/drills.json` == 实时重算）；单测见 `test_ops_contract.py`。

## 备份纪律

- 证据/回执默认不可变；GC 只删无引用且已归档副本（见 `docs/privacy/RETENTION.md` 与 `protocol/privacy.json`）。
- 密钥材料绝不入仓/入日志；备份走用户离线介质。
- 恢复后必须重跑冻结链与门禁，禁止用旧报告冒充新状态。

## 不承诺

- 不承诺外部服务可用性、不承诺日历级 RTO/RPO；真实灾难（磁盘物理损坏/密钥介质丢失）的最终恢复依赖用户备份。
