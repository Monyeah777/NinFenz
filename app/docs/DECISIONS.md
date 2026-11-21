# 追加决策 D21–D24

> 来源：v2 增量补丁 §1。D1–D20 见既有方案/ADR，不在此重复。

| # | 决策 | 选择 |
|---|---|---|
| D21 | 机制采用 | M1–M42 是 backlog，按层/优先级/分层实施，不一次全做 |
| D22 | 功能分层 | Free 日常全给；Pro 深度/规模/团队/保证；CCOS 执行；不锁导入/预览/导出/分享/清空 |
| D23 | 原型优先 | 高风险机制先做参考原型/负例，再进 Rust/Kotlin；zero_slice 已完成 |
| D24 | 研究输入 | IDE/跨领域模式是输入，不是范围；不抄 IDE/设计工具/表格/自动化平台 |

落地：

- Free/Pro/CCOS 边界见 `app/docs/FEATURES.md`；
- zero_slice 参考原型见 `app/prototypes/zero_slice/`（14 测试）；
- 机制只选 P0 原型，Phase M 不阻塞 A–G。
