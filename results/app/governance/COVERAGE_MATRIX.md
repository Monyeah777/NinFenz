# 112 节点覆盖矩阵

> absent=0 partial=0 missing_evidence=0

| 节点 | 层 | 名称 | 优先级 | 状态 | H | 证据 |
|---|---|---|---|---|---|---|
| C0-01 | C0 | 共享核心桥 | P2 | conformant | - | yes |
| C0-02 | C0 | 契约与错误码 | P2 | conformant | - | yes |
| C0-03 | C0 | 本地数据与原子写 | P2 | conformant | - | yes |
| C0-04 | C0 | 平台文件/分享接入 | P2 | conformant | - | yes |
| C0-05 | C0 | 安全与隐私边界 | P0 | conformant | - | yes |
| C0-06 | C0 | 诊断与崩溃 | P2 | conformant | - | yes |
| C0-07 | C0 | 存储与缓存 | P2 | conformant | - | yes |
| C0-08 | C0 | 证据信封与 claim ledger | P1 | conformant | H2.4,H4.1 | yes |
| C0-09 | C0 | 性能与资源预算 | P1 | conformant | H1.4 | yes |
| C0-10 | C0 | 数据/格式迁移 | P1 | conformant | H6.4 | yes |
| C1-01 | C1 | 文件导入 | P1 | conformant | H1.4 | yes |
| C1-02 | C1 | 分享导入 | P2 | conformant | - | yes |
| C1-03 | C1 | 剪贴板与示例 | P2 | conformant | - | yes |
| C1-04 | C1 | 结构化文档 | P1 | conformant | H1.1,H1.3 | yes |
| C1-05 | C1 | OCR | P1 | conformant | H1.1 | yes |
| C1-06 | C1 | CSV/TSV 表格 | P2 | conformant | - | yes |
| C1-07 | C1 | 归档/包导入 | P2 | conformant | - | yes |
| C1-08 | C1 | 接入治理 | P1 | conformant | H1.2 | yes |
| C1-09 | C1 | 来源与历史 | P2 | conformant | - | yes |
| C1-10 | C1 | 格式保真度报告 | P1 | conformant | H1.2,H2.3 | yes |
| C2-01 | C2 | 格式嗅探与适配 | P1 | conformant | H2.1 | yes |
| C2-02 | C2 | 自动切片 | P2 | conformant | - | yes |
| C2-03 | C2 | 零切片（zero-slice） | P1 | conformant | H2.3 | yes |
| C2-04 | C2 | 映射建议 | P1 | conformant | H1.3,H2.2 | yes |
| C2-05 | C2 | 导入草稿 | P2 | conformant | - | yes |
| C2-06 | C2 | 草稿转项目 | P2 | conformant | - | yes |
| C2-07 | C2 | 模板候选/模板包 | P1 | conformant | H6.3,H6.4 | yes |
| C2-08 | C2 | Prompt / AI 样本 | P2 | conformant | - | yes |
| C2-09 | C2 | 纠错语料与评估 | P1 | conformant | H2.2 | yes |
| C3-01 | C3 | 协议条款/字段 | P2 | conformant | - | yes |
| C3-02 | C3 | 协议渲染/规则 | P2 | conformant | - | yes |
| C3-03 | C3 | 管线图编辑 | P1 | conformant | H3.1 | yes |
| C3-04 | C3 | 管线校验 | P1 | conformant | H3.1,H3.2 | yes |
| C3-05 | C3 | 规格章节/槽位 | P2 | conformant | - | yes |
| C3-06 | C3 | 规格校验 | P2 | conformant | - | yes |
| C3-07 | C3 | 作者覆盖 | P2 | conformant | - | yes |
| C3-08 | C3 | 编辑安全 | P2 | conformant | - | yes |
| C3-09 | C3 | Pack 绑定/引用 | P2 | conformant | - | yes |
| C3-10 | C3 | 模板覆盖/引用 | P2 | conformant | - | yes |
| C4-01 | C4 | 装配计划 | P1 | conformant | H3.2,H3.3,H4.1 | yes |
| C4-02 | C4 | 槽位输入 | P1 | conformant | H2.1 | yes |
| C4-03 | C4 | 槽位批量导入 | P2 | conformant | - | yes |
| C4-04 | C4 | 约束面板 | P2 | conformant | - | yes |
| C4-05 | C4 | 装配 | P1 | conformant | H4.1 | yes |
| C4-06 | C4 | 预览 | P2 | conformant | - | yes |
| C4-07 | C4 | 块编辑 | P1 | conformant | H4.3 | yes |
| C4-08 | C4 | 变换 | P1 | conformant | H4.3 | yes |
| C4-09 | C4 | 形式化 | P2 | conformant | - | yes |
| C4-10 | C4 | nf-patch | P1 | conformant | H6.1 | yes |
| C4-11 | C4 | nf-doc 合并 | P1 | conformant | H2.1,H4.2,H6.1 | yes |
| C4-12 | C4 | 多项目批量装配 | P1 | conformant | H3.3,H3.4 | yes |
| C5-01 | C5 | L0/L1 校验 | P2 | conformant | - | yes |
| C5-02 | C5 | 问题定位/修复 | P2 | conformant | - | yes |
| C5-03 | C5 | 导出前门禁 | P2 | conformant | - | yes |
| C5-04 | C5 | 纠正 Prompt | P2 | conformant | - | yes |
| C5-05 | C5 | 导出复现 | P2 | conformant | - | yes |
| C5-06 | C5 | 导出物校验 | P2 | conformant | - | yes |
| C5-07 | C5 | 验收清单 | P2 | conformant | - | yes |
| C5-08 | C5 | 设备签收 | P1 | conformant | H5.2 | yes |
| C5-09 | C5 | 项目人审 | P2 | conformant | - | yes |
| C5-10 | C5 | 性质自检 | P2 | conformant | - | yes |
| C5-11 | C5 | 归档链/升级 | P2 | conformant | - | yes |
| C5-12 | C5 | 内容可访问性审计 | P1 | conformant | H5.1 | yes |
| C6-01 | C6 | 文档导出 | P1 | conformant | H4.2,H4.4,H5.3 | yes |
| C6-02 | C6 | 数据/迁移导出 | P1 | conformant | H4.4 | yes |
| C6-03 | C6 | 长期保存包 | P1 | conformant | H5.2,H5.4 | yes |
| C6-04 | C6 | DOCX 参考样式 | P1 | conformant | H4.4,H5.3 | yes |
| C6-05 | C6 | 分享/打开/复制 | P2 | conformant | - | yes |
| C6-06 | C6 | 导出记录 | P2 | conformant | - | yes |
| C6-07 | C6 | 能力授权 | P2 | conformant | - | yes |
| C6-08 | C6 | 归档只读 | P2 | conformant | - | yes |
| C6-09 | C6 | 交付状态 | P2 | conformant | - | yes |
| C6-10 | C6 | 可访问导出 | P1 | conformant | H5.1 | yes |
| C7-01 | C7 | Pack 安装 | P2 | conformant | - | yes |
| C7-02 | C7 | Pack 校验/信任 | P2 | conformant | - | yes |
| C7-03 | C7 | Pack 详情/卸载 | P2 | conformant | - | yes |
| C7-04 | C7 | 更新计划 | P1 | conformant | H6.2 | yes |
| C7-05 | C7 | 冲突裁决 | P1 | conformant | H6.2 | yes |
| C7-06 | C7 | 应用/回滚 | P1 | conformant | H6.2 | yes |
| C7-07 | C7 | 项目生命周期 | P1 | conformant | H1.3,H6.3 | yes |
| C7-08 | C7 | 状态/历史 | P2 | conformant | - | yes |
| C7-09 | C7 | 项目包/合集 | P2 | conformant | - | yes |
| C7-10 | C7 | 本地备份/恢复 | P2 | conformant | - | yes |
| C7-11 | C7 | 模板/项目复用 | P1 | conformant | H6.4 | yes |
| C7-12 | C7 | CCOS 交接 | P2 | conformant | - | yes |
| C7-13 | C7 | 能力层级/策略 | P2 | conformant | - | yes |
| C7-14 | C7 | Pack 签名与信任根 | P0 | conformant | H5.4 | yes |
| C7-15 | C7 | 审计/溯源日志 | P0 | conformant | H2.4,H5.2 | yes |
| C8-01 | C8 | 导航/外壳 | P2 | conformant | - | yes |
| C8-02 | C8 | 工作流 | P1 | conformant | H3.4 | yes |
| C8-03 | C8 | 库管理 | P2 | conformant | - | yes |
| C8-04 | C8 | 全局搜索 | P2 | conformant | - | yes |
| C8-05 | C8 | 命令面板/快捷方式 | P2 | conformant | - | yes |
| C8-06 | C8 | 设计系统 | P2 | conformant | - | yes |
| C8-07 | C8 | 自适应 | P2 | conformant | - | yes |
| C8-08 | C8 | 无障碍/触觉 | P2 | conformant | - | yes |
| C8-09 | C8 | 主题 | P2 | conformant | - | yes |
| C8-10 | C8 | 语言 | P2 | conformant | - | yes |
| C8-11 | C8 | 反馈/恢复 | P2 | conformant | - | yes |
| C8-12 | C8 | 隐私/诊断/关于 | P2 | conformant | - | yes |
| C8-13 | C8 | 首启引导 | P2 | conformant | - | yes |
| C8-14 | C8 | 辅助输入与读屏遍历 | P1 | conformant | - | yes |
| C8-15 | C8 | 搜索质量与排序 | P1 | conformant | - | yes |
| C8-16 | C8 | 本地化/RTL/pseudolocale | P1 | conformant | - | yes |
| C9-01 | C9 | 覆盖矩阵 | P1 | conformant | H1.2,H6.3 | yes |
| C9-02 | C9 | 扩展点/SPI | P1 | conformant | - | yes |
| C9-03 | C9 | 声明式扩展 | P1 | conformant | H6.4 | yes |
| C9-04 | C9 | 开放格式/互操作桥 | P1 | conformant | H1.1,H5.3 | yes |
| C9-05 | C9 | 数据可携带/退出 | P1 | conformant | H6.3 | yes |
| C9-06 | C9 | 用户控制/可逆/可解释 | P1 | conformant | - | yes |
| C9-07 | C9 | 自定义/预设 | P2 | conformant | - | yes |
| C9-08 | C9 | 扩展治理/信任 | P1 | conformant | H5.4,H6.2 | yes |
