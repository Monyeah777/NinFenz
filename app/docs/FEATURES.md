# Daily / Pro / CCOS 分层

> 依据 v2 增量补丁 §2/§3（D21–D24）与 0.3.3 去审计化。当前不写计费；`FeaturePolicy` 是策略即代码的规则表，`FeatureGate` 默认 Daily，未接 Pro/CCOS 购买入口。

## Daily（FREE）永不锁

导入/分享/SAF/剪贴板/清空/重置、自动切片/一键成稿/可编辑预览/撤销/自动保存、模板/协议整包替换/基础管线/槽位、装配/预览/基础导出（md/zip/docx/pdf/epub/html/json/skill/nfdoc）、分享 Markdown/文件/提示词、草稿→项目、基础 AI 样本/待修稿、基础来源/撤销、基础拍照/OCR、基础可读性。Daily 不展示校验/评审/审计/签收/CCOS/Pack Studio，也不以 L1 阻止导出。

## Pro 增量（加深度与审计，不替代 Daily）

L1/L2 校验、导出前门禁、项目人审、逐块评审、handoff、合同/签收、preservation/lineage、导出复现/manifest 对账、PDF/UA、决策日志、Pack verify/trust/Pack Studio/更新、CCOS 交接；完整 Pack/Graph/DSL/权重作者、多项目并行/批量/产品线、跨语料重构/类型/schema/约束求解/属性测试、Prompt 编译/CI/灰度/回滚/内容网格、组合 ROI/容量/长期保存、政策即代码/能力分享。

## CCOS 增量（执行面）

API/Provider/Agent/工具/批量/调度、重 OCR/LLM/检索/核查、运行时契约监控、执行证据/trace、密钥/预算/策略。APP 只发 `ccos-task`，不直连模型。

## 规则

- 不对导出/分享/清空/预览收费；
- 不强制云账号；
- Pro 关闭后 Free 仍可用；
- CCOS 关闭后本地仍工作；
- `FeatureGate` 默认 Daily（`FREE`）；Daily 永远放行，Pro/CCOS 规则只在对应 tier 放行。
- 未知能力默认 Free，避免误锁；已知 Pro/CCOS 能力默认锁定。
- 0.3.3 没有购买/授权 UI；Pro/CCOS 通过内部构建 `-PnfEdition=pro|ccos` 进入，不对外分发。

## 机制 backlog

M1–M42 是 backlog，不是一次性开发清单。Phase M P0 原型：M1、M2、M4、M12、M15、M24、M25、M35、M38；通过后再进 Rust/Kotlin，失败 `OPEN`。
