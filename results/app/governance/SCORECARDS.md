# 硬技术记分卡

> 当前 proven 24/24；未跑 Trials 0/10。proven 只来自 trials/ 下可复算结果。

## 六层 × 四项

### H1

| ID | 能力 | 当前 | 目标 | 关键阈值 |
|---|---|---|---|---|
| H1.1 | 版式感知通用接入 | proven | proven | 阅读顺序 ≥98%，表格 F1 ≥95%，脚注 ≥95%，0 OOM，500 页 <60s |
| H1.2 | 保真账本 | proven | proven | 100% 特征有账；0 静默丢失；差异可定位到页/框 |
| H1.3 | 多源融合 | proven | proven | 章节对齐 ≥95%，冲突 100% 标记，0 静默覆盖 |
| H1.4 | 可恢复流式接入 | proven | proven | 25/50/75% 杀进程后 100% 恢复；0 丢失；峰值 ≤300MB |

### H2

| ID | 能力 | 当前 | 目标 | 关键阈值 |
|---|---|---|---|---|
| H2.1 | 语义文档 IR | proven | proven | 100% P0 文档入 IR；往返语义等价 ≥98% |
| H2.2 | 约束感知 schema 归纳 | proven | proven | 槽位 P≥0.9/R≥0.85，ECE≤0.1 |
| H2.3 | 语义修复 | proven | proven | 修复成功 ≥90%，0 不可恢复，所有修复可撤销 |
| H2.4 | 块级溯源图 | proven | proven | 100% 块可追；篡改 100% 检出；离线可验 |

### H3

| ID | 能力 | 当前 | 目标 | 关键阈值 |
|---|---|---|---|---|
| H3.1 | 类型化管线演算 | proven | proven | 100% 图可校验；0 类型错误漏报；同输入同 plan hash |
| H3.2 | 约束求解/规划 | proven | proven | 合法 plan ≥95%，unsat 解释 100%，<2s |
| H3.3 | 增量重规划 | proven | proven | 重建集最小；0 过期输出；<300ms |
| H3.4 | 组合编排 | proven | proven | 0 交叉污染；失败隔离 100%；可恢复 |

### H4

| ID | 能力 | 当前 | 目标 | 关键阈值 |
|---|---|---|---|---|
| H4.1 | 确定性内容构建 | proven | proven | 100 次构建同 sha；缓存命中 ≥80%；增量 <300ms |
| H4.2 | 语义合并/装配 | proven | proven | 0 静默丢失；交叉引用 100% 有效；表格单元格正确 |
| H4.3 | 块级增量重算 | proven | proven | parity 100%；p95 <300ms；0 过期块 |
| H4.4 | 单 IR 多 Profile | proven | proven | 语义 parity ≥98%；验证器 0 error |

### H5

| ID | 能力 | 当前 | 目标 | 关键阈值 |
|---|---|---|---|---|
| H5.1 | 可访问即构造 | proven | proven | EPUBCheck/veraPDF/Open XML 0 error；WCAG AA 0 blocker |
| H5.2 | 证据随包 | proven | proven | 100% 可验；篡改 100% 检出；0 网络 |
| H5.3 | 跨端首次打开 | proven | proven | 100% 首次打开；0 修复；0 缺字 |
| H5.4 | 签名可复现包 | proven | proven | 两次构建同 sha；签名 100%；回滚/冻结 100% |

### H6

| ID | 能力 | 当前 | 目标 | 关键阈值 |
|---|---|---|---|---|
| H6.1 | 语义三方合并 | proven | proven | 0 静默丢失；冲突 precision ≥95%；引用 100% 有效 |
| H6.2 | Pack 更新演算 | proven | proven | 0 项目损坏；回滚/冻结 100%；未签名严格拒绝 |
| H6.3 | 内容复用图 | proven | proven | recall ≥90%；传播 100%；0 过期 |
| H6.4 | 模板归纳 + 迁移 | proven | proven | 模板 F1 ≥0.85；N-2 迁移 100%；0 丢失 |

## 10 Trials

| ID | 挑战 | 状态 |
|---|---|---|
| T01 | 500 页多栏 PDF → 可访问 EPUB/PDF/DOCX | passed |
| T02 | 两版 DOCX 语义三方合并 + 多源融合 | passed |
| T03 | spec+模块+资产求解合法管线 + unsat 解释 | passed |
| T04 | 改一块增量构建，输出完全一致 | passed |
| T05 | DOCX→IR→EPUB/PDF→IR→DOCX 往返 | passed |
| T06 | 20 文档可访问交付 | passed |
| T07 | 证据随包 + 离线验证 + 篡改检出 | passed |
| T08 | 签名 Pack 更新：冲突/应用/回滚/冻结 | passed |
| T09 | 100 项目复用图 + 组合编排 | passed |
| T10 | 500 页导入在 25/50/75% 杀进程后续传 | passed |

## 结论

- 当前 proven：24（H1.1, H1.2, H1.3, H1.4, H2.1, H2.2, H2.3, H2.4, H3.1, H3.2, H3.3, H3.4, H4.1, H4.2, H4.3, H4.4, H5.1, H5.2, H5.3, H5.4, H6.1, H6.2, H6.3, H6.4）
- 当前 prototype：
- 当前 not-started：
- 未跑 Trials：0/10