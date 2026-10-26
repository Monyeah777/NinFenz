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
