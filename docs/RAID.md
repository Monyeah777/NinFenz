# RAID 与风险治理（RAID）

> ⛔ 操作指令：本件是 NF-Final §16A.4 RAID 人读面；机读真源 `protocol/raid.json`（`nf-raid/1`），与 `results/assurance/CLAIMS.json` 的缺口一一绑定，判据 `desktop/tests/test_assurance_contract.py`。每 Gate 复审。
> 状态：v1（G0 · 2026-11-14）· 依据：§16.1 风险 R-01…R-08 + ISO 31000 / ISO/IEC 27005 / NIST AI RMF 思想
> 纪律：概率×影响只写 low/medium/high 逻辑档；未关闭项必须有 owner/触发/缓解/复审。

## 风险矩阵（R）

| 编号 | 风险 | 概率 | 影响 | owner | 触发 | 缓解 | 复审 | 状态 |
|---|---|---|---|---|---|---|---|---|
| R-01 | 生产被治理拖重 | high | high | architecture | import/延迟上升 | check49 双平面闭包 + core-only 目标 | 每 Gate | mitigated |
| R-02 | Wiki 变第二真源 | high | high | wiki | 手改/重复正文 | 生成物禁手改 + wiki-page schema + 新鲜度判据 | G1 | partial |
| R-03 | Agent 忽略 spec | high | high | production | 编造引用 | 无 spec 不生成 + nf-task/1 槽位 + 引用校验（G1/G2） | G1/G2 | partial |
| R-04 | 规范过度/上下文超预算 | medium | medium | context | 上下文超预算 | 短页/分层/注入预算上限 | G1 | mitigated |
| R-05 | 治理范围膨胀 | medium | high | governance | 新「通用信任」需求 | 只做契约约束下产物/流程 | 每 Gate | mitigated |
| R-06 | 生态标准变化 | medium | medium | trust | 上游协议变更 | 适配器隔离 + 冻结向量 | 每版本 | mitigated |
| R-07 | 双平面版本漂移 | medium | high | architecture | 兼容失败 | 契约版本 + 双方 contract test | G3 | partial |
| R-08 | 自扫描遗漏 | medium | high | qa | P0 反复 | S0–S15 + 变异/负例 + 外部复核 | 每 Gate | partial |

## 假设（A）

| 编号 | 假设 | owner | 触发 | 缓解 | 状态 |
|---|---|---|---|---|---|
| AS-01 | 用户需要规范驱动交付而非又一个 Agent | product | 访谈否定 | 回退产品假设（OPEN-PRODUCT） | open |
| AS-02 | 本地优先足以覆盖目标场景 | product | 出现强在线协作需求 | 适配器对接外部服务，不改离线核心 | open |
| AS-03 | 关键判定抽样变异测试即可代表测试有效性 | qa | 关键面 mutation 存活 | 扩到大面积 mutation（OPEN-MUT） | open |

## 问题（I，link 到保证案例缺口）

| 编号 | 问题 | 严重度 | owner | 缺口 |
|---|---|---|---|---|
| I-01 | Wiki/spec 编译器未建 | high | WP-10/11 | OPEN-G1 |
| I-02 | 跨 Agent parity 判据未建 | high | WP-20 | OPEN-G2 |
| I-03 | 全仓 mutation score 未测 | medium | WP-0H/54 | OPEN-MUT |
| I-04 | 产品发现/价值验证需外部访谈 | medium | WP-0A | OPEN-PRODUCT |
| I-05 | 外部提交/见证/语言服务/第三方合规审核 | medium | 维护者 | OPEN-EXTERNAL |

## 依赖（D）

| 编号 | 依赖 | owner | 触发 | 缓解 | 状态 |
|---|---|---|---|---|---|
| D-01 | GitHub（托管/CI/Advisory） | maintainers | 断供/封禁 | 本地仓库 + 远端镜像（`docs/legal/VENDORS.md`） | active |
| D-02 | 包注册源 | maintainers | 供应链投毒/断供 | 固定版本 + SBOM + 依赖审计 + 离线镜像 | active |
| D-03 | 外部 TSA/Rekor | trust | 不可达/行为变化 | 显式降级、不声称 T3/T4、离线验证已抓取证据 | active |

## 干系人（Stakeholders）

| 编号 | 角色 | 关注点 |
|---|---|---|
| S-01 | 维护者/作者 | 方向、质量与发布裁决 |
| S-02 | 使用者（内容生产者） | 可交付、可复现、离线可用 |
| S-03 | 外部审查者/复现者 | 证据可独立复算 |
| S-04 | 第三方投稿人 | 投稿条款与署名 |

## 变更控制

- 流程：Conventional Commits + 门禁（`verify --checks-only`）+ 冻结链；破坏性变更走新版本号/ADR。
- 记录：`CHANGELOG.md` + `decisions/` + `protocol/adr/registry.json`。
- 依据：`docs/release.md`。

## 复审节奏

每 Gate 复审一次；P0 风险（R-01/R-02/R-03/R-05/R-07/R-08 中 high 影响项）进保证案例 rebuttal，关闭前不得进下一 Gate。
