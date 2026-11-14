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
| 14 | 单 claim 可独立验证（claim 级、不读全包、O(log n)） | `desktop/src/core/trust/bundle.py` verify_claim | `test_trust_bundle.py`（只读一条 claim + proof 长度 ≤ log n） | T1（结构/哈希面；签名在 G2） | SUPPORTED |
| 15 | 删尾并重算本地摘要可被检测（head 签名/TSA） | `desktop/src/core/trust/anchor.py`（nf-anchor/1：target_digest 绑定 + RFC3161 token 离线验）+ `desktop/src/core/trust/signature.py`（nf-chain-head/1 链头签名，复用 DSSE + issuer registry） | `test_trust_anchor_evidence.py`（17 条）+ `test_trust_signature.py`（14 条，含真签名+真 TSA 端到端 T2） | T2 | SUPPORTED（WP-22/23） |
| 16 | DSSE/PAE 签名信封（≥1 有效签名、keyid 可解析） | `desktop/src/core/trust/dsse.py`（PAE + nf-dsse/1；算法白名单 hmac-sha256 / ed25519 / ecdsa-p256，后两者可插拔回调）+ `desktop/tests/test_trust_dsse.py` | `pae` 族向量逐条一致；信封签/验 + 篡改矩阵（载荷/签名/keyid/算法越界/算法不符） | T1 | SUPPORTED（G2 WP-20；issuer 注册/轮换/吊销接线 = WP-21） |
| 17 | 跨 bundle 拼接被拒（splice 防护） | `desktop/src/core/trust/bundle.py`（叶预像含 bundle_id/index） | `test_trust_bundle.py` cross-bundle splice 负例 | T1 | SUPPORTED |
| 18 | 未知实体类型/越权组合 fail-closed（typed entity） | `protocol/trust/type-registry.schema.json` + `desktop/src/core/trust/entity.py`（typed_admissibility：issuer 注册 kind/显式授权/有效期/refs 数量类别重复自引；composition_check：ref 可解析 + compose_with 类型对 + DAG/深度有界） | `test_trust_types.py`（19 条：注册表语义 + 准入矩阵 + 组合/DAG/深度 + CLI + 规则移除变异自证） | T1 | SUPPORTED（G3 WP-30） |
| 19 | 模型替换使旧 AI 证据失效（model card 绑定） | 计划 `core/ai_trust/`（未建） | — | — | TODO（G3） |
| 20 | 报告给出等级 + 缺项 + 修复指引 + 信任根（`nf-verify/1`） | `desktop/src/core/trust/verify.py` | `test_trust_verify.py`（11 条：level 向量 + 四场景退出码 + schema + CLI） | T0 骨架（签名/锚事实 G2） | SUPPORTED |
| 21 | Python ↔ .NET（引擎线）逐字节 parity（trust 面） | 计划；.NET 引擎线未接 | — | — | TODO（G3/G4；本机无 SDK，见 BASELINE §7） |
| 22 | trust 层 7 件 IDL 结构 fail-closed（未知字段/封闭词表/摘要/时间/base64 形状） | `protocol/trust/*.schema.json`（7 件） | `test_trust_schemas.py`（23 条：正/反样例 + 变异自证） | T0 | SUPPORTED |
| 23 | schema 不依赖校验器未实现语义（无静默忽略） | `core.json_schema` 叶子件 + `test_trust_schemas.py` 的 unsupported 断言 | 同上 | — | SUPPORTED |
| 24 | 威胁模型边界自洽：STRIDE 8 行 / 删除矩阵 8 行 / 边界 6 条 / 红队 2×5 均绑定现存控制点与判据；T0/T1 不写成 T3/T4 | `docs/trust/THREAT_MODEL.md` | `test_trust_threat_model_doc_contract.py`（3 条 + 7 项变异自证） | — | SUPPORTED |
| 25 | trust 实现契约被测试向量锚定：提交件==重算、期望值可被独立实现复算、跨语言 JSON 自验 | `scripts/trust_vectors.py` + `results/trust/trust_vectors.json`（34 条 / 7 族） | `test_trust_vectors.py`（6 条 + 9 项变异自证） | — | SUPPORTED |
| 26 | 六条 trust 裁决可校验：登记投影过 ADR 校验/reconcile、evidence 在场、与 schema/向量/实现双向绑定、决策正文不进公开仓 | `protocol/adr/registry.json`（ADR-005…010） | `test_trust_adr_contract.py`（5 条 + 7 项变异自证） | — | SUPPORTED |
| 27 | canonical 单点：键排序/紧凑分隔/禁 float 与 NaN/拒非法类型；域分隔摘要按 tag+0x00+payload；与既有签名口径逐字节一致 | `desktop/src/core/trust/canonical.py` | `test_trust_canonical.py`（12 条：向量逐条 + 既有实现对照 + 变异自证） | T0 | SUPPORTED |
| 28 | 实体准入 fail-closed：结构 → issuer 在册 → type 被授权，未知一律拒绝且返回稳定 reason 码 | `desktop/src/core/trust/entity.py` | `test_trust_entity.py`（12 条：向量逐条 + 失败面 + 变异自证） | T0 | SUPPORTED |
| 29 | claim bundle 构建/整包验证：RFC 6962 根 + 逐叶 proof + 覆盖/唯一性，且产物过冻结 schema | `desktop/src/core/trust/bundle.py` | `test_trust_bundle.py`（19 条：merkle 向量逐条 + 篡改矩阵） | T0 | SUPPORTED |
| 30 | 流程步骤前向绑定：step 摘要含全部字段 + prev/seq 连续，删/改/重排可检测（本地重算边界如实声明） | `desktop/src/core/trust/process.py` | `test_trust_process.py`（20 条：process 向量逐条 + 篡改矩阵 + 就地重算边界） | T0 | SUPPORTED |

| 31 | issuer↔keyid↔alg 注册表 fail-closed（未知/未来/过期/吊销即拒；retired 仅历史验签且轮换可寻址） | `protocol/trust/keys.schema.json` + `desktop/src/core/trust/keys.py` | `test_trust_keys.py`（18 条：结构/语义矩阵 + 生命周期 + 注册表口径验签 + 轮换 + CLI） | T1 | SUPPORTED（G2 WP-21） |
| 32 | 外部锚可离线验并投影为 T2/T3 事实（rfc3161/STH/witness/git-commit；错目标/错信任根/坏签名必 invalid，缺 verifier 记 none） | `protocol/trust/anchor.schema.json` + `desktop/src/core/trust/anchor.py` | `test_trust_anchor_evidence.py`（17 条：本地 TSA 全链路 + witness 阈值 + STH + 篡改/错根/错摘要 + verify 接线） | T2（TSA）/T3 部分（witness 语句为本仓约定） | SUPPORTED（G2 WP-22） |

| 33 | 链头/卡/事件签名语句绑定（nf-chain-head/1；错 kind/digest 必拒；registry 吊销/过期则 T1 失守） | `protocol/trust/chain-head.schema.json` + `desktop/src/core/trust/signature.py` | `test_trust_signature.py`（14 条：语句绑定 + 生命周期 + 篡改 + 真签名+真 TSA 端到端 T2） | T1 | SUPPORTED（G2 WP-23） |

**本轮判定**：`UNSUPPORTED` = 0（本轮抽检范围内）；`TODO` 2 条（19/21）落在计划 G3–G4 的工作包内；claim #15/#16/#18/#32/#33 均已 SUPPORTED（WP-20/22/23/30），不构成文档过度声明。

*维护纪律：新增 claim 必须同时补代码锚点与测试，再改状态；不得先写 SUPPORTED 后补测试。*
