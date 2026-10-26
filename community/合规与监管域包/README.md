# 合规与监管域包（community 非叙事题材域包 · 合规与监管装配流）
> 定位：**AI 品类域包**（清单 F02 · F · 治理、安全与产业生态）——把「合规与监管」这一域的 12 条细分协议化：口径可判定、判据可机检、锚可复核，并产出**可复算的域报告**与**可机验的形态面**。
> 协议声明：包根 `protocol.yaml`（01 §6.1 Schema，schema_version "2"）为机读真相，本 README 为人读速览，双源一致（check14 ⑥）。
> 结构：modules/（2 域模块 合规与监管:M01、合规与监管:M02，类内段编号）｜assets/（**12 内容资产**：口径三件 CONCEPT_GRAPH / DOMAIN_SPEC / STANDARDS_ANCHORS + 合规证据九件）｜gate_profiles/（严格质量门 `regulatory-strict.json`，34 clause）｜outputs/（**9 机验产出面** + samples/ 证据包样例）｜pipelines/P98_合规与监管装配流管线.md
> 依赖边界（R1）：只依赖官方核心层（M00 / 通用:M10 / M50 / M80，core_only true），官方模块文件不复制进包。

## 1. 包速览

| 项 | 值 |
| --- | --- |
| 管线 | **P98** 合规与监管装配流（九层线性回卷，装配自 P00 通用骨架） |
| 自带模块（本包） | 2：合规与监管:M01（P40 口径登记） / 合规与监管:M02（P60 收口与派生） |
| 资产 | **12 文件**：口径三件 `CONCEPT_GRAPH.md`（12 概念前置图）· `DOMAIN_SPEC.md`（12 条细分口径）· `STANDARDS_ANCHORS.md`（权威锚 + §2 合规标准锚 6 标准 × 可信度）；合规证据九件 `COMPLIANCE_STATEMENT` · `AI_TRANSPARENCY_NOTICE` · `RISK_REGISTER` · `DATA_PROVENANCE_LEDGER` · `AUDIT_LOG_SCHEMA` · `IMPACT_ASSESSMENT` · `HUMAN_OVERSIGHT` · `RETENTION_CONTACT` · `EVIDENCE_PACK_INDEX`
| 机验产出面 | **9 件**：schema 2 / 数据 2 / 可复算 1（T4）/ 图表 1 / 图结构 2 / 系统卡 1；另有 `outputs/samples/AI_CONTENT_COMPLIANCE_EVIDENCE_PACK.md`（P98 证据包样例，`--check` PASS） |
| 度量族 | `classification`（口径公式见 `docs/domain-packs.md`） |

## 2. 复现命令

| 产物 | 命令（仓库根目录） |
| --- | --- |
| 前置闭包 / 装载序 | `python scripts/ai_domain_closure.py --asset community/合规与监管域包/assets/CONCEPT_GRAPH.md --target F02-12` |
| 形态与档位机检 | `python scripts/nf.py output verify` |
| 重渲染产出面 | `python scripts/nf.py output render --write --package 合规与监管域包` |
| 重新生成整包 | `python scripts/nf.py domain build --spec F02 --write` |
| 证据包机器验收 | `python scripts/nf.py assemble "自定义：AI 内容合规证据包（合规与监管域包 P98 装配）" --check community/合规与监管域包/outputs/samples/AI_CONTENT_COMPLIANCE_EVIDENCE_PACK.md` |
| 严格质量门逐条报告 | `python desktop/src/core/gate_profile.py --profile community/合规与监管域包/gate_profiles/regulatory-strict.json --text <产物.md>` |

## 3. 质量门（M80 软门 · profile 入口）

- `gate_profiles/regulatory-strict.json`：34 条 clause（32 fail / 2 warn），映射 EU AI Act 第 50 条（含 2026-06 行为准则）、GB 45438-2025、ISO/IEC 42001:2023、GB/T 35273-2020、NIST AI RMF 1.0；覆盖 AI 披露/标识、来源与授权、风险分级、人类监督、审计日志字段、保留期与联系人、敏感信息、版本变更八类可机检项。
- 判据**只用已注册 predicate**（regex / required_sections / table / revision_trace / doc_type / heading_count / table_columns），引擎零改动；未装 profile 的叙事流行为不变。
- 资产与 profile 的对应关系见各资产「机检映射」段；标准可信度见 `assets/STANDARDS_ANCHORS.md` §2。

## 4. 边界与不宣称

- 本包是**口径协议 + 机验产出**类域包：**不提供**模型、不执行推理、不做能力承诺。
- 域报告是**样例集上的口径值**（合成夹具，非真实测量），不是模型评测结论。
- 外部权威锚只作口径参照，**不作质量背书**；本包正文自撰。
