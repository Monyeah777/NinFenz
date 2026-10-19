---
name: p90
description: 技术文档生成管线（P90）生成：协议/文档操作规格，共 1 个规则块。
license: MIT
---
# 技术文档结构规范



## 附加规则

### 技术文档类:M90 · 结构装配

### 模块 M90 · 结构装配

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

#### 1. 职责

把自然语言意图解析为**结构化要素**：标题层级、章节骨架、术语表、表格/引用登记、修订记录；按资产键选择章节模板、按规则过一致性校验。是结构化装配类管线的领域装载模块。

#### 2. 协议声明（01 §1 模块协议）

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

#### 3. 数据槽契约

```yaml
DocState:
  title: string
  doc_type: 类型枚举（由域包/模板定义）
  chapters: [{id, heading, level, body_refs[], status}]
  terms: {term: {def, first_use_chapter}}
  refs: {link_refs[], code_refs[]}
  revision: [{ver, date, change}]
```

#### 4. 事件联动

- publish doc_structure_ready：结构骨架就绪，通知 M80 进入渲染质检。
- publish doc_delta_committed：章节增量已提交，供一致性/修订消费方读取。
- subscribe intent_received：接收用户意图作为装载输入（发布方 M50；载荷机读登记见 protocol/event_registry.json，挂载与顺序见 02 §7.1–§7.2）。

#### 5. 核心逻辑（伪代码）

```
1. intent_received → doc_type = classify(intent)
2. skeleton = asset_get(TECH_TEMPLATES, doc_type)      # 取章节骨架
3. chapters = expand(skeleton, intent)                 # 拆章/节/小节
4. for each draft: doc_delta = compose(draft)          # 片段生产
5. tech_review: check(TECH_RULES, DocState)            # 一致性校验
6. publish doc_structure_ready
```

#### 6. 不变式遵守（01 §5）

- I1 三正交分离：只声明"结构能力"，不持有管线顺序（顺序在管线）与数据内容（内容在资产）。
- I2 核心固定：复用 M00 数据槽 / M50 调度 / M80 输出门，未替换任何核心模块。
- I3 通信契约：仅经 DocState 数据槽与结构事件通信。
- I4 数据隔离：TECH_TEMPLATES / TECH_RULES 只经 asset_get / asset_query 访问。
- I5 真相唯一：挂载与执行顺序以 02_联动注册表 §7 登记为准，禁止硬编码。

#### 7. 与装配管线的关系

本模块在九层管线中承担装载（骨架解析）、生产（片段）、决策（模板选择）、装配（章节组装）、一致性（跨章校验）等位职责；输出层仍由核心 M80 质检门把守（gate 唯一出口）。