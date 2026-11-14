# ST 制卡质量自查清单（v0 · 人工版）
> ⛔ 操作指令：逐条勾选，证据位填实卡观察；**M 级未勾不允许发布**。规则原文见 `protocol/st_quality.json`（本清单只管勾选与证据位，不重述规则）。
> 最后更新：2026-11-13
> **复核（2026-11-13）**：29 条自查点 / 四级判定 / 证据位用法**复核不变**；**修一处级别漂移**：W1 原标 `S`，而规则真源 `protocol/st_quality.json` 判其为 **`M`**（M 级未勾不许发布，标错会放过硬缺口）→ 已改 `M`。
> 并补可核现状：规则 **29 条**（M **6** / S **17** / R **6**）· scope **4 类**（C/W/V/X）· 自动判定面 **1 项（V2 卡头）** · 待作者定 **3 项** · A-S3 校验器**已有原型** `nf st-validate <path>`（R1 结构 / R3 世界书 / R4 变量）。见「§现状对照」。

用法：把本表复制到你的制卡工作区 → 逐条勾选 → 证据位写「在哪看到的 / 怎么验的」（例：`导入后首屏出现 X`）。
机检部分（`nf` 可判的）见 `core/st_quality.py`：仓库内**只有 V2（卡头版本/结构）自动判**，其余靠本清单；A-S3 校验器**已有原型** `nf st-validate <path>`（判 R1 结构 / R3 世界书 / R4 变量，产出 markdown 报告），可用于外部 JSON 卡自检——但**尚未**把本清单勾选项换成机检，口径仍是「先可用，后可判」。

## 现状对照（2026-11-13 · 以 `protocol/st_quality.json` 与 `core/st_quality.scan()` 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 规则条数 | **29**（C 8 / W 10 / V 7 / X 4） | `st_quality.json: rules` |
| 级别分布 | **M 6 / S 17 / R 6** | 同上 `rules[].level` |
| scope | **4 类**：C 角色卡 / W 世界书 / V MVU 变量 / X 跨类 | 同上 `scope_vocabulary` |
| 自动判定 | **1 项**（V2 卡头；`artifact_checked=1`） | `st_quality.scan()` 的 stats |
| 待作者定 | **3 项**（X2 测试法 / X3 长会话 N / PNG-JSON 实测与 A-S3 校验器落地） | `st_quality.json: pending` |
| 状态 | **draft**（草案，非冻结） | 同上 `status` |
| 外部校验器 | `nf st-validate <path>`（原型，R1/R3/R4） | CLI `--help` |

> 本表只作「当时 → 现行」导航；条数与级别以规则真源实读为准（清单不重述规则）。

## 复现与引用口径

```bash
python scripts/nf.py st-validate <卡.json> --json          # 外部卡自检（原型，R1/R3/R4）
python -m pytest desktop/tests/test_quality_gate.py -q    # 规范面 ↔ 清单面一致性判据
```

- 引用本文时：「M 级未勾不允许发布」= 长期口径；级别以 `st_quality.json` 为**唯一真源**，本清单只是勾选面。
- 待作者定的 3 项（X2 / X3 / A-S3 落地）在解决前，清单不得宣称「全机检」。

## 1. 角色卡（C）

| 编号 | 级别 | 自查点 | 勾选 | 证据位 |
|---|---|---|---|---|
| C1 | M | 可解析且命中 V1/V2/V3；V3 用 `ccv3` chunk、V2 用 `chara`，并存优先 `ccv3` | ☐ | |
| C2 | M | 版本字段正确（`chara_card_v2`+`2.0` / `chara_card_v3`+`3.0`） | ☐ | |
| C3 | M | 基础六字段齐备非空（name/description/personality/scenario/first_mes/mes_example） | ☐ | |
| C4 | S | `creator_notes` 不进提示词；`extensions` 无私有数据 | ☐ | |
| C5 | S | `character_version` 有值，修改后递增 | ☐ | |
| C6 | S | 只导出主世界书；额外依赖在 `creator_notes` 注明 | ☐ | |
| C7 | R | 卡内自称 / 世界书标题 / 状态栏显示名一致 | ☐ | |
| C8 | R | 导出后本地导入实测一次；PNG / JSON 双格式一致 | ☐ | |

## 2. 世界书（W）

| 编号 | 级别 | 自查点 | 勾选 | 证据位 |
|---|---|---|---|---|
| W1 | M | `entries` 每条含非空 `keys` 与 `content`，类型正确 | ☐ | |
| W2 | S | key 无冲突/遮蔽；纯文本 key 不含逗号 | ☐ | |
| W3 | S | 次级过滤逻辑（AND ANY / AND ALL / NOT ANY / NOT ALL）意图明确；正则 key 单独标注 | ☐ | |
| W4 | S | 蓝灯仅用于恒真设定；绿灯为主；求确定性用关键词而非向量 | ☐ | |
| W5 | S | 触发词位置落在 Scan Depth 之内 | ☐ | |
| W6 | S | 中文卡关闭 Match whole words | ☐ | |
| W7 | S | 内容简洁；关注 Context% / Budget 与 overflow | ☐ | |
| W8 | S | 不与 `personality` / `scenario` 重复定义同一信息 | ☐ | |
| W9 | S | Insertion Order 与 Position 明确选择 | ☐ | |
| W10 | R | 递归扫描 / sticky·cooldown·delay 自我限界，无意外链式触发 | ☐ | |

## 3. MVU 变量（V）

| 编号 | 级别 | 自查点 | 勾选 | 证据位 |
|---|---|---|---|---|
| V1 | M | Zod 结构脚本固定头尾 + `registerMvuSchema`；不 import `z` / `_` | ☐ | |
| V2 | M | `[initvar]` YAML 与 schema 一一对应（条目通常为禁用态） | ☐ | |
| V3 | S | `[mvu_update]` 更新规则 + 输出格式（JSON Patch）成套 | ☐ | |
| V4 | S | 变量列表让 AI 看到当前值；`_` / `$` 前缀语义正确 | ☐ | |
| V5 | S | 变量名不用宏；优先 `record` 代数组；parse∘parse = parse | ☐ | |
| V6 | S | 状态栏显示项 ⊆ 变量集合；占位符机制正确 | ☐ | |
| V7 | R | 插件启用状态 / 重新处理变量 / 重启后失效 都查过 | ☐ | |

## 4. 跨类（X）

| 编号 | 级别 | 自查点 | 勾选 | 证据位 |
|---|---|---|---|---|
| X1 | S | 版本 + 导出检查（配合 S2 人工清单） | ☐ | |
| X2 | S | 同卡同验：记录版本 + 一轮标准测试结果【测试法待作者设计】 | ☐ | |
| X3 | R | 长会话抽检：N 轮后关键设定一致性【N 待作者定】 | ☐ | |
| X4 | R | 状态键稳定可重建（Trace as State 接点，待评估） | ☐ | |
