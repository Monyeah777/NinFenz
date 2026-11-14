# NFA-L · NF 装配语言（声明式 + 命令式混合）

> 最后更新：2026-11-13
> **复核（2026-11-13）**：封闭语法 / 命名空间 / 三值判决 / 边界**复核不变**；补可核现状：
> CLI **5 个子命令**（parse / check / build / eval / schema-check）· 封闭函数 **6 个** · 类型词 **9 个** ·
> 诊断码 **6 个**（E0201 / E0202 / E0301 / E0302 / E0304 / E0310）+ 散文 advisory **A0201** ·
> 迁移 **110/110**（114 份管线文档里的 110 条 condition，全部 `=` 开头，散文 0 条）· 判据 **44 例**。见「§现状对照」。
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。

## 是什么

NFA-L 把 NF 的两半语言合到一处：

- **声明层（沿用，不新造）**：YAML 围栏 + protocol/schema 的 JSON-Schema IDL，回答「有什么」；
- **命令层（本件补）**：封闭 guard 表达式，回答「什么时候走」。

它补的那处内部缺口：Pipeline 的 structure.flow[].condition 此前只是自由字符串（IDL 仅
type: string / minLength: 1），仓内多处管线把它写成中文散文——人能读，机器既不能静态检查、
也不能执行。NFA-L 让它可检查、可执行、可复算。

设计纪律：不自造开放表达力（封闭函数集，无用户函数/循环/赋值/IO）；边缘全借仓库既有真源
（world_slots / event_registry / io_types / 模块 machine_contract）；散文 condition 不判死
（advisory），只有以 = 开头的 condition 才进命令层。

## 怎么用

    nf nfal help
    nf nfal parse 'WorldState.time.day >= 30'
    nf nfal check 'WorldState.time.day >= 30' --tokens
    nf nfal build 03_管线库/P01_标准管线.md --no-tokens
    nf nfal eval 03_管线库/P01_标准管线.md --state state.json
    nf nfal schema-check 03_管线库/P01_标准管线.md

把 condition 写成命令式片段：以 = 开头，其后是 nf-expr。未加 = 的 condition 保持原样（散文），
门禁只记 advisory A0201（V1 只增不删）。

## 命令层语法（封闭）

    expr    := ternary
    ternary := or ( "?" expr ":" expr )?
    or      := and ( "||" and )*
    and     := cmp ( "&&" cmp )*
    cmp     := add ( ("=="|"!="|"<"|"<="|">"|">="|"in") add )?
    add     := mul ( ("+"|"-") mul )*
    mul     := unary ( ("*"|"/"|"%") unary )*
    unary   := ("!"|"-") unary | postfix
    postfix := primary ( "(" expr ("," expr)* ")" )?     # 只有具名函数可调用
    primary := literal | path | "(" expr ")" | list | map

命名空间（不另造层级，直接借登记真源）：

| 写法 | 真源 | 语义 |
|---|---|---|
| WorldState.time.day 一类 | protocol/world_slots.json 的 slots 全名 | 世界状态量（也接受 state. 前缀） |
| event.<name> | protocol/event_registry.json 的 events | 事件是否发生（bool） |
| token.<name> | 模块 machine_contract 的 outputs | 产出令牌（类型取 io_types） |
| input.<name> | 调用方注入 | guard 输入 |

封闭函数集：size / contains / has / startsWith / int / string。

## 类型与判决（fail-closed）

类型词表复用既有 io_types：string / integer / number / boolean / array / object / event / state / untyped。

- 未登记符号 = fail（E0301）；guard 非 bool = fail（E0302）；函数越封闭集 = fail（E0304）；
- untyped = warn（E0310，合法但未收窄），执行后端记 abstain；
- 求值为三值 Kleene：unknown && false = false、unknown || true = true，其余 unknown；
- 判决三态 pass / fail / abstain，abstain 永不折算为 pass（与决策层同源口径）。

## 编辑器面（nf lsp）

管线文档里的 condition（nf-expr）静态检查结果会随 nf lsp 发布为 LSP 诊断：

- 源标记 nfal-guard；诊断码沿用 nfal（E0201 语法 / E0301 未登记符号 / E0302 非 bool / E0310 未收窄）；
- 位置落在该 condition 行的表达式列（UTF-16 口径，编辑器可直接定位）；
- 只对管线声明（03_管线库 与 community 的 pipelines）生效；非管线文档不产 guard 诊断；
- 散文 condition 不产诊断（不冒充错误；由 nf nfal build 记 advisory A0201）。

## 仓内迁移状态

官方核心与社区域包的管线 condition 已由散文迁移为 nf-expr，统一取 M50 已声明的抽象相位：

    condition: =data_bus.round.phase == "roll"                          # M50 调度下一回合 / 下一轮意图
    condition: =data_bus.round.phase == "roll" && event.tick_day        # 叠加 通用:M10 节拍同拍推进

真源：M50 的 world_model 有限相位集 begin/run/end/archive/roll 与其 roll 回卷迁移。

## 现状对照（2026-11-13 · 以实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| CLI 子命令 | **5**：parse / check / build / eval / schema-check | `nf nfal help` |
| 封闭函数 | **6**：size / contains / has / startsWith / int / string | `nfal` 函数表 |
| 类型词 | **9**：string / integer / number / boolean / array / object / event / state / untyped | 复用 io_types 词表 |
| 诊断码 | **6**：E0201 语法 / E0202 散文严格 / E0301 未登记符号 / E0302 非 bool / E0304 越封闭集 / E0310 未收窄 | `nfal` 诊断常量 |
| 散文 advisory | **A0201**（V1 只增不删） | `nf nfal build` 报告 |
| 迁移面 | **110/110** 条 condition 为 `=` 开头（114 份管线文档；散文 0 条） | 全库 condition 扫描 |
| 常驻判据 | **44 例**（test_nfal 26 / test_nfal_cli 6 / test_nfal_rules 12） | pytest |

> 本表只作「当时 → 现行」导航；语法与码表以 `nf nfal` 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py nfal help                       # 5 个子命令
python scripts/nf.py nfal parse 'WorldState.time.day >= 30'   # 表达式 → AST（规范 JSON）
python -m pytest desktop/tests/test_nfal.py desktop/tests/test_nfal_rules.py -q   # 44 例
```

- 引用本文时：「封闭函数集 + 三值判决 + abstain 永不折算为 pass」= 长期口径。
- 散文 condition 不判死只记 **A0201**；要进命令层必须写 `=` 前缀（严格档会升为 **E0202**）。

## 边界（不宣称）

- 不做通用编程语言：无循环、赋值、函数定义、模块导入、I/O；
- 不替代声明层：拓扑、层、模块边界仍是 YAML + schema；
- 不生成正文：只做判决与 NF-IR 中间表示（规范 JSON，可 diff/golden）。
