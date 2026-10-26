<!-- nf-asset: key="STANDARDS_ANCHORS" version="1.0" status="active" -->
# 权威锚表 · 合规与监管

> 用途：本域 12 条细分各自的**外部权威锚**（规范 / 论文 / 参考实现）与**可达性实证**。外部锚只作口径与机制参照，**不作品质背书**（STRATEGY §3.2/§3.3）。
> 资产键：`STANDARDS_ANCHORS`｜细分锚实测日期：2026-09-22（本机 GET，HTTP 状态见下表；不可达如实记 `✗`，不假装可达）｜标准锚实测日期见下表「标准锚」列（取自 `protocol/standards_catalog.json` 的本机探针记录）。

## 1. 锚表

| 条目键 | 锚类型 | URL | 可达性 | 主锚（域口径标准） | 辅锚（产出承载标准） |
|---|---|---|---|---|---|
| `F02-01` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `oasis-openapi` OpenAPI 3.1（OpenAPI Initiative｜iface｜✓ 2026-09-24；关键词「接口|API|端点|服务|部署」命中） | `ietf-json-schema` JSON Schema 2020-12（IETF/JSON Schema｜data｜✓ 2026-09-24；F 段载体锚（轮换 0；与主锚异层）） |
| `F02-02` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `w3c-prov-o` PROV-O 溯源本体（W3C｜gov｜✓ 2026-09-24；F 段默认绑定（轮换 1）） | `vega-lite` Vega-Lite v5（Vega｜form｜✓ 2026-09-24；F 段载体锚（轮换 2；与主锚异层）） |
| `F02-03` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `spdx-licenses` SPDX 许可证清单（SPDX｜gov｜✓ 2026-09-24；F 段默认绑定（轮换 2）） | `vega-lite` Vega-Lite v5（Vega｜form｜✓ 2026-09-24；F 段载体锚（轮换 3；与主锚异层）） |
| `F02-04` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `nist-ai-rmf` AI 风险管理框架（NIST｜gov｜✓ 2026-09-24；F 段默认绑定（轮换 0）） | `vega-lite` Vega-Lite v5（Vega｜form｜✓ 2026-09-24；F 段载体锚（轮换 3；与主锚异层）） |
| `F02-05` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `gdpr` GDPR（EU｜gov｜✓ 2026-09-24；关键词「隐私|个人信息|去标识|合规|监管」命中） | `mermaid` Mermaid 图语言（Mermaid｜form｜✓ 2026-09-24；F 段载体锚（轮换 4；与主锚异层）） |
| `F02-06` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `spdx-licenses` SPDX 许可证清单（SPDX｜gov｜✓ 2026-09-24；F 段默认绑定（轮换 2）） | `ietf-json-schema` JSON Schema 2020-12（IETF/JSON Schema｜data｜✓ 2026-09-24；F 段载体锚（轮换 0；与主锚异层）） |
| `F02-07` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `gdpr` GDPR（EU｜gov｜✓ 2026-09-24；关键词「隐私|个人信息|去标识|合规|监管」命中） | `vega-lite` Vega-Lite v5（Vega｜form｜✓ 2026-09-24；F 段载体锚（轮换 3；与主锚异层）） |
| `F02-08` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `gdpr` GDPR（EU｜gov｜✓ 2026-09-24；关键词「隐私|个人信息|去标识|合规|监管」命中） | `vega-lite` Vega-Lite v5（Vega｜form｜✓ 2026-09-24；F 段载体锚（轮换 3；与主锚异层）） |
| `F02-09` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `w3c-prov-o` PROV-O 溯源本体（W3C｜gov｜✓ 2026-09-24；关键词「溯源|证据链|审计」命中） | `ietf-json-schema` JSON Schema 2020-12（IETF/JSON Schema｜data｜✓ 2026-09-24；F 段载体锚（轮换 0；与主锚异层）） |
| `F02-10` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `gdpr` GDPR（EU｜gov｜✓ 2026-09-24；关键词「隐私|个人信息|去标识|合规|监管」命中） | `mermaid` Mermaid 图语言（Mermaid｜form｜✓ 2026-09-24；F 段载体锚（轮换 4；与主锚异层）） |
| `F02-11` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `gdpr` GDPR（EU｜gov｜✓ 2026-09-24；关键词「隐私|个人信息|去标识|合规|监管」命中） | `ietf-json-schema` JSON Schema 2020-12（IETF/JSON Schema｜data｜✓ 2026-09-24；F 段载体锚（轮换 0；与主锚异层）） |
| `F02-12` | spec | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | ✓ 200 | `spdx-licenses` SPDX 许可证清单（SPDX｜gov｜✓ 2026-09-24；F 段默认绑定（轮换 2）） | `vega-lite` Vega-Lite v5（Vega｜form｜✓ 2026-09-24；F 段载体锚（轮换 3；与主锚异层）） |

## 2. 合规标准锚（T4.2 纵深：可机检项 + 可信度）

> 目的：给 `gate_profiles/regulatory-strict.json` 的 clause 提供**标准出处与可信度标注**，避免「有标准编号但没有可检项」的空锚。
> 口径：只选**可机检**的标准要项（能落到章节 / 表头 / 字段 / 日期 / 词表的固定形状）；不可机检的义务（如「适当治理」）不登记为锚。

| 标准 | 正式编号 / 版本 | 本包可机检项（profile clause） | 本机 catalog 在册 | 可信度 | 依据与口径 |
|---|---|---|---|---|---|
| EU AI Act 第 50 条透明度义务 | Regulation (EU) 2024/1689，Art. 50；2026-08-02 起适用 | `EU-AIA-50-TRANSPARENCY-SECTION` / `EU-AIA-50-GEN-STATEMENT` / `EU-AIA-50-DISCLOSURE-TABLE` / `EU-AIA-50-DEEPFAKE` / `EU-AIA-50-EFFECTIVE-DATE` | 在册（`eu-ai-act`，含本机探针记录） | **高** | 条文与适用日期为公开发布文本的固定事实；本包只检披露章节/文本/表/深度合成/适用日期的形状，不检披露内容是否充分 |
| 2026-06 透明度行为准则 | Code of Practice on transparent AI-generated content（2026-06 版） | `EU-AIA-COP-2026-06` | 未入本机 catalog（catalog 只收标准，不收行为准则类文件） | **中** | 按任务输入登记为 2026-06 版，条款细节以正式发布文本为准；本包只检「合规声明是否引用行为准则」这一可检形状 |
| GB 45438-2025 标识方法 | GB 45438-2025《网络安全技术 人工智能生成合成内容标识方法》 | `GB-45438-EXPLICIT` / `GB-45438-IMPLICIT` / `GB-45438-LABEL-TABLE` | 未入本机 catalog（未做本机可达性实测，不假装可达） | **中高** | 「显式/隐式标识」二元结构为公开信息；本包只检两类标识与标识表三列，不检字号/位置/时长等量化排版要求 |
| ISO/IEC 42001:2023 | ISO/IEC 42001:2023 人工智能管理体系 | `ISO-42001-STATEMENT` / `ISO-42001-DOC-REGISTER` / `VERSION-TRACE` / `VERSION-CHANGE-TABLE` | 在册（`iec-42001`，含本机探针记录） | **高** | 文档化信息与版本控制要求稳定；本包只检「声明章节 + 文档台账四列 + 修订表递增/ISO 日期」 |
| GB/T 35273-2020 | GB/T 35273-2020《信息安全技术 个人信息安全规范》 | `DATA-SOURCE-TABLE` / `RETENTION-SECTION` / `RETENTION-DURATION` / `RETENTION-CONTACT` / `PRIVACY-SECTION` / `PRIVACY-MINIMIZATION` / `PRIVACY-NO-PLAINTEXT` | 未入本机 catalog（未做本机可达性实测，不假装可达） | **中高** | 告知—同意、保存期限、去标识化为规范正文的固定要项；本包只检「来源/授权/用途表 + 量化保留期 + 联系方式 + 去标识化字样 + 无明文敏感值」 |
| NIST AI RMF 1.0 | NIST AI Risk Management Framework 1.0（2023-01） | `NIST-AIRMF-RISK-SECTION` / `NIST-AIRMF-RISK-LEVELS` / `NIST-AIRMF-RISK-TABLE` / `AUDIT-TRACE-ID` | 在册（`nist-ai-rmf`，含本机探针记录） | **高** | RMF 的 GOVERN/MAP/MEASURE/MANAGE 为框架性要求；本包只检「风险章节 + 四档词表 + 风险登记表 + 链路标识」的机检形，不检风险管理过程完备性 |

**可信度口径**：`高` = 编号/版本/可检要求可由公开发布文本直接核对且本机 catalog 在册；`中高` = 编号与结构为公开信息、但本机未做可达性实测（登记为文档锚）；`中` = 按任务输入登记的版本，细节以正式文本为准。可信度只描述**锚的可靠度**，不描述本包对该标准的符合程度。

## 3. 使用边界

- 锚用于**口径复核**（该细分的通行定义/评测口径从何而来），不表示 NF 复制了外部文本；本包正文自撰。
- **双锚分工**：主锚 = 该细分依据的域口径标准（可能与细分锚不同源，形成第二证据链）；辅锚 = 该细分产出（数据 / 契约 / 图表 / 图示 / 溯源）所承载的开放标准。
- 标准锚取自 `protocol/standards_catalog.json` 的**本机实测记录**（含取样标题与 sha256），可达性 false 如实标注，不假装可达。
- 锚不可达时按不可达记档，不影响本包口径面的机检（判据落在本包 schema 与度量族）。
- 锚版本漂移（规范改版）由维护者按需复核；本表不做自动追踪。
