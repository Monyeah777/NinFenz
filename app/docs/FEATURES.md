# Free / Pro / CCOS 分层

> 依据 v2 增量补丁 §2/§3（D21–D24）。当前不写计费，`FeatureGate` 为空实现，默认 Free 全开。

## Free 永不锁

导入/分享/SAF/剪贴板/清空/重置、自动切片/一键成稿/可编辑预览/撤销/自动保存、模板/协议整包替换/基础管线/槽位、L0/L1 校验与基础修复、md/zip/docx/pdf/print 导出、分享 Markdown/文件/提示词、草稿→项目、基础 AI 样本/待修稿、基础来源/历史/撤销、基础拍照/OCR、基础可读性。

## Pro 增量（加深度，不替代 Free）

完整 Pack/Graph/DSL/权重作者、多项目并行/批量/产品线、跨语料重构/类型/schema/约束求解/属性测试、合同/验收/监管/披露/lineage/审计/trace、Prompt 编译/CI/灰度/回滚/内容网格、组合 ROI/容量/评审/长期保存、政策即代码/能力分享、高级采集/音频/渠道/因果/情景/校准风险。

## CCOS 增量（执行面）

API/Provider/Agent/工具/批量/调度、重 OCR/LLM/检索/核查、运行时契约监控、执行证据/trace、密钥/预算/策略。APP 只发 `ccos-task`，不直连模型。

## 规则

- 不对导出/分享/清空/预览收费；
- 不强制云账号；
- Pro 关闭后 Free 仍可用；
- CCOS 关闭后本地仍工作；
- `FeatureGate` 默认 `FREE`，`allows()` 全开；未来 Pro/CCOS 只加层，不回锁 Free。

## 机制 backlog

M1–M42 是 backlog，不是一次性开发清单。Phase M P0 原型：M1、M2、M4、M12、M15、M24、M25、M35、M38；通过后再进 Rust/Kotlin，失败 `OPEN`。
