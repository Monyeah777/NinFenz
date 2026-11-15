# ADR-APP-007：VIP 只做领域 IDE 面（作者/图/DSL/评审），不做通用 IDE

| 项 | 值 |
|---|---|
| 编号 | ADR-APP-007 |
| 状态 | accepted |
| 日期 | 2026-11-15 |
| 范围 | NF APP（Android / Desktop / 平板控制面 + 共享核心） |
| 上位 | `STRATEGY.md` → `app/docs/CONTRACT.md`（A0 冻结）/ `app/docs/CLI.md` |

## 背景

面向专业作者的高阶能力（计划称 VIP）容易被扩张成「通用 Markdown 编辑器 + 代码 IDE + 云同步」。那会带来长尾功能、跨端一致性、无障碍与安全面爆炸，且与「无账号/无遥测/离线」定位冲突。需要把 VIP 的边界固化成可核口径。

## 决策

1. VIP = 专业作者面：`pro`/`expert` 模式 + 领域工作台（协议条款编辑、管线图、DSL、评审、打印、Pack 管理）。
2. 不做通用 Markdown 编辑器、通用代码 IDE、云同步、端上 LLM、长驻 MCP；范围外任务引导用户用外部编辑器处理后再导入（ADR-APP-005）。
3. 模式限制是**硬拒**不是 UI 灰化：`mode=simple` 时 branch/merge/asset 节点 → `NF-GRF-006`（exit 1），不静默忽略。
4. VIP 能力不引入新账号/订阅/遥测；功能分层只靠模式与领域包，不靠服务端鉴权。

> 口径说明：计划原文（作者本地输入）未入仓，本 ADR 把「VIP」固化为可核口径（`pro`/`expert` 模式 + 领域工作台）。若与计划本意不符，以修订本 ADR 为准，不在实现里做第二套解释。

## 后果

**正面**

- 面窄可深：把工程投入集中在协议/图/评审这些真差异点。
- 避免通用编辑器长尾（语法高亮/插件/协作/云盘）拖垮质量。
- 模式限制在核心层强制，UI 无法绕过。

**负面 / 代价**

- 用户需要外部编辑器处理范围外任务（体验不连贯）。
- pro/expert 模式与 schema 校验强耦合：模式切换会让部分已有图失效（需显式提示与迁移）。
- 不做账号/订阅意味着无法用「付费解锁」做能力分层。

## 替代方案（及否决理由）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. 全功能通用 IDE | 否决 | 范围爆炸；与离线/无账号冲突 |
| B. 纯表单（无图/无 DSL） | 否决 | 专业作者需要图与 DSL；且图已是 A2 核心能力 |
| C. 分级订阅锁 | 否决 | 需账号与服务端；违反无账号/无遥测 |
| D. VIP = 只读高级检视 | 否决 | 不覆盖专业作者的写操作需求 |

## 证据落点

| 证据 | 路径 / 判据 |
|---|---|
| 非目标清单（不做通用编辑器/IDE/云同步/端上 LLM/长驻 MCP） | `app/README.md` 边界节 |
| 模式限制与错误码（simple 禁 branch/merge/asset） | `app/docs/CONTRACT.md` §5.4；`app/schema/error_codes.json`（NF-GRF-006） |
| 图/模式结构（mode enum、nodes/edges/weights） | `app/schema/nf-pipeline-graph.schema.json` |
| 决策被实现层的引用点 | `app/core`（`graph-validate`）与 `app/docs/CLI.md` §3 |

## 复审条件

- 作者流出现范围外强需求（多人协作、学术引用、插件）时——先评估是否改仓库流程而非扩 APP。
- simple 模式被证明不可用（大量作者被迫升模式）时。
- 术语「VIP」与计划本意不一致时（改本 ADR，不散改实现）。

> 本 ADR 只声明决策与边界。实现状态以 `app/docs/ARCHITECTURE.md` §5/§11、`app/results/GATES.json` 与现场复跑命令为准；未落地项写 `OPEN`，不得据本 ADR 声称「已实现」。
