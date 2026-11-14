# 已实现结果导航

> 本目录只收录“已实现、可验证、可消费”的结果入口；计划/草案已内部归档，不在公开仓。

## 门禁与状态

- [README.md](../README.md) · [CHANGELOG.md](../CHANGELOG.md) · [docs/meta/VERSION-MATRIX.md](../docs/meta/VERSION-MATRIX.md) · [docs/release.md](../docs/release.md)

## 审计与收口

- [docs_audit-95-meta-cockpit.md](audit/docs_audit-95-meta-cockpit.md)（元认知生产驾驶舱主仓融合）
- [meta-cockpit-manifest.json](meta-cockpit-manifest.json)（运行时代码/契约/协议统一摘要清单）
- [docs_audit-58-pending-items.md](audit/docs_audit-58-pending-items.md)（六条挂账收口 + 出口/会话面外部核验）
- [docs_audit-57-external-protocols.md](audit/docs_audit-57-external-protocols.md) · [interop-schema-validation.md](interop-schema-validation.md)（外部权威校验取证）
- [trust/BASELINE.md](trust/BASELINE.md) · [trust/CLAIM_MATRIX.md](trust/CLAIM_MATRIX.md)（Trust Fabric WP-00 基线审计：锚点复验 + 差距重估 + Claim–Evidence 矩阵）
- [trust/trust_vectors.json](trust/trust_vectors.json)（Trust Fabric 测试向量集：34 条 / 7 族；跨语言可自验，生成器 `scripts/trust_vectors.py`）
- [trust/SELF_AUDIT.json](trust/SELF_AUDIT.json) · [docs/trust/SELF_AUDIT.md](../docs/trust/SELF_AUDIT.md)（G1 收口自审计：S0–S12 维度 + P0/P1 分诊 + 门禁取证）
- [BASELINE.md](BASELINE.md)（NF Final WP-00 基线审计：34 条 FR/NFR Claim–Evidence 矩阵 + check 编号对账 + 环境/门禁实读）
- [reverse/INVENTORY.md](reverse/INVENTORY.md)（§4A R0 仓库考古：真源/生成物/草稿三表 + 入口 + 失败面初判）
- [reverse/CONTRACT_MAP.md](reverse/CONTRACT_MAP.md)（§4A R1 契约提取：显式 11 组 / 隐式 8 组 / 缺口 5 条；机读 `reverse/contracts.json`，判据 `test_reverse_contracts.py`）
- [reverse/BEHAVIOR.md](reverse/BEHAVIOR.md)（§4A R2 行为重建：11 条行为流 9 documented + 2 gap、3 个状态机、exit 0/1/2 失败语义；机读 `reverse/behavior.json`，判据 `test_reverse_behavior.py`）
- [reverse/COUPLING.md](reverse/COUPLING.md)（§4A R3 耦合与重复实现：300 模块/540 边/0 环/9 SDP、fan-in/out 热点、7 项重复裁定；机读 `reverse/coupling.json`，判据 `test_reverse_coupling.py` 实时重算图）
- [reverse/FAILURE_ARCHAEOLOGY.md](reverse/FAILURE_ARCHAEOLOGY.md)（§4A R4 失败考古：13 条失败模式、5 条文档-代码不一致、9 个缺口进 R6；机读 `reverse/failures.json`，判据 `test_reverse_failures.py`）
- [reverse/PEER_DIFF.md](reverse/PEER_DIFF.md)（§4A R5 同行差分：6 项对照、借/不造边界、3 条影响设计的决策 D-PD-01…03；机读 `reverse/peers.json`，判据 `test_reverse_peers.py`）
- [reverse/INVARIANTS.md](reverse/INVARIANTS.md)（§4A R6 不变量：7 层 14 条，tested 6 / covered-by-existing 4 / unobservable 4（挂 G1/G2）；机读 `reverse/invariants.json`，判据+执行器 `test_reverse_invariants.py`）
- [ADR_MAP.md](ADR_MAP.md)（方案 §16.2 裁决 → `nf-adr/1` 登记投影：12 条映射、`plan_ref` 一对一、实施状态与缺口 WP）
- [independence.json](independence.json)（生产/治理双平面边界报告：`protocol/independence.json` 65 个模块归属 + 295 个 core 模块静态闭包零跨界，check49 判据件）
- [production/threat_vectors.json](production/threat_vectors.json)（NF-Final §8 威胁向量：六条信任边界 + STRIDE 8 行 + 失败矩阵 8 行，逐条绑定控制点/证据/状态；判据 `test_production_threat_vectors.py`）
- [docs/production/THREAT_MODEL.md](../docs/production/THREAT_MODEL.md)（生产平面威胁模型人读面：边界/STRIDE/失败矩阵 + 状态词表 + 不承诺边界）
- [docs/qa/PRIVACY_QA.md](../docs/qa/PRIVACY_QA.md)（隐私 QA：数据地图/删除证据/PII 扫描/保留约束的判据与实测；配套 `PRIVACY.md` + `protocol/privacy.json`）
- [ops/drills.json](ops/drills.json)（运维演练报告：桌面演练 4 级 + 恢复闭环 + 披露口径 + 供应商退出就绪；判据 `test_ops_contract.py`，配套 `docs/security/INCIDENT_RESPONSE.md`/`docs/sre/`/`docs/legal/VENDORS.md`）
- [docs/ai/AI_GOVERNANCE.md](../docs/ai/AI_GOVERNANCE.md) · [docs/eval/EVAL_PROTOCOL.md](../docs/eval/EVAL_PROTOCOL.md)（AI 影响评估/模型风险/监管映射 + 评测效度协议；真源 `protocol/{ai_governance,eval_validity}.json`，判据 `test_ai_eval_contract.py`）
- [eval/interrater_sample.json](eval/interrater_sample.json)（inter-rater 样本：12 条双评；Cohen's kappa 由 `core.eval_validity.interrater` 现算）
- [../LEGAL.md](../LEGAL.md) · [../GOVERNANCE.md](../GOVERNANCE.md) · [../docs/legal/](../docs/legal/)（法务/许可/出口 + 开源治理；真源 `protocol/legal.json`，审计入口 `scripts/legal_audit.py`，判据 `test_legal_contract.py`）
- [../A11Y.md](../A11Y.md) · [../I18N.md](../I18N.md) · [a11y/A11Y_QA.md](../docs/a11y/A11Y_QA.md) · [i18n/I18N_QA.md](../docs/i18n/I18N_QA.md)（可访问性 WCAG/PAIR-HAX + 语言面/时区/RTL-bidi；真源 `protocol/{accessibility,i18n}.json`，判据 `test_a11y_i18n_contract.py`）
- [assurance/CLAIMS.json](assurance/CLAIMS.json) · [../docs/assurance/ASSURANCE_CASE.md](../docs/assurance/ASSURANCE_CASE.md) · [../docs/RAID.md](../docs/RAID.md) · [../docs/ETHICS.md](../docs/ETHICS.md)（GSN/CAE 保证案例 + RAID + 伦理评审；真源 `results/assurance/CLAIMS.json` + `protocol/raid.json`，判据 `test_assurance_contract.py`）
- [cq/scan.json](cq/scan.json) · [cq/toolchain.json](cq/toolchain.json) · [../docs/CQ_REPORT.md](../docs/CQ_REPORT.md) · [../docs/QUALITY_DEBT.md](../docs/QUALITY_DEBT.md)（全仓 CQ0/CQ1：工具矩阵 + 九维自动扫描 + 质量债/人工审查清单；判据 `test_cq_scan_contract.py`）
- [../docs/product/PRFAQ.md](../docs/product/PRFAQ.md) · [../docs/product/GTM.md](../docs/product/GTM.md) · [../docs/product/INTERVIEWS.md](../docs/product/INTERVIEWS.md)（产品假设/GTM/访谈计划，全部 unverified；真源 `protocol/product.json`，判据 `test_product_contract.py`）

## 互操作导出面（入仓投影）

- [results/interop/](interop/)（11 面派生投影：openapi / asyncapi / intoto / sbom / slsa / a2a / prov / cyclonedx / vc / c2pa / cid；与实时派生逐字节一致由 check33 断言）
- [docs_audit-56-queue-and-quant-absorption.md](audit/docs_audit-56-queue-and-quant-absorption.md)
- [docs_audit-55-quant-domain.md](audit/docs_audit-55-quant-domain.md)
- [docs_audit-54-external-inputs-shell.md](audit/docs_audit-54-external-inputs-shell.md)
- [docs_audit-53-authors-decisions.md](audit/docs_audit-53-authors-decisions.md)
- [docs_audit-52-external-inputs.md](audit/docs_audit-52-external-inputs.md)
- [docs_audit-51-ai-domain-deepen.md](audit/docs_audit-51-ai-domain-deepen.md)
- [docs_audit-50-ai-domain.md](audit/docs_audit-50-ai-domain.md)
- [docs_audit-45-quality-deep.md](audit/docs_audit-45-quality-deep.md)
- [docs_audit-46-a5-instruction.md](audit/docs_audit-46-a5-instruction.md)
- [docs_audit-44-ai-channel.md](audit/docs_audit-44-ai-channel.md)

## 正式协议与实现

- [01_核心协议.md](../01_核心协议.md) · [02_联动注册表.md](../02_联动注册表.md) · [06_Agent执行协议.md](../06_Agent执行协议.md) · [07_官方核心出厂与社区预设导航.md](../07_官方核心出厂与社区预设导航.md)
- [docs/meta-cockpit/README.md](../docs/meta-cockpit/README.md) · [功能解析.md](../docs/meta-cockpit/功能解析.md)（元认知生产驾驶舱入口与功能解析）
- [protocol/schema](../protocol/schema) · [protocol/generated](../protocol/generated)
- [desktop/src/core](../desktop/src/core) · [scripts](../scripts)

## 内容与资产

- [community](../community) · [05_资产库](../05_资产库)
- [docs/完整版样本_西幻生存流P03.md](../docs/完整版样本_西幻生存流P03.md)
