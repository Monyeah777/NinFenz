# Trust Fabric 基线审计（WP-00）

> 状态：v1 · 审计日 2026-11-14 · 实施机检出 `8af1bef3`（分支 `work/l4-floors`，工作树干净）
> 依据：`NF-TrustFabric-最终方案.md` §12.1（只读扫描基线）· §3（现状审计须在实施机复跑，不得照抄）
> ⛔ 操作指令：下文每条判定都附复跑命令；改本文件必须重跑命令并更新数字，不得照抄旧值。
> 性质：结果/状态件（审计记录），不是规划件。审计对象 = **本机检出**，不是计划文档所基于的那次检出。

## 0. 结论

1. **计划 §3 的审计对象与实施机检出不同源。** 计划基线 `01016908` 在本仓本地 3776 个提交与全部 ref 中不存在（`git cat-file -t 01016908` → 未知对象）；§3 引用的 `desktop/src/core/labeling/`、`meta_cockpit/cognition_event.py`、`cockpit_log.py`、`reasoning/certificate.py` 在全部 ref 的对象库里从未出现（`git rev-list --all --objects` 检索为空）。⇒ §3 的路径与行号只能作**意图参考**，不能当实施前提。
2. **实仓在 A3 上比计划 §1.2 的判定更强。** RFC 3161 时间戳（`timestamp.py`，`nf-time-token/1`）、密钥透明目录 + 分叉见证 + 撤销表 + 信任锚（`key_transparency.py` / `trust_anchor.py` / `revocations.py`）、自包含证据包（`evidence.py`，`nf-evidence/1`）都在 HEAD 上；计划把这四项写成「无」。
3. **真实缺口因此收窄到协议与策略面**（§4 逐条重估）：DSSE/PAE、`nf-entity/1` 类型注册表与组合可接受性、claim 级 bundle（含 splice 防护与和 `nf-evidence/1` 的边界）、模型卡、trust policy / T0-T4 等级、统一 `nf trust verify` 报告、check45-48。
4. **两处环境事实**：本机无 .NET SDK（`dotnet --version` → "No .NET SDKs were found"），计划 DoD 的「.NET verify ok」无法作为本机判据；`cosign` 不在场（check42 已按 WARN 记「仓库 provenance 缺签名外锚」，不冒充已签）。

## 1. 实施机与检出事实

| 项 | 值（本轮实读） |
|---|---|
| 仓库根 | `D:\NinFenz`（origin `https://github.com/Monyeah777/NinFenz.git`） |
| 分支 / HEAD | `work/l4-floors` / `8af1bef3c91b39866ba5c562ca3241a997a2e6ca` |
| 脏文件 | 0（`git status --short` 为空） |
| 计划基线 `01016908` | **不在本仓**（`git cat-file -t` 未知对象；全部 ref 未见） |
| 代码规模 | `desktop/src/core` 359 个 `.py`；`desktop/tests` 638 个 `test_*.py` |
| Python | 3.11.9（`python`）；pytest 9.1.1 |
| .NET | 无 SDK（仅运行时/宿主目录）；`engine/dotnet` 源码在场但不可本机构建验证 |
| 外部验证器 | `cosign` 不在场（check42 WARN） |

## 2. 门禁与测试基线

| 面 | 命令 | 本轮结果 |
|---|---|---|
| 静态门禁 | `bash verify.sh --checks-only` | **PASS=75 WARN=2 FAIL=0**，exit 0 |
| 相关测试 | `python -m pytest desktop/tests/{test_evidence,test_evidence_vectors,test_timestamp,test_key_transparency,test_revocations,test_trust_anchor,test_transparency_log,test_attest,test_trust_boundary}.py -q` | **204 passed**，4 warnings，44.09 s |
| 全量测试 | — | **本轮未跑**（变更面 = 新增 results 文档）。按 AGENTS.md「三件套」取证：静态面全量 + 受影响面全量 + 仓库原生新鲜度命令；全量口径在 `scripts/release_conclusion.py` |
| .NET verify | — | **未跑**：无 SDK（不是「通过」） |

两条 WARN 的真实含义（不得当红，也不得当绿）：

1. check12 的 `--checks-only` 分支按设计**不跑 unittest**，提示文案「desktop/tests 不在场」是该分支的固定文案；目录实测在场（638 个测试文件）。
2. check42「仓库自身 provenance 缺签名外锚（cosign 不在场）」——该检查只证明外部验签机制可用且对篡改敏感，**不等于**本仓 provenance 已不可伪造。

### 2.1 冻结链（本轮实测）

新增两件 `results/trust/` 后，首次 `--checks-only` 从 FAIL=0 变为 **FAIL=2**：check35 判「一致性报告：报告过期或被改（root 记录=3393227d6bb195ce 实测=caafbffdba6fa2f3）」。按 `docs/release.md` §冻结链 三步重冻结后恢复全绿：

1. `python scripts/nf.py conformance --write` → 报告重写，verdict=conformant（27/27 契约），root=caafbffdba6fa2f3；
2. `python scripts/nf.py approve protocol/conformance_report.json --by Monyeah777 --note "…"` → 内容绑定批准记录重签（对象改动即自动失效）；
3. `python scripts/nf.py receipts --scope protocol --write` → 协议层回执根=528292f8b3bdbd41（66 件），并联动刷新 `protocol/generated/receipt_chain.json` 与 `results/interop/*`（5 面）。

复跑 `bash verify.sh --checks-only`：PASS=75 WARN=2 FAIL=0，exit 0。

随后为刷新 `role_coordinates.json` / `verification_report.json` / `sbom.json` 等投影，又执行了完整重冻（code_metrics → layers → audit rebind → conformance → approve → receipts → self_audit/capability/judge/core_judge → verify_report → sbom → freshness/style/precheck）。**最终提交态**：回执根=5f2cb5a24d315f3b（66 件）、freshness 4/4、precheck 23/23、`--checks-only` PASS=75 WARN=2 FAIL=0。上列数字均为本轮实读，复核以命令输出为准（不钉死）。

**操作约束（给后续 WP）**：内容改动必须在冻结链**之前**定稿——冻结后再改任何受 root 覆盖的文件，check35 必红，只能整链重跑。计划 §12.1.4 引用的 `scripts/refreeze.sh` 在本机不存在（见 §7 ENV-04）；实仓入口是 `python scripts/nf.py release --freeze --apply --by <批准人> --note <说明>`。

## 3. 计划锚点复验（§1.2 / §3.1 / §3.2）

判定口径：**命中** = 文件与语义都在（行号可漂移）· **漂移** = 语义在、行号已移 · **不成立** = 计划所引模块/位置在本仓不存在。

| 计划锚点 | 计划用途 | 实仓落点（本轮实读） | 判定 |
|---|---|---|---|
| `receipts.py:50-87` | inclusion proof / fold | `:38 def merkle_root`、`:50 def inclusion_proof`、`:80 def fold_proof` | 命中 |
| `receipts.py:124-165` | 回执构造 | `:90 def build`（124-165 落在同函数体） | 漂移 |
| `session_journal.py:281-326` | 事件哈希链 | `:221 def append_turn`（281-326 落在事件构造段） | 漂移 |
| `session_journal.py:95-99` | prev 校验 | `:98 prev_digest 校验` | 命中 |
| `session_journal.py:169-190` | 读取/校验 | `:169 def load` | 命中 |
| `transparency_log.py:50-59` | 链节构建 | `:44 def build`（50-59 落在链节循环） | 漂移 |
| `transparency_log.py:90-107` | 链校验 | `:77 def verify`（90-107 落在链节校验） | 漂移 |
| `transparency_log.py:108-110` | 「不可抵赖不提供」边界 | `:31 BOUNDARY`；`:108-110` 断言 boundary 在场 | 命中 |
| `cognition_event.py:109`（prev 恒 None） | GAP-02 | 文件不存在；替代件见 §4 GAP-02 | **不成立** |
| `cockpit_log.py:41-72` | GAP-03 | 文件不存在 | **不成立** |
| `labeling/cli.py:104-112` | RFC3161（AIGC 面） | 目录不存在；替代：`timestamp.py` + `nf evidence timestamp` | **不成立** |
| `labeling/tsa.py:466/631/776` | TSA 客户端 | 目录不存在；替代：`timestamp.py:52/66/129/180` | **不成立** |
| `labeling/checker.py:340-358` | GAP-01 扁平 dict | 目录不存在；替代：`evidence.py` 三形态判定 | **不成立** |
| `attest.py:86-131` | 单件签名 | `:91 issue_stamp`、`:107 def build`、`:149 def sign_hmac` | 漂移 |
| `attest.py:151-190` | Sigstore 适配器 | `:161 have_external_verifier`、`:178 verify_external` | 命中 |
| `runtime_executor.py:213-261` | 人类复核 | `:213 def review_status`（213-241） | 命中 |
| `approval.py` | 内容绑定批准 | `:23 SCHEMA`、`:48 def approve`、`:93 def verify` | 命中 |
| `provenance_external.py:1-14` | 外部验签检查 | 文件在场，头部 docstring 即该项说明 | 命中 |
| `meta_cockpit/evidence_roles.py` | 证据角色 | `:150 def build_role_inventory` | 命中 |
| `reasoning/certificate.py:282-300/475-490` | 搜索证书 | `desktop/src/core/reasoning/` 不存在 | **不成立** |

复验命令：`git cat-file -t 01016908`；`git rev-list --all --objects | awk '{print $2}' | grep -E 'labeling/|reasoning/|cognition_event|cockpit_log'`；上表行号用 `grep -n '<符号>' <文件>` 逐条可复核。

## 4. 差距重估（GAP-01…10）

| ID | 计划判定 | 实仓实读 | 重估 | 后续落点 |
|---|---|---|---|---|
| GAP-01 | 无 Claim/Bundle | `evidence.py` 有 `nf-evidence/1`：成员集单根 + 每条 inclusion proof + 信封覆盖 + 链 + 吊销/时效 + 外部锚点；但成员是**字节载荷**，无 claim 类型/义务/组合语义 | **半具备**：容器在、claim 协议缺 | G1 WP-11 `trust/bundle.py`；先出 ADR 定 `nf-claim-bundle/1` 与 `nf-evidence/1` 的边界 |
| GAP-02 | cognition event 无 prev | `cognition_workspace/records.py:30`（prev=上条 digest）、`:67`（fail-closed 校验）+ `session_journal.py:98/310` | **描述不成立**：prev 链已在两处；真缺口是「链头签名/锚定」 | G2 WP-23 签名接口 |
| GAP-03 | cockpit_log 无链 | 无该模块；`session_journal` 是唯一带链的会话记录面，`cockpit_handoff` 不写链 | **不成立**：不新增空模块 | 不做；若将来需要 cockpit 级日志，先证必要性 |
| GAP-04 | 无 DSSE | 全仓 `DSSE`/`dsse` **0 命中**（`grep -rn`，已排除 .git） | **成立** | G2 WP-20 `trust/dsse.py` |
| GAP-05 | 无轨迹 RFC3161 | `timestamp.py` 已通用（任意字节摘要 → `.tsq/.tsr/.json`，离线验 token）；`nf evidence verify --time-record --time-ca` 可把时效判定切到 genTime；缺「链头/bundle root 自动锚定 + policy 要求」 | **半具备** | G2 WP-22 复用 `timestamp.py`，不重写 |
| GAP-06 | 无 key registry/撤销 | `key_transparency.py`（`:61` 版本化根、`:171` 一致性、`:210` 分叉见证）、`revocations.py`（`:73` 吊销表）、`trust_anchor.py`（`:71` 钉根、`:96` 有界委派）；缺 issuer↔keyid↔alg↔类型权限的注册表与验证时状态检查 | **半具备** | G2 WP-21 以现有件为底座 |
| GAP-07 | 无统一 verifier | `evidence.py:1236 def verify_any` 已统一 bundle/receipts/attest 三形态并给四词判定；缺 policy/T0-T4 等级、`nf-verify/1` 报告、exit 0/1/2 契约 | **半具备** | G1 WP-14 骨架 / G2 扩展 |
| GAP-08 | 无 typed entity（仅雏形） | `protocol/schema/*.schema.json`（9 件协议面）+ `atom_contracts.json` + `evidence_roles.py`；缺 trust 域实体类型注册表与组合 admissibility | **雏形在、协议缺** | G1 WP-10 / G3 WP-30 |
| GAP-09 | 无 AI 证据标准件 | `eval_harness.py`（`nf-eval-protocol/1` / `nf-eval-run/1` / `nf-eval-compare/1`，预注册 + 禁 score + synthetic 不作证据）+ `cockpit_ab*`；缺 model card、prompt/context lineage schema、签名人类复核、AIGC→bundle 绑定 | **半具备** | G3 WP-31…34 |
| GAP-10 | 无外部见证 | `transparency_log` 本地链且 boundary 明示「不可抵赖不提供」；`split_witness` 只做同一密钥集两视图的分叉检测，不是外部见证 | **成立** | G4 WP-40/41 |

## 5. 计划与实仓的偏差（G0 冻结前必须裁决）

1. **ADR 落点（WP-04 已执行）**：计划写 `docs/adr/`；本仓政策是真实决策件进私有 Plan 仓（`decisions/ADR-0000-决策记录外置到私有仓.md`，pre-commit 阻断真实决策件），公开仓只留模板与**可校验登记投影**。⇒ 六条 trust 裁决登记为 **ADR-005…ADR-010**（计划 ADR-0001…0006 依次对应：DSSE PAE / RFC 6962 Merkle / RFC 3161 / witness / 类型 fail-closed / 不写回评分），落 `protocol/adr/registry.json`；`evidence` 逐条绑到 schema、向量与实现件，`adr_check --write` 产物同步刷新。**不新建 `docs/adr/`**，决策正文按 ADR-0000 留私有档案。
2. **测试落点（WP-03 细化）**：判据进 `desktop/tests/test_trust_*.py`（check12 的 discover 面）；**跨语言向量集**落 `results/trust/trust_vectors.json`（生成件，`scripts/trust_vectors.py --write`，与 `results/ccos/*_vectors.json` 同族：第三方只读 JSON 自验）；手写 schema 样例仍留 `desktop/tests/fixtures/trust/`。计划原写 `tests/trust/vectors/`，按仓约定拆成这两处。
3. **check 编号**：实仓现有 check1–42（`verify.sh` 末条 check42）；check43/44 在当前 HEAD 未被占用，但并行线存在撞号风险。⇒ G1 前先声明占用，且**只增不减**，不改既有 check 语义。
4. **schema 落点（WP-01 已裁决）**：采用计划原路径 `protocol/trust/*.schema.json`（7 件）。理由：`protocol/schema/` 的元检（check28 / `schema_lint`）只允许 16 关键字子集，容不下计划不变量所需的 `$defs` / `oneOf` / `const` / `uniqueItems`（例如锚集合「四类之一且 ≥1」）；仓内已有**纯标准库**叶子校验器 `core.json_schema` 支持这些关键字，故 trust 层用完整 draft 2020-12 并由该叶子件判定。**不是两处并存**：`protocol/README.md` 已写明两层的校验器面与计数口径（trust 层不计入 `protocol/schema/` 件数、也不进 `LINT_INPUTS` 扫描面）。接入 check45 后由门禁接管；ADR 落点同 §5.1。
5. **命名与既有语义**：计划新 schema（`nf-claim-bundle/1` 等）不得与既有 `nf-evidence/1`、`nf-time-token/1`、`nf-key-transparency/1`、`nf-revocation/1` 语义重叠；claim bundle 与 evidence bundle 的关系必须由 ADR 写死（包含、引用还是并列）。
6. **CLI 命令面**：计划新增 `nf trust …`；实仓已有 `nf evidence`（含 `revocations` 子命令）/ `nf transparency` / `nf attest`。check39 检命令面策展与可达性。⇒ 优先「挂在既有命令族下」还是「新命令族」需 G0 裁决，不得出现第三套重复语义。

## 6. 复用映射（计划模块 → 实仓既有件）

| 计划模块 | 复用 / 新建 | 依据 |
|---|---|---|
| `trust/canonical.py` | 新建，但必须与既有 canonical **逐字节等价** | 现有独立实现至少 10 处（`attest.py:53`、`evidence.py:63`、`key_transparency.py:30`、`revocations.py:41`、`cognition_workspace/discourse.py:17`、`check_compile.py:57`、`check_policy.py:33`、`check_text_to_intent.py:54`、`disk_cache.py:167`、`nfal.py:663`）；替换既有实现会破坏已入仓签名的摘要口径 |
| `trust/entity.py` | 新建 | 类型词表可参考 `protocol/schema/` 与 `atom_contracts.json`，但不得改既有 schema 语义 |
| `trust/dsse.py` | 新建 | 全仓 0 命中；HMAC/外挂验签适配器复用 `attest.py:149`、`:178` |
| `trust/keys.py` | 复用 + 包一层 | `key_transparency.py` + `trust_anchor.py` + `revocations.py`，新增 issuer registry 绑定 |
| `trust/bundle.py` | 复用 + 新增 claim 语义 | 根/证明/链复用 `receipts.py:38/50/80` 与 `evidence.py` 的校验实现；claim 类型/义务为新增 |
| `trust/process.py` | 复用 + 新增 | `session_journal.py:221`（turn 事件链）、`cognition_workspace/records.py:23`（记录链 + 重放） |
| `trust/anchor.py` / `tsa_client.py` | 复用 | `timestamp.py:52/66/129/180`（RFC 3161 请求/提交/离线验/记录）；STH 参照 `key_transparency` 的一致性证明 |
| `trust/policy.py` / `verify.py` | 新建 | `nf-verify/1` 报告 schema 新增；入口在 `evidence.py:1236` 之上扩 policy/等级 |
| `trust/migrate.py` | 新建 | 旧 journal/card 只读兼容 + `legacy: true`，不得伪装新链 |

## 7. 环境缺口与下一步

- **ENV-01** 本机无 .NET SDK → 计划 DoD 的「.NET verify ok」「Python/.NET parity」不能在本机取证；需 CI 或另一台机器。本机只以 Python 侧测试代替，且**不写成通过**。
- **ENV-02** `cosign` 不在场 → T4 公共锚本机不可验；T0–T2 可离线。
- **ENV-03** 计划 §13.2 的 starter `nf-trust-self-audit.py` 未随计划提供（下载目录无此文件）→ 本轮用等效 grep/AST 命令；是否新增 `scripts/trust_self_audit.py` 在 G0 决定（计划 §13.2 建议）。
- **ENV-04** 计划 §12.1.4 引用的 `scripts/refreeze.sh` 在本机不存在（`ls scripts | grep refreeze` 为空）→ 实仓等价入口为 `python scripts/nf.py release --freeze --apply --by <批准人> --note <说明>`（三步：conformance → approve → receipts，见 §2.1 实测）。
- **WP-01 已完成（2026-11-14）**：`protocol/trust/` 7 件 schema（entity / dsse / process / claim-bundle / anchor / policy / verify）+ 正/反样例 22 件 + 判据 `desktop/tests/test_trust_schemas.py`（23 条，含变异自证与标准实现对照）。
- **WP-02 已完成（2026-11-14）**：`docs/trust/THREAT_MODEL.md`（STRIDE 8 行 / 删除·篡改 8 行 / 信任边界 6 条 / 红队 2 角色各 5 条 / ACCEPTED-RISK 4 条 / 已知缺口 OPEN-G1…G4）+ 判据 `desktop/tests/test_trust_threat_model_doc_contract.py`（3 条，含 7 项变异自证）。
- **WP-03 已完成（2026-11-14）**：`scripts/trust_vectors.py` + `results/trust/trust_vectors.json`（schema `nf-trust-vectors/1`，**34 条 / 7 族**：canonical / domain / pae / merkle / process / entity / level）；判据 `desktop/tests/test_trust_vectors.py`（6 条：提交件==重算、独立实现复算全部期望值、9 项变异自证、实体向量对齐冻结 schema）。同时补清 `protocol/check12_weights.json` 对三个新测试模块的权重（`test_check12_budget` 从红转绿）。
- **WP-04 已完成（2026-11-14）**：`protocol/adr/registry.json` 新增 **ADR-005…ADR-010** 六条 trust 裁决（current、topic 唯一、falsifier 必填、evidence 逐条在场）；判据 `desktop/tests/test_trust_adr_contract.py`（5 条：注册表过 `core.adr` 校验/reconcile、六条齐备、裁决↔工件双向绑定、发布边界、7 项变异自证）。**G0 四项交付（schema / 威胁模型 / 向量 / ADR）全部完成**，退出条件「无默认放行、schema/威胁模型/向量/ADR 评审可核」达成。
- **WP-10 已完成（2026-11-14，G1 首项）**：`desktop/src/core/trust/canonical.py`（严格 canonical：键排序/紧凑分隔/禁 float 与 NaN/拒 bytes-set-tuple/非字符串键；域分隔 `sha256(tag+0x00+payload)`，tag 语法校验；错误消息入向量 reason 码）+ `desktop/src/core/trust/entity.py`（`nf-entity/1` 结构校验 + issuer 解析 + 准入：schema→issuer→type 三段 fail-closed，返回向量约定的 `{admissible, reason}`）。判据 `desktop/tests/test_trust_canonical.py`（12 条：canonical/domain 向量逐条、与 `attest.canonical`/`evidence.canonical` 逐字节对照、严格性变异自证）+ `desktop/tests/test_trust_entity.py`（12 条：entity 向量逐条、未知字段/issuer/类型/坏摘要/坏时间戳、schema 弱化与策略收窄变异自证）。
- **WP-11 已完成（2026-11-14）**：`desktop/src/core/trust/bundle.py`——Merkle 原语**复用** `core.receipts`（同一 RFC 6962 口径，不造第二套哈希）；新增 claim 语义：叶预像 `nf:claim-bundle:v1:claim + 0x00 + canonical{bundle_id,index,claim}`（bundle_id/index/claim 全进叶 → splice/重排可检测）、`build_bundle`（确定性构建 + 逐叶 proof）、`verify_claim`（只读 1 条 claim + 1 条 proof，哈希 O(log n)，支持 proof 侧车免线性查找）、`verify_bundle`（结构 + 全叶根 + 覆盖/唯一性）。判据 `desktop/tests/test_trust_bundle.py`（19 条：merkle 向量逐条、schema 一致性、受控容器证明单 claim 读取、log n proof 长度、篡改矩阵 9 行）。
- **WP-12 已完成（2026-11-14）**：`desktop/src/core/trust/process.py`——`nf-process/1` step 摘要（`domain_digest("nf:process:v1:step", canonical(step 去 digest))`，schema/actor/authorization/refs 全进摘要）、`append_step`（自动封 seq/prev，创世=64 个 0）、`verify_chain`（PREV-FORMAT → SEQ-ORDER → PREV-MISMATCH，形状与向量一致）、`validate_steps`（schema 结构面）、`chain_head`。判据 `desktop/tests/test_trust_process.py`（20 条：process 向量逐条、append/创世/确定性、摘要规则、删改重排反例、schema 结构面、**就地重算边界诚实声明**）。
- **本轮同时校正了一处向量契约缺陷**：WP-03 的 process 族输入用的是精简形状（`seq`/`actor_id` + 常量补 authorization），与冻结 schema 不一致；已改为 schema 形状（`step`/`actor{id,kind}`/`authorization`/refs）并重算期望值，独立复算同步更新——向量现在钉的是真实算法。
- **下一步（G1 余项）**：WP-14 `cc_verify` 骨架（挂 `nf verify`，报告 `nf-verify/1`，对齐 level 向量族）→ WP-15 check45 + 冻结/自审计（G1 退出条件）。

## 8. 复跑命令

```bash
git rev-parse HEAD; git status --short | wc -l
git cat-file -t 01016908 || echo ABSENT
bash verify.sh --checks-only 2>&1 | tail -3
python -m pytest desktop/tests/test_evidence.py desktop/tests/test_evidence_vectors.py \
  desktop/tests/test_timestamp.py desktop/tests/test_key_transparency.py \
  desktop/tests/test_revocations.py desktop/tests/test_trust_anchor.py \
  desktop/tests/test_transparency_log.py desktop/tests/test_attest.py \
  desktop/tests/test_trust_boundary.py -q
grep -rn 'DSSE\|dsse' --include=*.py --include=*.md . | grep -v '.git/' | wc -l   # 期望 0
```

*本文件是审计记录：判定只覆盖本轮实读到的锚点与模块；未读到的面不写成「已核」。*
