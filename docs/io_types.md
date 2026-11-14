# I/O 类型面（io_types）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13

## 是什么

`machine_contract` 的可选键（01 §7 **V1 字段级新增**，非 bump）：`outputs` = token→kind、
`inputs` = 依赖模块→期望 kind。词表 `string|integer|number|boolean|array|object|event|state|untyped`。

> **复核（2026-11-13）**：词表 9 值 / 判定原则 / 取值来源 / 边界**复核不变**；补可核现状：
> 机读契约模块 **248** · L0 未承载 **0** · 已标注 **308/1141 字段（27.0%）** · 可证不匹配 **0**；
> `module types --write` 幂等（本轮实跑「已补标 0 件」）。见「§现状对照」。

## 判定原则（只判可证）

- kind 越词表 → **FAIL**；消费方声明期望 kind 且提供方已声明类型、无一匹配 → **FAIL**；
- 未收窄（`untyped`）或未标 → **WARN**（如实缺口，**不判死**）；
- `untyped` 是合法值（与 `protocol/event_registry.json` 措辞一致）——**禁止为省事编造类型**。

## 取值来源（确定性、有据可依）

1. `outputs[token]` = `event_registry.json` 里同名事件字段的类型（证据）；未命中 → `untyped`。
2. `inputs[M00]` = `state`；其余依赖 → `untyped`。

## 怎么用

```bash
python scripts/nf.py module types            # 覆盖率 + 可证不匹配
python scripts/nf.py module types --write    # 按上述规则补标（幂等）
```

## 现状对照（2026-11-13 · 以 `coverage()` 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 词表 | **9 值**（`io_types.KINDS`） | `python -c "…print(io_types.KINDS)"` |
| 机读契约模块 | **248** | `coverage()['modules_with_contract']` |
| L0 未承载 | **0** | `coverage()['l0_modules']` |
| 已标注字段 | **308** / 1141（**27.0%**） | `coverage()['typed_fields'] / total` |
| 可证不匹配 | **0** | `nf module types` 尾行「✓ 无可证类型不匹配」 |
| `--write` 幂等 | 是（本轮补标 0 件） | 连跑两次第二次必为 0 |

> 覆盖率只随「模块是否显式声明 outputs」变；它降了说明内容侧回退，不是判据松了。

## 复现与引用口径

```bash
python scripts/nf.py module types            # 覆盖率 + 可证不匹配（0 即绿）
python -m pytest desktop/tests/test_io_types.py -q   # 10 项
```

- 引用本文时：「只判可证，不编造类型；`untyped` 是合法缺口」= 长期口径；数字以 `coverage()` 实读为准。
- `--write` 只按两条确定性规则补标，不猜类型；写后应连跑一次确认 0 变更。

## 边界

覆盖率取决于模块**显式声明 outputs**；未声明就只能是 `untyped`——这是内容侧的活。

## 相关

- 命令式 guard 表达式（封闭、可静态检查 + 执行）：docs/nfal.md。
