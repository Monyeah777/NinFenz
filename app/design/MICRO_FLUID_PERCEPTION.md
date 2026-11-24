# 微观排版、流式缩放、滚动与非视觉感知

> 补齐四项此前缺失，并把盲区显式登记。代码见 `ui/design/MicroType.kt`、`Fluid.kt`、`Rhythm.kt`、`NonVisual.kt`。

## 1. 微观排版硬约束

| 约束 | 值 | 判定 |
|---|---|---|
| 中文行宽 | 20–26 字 | `MicroType.cjkLineChars` |
| 拉丁行宽 | 45–90 字符 | `ReadingMeasure` |
| 正文行高 | 1.5–1.75 | `MicroType.validLineHeight` |
| 字距 | 0 | `validTracking` |
| 孤行 | 最后一行 1 字且 >3 行 = 失败 | `isWidow` |
| 哈希 | 4 字符分组 | `groupHash` |
| 引号 | 中文成对 “ ” | `quote` |
| 断行 | 标题 Heading / 正文 Paragraph；不两端对齐 | `NfType` |
| 数字 | tabular（tnum） | `NfType.numeric` |
| 连字符 | 关闭 | `NfType` |

**未做**：Compose 没有直接暴露悬挂标点；目前只锁断行/字距/行高，悬挂标点需自定义 Layout。

## 2. 流式缩放

- 只流式：页面边距 16→32、区块间距 24→32、卡片内边距 12→16。
- 不流式：字号、触控、行高；字号只由系统 fontScale 控制。
- 插值在断点内连续，断点外 clamp；`FLUID_TYPE=false` 锁死“字号不得随屏宽缩小”。

## 3. 视觉节奏与滚动

- 垂直拍 = 8dp；所有纵向间距落在拍上。
- 列表行高 56/72 是 8 的整数倍。
- 底部内容 padding = 导航 80 + 16。
- 固定 section header、恢复滚动位置、关闭 overscroll。
- 顶栏 64、Fling 最小速度 400。

## 4. 非视觉感知

| 通道 | 规则 |
|---|---|
| 触觉 | confirm 12ms/80、error 24ms/160、selection 8ms/60；loading/empty 不震 |
| 声音 | 默认关闭，尊重静音/勿扰；成功音不能是唯一反馈 |
| 读屏 | error assertive；partial/signed/expired polite；loading 不抢占 |
| 减少动效 | duration 归零，仅 150/250/300 可动画 |
| IME | 底部 padding 必须避让键盘；刘海/导航栏安全区 |

## 5. 盲区登记

| # | 盲区 | 现状 | 下一步 |
|---|---|---|---|
| B1 | 悬挂标点 | 未实现 | 自定义 Layout / 文本后处理 |
| B2 | 真正的流式字号 | 明确禁止 | 只用 fontScale；不随屏宽缩小 |
| B3 | 滚动吸顶/折叠 | 只有策略常量 | 接入 LazyColumn stickyHeader |
| B4 | 触觉/声音 | 只有契约 | 接 HapticFeedback / 系统设置 |
| B5 | 键盘/IME | 只有 InsetsPolicy | 真机 IME 测试 |
| B6 | RTL | 有规则，无镜像测试 | 加 LayoutDirection 测试 |
| B7 | 折叠屏/分屏 | 未覆盖 | 600/840 宽度真机 |
| B8 | 进程死亡 | 有 ShellStateCodec | 边界恢复测试 |
| B9 | 权限拒绝/存储满 | 未覆盖 | 负向测试 |
| B10 | Emoji/双向文本 | 未覆盖 | 混排截图 |
| B11 | 大列表性能 | 未测 | Macrobenchmark |
| B12 | HEART 留存/时长 | 未埋点 | 本地自愿指标，不上报 |
| B13 | 焦点顺序/键盘 | 未覆盖 | TalkBack + 键盘 |
| B14 | 纹理/方向变量 | 有规则，无组件 | 只在数据可视化使用 |

## 6. 测试

`MicroFluidRhythmTest` 锁：

- 正文/长文/元信息行高在 1.5–1.75
- 中文行宽 20–26
- 哈希分组、中文引号、孤行
- 流式间距 clamp 与 300dp 中点
- 8dp 拍、底部 padding 96、overscroll 关闭
- 错误/已签/加载的触觉与读屏映射

## 7. 不冒充

- 这些是**系统层约束**，尚未接入默认 App 屏幕。
- IME/横屏/TalkBack 未真机验证。
- 触觉/声音尚未实际触发；只有策略与映射。
