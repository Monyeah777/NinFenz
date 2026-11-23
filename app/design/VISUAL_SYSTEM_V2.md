# NF 视觉体系 2.0 · 深度研究与拔高

> 不是把理论贴到令牌上，而是把每一层变成**可计算、可失败、可复算**的约束。
> 代码：`ui/design/Perception.kt`、`Encoding.kt`、`Composition.kt`、`Theory.kt`。

## 1. 这一轮真正改变了什么

| 层 | 原方案 | 2.0 拔高 | 结果 |
|---|---|---|---|
| 格式塔 | 写“接近性/相似性” | 组内 12 / 组间 24，比例 ≥1.5；视觉重量公式 | `Proximity` / `Salience` |
| 图底 | 明度阶梯 0–3 | 深色阶梯实测；发现最后一级 ΔL=0.003 不可感知 | **改深色 surface** |
| Bertin | 列 7 变量 | 按数据类型给通道排序；色相禁止表达定量 | `ChannelRanking` |
| 色觉 | 只做 WCAG 对比 | 加入 deuteranopia/protanopia 模拟与 ΔE | `ColorVision` |
| Kress | 说“上理想/下现实” | 信息角色可验证：1 PRIMARY / ≤1 ACTION / CONTEXT first / ACTION last | `Composition` |
| Lupton | 列 9 原则 | 网格 4/8/12 列、限宽 720、密度函数 | `Breakpoint` / `Density` |
| 动效 | 150/250/300 | 反馈 <400ms、150ms 后骨架、长任务 2s | `Feedback` |
| 体验 | 映射 Morville/HEART | 指标口径 + instrumented 标记，未埋点不写已测 | `VisualTheory.metrics` |

## 2. 关键发现：深色图底阶梯不合格

旧深色表面：

| 层 | 色值 | 相对亮度 | 相邻 ΔL |
|---|---|---|---|
| base | #0F1413 | 0.0065 | — |
| card | #1B2725 | 0.0182 | 0.0117 |
| raised | #232F2D | 0.0258 | 0.0076 |
| variant | #253230 | 0.0289 | 0.0031 |

最后一级在深色下几乎不可见。**2.0 改为**：

| 层 | 色值 | 相对亮度 | 相邻 ΔL |
|---|---|---|---|
| base | #0F1413 | 0.0065 | — |
| card | #1B2725 | 0.0182 | 0.0117 |
| raised | #2A3734 | 0.0347 | 0.0165 |
| variant | #34433F | 0.0510 | 0.0163 |

阈值 `GroundLadder.MIN_STEP=0.01`；测试用真实令牌，不用手写色值。

## 3. 创新 1：显著性预算

`weight = area × contrast × (1 + colorfulness) × (weight/400) × accent`

约束：

- 一屏 PRIMARY ≤1
- accent 面积 ≤18%
- 主操作必须显著高于正文

这把“主操作只有一个”从口号变成可算预算。

## 4. 创新 2：Bertin 通道选择

| 数据类型 | 首选 | 禁用 |
|---|---|---|
| 定量 | 位置 > 大小 > 明度 | 色相表达大小 |
| 定序 | 位置 > 明度 > 大小 | 色相表达顺序 |
| 定类 | 位置/形状/色相 | 大小表达类别 |

NF 的覆盖条用长度；信任等级用位置+文字；状态用色相+形状+文字；不用颜色单独承担定量。

## 5. 创新 3：信息角色验证

`Composition.validate` 强制：

- 恰好 1 个 PRIMARY
- ≤1 个 ACTION
- CONTEXT 在首
- ACTION 在末

这把 Kress 的“信息价值”变成布局测试。

## 6. 创新 4：响应式密度不做“无脑 0.75”

`Density.factor`：

- <360dp：1.0
- 360–599：0.9
- ≥600：0.82
- fontScale ≥1.3：**回到 1.0**

原因：大字下继续压缩，会把可读性压没；密度是空间策略，不是全局缩放。

## 7. 创新 5：色觉安全

`ColorVision`：

- deuteranopia / protanopia 近似矩阵
- ΔE76 检查状态色间距
- 品牌色相仍锁 168±10°

状态不只用红/绿；必须文字+形状+颜色。色觉模拟用于发现“看起来分开、模拟后合并”的状态色。

## 8. 创新 6：反馈预算

- 反馈 <400ms
- 150ms 后才显示骨架，避免闪烁
- >2s 长任务必须有进度/可取消

比“动效 150/250/300”更接近真实感知。

## 9. 理论到代码的覆盖

- Gestalt 6
- Bertin 7
- Kress 3
- Lupton 9
- Morville 7
- HEART 5
- Garrett 5
- 补充 8（Fitts/Hick/Miller/Sweller/Doherty/Jakob/Peak-End/Tufte）
- 共 **50 条规则**

`VisualTheoryTest` 锁：

- 构造覆盖无缺口
- 规则 ID 唯一、source/token/rule 非空
- 指标 instrumented 不造假
- 间距/圆角/字阶/动效在栅格
- 对比度全过
- 状态色成对

## 10. 明确拒绝的“高级感”

- 深色阴影堆层级 → 改用明度阶梯
- 玻璃拟态/渐变强调 → 降低正文对比，拒绝
- 红绿双色状态 → 色觉不安全，拒绝
- 嵌套卡片 → 框架语义重复，拒绝
- 每屏都 0.75 密度 → 大字不可读，拒绝
- 绝对左=已知/右=新 → RTL/中文竖排不成立，改为角色验证

## 11. 仍不冒充

- 默认 App 主题未迁移；当前是 `NfDesignTheme` opt-in
- 系统层 `design_lint --scope system` 0 违规；`--scope app` 仍报旧 `Theme.kt` 14 条迁移债
- 没有逐屏 6 张截图矩阵
- 没有 TalkBack/横屏/200% 真机证据
- HEART 的留存/时长未埋点


## 13. 系统层自评（不冒充屏幕层）

| 项 | 结果 | 证据 |
|---|---|---|
| 理论构造覆盖 | 50/50 | `VisualTheoryTest.everyRequiredTheoryConstructHasARule` |
| 明暗对比对 | 19/19 × 2 | `VisualTheoryTest.allContrastPairsPassTheirMinimum` |
| 深色图底阶梯 | 3/3 步 ≥0.01 | `GroundLadder` + `DeepVisualSystemTest` |
| 间距/圆角/字阶/动效 | 全在栅格 | `spacingAndScaleStayOnTheGrid` |
| 显著性预算 | 可计算 | `SalienceBudget` |
| 通道选择 | 按数据类型 | `ChannelRanking` |
| 构图角色 | 1 PRIMARY / ACTION last | `Composition.validate` |
| 响应式密度 | 大字回 1.0 | `Density.factor` |
| 反馈预算 | <400ms | `Feedback` |
| 系统层 lint | **0 违规** | `python app/scripts/design_lint.py` |
| 旧 App 主题 | **14 条迁移债** | `python app/scripts/design_lint.py --scope app` |

**未得分项**：逐屏评分、200%/横屏/TalkBack、真实 HEART 指标。没有这些，不写“屏幕层完美”。


## 14. 单屏审计已代码化

`ScreenAudit` 把 24 项评分卡收敛为 12 条可执行证据：

| ID | 检查 |
|---|---|
| S-TYPE | 字号 ≤4 |
| S-WEIGHT | 字重 ≤2 |
| S-ACTION | 主操作 ≤1 |
| S-ACCENT | accent 面积 ≤18% |
| S-GRID | 间距全在 4dp 栅格 |
| S-PROX | 组内/组间 ≥1.5 |
| S-CONTRAST | 最低对比 ≥4.5 |
| S-STATE | 状态有文字+形状+颜色 |
| S-CLIP | 200% 无截断（null 不算通过） |
| S-COMP | 1 PRIMARY / ACTION last |
| S-MOTION | 动效在 150/250/300 |
| S-FEEDBACK | 反馈 <400ms |

规则：

- **null 不通过**：没有截图证据不能填“200% 通过”。
- **blocked**：对比或截断失败直接阻断发布。
- 分数只用于同一套证据内比较，不跨设备比。


## 15. 组件契约

`ComponentContract.kt` 把 7 态与组件尺寸变成数据：

- 7 态：empty / loading / error / offline / partial / signed / expired
- 每态必须有标题、动作（loading 除外）、语气；error/partial/signed/expired 必须有证据
- 组件：顶栏 64、按钮 40/触控 48、输入 56、列表 56/72、chip 32/触控 48、导航 80
- 全在 4dp 栅格；full 圆角为 999 哨兵

这补上了“闭合性”和“组件状态”的可测部分。

## 12. 下一步

1. 用 2.0 令牌替换默认主题（只换 token，不换布局）
2. 把 `Proximity/Salience/GroundLadder/Composition` 接进 `design_lint`
3. 对 Library / Import / Delivery 三屏做 24 项评分
4. 截 6 张矩阵图，记录失败项
5. 通过后再全量迁移

