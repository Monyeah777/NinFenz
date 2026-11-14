# Trust Fabric Claim–Evidence 矩阵（WP-00 起点）

> 状态：v1 · 2026-11-14 · 与 `results/trust/BASELINE.md` 同批复核
> 规则（计划 §13.3）：每条 claim 至少 1 代码锚点 + 1 测试，否则标 `UNSUPPORTED` 并修文档或补证据。
> 状态口径：`SUPPORTED` = 本轮实读代码 + 跑过测试；`PARTIAL` = 原语在但 claim 所述整体未成立；`TODO` = 未实现；`UNSUPPORTED` = 文档声称但无证据（本轮抽检为 0，全量复核待 check48）。
> 等级口径：「等级」列是该 claim 在计划 §7.3 体系里的**上限**（按实现可支撑的强度），**不是本仓已达到的等级**——本仓尚无 policy 判定入口，整体等级要等 `nf trust verify` 给出。

| # | Claim | 代码锚点 | 测试 | 等级 | 状态 |
|---|---|---|---|---|---|
| 1 | 证据包成员字节未被改（逐成员 sha256） | `evidence.py` `_check_members` | `test_evidence.py` | T0 | SUPPORTED |
| 2 | 叶 → RFC 6962 根一致 | `evidence.py` `_check_root`、`receipts.py:38` | `test_evidence.py`、`test_evidence_vectors.py` | T0 | SUPPORTED |
| 3 | 每条 inclusion proof 独立折叠到根 | `evidence.py` `_check_proofs`、`receipts.py:50/80` | `test_evidence.py` | T0 | SUPPORTED |
| 4 | 条目顺序/链头未被改（链必填且重算一致） | `evidence.py` `_check_chain`、`transparency_log.py:44/77` | `test_evidence.py`、`test_transparency_log.py` | T0 | SUPPORTED |
| 5 | 三种证据形态统一判定（`cc_verify` 入口） | `evidence.py:1236 verify_any` | `test_evidence.py` | T0–T1（按信封强度，最弱环） | SUPPORTED |
| 6 | RFC 3161 时间存在性可离线验（token 绑定摘要） | `timestamp.py:129` | `test_timestamp.py` | T2 | SUPPORTED |
| 7 | 密钥集版本化 / 一致性 / 分叉检测 | `key_transparency.py:61/171/210` | `test_key_transparency.py` | T1 | SUPPORTED |
| 8 | 吊销命中（吊销表 / feed） | `revocations.py:68/73` | `test_revocations.py` | T1 | SUPPORTED |
| 9 | 钉根 + 有界委派（换公钥即冒充被挡） | `trust_anchor.py:71/96` | `test_trust_anchor.py` | T1 | SUPPORTED |
| 10 | 会话事件 prev 链 + 重放一致 | `session_journal.py:98/310` | `test_meta_cockpit.py` | T0 | SUPPORTED |
| 11 | 认知记录 prev 链 + 重放 fail-closed | `cognition_workspace/records.py:23/45/67` | `test_cognition_workspace.py` | T0 | SUPPORTED |
| 12 | 预注册评测协议（禁 score / synthetic 不作证据） | `eval_harness.py:21-23` | `test_eval_harness.py` | — | SUPPORTED |
| 13 | 人类复核状态机（未签 = PENDING，不得冒充通过） | `runtime_executor.py:213` | `test_meta_cockpit.py` | — | PARTIAL（状态机在，记录未签名） |
| 14 | 单 claim 可独立验证（claim 级、不读全包、O(log n)） | 计划 `trust/bundle.py:verify_claim`（未建） | — | T1 | TODO（G1） |
| 15 | 删尾并重算本地摘要可被检测（head 签名/TSA） | 计划 `trust/anchor.py`（未建） | — | T2 | TODO（G2） |
| 16 | DSSE/PAE 签名信封（≥1 有效签名、keyid 可解析） | 计划 `trust/dsse.py`（未建） | — | T1 | TODO（G2） |
| 17 | 跨 bundle 拼接被拒（splice 防护） | 计划 `trust/bundle.py`（未建） | — | T1 | TODO（G1） |
| 18 | 未知实体类型/越权组合 fail-closed（typed entity） | 计划 `trust/entity.py`（未建） | — | T1 | TODO（G3） |
| 19 | 模型替换使旧 AI 证据失效（model card 绑定） | 计划 `core/ai_trust/`（未建） | — | — | TODO（G3） |
| 20 | 报告给出等级 + 缺项 + issuer 状态（`nf-verify/1`） | 计划 `trust/verify.py`（未建） | — | — | TODO（G2） |
| 21 | Python ↔ .NET（引擎线）逐字节 parity（trust 面） | 计划；.NET 引擎线未接 | — | — | TODO（G3/G4；本机无 SDK，见 BASELINE §7） |
| 22 | trust 层 7 件 IDL 结构 fail-closed（未知字段/封闭词表/摘要/时间/base64 形状） | `protocol/trust/*.schema.json`（7 件） | `test_trust_schemas.py`（23 条：正/反样例 + 变异自证） | T0 | SUPPORTED |
| 23 | schema 不依赖校验器未实现语义（无静默忽略） | `core.json_schema` 叶子件 + `test_trust_schemas.py` 的 unsupported 断言 | 同上 | — | SUPPORTED |
| 24 | 威胁模型边界自洽：STRIDE 8 行 / 删除矩阵 8 行 / 边界 6 条 / 红队 2×5 均绑定现存控制点与判据；T0/T1 不写成 T3/T4 | `docs/trust/THREAT_MODEL.md` | `test_trust_threat_model_doc_contract.py`（3 条 + 7 项变异自证） | — | SUPPORTED |
| 25 | trust 实现契约被测试向量锚定：提交件==重算、期望值可被独立实现复算、跨语言 JSON 自验 | `scripts/trust_vectors.py` + `results/trust/trust_vectors.json`（34 条 / 7 族） | `test_trust_vectors.py`（6 条 + 9 项变异自证） | — | SUPPORTED |

**本轮判定**：`UNSUPPORTED` = 0（本轮抽检范围内）；`TODO` 11 条全部落在计划 G1–G4 的工作包内，不构成文档过度声明。计划 §13.3 的示例行「删尾可检测 / T2 / TODO」与本矩阵第 15 行同源。

*维护纪律：新增 claim 必须同时补代码锚点与测试，再改状态；不得先写 SUPPORTED 后补测试。*
