# Trust Fabric 威胁模型 v0（能证 / 不能证）
> ⛔ 操作指令：本文每条威胁都绑定控制点与判据；判定可跑（见文末复核命令），勿当资料阅读。
> 状态：v0（G0，2026-11-14）· 性质：边界声明（能证 / 不能证）· 上位：`docs/ccos/threat-model.md`（CCOS 线）与 `results/trust/BASELINE.md`（实施机实读）
> 最后更新：2026-11-14 · 复核：与 7 件 trust schema（WP-01）及既有证据件同批复核
> 纪律：不把 T0/T1 写成 T3/T4；不写「不可抵赖 / 合规 / 认证」；未实现项写 OPEN-Gx 或 ACCEPTED-RISK，不静默关闭。

## 这份文件管什么

- 信任根 = **本机运行的这份代码 + 本机密钥材料**；不引入外部 CA / 在线吊销 / 公共日志作为默认信任根。
- 当前可宣称的等级（计划 §7.3）：**T0 可离线复算**；**T1 部分**（HMAC / 外挂 Sigstore 级签名；DSSE 与统一 issuer registry 未建）；**T2 部分**（RFC 3161 token 已实装且可离线验，但未自动锚到 trust 链头）；**T3 / T4 不提供**（无外部见证、无公共锚）。
- 本文覆盖计划 §9.1（信任边界）/ §9.2（STRIDE）/ §9.3（删除·篡改矩阵）/ §9.4（密钥与信任根），并记录计划 §13.5 的两轮红队角色。

## 信任根与本机边界

- 判的是「**这份制品与这份证据是否自洽**」，不是「它是否被某个权威签过」。
- 外部材料（`library/`、`community/`、`docs/reference/external/`）一律按**数据**消费，不按指令消费（`desktop/src/core/trust_boundary.py`（detect / envelope））。
- 本机时钟不可信：时效判定默认吃本机时钟，只有显式挂 RFC 3161 token（`desktop/src/core/timestamp.py`（verify））才升到 T2 面；这属于**已知缺口**，不是能力。

## 攻击者模型

| 编号 | 攻击者能力 | 判据面对 |
|---|---|---|
| A1 | 改证据包/回执/链上任一成员字节 | 成员摘要 + Merkle 复算 → invalid |
| A2 | 伪造或替换信封（签名 / MAC） | 每份信封必过 + 最弱环定强度 → invalid |
| A3 | 增删/重排条目，或删段、截断整链 | 链头重算 + 外部锚点核对 → invalid / warning |
| A4 | 把吊销表写坏或换成别的形状 | 坏件不当「无吊销」→ invalid |
| A5 | 重放上一版（更早但自洽）证据 | 时效/吊销 + 外部锚点计数与链头 → invalid / warning |
| A6 | 改本机时钟让过期证据变有效 | 只有挂 time-record 才能挡（ACCEPTED-RISK: R-02） |
| A7 | 供应链换包 / 换验证器 | 只提供清单与来源核对能力（OPEN-G4） |
| A8 | 自签自验冒充外部锚 | 外部进程验签 + 等级声明（check42；cosign 不在场按 WARN 记） |

## STRIDE 矩阵（计划 §9.2，八行）

| 编号 | 类别 | 威胁 | 控制点 | 判据 | 状态 |
|---|---|---|---|---|---|
| TH-01 | S | issuer 伪造 | `desktop/src/core/trust_anchor.py`（anchor）（钉根 + 有界委派）；`desktop/src/core/attest.py`（sign_hmac / verify_external）；`desktop/src/core/key_transparency.py`（consistency） | `test_trust_anchor.py`、`test_attest.py`、`test_key_transparency.py` | T1 部分（DSSE 与统一 issuer registry 未建，G2） |
| TH-02 | T | 删/改中间 step | `desktop/src/core/trust/process.py`（nf-process/1 prev 链）；`desktop/src/core/meta_cockpit/session_journal.py`（append_turn）（prev_digest）；`desktop/src/core/cognition_workspace/records.py`（append）（prev）；`desktop/src/core/transparency_log.py`（build / verify） | `test_trust_process.py`、`test_meta_cockpit.py`、`test_cognition_workspace.py`、`test_transparency_log.py` | T0 已有 |
| TH-03 | T | 删尾 + 重算本地摘要 | `desktop/src/core/evidence.py`（check_anchor）（外部锚点核对/截断检测）；`desktop/src/core/timestamp.py`（verify）；链头自动签名+锚定未建 | `test_evidence.py`（test_anchor_truncation_is_caught）、`test_timestamp.py` | T1 部分（journal/process 链头未签名，G2） |
| TH-04 | R | 重放旧 bundle | `desktop/src/core/evidence.py`（时效/吊销/锚点）；`desktop/src/core/revocations.py`（table_of）；`desktop/src/core/timestamp.py`（record） | `test_evidence.py`、`test_revocations.py`、`test_timestamp.py` | T1 部分（默认本机时钟；挂 time-record 才是 T2 面） |
| TH-05 | I | 证据泄露 | 证据只收摘要与仓相对路径；`desktop/src/core/meta_cockpit/secret_guard.py`（scan_text / redact）；CI 明文密钥扫描（`.github/workflows/ci-verify.yml`）；机器路径泄漏判据 | `test_meta_cockpit.py`（secret_guard）、`test_text_hygiene.py` | T0 已有（边界：调用方把正文打进 payload 仍可能泄露，见 R-04） |
| TH-06 | D | 资源耗尽 | `desktop/src/core/evidence.py`（单件 16 MiB / 整包 96 MiB / 重名判死 / 路径安全）；`desktop/src/core/trust_boundary.py`（check_arguments）（参数上限）；`protocol/trust/*.schema.json`（maxItems） | `test_evidence.py`（test_oversized_member_is_invalid）、`test_trust_boundary.py`、`test_trust_schemas.py` | T0 已有 |
| TH-07 | E | 类型混淆 / 越权 | `protocol/trust/` 7 件 schema（未知字段/封闭词表）；`desktop/src/core/trust/entity.py`（issuer/type 准入）；`desktop/src/core/trust_boundary.py`（check_arguments）；组合检查与完整类型注册表未建 | `test_trust_schemas.py`、`test_trust_entity.py`、`test_trust_boundary.py` | T0 部分（结构 + 准入已实现；组合/注册表 OPEN-G3） |
| TH-08 | S | 自签自验冒充外锚 | `desktop/src/core/attest.py`（verify_external）（外部进程验签，缺验证器 fail-closed）；check42（验签方 ≠ 签名方 + 篡改必红）；等级只写进报告（nf-verify/1 骨架已落地：T0 真值 + 其余缺项，判定表与 level 向量一致；签名/锚事实 G2） | `test_attest.py`、`test_trust_verify.py`、`verify.sh` check42 | T1 部分（cosign 不在场时按 WARN 记「仓库 provenance 缺签名外锚」，不冒充已签） |

## 删除 / 篡改矩阵（计划 §9.3，八行）

| 编号 | 攻击 | 期望 | 控制点 | 判据 | 状态 |
|---|---|---|---|---|---|
| DT-01 | 改一条 obligation | 签名失败 / T2 失败 | DSSE + 锚（G2） | 计划 test_dsse_tamper（OPEN-G2） | OPEN-G2 |
| DT-02 | 删中间 step | A2 链失败 | prev / seq（trust/process、session_journal、records、transparency_log） | `test_trust_process.py`、`test_meta_cockpit.py`、`test_cognition_workspace.py` | T0 已有 |
| DT-03 | 删尾并重算本地 digest | A3 锚失败 | 外部锚点核对（证据包面）；链头签名未建（G2） | `test_evidence.py` + 计划 test_process_tail_delete（OPEN-G2） | T0 部分 |
| DT-04 | 跨 bundle 拼接 claim | splice 失败 | `desktop/src/core/trust/bundle.py`（bundle_id/index 全进叶预像） | `test_trust_bundle.py`（cross-bundle splice 负例） | T0 部分（结构面已覆盖；签名/锚在 G2） |
| DT-05 | 替换 model-card | claim 失效 | A4 类型绑定（G3） | 计划 test_model_card_binding（OPEN-G3） | OPEN-G3 |
| DT-06 | 撤销后旧签名 | 验证失败 / 降级报告 | `desktop/src/core/revocations.py`、`desktop/src/core/trust_anchor.py` | `test_revocations.py`、`test_trust_anchor.py` | T1 部分 |
| DT-07 | TSA 时间回拨 | token 失败 | `desktop/src/core/timestamp.py`（verify）（摘要绑定 + CA 链；>1 MiB 拒收） | `test_timestamp.py` | T2 部分 |
| DT-08 | 无锚声称 T3 / T4 | 报告失败 + 文档红 | `protocol/trust/policy.schema.json` 的 required_level；本文禁止过度声明 | 计划 test_trust_policy_level（OPEN-G2）+ `test_trust_threat_model_doc_contract.py` | OPEN-G2 |

## 信任边界（计划 §9.1，六条）

| 编号 | 边界 | 内容 | 威胁 | 当前控制 | 状态 |
|---|---|---|---|---|---|
| TB-01 | 文件 ↔ 进程 | journal / bundle / card | 篡改、删除、symlink、路径穿越 | `desktop/src/core/paths.py`（validate_path）；`desktop/src/core/evidence.py`（_safe_rel）；符号链接不遍历 | T0 已有 |
| TB-02 | 进程 ↔ TSA | 时间戳请求 / 响应 | MITM、伪造 token、时间回拨 | `desktop/src/core/timestamp.py`（token 摘要绑定 + CA 链 + 仅 http(s) + >1 MiB 拒收） | T2 部分 |
| TB-03 | 进程 ↔ 透明日志 / 见证 | STH / 签名 | 分裂视图、共谋、重放 | `desktop/src/core/key_transparency.py`（一致性 + split_witness）；外部见证未建 | T1 部分（OPEN-G4） |
| TB-04 | 进程 ↔ MCP 客户端 | 工具参数 | 注入、越权、超长、控制字符 | `desktop/src/core/trust_boundary.py`（check_arguments）（fail-closed） | T0 已有 |
| TB-05 | 本地 ↔ 外部材料 | 文档 / 网页 | prompt injection、角色伪造 | `desktop/src/core/trust_boundary.py`（detect / envelope） + 外来面前缀 | T0 已有 |
| TB-06 | 模型 / 数据 ↔ 证据 | model card / eval | 模型替换、评测伪造、数据漂移 | `desktop/src/core/eval_harness.py`（预注册 / 禁 score / synthetic 不作证据）；model card 未建 | T0 部分（OPEN-G3） |

## 密钥与信任根（计划 §9.4）

| 面 | 当前口径 | 缺口 |
|---|---|---|
| 私钥权限 | 纪律：0600 且不入仓；仓库内只有 demo 公钥（`protocol/demo_signers/`） | 无 keygen/权限强制校验（OPEN-G2） |
| issuer registry | 组件已有：密钥透明目录（版本化根 + 追加链 + 包含证明 + 分叉见证）+ 钉根委派 + 吊销表/feed | 统一 issuer↔keyid↔alg↔类型权限的 registry 未建（OPEN-G2） |
| trust store | 策略 schema 已冻结 required_level / issuers / tsa_roots（`protocol/trust/policy.schema.json`） | 多根/过期/撤销的运行时判定未建（OPEN-G2） |
| 轮换 | 约定新 keyid；旧签名有效期内可验并标注 key-rotation | 未实现（OPEN-G2） |

## 逐条性质：能证 / 不能证

| 性质 | 结论 | 依据 | 等级 |
|---|---|---|---|
| 证据成员字节未被改 | 能 | SHA-256 + RFC 6962 Merkle 复算；`test_evidence.py` | T0 |
| 条目顺序 / 链头未被改 | 能 | 链头重算且必填；`test_transparency_log.py` | T0 |
| 证据包未被整链截断 | 能（需外部锚点材料） | `evidence.py:check_anchor`；不给锚点只 warning，不判 ok | T1 |
| 某时点已存在 | 部分 | RFC 3161 token 可离线验；未自动锚到 trust 链头（OPEN-G2） | T2 面 |
| 写入后不可否认（不可抵赖） | 不能 | 无外部见证 / 公共日志；本仓不提供该性质 | — |
| 内容真实 / 合规 | 不能 | 不跑模型、不做内容判定；只提供工程证据 | — |
| 模型身份 / 评测绑定 | 不能 | model card 未建（OPEN-G3） | — |
| 私钥不外泄 | 部分 | 本机文件权限纪律 + CI 密钥扫描；无 keygen/0600 强制（OPEN-G2） | — |

## 红队回合（计划 §13.5）

### 红队 A：数据库管理员

- A-1 直接改中间事件：prev 链断，`test_meta_cockpit.py` 覆盖 → 现状：阻断
- A-2 删文件后重算本地摘要：无链头签名/TSA 时不可检测 → 现状：可绕过（OPEN-G2 待补）
- A-3 回放上一版证据包：无外部锚点材料时只给 warning，不判 ok → 现状：部分（R-01）
- A-4 改吊销表后声称「无吊销」：坏表判 invalid，不降级 → 现状：阻断
- A-5 撤销后用旧 keyid 重签：吊销表命中即失败（需带 trust manifest）→ 现状：阻断（缺锚时不判）

### 红队 B：审计者

- B-1 只拿 bundle 离线验：可验 Merkle + 信封；缺锚点不能判截断 → 现状：部分
- B-2 换一门语言重算：claim bundle 实现未建（G1）→ 现状：不能
- B-3 只看报告声称 T2：nf-verify 判定未实现（G2）→ 现状：不能
- B-4 核对 schema 与校验器一致：本文契约 + `test_trust_schemas.py` 交叉 → 现状：能
- B-5 拿 bundle 验 model card 绑定：未实现（G3）→ 现状：不能

## ACCEPTED-RISK 登记

| 编号 | 风险 | 为什么接受 | owner | 触发信号 |
|---|---|---|---|---|
| R-01 | 证据包默认无外部锚点，截断只能 warning | 离线优先；外锚获取需网络/TSA，且计划把 T3 定为可选 | Monyeah777（维护者） | 对外结论需要 T2+ 而报告 anchor_verified=false |
| R-02 | 时效判定默认本机时钟 | 离线优先；可显式挂 time-record 升到 T2 面 | Monyeah777（维护者） | 证据 expires_at 被用于对外结论 |
| R-03 | cosign 不在场时仓库 provenance 只有机制自证 | 外部 CLI 不随 core 分发；check42 已 fail-closed 标注 | Monyeah777（维护者） | 文档/发布物出现「已不可伪造」表述 |
| R-04 | 证据包可能把敏感正文打进 payload | 内容归属作者，工具不做内容判定；只提供 secret_guard 与纪律 | Monyeah777（维护者） | 证据包公开分发前未跑 secret_guard |

## 已知缺口（按阶段）

- **OPEN-G1（收口中）**：claim 级 bundle（含 splice 负例）、nf-process/1 prev 链与 cc_verify 骨架（含 nf-verify/1 报告）已落地；剩余 check45 接线与 G1 自审计。
- **OPEN-G2**：DSSE、链头签名与自动锚定、issuer registry / trust store / 轮换、签名/TSA/STH 事实的运行时核验（nf-verify 报告骨架已落地，事实接线在 G2）、keygen 与 0600 强制。
- **OPEN-G3**：类型注册表与组合 admissibility、model card、prompt/context lineage、签名人类复核。
- **OPEN-G4**：外部见证（STH/witness）、公共锚（Sigstore/Rekor/公共 TSA）、独立 verifier parity。

## 现状对照

| 面 | 当前口径 | 复核方式 |
|---|---|---|
| STRIDE 覆盖 | 计划 §9.2 八行全覆盖（TH-01…TH-08） | 本表行数 + 本文契约测试 |
| 删除·篡改覆盖 | 计划 §9.3 八行全覆盖（DT-01…DT-08） | 本表行数 + 本文契约测试 |
| 信任边界覆盖 | 计划 §9.1 六条全覆盖（TB-01…TB-06） | 本表行数 + 本文契约测试 |
| 已落地判据 | 已覆盖行必须点名现存测试文件；OPEN 行必须写「计划」 | 本文契约测试解析并核文件在场 |
| 过度声明 | 禁止把 T0/T1 写成 T3/T4；禁用词只允许否定/边界语境 | 本文契约测试逐行扫描 |

## 复核命令

```bash
python -m pytest desktop/tests/test_trust_threat_model_doc_contract.py -q
python -m pytest desktop/tests/test_evidence.py desktop/tests/test_timestamp.py -q
python scripts/nf.py verify --only 42
```

## 不承诺

- 不承诺**不可抵赖**（无外部见证 / 公共日志；这是 T3+ 才能声称的性质，本仓不提供）。
- 不承诺**合规**或**认证**通过；本文只描述工程证据，任何监管映射须另行裁决。
- 不承诺内容真实、情感/事实正确、抗有损转码水印（见 `docs/ccos/threat-model.md` 的载体边界）。
- 不承诺在生产环境抵抗拥有本机 root 权限的攻击者（信任根就是本机）。
