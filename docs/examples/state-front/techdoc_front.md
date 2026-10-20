## 状态块（条件先行摘要）

> 本块由产物**确定性提取**（非模型生成）——它是该产物的「状态文本代理」，供重读时先对齐状态。

| 项 | 值 |
| --- | --- |
| 模块/挂载编号 | M00、M01、M02、M03、M04、M06、M07、M08、M09、M10、M11、M12、M13、M14、M15、M16、M17、M18、M19、M20、M22、M23、M24、M40、M41、M43、M50、M55、M65、M80、M90、M91、M93、M97、M98、P00、P01、P02、P03、P06、P10、P20、P30、P40、P50、P60、P70、P80、P90 |
| NF 编号 | NF-1、NF-TECHDOC-Monyeah777-1 |
| 二级标题数 | 89 |
| 要点行数 | 158 |
| 原文 sha256 | `25ca28cdcccea1a3` |

**关键设置点（原文摘录，非改写）**：

- 04_模块库（官方核心 13 件）
- community/技术文档域包（自带 2 件 + P06 管线）
- 技术文档
- 自包含
- 装配样本
- **需求原话**：「组装一个技术文档生成流程的完整版：要有术语管理与修订记录，能直接交给任意 AI 装载开跑」
- **选件决策**（`nf assemble` 装配计划实测输出）：
- 匹配预设：技术文档域包 → 管线 **P06**（`community/技术文档域包/pipelines/P06_技术文档题材装配流管线.md`）

---

---
id: NF-TECHDOC-Monyeah777-1
type: 技术文档装配（自包含完整版）
title: 技术文档装配流 P06 · 自包含完整版
description: 技术文档域包 P06 装配的自包含完整版——15 件模块正文与管线声明全文内嵌、零资产、无需仓库路径即可装载开跑
author: Monyeah777
license: MIT
generated: 2026-09-15
verified: 2026-09-15
status: active
stale_after: 2027-03-15
sources:

- 04_模块库（官方核心 13 件）
- community/技术文档域包（自带 2 件 + P06 管线）
tags:
- 技术文档
- 自包含
- 装配样本

---

> 📚 NF 云端图书馆条目 **NF-TECHDOC-Monyeah777-1** · 入库 2026-09-15 · 投稿人：Monyeah777 · 类型：装配样本（自包含）
> 许可：MIT（登记表同列同值）

> 档位：**全文内嵌式（自包含）**——与 `NF-1`、「西幻生存流 P03 样本」的**引用式**相对。
> 引用式档位的正文以仓库路径与 `assets/` 为准，离线须另粘贴；本件不引用任何仓库路径：
> 15 件模块正文与 P06 管线声明全部内嵌，任何 AI 单文件即可装载开跑。

---

## 0. 装配记录

- **需求原话**：「组装一个技术文档生成流程的完整版：要有术语管理与修订记录，能直接交给任意 AI 装载开跑」
- **选件决策**（`nf assemble` 装配计划实测输出）：
  - 匹配预设：技术文档域包 → 管线 **P06**（`community/技术文档域包/pipelines/P06_技术文档题材装配流管线.md`）
  - 取件模块：**M97 术语管理**（P40 行为决策）、**M98 修订记录**（P60 长期演变）
  - 装配允许集：官方核心 + 包模块 = **44**；本件实际内嵌 **15** 件（核心 13 + 自带 2）
  - 资产：**0 文件**（技术文档域包为机制增强包，无题材资产，同通用核心基础包先例）
  - references：**0**（零跨包引用，`core_only: true`）
- **档位声明**：全文内嵌式。本件与引用式样本的差异不在内容，在**可离线自足性**——
  引用式需要接收方另取仓库文件，本件不需要。
- **缺口声明（如实）**：
  - ① 本件内嵌的是**模块层**正文与管线声明；`01_核心协议`/`02_联动注册表`/`06_Agent执行协议` 三份协议件不内嵌——
    它们是全库共用的上位规范，非本装配的专属件（引用式样本同样如此）。
  - ② 内嵌正文为 2026-09-15 仓库快照的**逐字节复制**，不含改写；上游模块若变更，本件须重新生成。
  - ③ 本件未挂签名锚（`anchor_*` 字段缺省），如需第三方独立验真，另走 `nf library attest`。

## 1. 文档域速览

- **定位**：技术文档装配流（非叙事题材）——把「术语一致性 + 修订可追溯」这两条技术文档的工程纪律，做成可装载的产线。
- **主轴**：M90 结构骨架（P00 位装载 DocState）→ **M97 术语管理**（P40：登记/补定义/冲突检测）→ **M98 修订记录**（P60：版本递增/变更日志/回溯）→ M80 质检渲染（P80）。
- **产物形态**：技术文档装配产物，供下游 agents / mcp / skill 适配器消费。
- **输出门**：M80 是唯一渲染出口（gate 唯一出口，与叙事流同规矩）。
- **域中立证据**：本件与校园情感、西幻生存两类叙事包**共用同一套官方核心**，仅替换题材层的 2 件与 1 条管线——这是「机制不绑域」的可装载证据。

## 2. 管线（P06 · 技术文档题材装配流 · techdoc 九层回卷）

挂载投影（源自 P06 layers，逐层列出）：

| 层 | 挂载（default） | 职责 | 归属 |
| --- | --- | --- | --- |
| P00 数据基座 | M00、M90 | 数据槽装载 + 技术文档结构骨架（DocState 产） | 官方核心 |
| P40 行为决策 | **M97** | 术语管理：DocState.terms 登记/补定义/冲突检测 | 本包 |
| P60 长期演变 | **M98** | 修订记录：DocState.revision 版本递增/变更日志/回溯 | 本包 |
| P80 输出呈现 | M80 | 质检渲染（gate 唯一出口） | 官方核心 |
| 全局调度 | M50 | 主循环：回合 begin → 逐层推进 → end 一致性校验 → 回卷 | 官方核心 |

管线声明原文（内嵌）：

```markdown
# 管线 P06 · 技术文档题材装配流
> 社区版「技术文档域包」使用的管线（v2.1.0-C-b 战例落盘）。以「非叙事题材：技术文档装配」为流主轴：官方 M90 技术文档结构（P90 链官方模块，core_modules 依赖引用不搬移）在 P00-P60 位产 DocState 骨架/正文/决策/装配；本包自带 M97 术语管理挂 P40 位做术语域深化（DocState.terms 统一性），M98 修订记录挂 P60 位做修订域追踪（DocState.revision 版本/回溯）；P80 输出呈现仍由官方核心 M80 质检渲染（gate 唯一出口，同叙事流）。
> 实例声明：本管线是通用骨架 **P00**（03_管线库/P00_通用文档生成管线.md）在**技术文档·题材装配**的实例——九层位名沿用骨架；本包 P40/P60 两驻留自带模块（M97/M98），M90 官方模块经依赖引用随流协作（M90 本体不复制进包，I5 单一真相源）。
> **允许编号段固化（R2，v2.1.0-C-b）**：本包 `allowed_modules` 仅限官方核心（M00 / M80 / M90 等 core_modules 13 件含 M90）与本包社区段（M97 / M98，modules/ 在册 2 件）。references=[] 零跨包零借阅。
> **挂载层规避（check15 ③）**：官方 P00 骨架九层 default 均空；既有社区包同层 default（校园 P40=[情感:M22,M40...]、P60=[M40,M65]；西幻 P40=[M04,M11]、P60=[生存:M10...]）与本包 P40=[M97]、P60=[M98] 无交集——M97/M98 新编号唯一，独立装载不冲突（32 方案反证实证）。
```yaml
Pipeline:
  id: P06
  name: 技术文档题材装配流
  structure:
    type: techdoc
    flow:
      - from: P00
        to: P10
      - from: P10
        to: P20
      - from: P20
        to: P30
      - from: P30
        to: P40
      - from: P40
        to: P50
      - from: P50
        to: P60
      - from: P60
        to: P70
      - from: P70
        to: P80
      - from: P80
        to: P00
        condition: =data_bus.round.phase == "roll" && event.tick_day
  layers:
    - id: P00
      name: 数据基座
      description: 官方 M00 数据槽（core 依赖；技术文档 DocState 主载体，M90 结构骨架在此装载——M00/M90 本体驻官方位不搬移）
      optional: false
      default_modules: []
      allowed_modules: [M00, M90]
    - id: P40
      name: 行为决策
      description: 术语决策层：自带 M97 术语管理审 DocState.terms（登记/补定义/冲突检测，publish term_synced）
      optional: false
      default_modules: [M97]
      allowed_modules: [M97]
    - id: P60
      name: 长期演变
      description: 修订层：自带 M98 修订记录维护 DocState.revision（版本递增/变更日志/回溯，publish revision_recorded）
      optional: false
      default_modules: [M98]
      allowed_modules: [M98]
    - id: P80
      name: 输出呈现
      description: 官方核心 M80 输出生成器（gate 唯一出口；读 term_synced/revision_recorded 后质检渲染）
      optional: false
      default_modules: []
      allowed_modules: [M80]
```
```

## 3. 注册表投影

本次装配的执行顺序（可由 P06 layers 与官方 02 执行顺序推出，不硬编码于产物内）：

| 步 | 层 | 模块 | 动作 | 写入 |
|---|---|---|---|---|
| 1 | P00 | M00 | 装载数据槽结构（DocState 主载体） | 初始数据槽 |
| 2 | P00 | M90 | 装载技术文档结构骨架（章节层级/文档类型） | DocState 骨架 |
| 3 | 全局 | M50 | 回合 begin：打快照 | round.begin 快照 |
| 4 | P40 | M97 | 术语登记/补定义/冲突检测 → 发布 `term_synced` | DocState.terms |
| 5 | P60 | M98 | 版本递增/变更日志/回溯 → 发布 `revision_recorded` | DocState.revision |
| 6 | P80 | M80 | 读 `term_synced` / `revision_recorded` 后质检渲染 | 玩家可见文档 |
| 7 | 全局 | M50 | 回合 end：一致性校验 → 回卷下一回合 | 存档 |

> 说明：上表为本次装配的**投影**，供接收方装载时对照；执行顺序的真源仍是接收方所装载的注册表（02 不变式 I5：顺序一律读注册表，禁止硬编码）。

## 4. 模块库（15 件 · 正文全文内嵌）

> 下列 15 段为**逐字节内嵌的模块正文原文**（置于代码围栏内，便于机器验收跳过扫描）。
> 每段前的粗体行标明：模块号 / 名称 / 归属 / 源文件路径（路径仅作溯源标注，装载不需要仓库）。

**4.1 M00_数据槽总线** · 归属：官方核心 · 溯源：04_模块库/通用类/M00_数据槽总线.md

```markdown
# 模块 M00 · 数据槽总线

> 类别：通用｜来源：核心｜挂载点：P00 数据基座（active）｜依赖：无｜被依赖：通用:M10、M50、M23、M24、M20、M90（核心；社区侧依赖见各包模块 inputs 声明）

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M00
  name: 数据槽总线
  category: 通用
  layer: P00
  inputs: []
  outputs: []
  events:
    publish: []
    subscribe: []
  interfaces: []
  io_types:
    outputs: {}
    inputs: {}
```

## 1. 职责

定义全系统的**数据槽总线**与槽位契约，是所有模块读写的唯一数据通道。数据隔离（I4）与通信契约（I3）在此落地：模块之间不得直接互访内部状态，只能通过数据槽与事件交换。

## 2. 总线

```yaml
data_bus:
  schema_version: "1"     # 总线协议版本；只增不删，结构性变更须 bump 并注明迁移
  注册: 模块启动时声明 [读槽, 写槽]，冲突由 M00 拒绝并报错
  读写: 只允许写自己声明的槽；读他人槽须声明只读，写他人槽视为违例
  生命周期: 每回合结束由 M50 触发快照，供持久化与回卷
  active_pipeline: P01   # 当前装配管线 id（M50 调度/装配切换维护）
  round:                 # 主循环抽象状态槽（M50 写入；world_model slot 投影）
    phase: begin         # 主循环相位（begin/run/end/archive/roll）
    phase_trace: []      # 主循环相位轨迹（旧相位按迁移顺序追加）
```

## 3. 槽位模型（通用四类 + 域包扩展）

```yaml
slots:
  state:      # 实体状态槽：任意实体的属性与状态
    <entity_id>: {type, attributes: {}, state: {}, tags: []}
  relation:   # 关系槽：实体间关联（类型/权重/历史）
    <from>-><to>: {kind, weight, history: []}
  context:    # 上下文槽：时间/环境/全局标记
    time: {tick, ...}
    flags: {}
  queue:      # 队列槽：待处理条目与已消费条目
    pending: []
    consumed: []
  extensions: # 域包扩展命名空间：域专属槽位一律放这里（核心不预设）
    <namespace>: {}
```

- 核心只定义上述**结构与读写纪律**；实体字段、关系语义、环境维度由域包在自己的命名空间内声明，核心不内嵌任何领域字段。
- 形状演进只增不删（01 §7 V1）；新增顶层槽须在 02 §2 备注登记。

## 4. 冻结兼容槽位（Phase 1）

```yaml
# 以下槽路径是既有 machine/AI 通道与 world_model 的冻结寻址面（protocol/world_slots.json 在册）：
#   data_bus.active_pipeline / data_bus.round.phase / data_bus.round.phase_trace
#   WorldState.time.{tick,day,season,weather}
#   PlayerState.memories.{working,episodic,semantic}
# Phase 1 逐字保持（社区 107 包与管线 condition 依赖这些标识符）；
# Phase 2 迁移为 context.time.* 与 state.memories.*，并重签 world_slots.json。
```

## 5. 违例与边界

- 模块未声明写槽而写入 → M00 抛出 DATA_SLOT_VIOLATION，该写入丢弃并记录。
- 持久化读取时未知字段忽略并告警，不崩溃（向前兼容）。
```

**4.2 M06_流程状态机** · 归属：官方核心 · 溯源：04_模块库/事件类/M06_流程状态机.md

```markdown
# 模块 M06 · 流程状态机

> 类别：事件｜来源：共享｜挂载点：P30 内容生产（active）｜依赖：M20｜被依赖：M13、事件:M22｜发布：quest_state

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M06
  name: 流程状态机
  category: 事件
  layer: P30
  inputs: [M20]
  outputs: [quest_id, state, tick]
  events:
    publish: [quest_state]
    subscribe: [combat_result, travel_event, chaos_event, reputation_change]
  interfaces: []
  io_types:
    outputs:
      quest_id: string
      state: string
      tick: number
    inputs:
      M20: untyped
```

## 1. 职责

管理**流程/步骤的生成与状态机**：按模板实例化流程，维护其状态与链式依赖，按进度发布状态。是流程结构生成方——文本与表现交 M12/M13，具体结算交各自域模块。

## 2. 流程规则

```yaml
flow:
  id: # 流程模板（随域包）
  模板结构: 背景/目标/位置/关键实体/奖励/后续链
  触发条件: 依赖前置模块提供的状态与位置条件
  phase: available | active | complete | failed | chain_next
flow_chain:
  梯度: 每链若干环，奖励/后果随梯度升级
  断链: 失败后提供替代入口（不硬卡流程）
```

- 具体模板与数值随域包资产分发，经 asset_get 寻址。

## 3. 事件契约

```yaml
subscribe:
  combat_result: # 结算类目标达成判定（随域包）
  travel_event: # 到达/转移类目标判定（随域包）
  chaos_event: # 外部扰动改写目标/生成救援流程（随域包）
  reputation_change: # 评价升降开关流程线（随域包）
publish:
  quest_state:
    payload: {quest_id, phase, objective, location, reward, next_quest}
    subscribers: 需求消费方（随域包装配登记）
```

## 4. 结算流程

1. 流程生成器按触发条件实例化流程（取材自 M20 知识库与位置信息）。
2. 目标与位置/门槛绑定。
3. 推进 phase 变更并发布 quest_state。
4. 相邻模块据此调整表现与结算。

## 5. 违例与边界

- M06 **只生成流程结构与状态**：不写文本（M12）、不裁决结算（各域模块）、不直接改评价。
- 流程文本须经 M80 质检门（结构门 + profile 质量门）后输出，M06 内部不做渲染。
- 关键失败/回卷判定归对应域模块与 M50，M06 不自行判死。
```

**4.3 M08_环境状态** · 归属：官方核心 · 溯源：04_模块库/世界类/M08_环境状态.md

```markdown
# 模块 M08 · 环境状态

> 类别：世界｜来源：共享｜挂载点：P10 语境推进（available）｜依赖：通用:M10｜被依赖：域包消费方｜发布：weather_state

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M08
  name: 环境状态
  category: 世界
  layer: P10
  inputs: [通用:M10]
  outputs: [region, season, weather, day_phase, modifiers]
  events:
    publish: [weather_state]
    subscribe: [tick_day]
  interfaces: []
  io_types:
    outputs:
      region: untyped
      season: string
      weather: untyped
      day_phase: untyped
      modifiers: object
    inputs:
      通用:M10: untyped
```

## 1. 职责

管理**周期与环境状态**：按世界历推进周期，按周期权重生成环境状态，维护各区域当前环境并广播给依赖方。是环境依赖型模块的环境真相来源（具体维度与数值随域包）。

## 2. 周期与环境规则

```yaml
cycle:
  year_length: # 由域包/资产定义
  date: # 由 通用:M10 日历驱动
environment:
  generation: 按周期权重生成/延续（维度由域包定义）
  persistence: 环境状态持续若干 tick_day 后自然更替
effects:
  # 对下游域模块的修正由域包声明；核心只广播状态，不裁决结果
```

- 各区域环境描述与效果数值全表随域包资产分发，经 asset_get 寻址。

## 3. 事件契约

```yaml
subscribe:
  tick_day: # 通用:M10 → 周期演进与环境推进
publish:
  weather_state:
    payload: {region, season, weather, day_phase, modifiers}
    subscribers: 域包环境消费方
```

## 4. 结算流程

1. 收到 tick_day，推进日历。
2. 判定周期更替（跨期时广播周期事件）。
3. 按权重生成/延续当前区域环境。
4. 发布 weather_state，订阅方按需应用修正。

## 5. 违例与边界

- M08 **只计算环境状态并广播，不裁决结果**——修正由各域模块自行应用。
- 不得跳过 tick_day 自行推进时间（时间唯一来源是 通用:M10）。
- 环境异象若构成事件，须交事件:M22 组织，M08 不直接发布编排结果。
```

**4.4 M10_节拍推进** · 归属：官方核心 · 溯源：04_模块库/通用类/M10_节拍推进.md

```markdown
# 模块 通用:M10 · 节拍推进

> 类别：通用｜来源：核心｜挂载点：P10 语境推进（active）｜依赖：M00｜发布：tick_day

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: 通用:M10
  name: 节拍推进
  category: 通用
  layer: P10
  inputs: [M00]
  outputs: [tick, day, season]
  events:
    publish: [tick_day, minute_tick]
    subscribe: []
  interfaces: []
  tool_face:
    - purpose: 回合/日/子刻三轨时间换算与跨日判定
      candidates:
        - repo: https://github.com/arrow-py/arrow
          ref: 1.3.0
          license: BSD-2-Clause
          note: 成熟时间库，仅作实现参考；引用不等于背书，AI 可自造等价能力
      guidance:
        要算什么: 从 tick 折算 day、子刻、is_new_day 与 season_ctx
        输出形状: 整数 tick/day/子刻；布尔 is_new_day；字符串 season_ctx
        对接字段: outputs=[tick, day, season]，事件 payload 见第 4 节
        常见坑: 子刻推进只在需要的域包启用；跨日只发布一次 tick_day；禁止模块自行推进时间
  io_types:
    outputs:
      tick: number
      day: number
      season: string
    inputs:
      M00: state
```

## 1. 职责

驱动系统时间轴，维护 tick / day / season 三轨时钟，并广播推进事件。所有按回合/按日结算的模块均以本模块的推进信号为节拍。

## 2. 时间尺度

| 尺度 | 单位 | 用途 | 启用方 |
| --- | --- | --- | --- |
| tick | 1 回合 | 主循环最小步进（M50 回卷单位） | 全装配 |
| day | 1 日 = 若干 tick | 按日结算/刷新 | 需要日粒度的管线 |
| 子刻 | 1 日细分 | 高频消耗逐刻结算 | 需要子刻的域包（可选） |

- 子刻推进默认关闭；某域包需要时经装配参数启用，由 M10 把子刻折算为 tick 事件。
- 核心不预设任何具体日历或季节语义（由域包注入）。

## 3. 推进流程

```yaml
advance:
  1. tick += 1
  2. 若跨日（day 变更）→ 发布 tick_day（含新 day 号、季节/环境状态）
  3. 若启用子刻 → 额外发布 minute_tick（按域包刻度）
  4. 等待订阅者完成结算（同步），再返回 M50 继续下一层
```

## 4. 事件契约

```yaml
publish: tick_day
  payload: {tick, day, is_new_day: bool, season_ctx}
  subscribers: 日粒度结算模块（随域包装配登记）
publish: minute_tick        # 仅在启用子刻时
  payload: {tick, minute}
  subscribers: 子刻结算模块（随域包装配登记）
```

## 5. 违例与边界

- 任何模块禁止自行推进系统时间；只允许请求 M10.advance(n)。
- 时间回卷（回溯/读档）由 M50 统一触发，M10 只接受回卷指令并重放事件。
```

**4.5 M12_模板检索库** · 归属：官方核心 · 溯源：04_模块库/事件类/M12_模板检索库.md

```markdown
# 模块 M12 · 模板检索库

> 类别：事件｜来源：共享｜挂载点：P50 装配执行（active）｜依赖：M20、M13｜被依赖：M13｜发布：无

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M12
  name: 模板检索库
  category: 事件
  layer: P50
  inputs: [M20, M13]
  outputs: []
  events:
    publish: []
    subscribe: []
  interfaces: []
  io_types:
    outputs: {}
    inputs:
      M20: untyped
      M13: untyped
```

## 1. 职责

维护**可检索的内容模板库**：把「按条件供给可选项与文本」的能力集中于此，模板内容随域包扩展。是"素材库"，与 M13 的状态机构成模板-状态互查的双向耦合。

## 2. 模板规则

```yaml
content_template:
  template_id: # 模板全表（随域包）
  category: 分类名（闲聊 | 线索 | 回应 | 情报 | 事件回应 等，随域包定义）
  trigger_condition:
    关联档: # 由 M13 关联度函数提供
    流程阶段: # 由 M06 流程状态提供
    群体评价: # 由域包群体模块提供（可选）
  content: # 模板条目（按 profile 质检，若有）
  options: []  # 消费方可选项
  effect: 关系影响 | 信息解锁 | 流程推进（回传 M13）
```

- 模板全表 → 对应域包资产（随域包分发，经 asset_get 寻址）。

## 3. 模板-状态互查

- M12 提供**静态模板**，M13 提供**运行时实体状态**（关联度/日程/目标/记忆）。
- 触发 = M13 判定「该不该交互」→ M12 按条件检索「给什么模板」→ 效果回写 M13。
- 二者循环依赖在注册表已登记；执行顺序由 M50 按注册表编排（跨预设并集见 06 §3；官方核心 10 步见 02 §6）。

## 4. 事件契约

```yaml
subscribe: []  # 不直接订阅运行时事件；经 M13 查询接口取状态
publish: []    # 不发布事件；交互效果经 M13 的 interaction_update 统一广播
```

## 5. 违例与边界

- M12 只提供模板与选项素材，**不裁决关系数值**（关联函数在 M13）、**不生成流程**（M06）。
- 模板含隐藏域信息时，供给消费方须经 M23 可见性裁剪。
- 模板文本遵循 M80 质量门（profile 配置，若有）；禁止超长整段模板。
```

**4.6 M13_实体交互** · 归属：官方核心 · 溯源：04_模块库/事件类/M13_实体交互.md

```markdown
# 模块 M13 · 实体交互

> 类别：事件｜来源：共享｜挂载点：P30 内容生产（active）｜依赖：M12、M06、M20｜被依赖：事件:M22、域包消费方｜发布：interaction_update

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M13
  name: 实体交互
  category: 事件
  layer: P30
  inputs: [M12, M06, M20]
  outputs: [npc_id, action, result, tick]
  events:
    publish: [interaction_update]
    subscribe: [quest_state, level_up]
  interfaces: []
  io_types:
    outputs:
      npc_id: string
      action: string
      result: string
      tick: number
    inputs:
      M12: untyped
      M06: untyped
      M20: untyped
```

## 1. 职责

管理**实体的运行时状态机、记忆、日程、目标与关联函数**：实例化实体个体，维护其与主体之间的关联度与交互历史，把每次交互结算为 interaction_update 广播给关系/评价/编排模块。**实体个体真相来源**（群体评价归域包群体模块）。

## 2. 实体状态机

```yaml
entity_instance:
  id: # 实例化自域包模板
  state: 身份/位置/属性（随域包）
  affinity: 关联度数值（区间，关联模型可校准）
  memory: []  # 记忆条目（经 M23 可见性管理：记得什么/不记得什么）
  schedule: 日程（可选，随域包）
  goals: []   # 目标（流程 M06 / 域包目标）
  alive: true # 存在状态（继承/回收随域包）
affinity_function:
  输入: 交互(M12) / 馈赠 / 协助 / 冲突
  输出: affinity_delta → interaction_update
```

## 3. 事件契约

```yaml
subscribe:
  quest_state: # M06 → 流程改变实体目标与可用模板
  level_up: # 成长类模块 → 主体状态影响实体基线
publish:
  interaction_update:
    payload: {npc_id, type, affinity_delta, context, flags[]}
    subscribers: 关系/评价/编排消费方（随域包装配登记）
```

## 4. 结算流程

1. 每日/事件驱动实体日程更新。
2. 交互发起 → 经 M12 检索模板、消费方选择生效。
3. 关联函数结算 affinity_delta。
4. 发布 interaction_update：关系模型折算关联度、评价模块折算贡献、编排模块采集素材。

## 5. 违例与边界

- M13 裁决**实体个体**的关联/记忆/目标；群体评价归域包群体模块。
- 记忆写入须遵守 M23：不可见的记忆不进入可见域。
- 实体存在状态判定归对应域模块，M13 只执行状态清理与继承。
- 交互产生的文本表现归 M12/M80，M13 不做渲染。
```

**4.7 M20_知识条目库** · 归属：官方核心 · 溯源：04_模块库/事件类/M20_知识条目库.md

```markdown
# 模块 M20 · 知识条目库

> 类别：事件｜来源：共享｜挂载点：P70 参考素材（active）/ P00 数据基座（available）｜依赖：M00｜被依赖：M06、M12、M13｜发布：无

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M20
  name: 知识条目库
  category: 事件
  layer: P70
  inputs: [M00]
  outputs: []
  events:
    publish: []
    subscribe: []
  interfaces: [query]
  io_types:
    outputs: {}
    inputs:
      M00: state
```

## 1. 职责

管理**领域知识条目库**：按域提供结构化知识条目，按需供给各模块作为「背景上下文」，防止输出违反域内约定。**只读库，不含数值规则**（数值在各模块/资产库）；条目内容随域包分发。

## 2. 知识条目结构

```yaml
knowledge_entry:
  domain: 域分类（由域包定义）
  key: 知识键（如 <域>.<类>.<条目>）
  content: 条目内容（面向引擎的客观描述）
  access: # 供给条件：消费方是否"应该知道"（经 M23 可见性裁剪）
  consumers: [允许消费方模块]
```

- 全量知识条目随域包资产分发，经 asset_get 寻址。

## 3. 供给与查询

```yaml
query(domain, key, viewer):
  1. 检索条目；未知键 → 返回空并告警（防幻觉）
  2. 按 viewer 可见性（M23）裁剪：隐藏域内容不供给
  3. 返回条目供消费方做一致性校验
装载时机: 由 M50 调度（按注册表执行顺序的常识装载位）
```

## 4. 与各模块的配合

- 各域模块据知识库校验自身行为/能力是否符合域内设定。
- M06 取材（背景/位置常识）；M12/M13 的表现不得违反域内常识。

## 5. 违例与边界

- M20 是**只读知识库**：不裁决行为、不产出流程、不持有数值曲线。
- 消费方检索不到的键视为"知识不存在"，禁止凭模型先验脑补写入。
- 新知识条目须走资产库新增，运行时不可直接改写知识库。
```

**4.8 M22_事件编排** · 归属：官方核心 · 溯源：04_模块库/事件类/M22_事件编排.md

```markdown
# 模块 事件:M22 · 事件编排

> 类别：事件｜来源：核心｜挂载点：P30 内容生产（active）｜依赖：无（监听事件总线；具体事件源随域包装配）｜被依赖：M80｜发布：narrative_event

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: 事件:M22
  name: 事件编排
  category: 事件
  layer: P30
  inputs: []
  outputs: [type, payload, tick]
  events:
    publish: [narrative_event]
    subscribe: [death_trigger, relationship_change, chaos_event, ghost_event, market_event, production_output, interaction_update]
  interfaces: []
  io_types:
    outputs:
      type: untyped
      payload: object
      tick: number
    inputs: {}
```

## 1. 职责

管理**事件编排、时间线推进与因果组织**：汇聚各源模块发布的事件，校验因果一致性后组织为按序的事件流，驱动连贯时间线。是**编排者**——不做数值结算，只做因果编排。

## 2. 事件编排规则

```yaml
narrative_event:
  type: 分类（由域包定义；核心不预设类别）
  source: 事件来源模块
  beats: []  # 编排节拍（供输出层渲染的素材序列）
  pov: # 视角域（M23 可见性）：可见/推断/隐藏
  causal_chain: # 前因链：每事件须有前因，禁止空降
consistency_check:
  冲突 → 降级/重排/要求源模块修正
  去重 → 同类同因事件合并
  编排 → 因果顺序写入时间线
```

## 3. 事件契约

```yaml
subscribe:
  death_trigger: # 生命周期类事件入线（随域包）
  relationship_change: # 关系里程碑（随域包）
  chaos_event: # 外部扰动（随域包）
  ghost_event: # 残留状态显形（随域包）
  market_event: # 经济/资源大事（随域包）
  production_output: # 产出事件（随域包）
  interaction_update: # 关键交互（M13）
publish:
  narrative_event:
    payload: {seq_no, type, beats[], pov, causal_chain}
    subscribers: [M80, 域包消费方]
```

## 4. 编排流程

1. 接收各源模块事件（本回合内暂存）。
2. 一致性校验 + 去重 + 因果链接（查 M00 事件总线历史）。
3. 决定哪些入线、以何顺序、以何视角呈现（M23 裁剪）。
4. 发布 narrative_event → M80 渲染为输出；域包消费方按需读取。

## 5. 违例与边界

- 事件:M22 **只编排因果与顺序**，不执行数值结算（结算在各源模块内完成）。
- 未公开的线索放入隐藏域（M23），不得提前进入可见输出。
- 域包若自发布事件，须在其登记中显式标记来源与豁免关系，不留隐式特例。
- 时间线须尊重既有状态与设定（一致性纪律），禁止设定漂移。
```

**4.9 M23_可见性边界** · 归属：官方核心 · 溯源：04_模块库/通用类/M23_可见性边界.md

```markdown
# 模块 M23 · 可见性边界

> 类别：通用｜来源：核心｜挂载点：P20 实体状态（active）｜依赖：M00｜被依赖：M13、事件:M22

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M23
  name: 可见性边界
  category: 通用
  layer: P20
  inputs: [M00]
  outputs: []
  events:
    publish: []
    subscribe: []
  interfaces: [cognition.filter]
  io_types:
    outputs: {}
    inputs:
      M00: state
```

## 1. 职责

执行**信息可见性裁剪**：输出只能呈现「消费方当前可知」的信息。任何内部状态、不可观察输入、系统真实状态一律不得进入输出素材——这是信息边界纪律（消费方可知原则）的系统侧保障。

## 2. 可见性模型

```yaml
visibility:
  可见域: 消费方在场且可观察（当前上下文 + 已知信息）
  推断域: 由可见域证据可推出的结论（允许推测，须标注不确定）
  隐藏域: 其他实体的内部状态/意图、未触发输入、系统真实状态
裁剪规则:
  - 输出素材仅允许来自 可见域 ∪ 推断域
  - 隐藏域信息不得直接呈现；只可通过可观察证据间接透出
```

## 3. 多重真相支持

- 系统层可保留完整真相（供一致性校验与上层消费）；
- 呈现层（M80）只能拿到裁剪后的素材；
- 同一输出可承载两层含义：表层为消费方所见，深层真相留白（信息边界的自然延伸）。

## 4. 联动

- 读取：M13（实体运行时状态）、M20（知识条目库），以及域包扩展的实体状态。
- 事件：M23 不发布事件；M13/事件:M22 每次取素材前须先过 cognition.filter()（接口标识符 Phase 1 冻结，Phase 2 迁移为 visibility.filter）。

## 5. 违例与边界

- 输出中出现隐藏域直述 → 质检 fail（可见性纪律违例，M80 结构门 S5）。
- 消费方失能/离线场景：可见域降为空，只能输出环境描述（不得臆测隐藏域）。
```

**4.10 M24_规则组合** · 归属：官方核心 · 溯源：04_模块库/通用类/M24_规则组合.md

```markdown
# 模块 M24 · 规则组合

> 类别：通用｜来源：共享｜挂载点：P70 参考素材（active）｜依赖：M00｜被依赖：无

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M24
  name: 规则组合
  category: 通用
  layer: P70
  inputs: [M00]
  outputs: []
  events:
    publish: []
    subscribe: []
  interfaces: [resolve]
  io_types:
    outputs: {}
    inputs:
      M00: state
```

## 1. 职责

系统**组合/推导规则**的唯一结算入口：把「两个或以上输入合出新结果」的规则统一在此登记与判定，防止各模块各自为政产生规则冲突。域包以各自配方表扩展本模块，核心不内嵌任何领域配方。

## 2. 规则注册表

```yaml
combinations:
  <规则组名>:        # 由域包登记；核心只定义结构，不含具体配方
    input: [输入A, 输入B]
    output: 结果（新名 + 叠加/合成规则）
    conditions: 触发所需条件（可选：阈值/前置资源/依赖状态等，随域包定义）
    source: 规则出处（域包章节号或用户自定义包）
```

## 3. 判定流程

```yaml
resolve(inputA, inputB):
  1. 查规则表 → 命中返回 output
  2. 未命中 → 返回 null（不自动脑补组合，禁止自由发挥）
  3. 命中但条件不足 → 返回 blocked + 缺什么
  4. 结算结果写入 P70 参考素材槽，供输出层消费
```

## 4. 扩展约定

- 新增规则须在此登记并附带出处（域包章节号或用户自定义包）。
- 用户自定义包可覆盖默认规则，优先级：用户自定义 > 域包 > 核心默认。
- 规则表按域包装配注入；核心不含领域词。

## 5. 违例与边界

- 禁止在规则表中不存在时自行生成「看似合理」的新组合——保持可解释、可复现。
- 组合失败只返回 blocked 原因，不消耗输入（可重试），除非规则注明消耗。
```

**4.11 M50_调度器** · 归属：官方核心 · 溯源：04_模块库/通用类/M50_调度器.md

```markdown
# 模块 M50 · 调度器

> 类别：通用｜来源：核心｜挂载点：调度器（全局）｜依赖：M00｜被依赖：M80｜发布：intent_received

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M50
  name: 调度器
  category: 通用
  layer: 调度器
  inputs: [M00]
  outputs: [intent_id, mode, text]
  events:
    publish: [intent_received]
    subscribe: []
  interfaces: []
  world_model:
    abstract_state:
      variables:
        - name: pipeline
          kind: string
          source: M50
          slot: data_bus.active_pipeline
          note: 当前装配管线 id
        - name: tick
          kind: integer
          source: 通用:M10
          slot: WorldState.time.tick
          note: 时间节拍；M50 只读
        - name: phase
          kind: string
          source: M50
          slot: data_bus.round.phase
          note: 主循环抽象相位
        - name: phase_trace
          kind: array
          item_kind: string
          source: M50
          slot: data_bus.round.phase_trace
          note: 主循环相位轨迹；旧相位按迁移顺序追加
      initial:
        pipeline: P01
        tick: 0
        phase: begin
        phase_trace: []
    transition:
      initial_phase: begin
      phases:
        - phase: begin
          next: run
          guard: 回合开始并快照 M00 数据槽
          writes: []
        - phase: run
          next: end
          guard: 按 02 §6 执行官方核心与域包合并顺序
          writes: [memory.working]
        - phase: end
          next: archive
          guard: I2 核心固定结构/字段一致性校验通过
          writes: []
        - phase: archive
          next: roll
          guard: end 通过后执行回合末状态写回
          writes: [memories.memory.episodic.items, memories.memory.semantic.facts]
        - phase: roll
          next: begin
          guard: 回卷至 begin 快照并进入下一回合
          writes: [memory.working]
    invariants:
      - "抽象状态变量必须是 world_model.abstract_state 显式声明的有限集"
      - "tick 单调不减"
      - "phase 只在 begin/run/end/archive/roll 有限集合内迁移"
      - "每个 phase 显式声明 next，迁移图从 initial_phase 全可达"
      - "非 M50 模块不得直写 M00 数据槽"
    checks:
      - kind: finite_phase
        field: phase
        values: [begin, run, end, archive, roll]
      - kind: monotonic
        field: tick
      - kind: finite_sequence
        field: phase_trace
        values: [begin, run, end, archive, roll]
  io_types:
    outputs:
      intent_id: untyped
      mode: untyped
      text: untyped
    inputs:
      M00: state
```

## 1. 职责

回合调度器。按注册表给出的执行顺序（官方核心装配真相源见 02 §6）依序驱动各层模块；装域包后按包索引动态合并。回合结束回卷并进入下一回合。主循环决定"谁先跑、谁后跑、何时结算"。

## 2. 执行顺序

官方装配的执行顺序以 **02_联动注册表.md §6 为唯一真相源（I5）**，本模块不维护静态编号清单，避免双源漂移。装配任域包后，按包索引把域包模块合并进对应层位（R3），生成最终执行顺序。

## 3. 调度规则

```yaml
scheduler:
  层间同步: 每一步等待上一步完成（同步串行），保证数据因果
  层内: 该层多模块按注册表 available→active 过滤后执行
  跳过: 模块声明 skip（条件不满足）→ 跳过并记 skip_reason
  异常: 单模块异常不中断整轮；捕获后记 error_log，回合继续
  管线切换: 换用其它管线时同步切换挂载表与执行顺序
```

## 4. 回合生命周期

```yaml
round:
  begin:   快照（M00 数据槽）
  run:     按注册表 §6 顺序执行（官方核心 + 域包动态合并）
  end:     校验一致性（I2 核心固定：结构/字段不漂移）
  archive: 回合末状态写回（writeback 三规则，见下）—— end 通过后执行
  roll:    回卷至 begin 快照

writeback:  # 回合末状态写回（经 M00 数据槽总线，仅 M50 于 archive 步触发）
  working→清理:    # 工作层随回合快照滚动：end 后清空重置本回合临时状态，不跨回合滞留
  episodic→写回:   # 重要条目写回 episodic：命中规则集的条目带 tick 追加
  semantic→沉淀:   # episodic 提炼沉淀 semantic：跨回合稳定的事实精炼为 semantic.facts
  约束:            # 仅写 M00 声明的槽（I4 数据隔离）；消费方只读，
                   # 直写他模块字段 = DATA_SLOT_VIOLATION
```

## 5. 违例与边界

- 禁止任何模块在 step 之外自行触发其他模块逻辑（必须经由注册表订阅/挂载）。
- 死循环防护：单回合执行超时/步数超限 → M50 强制打断并回卷。

## 6. 事件契约

- 发布 intent_received：接收用户意图并广播，供意图驱动管线订阅（P90 的 M90 订阅）；载荷字段 intent_id / mode / text 的机读登记见 protocol/event_registry.json，本模块不另立第二份形状（I5）。
- 订阅：无（M50 只发布不订阅）。
```

**4.12 M80_输出质检门** · 归属：官方核心 · 溯源：04_模块库/通用类/M80_输出质检门.md

```markdown
# 模块 M80 · 输出质检门

> 类别：通用｜来源：核心｜挂载点：P80 输出质检（active）｜依赖：M50、事件:M22｜被依赖：无

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M80
  name: 输出质检门
  category: 通用
  layer: P80
  inputs: [M50, 事件:M22]
  outputs: []
  events:
    publish: []
    subscribe: []
  interfaces: []
  io_types:
    outputs: {}
    inputs:
      M50: untyped
      事件:M22: untyped
```

## 1. 职责

将上游素材/装配产物渲染为最终可读输出，是质检门的**执行器**：输出先过结构门（硬 · 全域通用），再按 profile 加载质量门（软 · profile 配置；profile 未配置时仅过结构门），判定后放行、自纠或重写。

## 2. 质检双门

### 2.1 结构门（硬 · 全域通用 · 可机器核验）

- 编号合法：文中 Mxx/Pxx 全部在册（02 联动注册表），不在册即编造 = fail
- 引用可寻址：引用资产键可经 asset_get 取到，悬空 = fail
- 结构完整：素材覆盖当前管线要求段（P00–P80）
- 术语一致：与协议术语表一致，不混用
- 无越层直写：素材无越层输出（M23 可见性纪律前置，隐藏域直述 = fail）

### 2.2 质量门（软 · 可插拔 profile · 可配置）

- 渲染前加载当前 profile 配置（资产键 STYLE_DNA 或 protocol.yaml 的 profile 字段；标识符 Phase 1 冻结，Phase 2 迁移为通用「输出 profile」）；
- profile 由用户/域包自定义——**协议层不内嵌任何固定条目**；
- profile 未配置时，仅过结构门即放行（风格由运行方自担）。

## 3. 质检门（声明式 gate_action 流水线）

```yaml
gate:                      # 双门判定（2.1 结构门 + 2.2 质量 profile）
  pass: 结构门全过 且（无 profile 或 profile 符合 ≥ 阈值）→ 直接输出
  warn: 结构门全过 且 profile 部分符合 → 自纠后输出（标注修订点）
  fail: 结构门违例（硬错）或 profile 连续不符 → 整段重写；连续 3 次 fail 降级为最小可读模式（保底，仅结构门）
前置校验: 素材必须已过 M23 可见性裁剪（隐藏域直述 = fail）
gate_action:               # 声明式门禁流水线
  pass: [direct]
  warn: [self_correct, log_revision]
  fail: [rewrite, retry_limit: 3, fallback: minimal]
gate_decision_record:      # 决策记录（结构化行，走系统日志独立通道，不进输出正文）
  格式: gate|<流水号>|tick|判定(pass/warn/fail)|命中项|修订点|重写次数|fallback
  样例: gate|014|t_2042|warn|S1,S3,D1,D3,D5|L7 直述改间接|0|none
        gate|015|t_2043|fail|S2|隐藏域直述|3|minimal
```

## 4. 输出格式

- 由域包按自身模板与风格档定义（核心不含任何域特有输出格式）。
- 通用回退：无管线标注时按当前装配管线的中性模板渲染。

## 5. 违例与边界

- 输出篇幅上限由管线参数控制；禁止输出 JSON/YAML 原始结构（只输出面向消费方的文本）。
- 系统结算内容与呈现内容分离：系统日志走独立通道，不进输出正文。
- 门禁为**唯一输出闸**（I2 核心固定）：任何域（含文档线经 M80）产出均不可绕过本 gate。
```

**4.13 M90_结构装配** · 归属：官方核心 · 溯源：04_模块库/技术文档类/M90_结构装配.md

```markdown
# 模块 M90 · 结构装配

> 类别：技术文档｜来源：核心（P90 实证样例）｜挂载点：P90（active，default）｜依赖：M00｜被依赖：M80
> 用途：04_模块库**无损接入非叙事领域模块**的实证件——新类别/新模块自动纳入计数、可增不减（派生规程见 06_Agent执行协议.md §10；类别基线下限见 verify.sh check1）。

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M90
  name: 结构装配
  category: 技术文档
  layer: P90
  inputs: [M00]
  outputs: [DocState, doc_delta]
  events:
    publish: [doc_structure_ready, doc_delta_committed]
    subscribe: [intent_received]
  interfaces: []
  io_types:
    outputs:
      DocState: untyped
      doc_delta: untyped
    inputs:
      M00: state
```

## 1. 职责

把自然语言意图解析为**结构化要素**：标题层级、章节骨架、术语表、表格/引用登记、修订记录；按资产键选择章节模板、按规则过一致性校验。是结构化装配类管线的领域装载模块。

## 2. 协议声明（01 §1 模块协议）

```yaml
Module:
  id: M90
  name: 结构装配
  layer: P90
  inputs: [M00]                  # 数据槽就绪；用户意图经 intent_received 事件到达（见 §4）
  outputs: [DocState, doc_delta] # 结构状态 + 章节增量
  events:
    publish: [doc_structure_ready, doc_delta_committed]
    subscribe: [intent_received]
  core:
    assets: [TECH_TEMPLATES, TECH_RULES]   # I4：仅经五接口访问，禁止直读
    logic:
      解析: 意图 → 类型判定 → 选章节骨架
      装配: 章节 → 术语/表格/引用登记 → 更新 DocState
      校验: 按规则资产检查结构一致性（章节闭合/术语统一/修订记录）
  replaceable: true
```

## 3. 数据槽契约

```yaml
DocState:
  title: string
  doc_type: 类型枚举（由域包/模板定义）
  chapters: [{id, heading, level, body_refs[], status}]
  terms: {term: {def, first_use_chapter}}
  refs: {link_refs[], code_refs[]}
  revision: [{ver, date, change}]
```

## 4. 事件联动

- publish doc_structure_ready：结构骨架就绪，通知 M80 进入渲染质检。
- publish doc_delta_committed：章节增量已提交，供一致性/修订消费方读取。
- subscribe intent_received：接收用户意图作为装载输入（发布方 M50；载荷机读登记见 protocol/event_registry.json，挂载与顺序见 02 §7.1–§7.2）。

## 5. 核心逻辑（伪代码）

```
1. intent_received → doc_type = classify(intent)
2. skeleton = asset_get(TECH_TEMPLATES, doc_type)      # 取章节骨架
3. chapters = expand(skeleton, intent)                 # 拆章/节/小节
4. for each draft: doc_delta = compose(draft)          # 片段生产
5. tech_review: check(TECH_RULES, DocState)            # 一致性校验
6. publish doc_structure_ready
```

## 6. 不变式遵守（01 §5）

- I1 三正交分离：只声明"结构能力"，不持有管线顺序（顺序在管线）与数据内容（内容在资产）。
- I2 核心固定：复用 M00 数据槽 / M50 调度 / M80 输出门，未替换任何核心模块。
- I3 通信契约：仅经 DocState 数据槽与结构事件通信。
- I4 数据隔离：TECH_TEMPLATES / TECH_RULES 只经 asset_get / asset_query 访问。
- I5 真相唯一：挂载与执行顺序以 02_联动注册表 §7 登记为准，禁止硬编码。

## 7. 与装配管线的关系

本模块在九层管线中承担装载（骨架解析）、生产（片段）、决策（模板选择）、装配（章节组装）、一致性（跨章校验）等位职责；输出层仍由核心 M80 质检门把守（gate 唯一出口）。
```

**4.14 M97_术语管理** · 归属：技术文档域包（自带） · 溯源：community/技术文档域包/modules/M97_术语管理.md

```markdown
# 模块 M97 · 术语管理

> 类别：技术文档｜来源：社区（技术文档域包自带，M91-99 社区段）｜挂载点：P40（active，default）｜依赖：M90 技术文档结构、M00｜被依赖：M80
> 用途：README「扩展新领域三步之①」社区 techdoc 域包首模块——在官方 M90（技术文档结构）之上维护 DocState.terms 术语表（定义/首次使用章节/统一性校验），M90 专注结构骨架、M97 专注术语一致，I1 正交分工。

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M97
  name: 术语管理
  category: 技术文档
  layer: P40
  inputs: [M90, M00]
  outputs: [term_delta]
  events:
    publish: [term_synced, term_conflict_detected]
    subscribe: [doc_structure_ready, term_conflict_detected]
  interfaces: []
  io_types:
    outputs:
      term_delta: untyped
    inputs:
      M90: untyped
      M00: state
```

## 1. 职责
维护技术文档的术语表一致性：从 DocState.terms 读取术语条目（M90 结构生产时登记），做首次使用章节标注与定义补全；检测同一术语多定义/首用未定义等冲突（term_conflict_detected）；发布 term_synced 供 M80 质检参考。是本包（技术文档题材增强）相对官方 M90 的增值位——M90 负责骨架，M97 负责术语域。

## 2. 协议声明（01 §2 模块协议）
```yaml
Module:
  id: M97
  name: 术语管理
  layer: P40
  inputs: [M90, M00, intent]
  outputs: [term_delta, term_status]
  events:
    publish: [term_synced, term_conflict_detected]
    subscribe: [doc_structure_ready, term_conflict_detected]
  core:
    assets: []                     # 零题材资产（机制增强；同通用包 M93-96 先例）
    logic:
      登记: doc_structure_ready → 扫描章节正文 → 首次使用术语登记 first_use_chapter
      补定义: 术语无定义 → 查已有术语表 / 留待人工（term_status=pending_definition）
      校验: 多定义同一术语 / 首用未定义 → term_conflict_detected
      同步: 校验通过 → term_synced（DocState.terms 收敛）
  replaceable: true
```

## 3. 数据槽契约（扩展 M90 DocState · 术语域）
```yaml
term_delta:
  term: string
  first_use_chapter: string
  definition: string          # 空 = 待补
  status: ok|pending_definition|conflict
term_status:
  total: int
  defined: int
  conflicts: [string]
```

## 4. 事件联动
- subscribe `doc_structure_ready`（M90 发布）：结构骨架就绪 → M97 扫描登记术语。
- subscribe `term_conflict_detected`：本模块自检发现多定义/未定义 → 内部状态标记。
- publish `term_synced`：术语表收敛 → M80 质检可读术语一致性。

## 5. 核心逻辑（伪代码）
```
1. doc_structure_ready → for chapter: scan(chapter.body) → collect terms
2. term not in DocState.terms → add with first_use_chapter, definition=""
3. term.definition=="" and known → backfill；else status=pending_definition
4. dup definition → status=conflict → publish term_conflict_detected
5. no conflict → publish term_synced
```

## 6. 不变式遵守（01 §5）
- I1 三正交分离：只声明术语能力，不持管线顺序（顺序在 P06 管线）与内容（M90 产 DocState）。
- I2 核心固定：依赖 M90/M00 数据槽，未替换核心模块（M90 官方位不动）。
- I3 通信契约：仅经 term_delta / term_status 与 term_synced 事件通信。
- I4 数据隔离：无自有资产（零资产机制增强）。
- I5 真相唯一：挂载与登记以 02 §8.5 + registry protocols[] 为准（本包第 5 条投影）。

## 7. 与官方链的关系
本模块是 M90（官方，挂 P90 位）的题材增强——M90 产 DocState（含 terms 雏形），M97 挂 P40 位做术语域深化；不复制 M90 正文（core_modules 依赖引用，I5），是「扩展新领域三步」社区自带模块示范。
```

**4.15 M98_修订记录** · 归属：技术文档域包（自带） · 溯源：community/技术文档域包/modules/M98_修订记录.md

```markdown
# 模块 M98 · 修订记录

> 类别：技术文档｜来源：社区（技术文档域包自带，M91-99 社区段）｜挂载点：P60（active，default）｜依赖：M90 技术文档结构、M00｜被依赖：M80
> 用途：README「扩展新领域三步之①」社区 techdoc 域包次模块——维护 DocState.revision 修订记录（版本号/变更日志/回溯），M90 专注结构骨架、M98 专注变更追踪，I1 正交分工。

```yaml
machine_contract:
  conformance: "L2"
  schema: "1"
  id: M98
  name: 修订记录
  category: 技术文档
  layer: P60
  inputs: [M90, M00]
  outputs: [revision_entry, revision_log]
  events:
    publish: [revision_recorded]
    subscribe: [doc_structure_ready, doc_delta_committed]
  interfaces: []
  io_types:
    outputs:
      revision_entry: untyped
      revision_log: untyped
    inputs:
      M90: untyped
      M00: state
```

## 1. 职责
维护技术文档的修订历史：M90 每产出结构增量（doc_delta）或正文变更（doc_delta_committed）时，M98 追加修订条目（版本号递增/变更摘要/日期/作者），维护可回溯的变更日志（revision_log）；供 M80 渲染「修订记录」章节与读者追溯。是本包相对官方 M90 的增值位。

## 2. 协议声明（01 §2 模块协议）
```yaml
Module:
  id: M98
  name: 修订记录
  layer: P60
  inputs: [M90, M00, intent]
  outputs: [revision_entry, revision_log]
  events:
    publish: [revision_recorded]
    subscribe: [doc_structure_ready, doc_delta_committed]
  core:
    assets: []                     # 零题材资产（机制增强）
    logic:
      变更: doc_delta_committed → 比较前版 DocState → 提取变更点
      登记: 版本号 v{n+1} + 变更摘要 + date + author → revision_log 追加
      回溯: 按版本号取历史快照 → 供 diff 展示
      发布: revision_recorded → M80 渲染修订章节
  replaceable: true
```

## 3. 数据槽契约（扩展 M90 DocState · 修订域）
```yaml
revision_entry:
  ver: string          # v1.0 → v1.1
  date: string
  author: string
  changes: [string]    # 变更摘要列表
revision_log:
  entries: [revision_entry]
```

## 4. 事件联动
- subscribe `doc_structure_ready`（M90 发布）：首版 v1.0 基线登记。
- subscribe `doc_delta_committed`：后续变更增量 → 追加 revision_entry。
- publish `revision_recorded`：修订登记完成 → M80 质检/渲染可读。

## 5. 核心逻辑（伪代码）
```
1. doc_structure_ready → revision_log.entries=[v1.0 基线]
2. doc_delta_committed → cur=DocState；changes=diff(prev, cur)
3. changes 非空 → ver=bump(prev.ver)；append entry；publish revision_recorded
4. query(ver) → 返回该版本 DocState 快照（回溯）
```

## 6. 不变式遵守（01 §5）
- I1 三正交分离：只声明修订能力，不持管线顺序（顺序在 P06）与内容（M90 产 DocState）。
- I2 核心固定：依赖 M90/M00，未替换核心模块。
- I3 通信契约：仅经 revision_entry / revision_log 与 revision_recorded 事件通信。
- I4 数据隔离：无自有资产。
- I5 真相唯一：挂载与登记以 02 §8.5 + registry protocols[] 为准。

## 7. 与官方链的关系
同 M97——M90 官方挂 P90 位产 DocState，M98 挂 P60 位做修订域深化；不复制 M90 正文（core_modules 依赖引用，I5）。
```

## 5. 资产（0 文件）

- 本装配**零题材资产**：技术文档域包为机制增强包（同通用核心基础包先例，无 `assets/` 目录）。
- 因此本件不存在资产键表，也不存在资产正文引用的缺口——**这是它天然可自包含的结构原因**。
- 对照：校园情感包 29 资产文件 / 西幻生存包 23 资产文件，其引用式档位正源于资产正文体量。

## 6. 装载指引

给接收方 AI 的装载四步（对齐 06 执行协议）：

1. **读本件**：§2 取管线结构，§3 取执行顺序投影，§4 取各模块的契约与逻辑。
2. **对表**：按 §3 的表逐层挂载；模块契约见 §4 对应的内嵌段（含 `machine_contract` 机读块）。
3. **执行**：按 M50 主循环推进——P00 装载骨架 → P40 术语同步 → P60 修订记录 → P80 质检渲染；回合 begin/end 打快照与回卷。
4. **验收**：过 §7 自检清单；任一不满足先修正再交付。

边界提醒：

- 本件内嵌的是**模块层与管线层**；上位协议件（01/02/06）为全库共用规范，本件不含其正文。
- 若接收方需要与官方核心保持严格同步，请以仓库最新版为准重新生成本件（见本次生成方式）。

## 7. 自检清单（交付前逐项核对）

- [ ] §0–§7 八段骨架齐备
- [ ] §4 内嵌段数 = 15（两包自带 2 + 官方核心 13）
- [ ] §3 执行顺序与 §2 管线 layers 一致（default 挂载不冲突）
- [ ] 形态为**全文内嵌**：接收方在不访问仓库时可完成装载
- [ ] 缺口声明与会话一致（协议件不内嵌 / 快照时点 / 未挂签名锚）
- [ ] 机器验收通过：nf assemble --check 本文件（需求原话见 §0）

---

*—— 自包含样本 · 由 build_selfcontained_sample.ps1 生成（可复现）· 2026-09-15 · 内嵌 15 件*

