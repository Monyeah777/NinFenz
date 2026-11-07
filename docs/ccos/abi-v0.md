# CCOS ABI v0：7 个系统调用
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-06
> **Status**: Draft v0 · **性质**: 正式协议（形状固定；实装状态逐调用如实标注，未实装不许当已实装读）
> **上位**: `STRATEGY.md`（方向与禁令）→ 本文件（ABI 层）。

## 是什么

CCOS（Content Contract Operating System）= 内容契约运行时。本文件把它的**对外表面**压成
7 个系统调用：每个调用给出签名、输入/输出形状、错误码、幂等语义、判定规则与**当下实装状态**。

ABI 只固定「调用长什么样、判什么、错了说什么」，**不**定义内容域、**不**新增真源：
所有调用都必须能落到仓库内**已存在**的产物或命令上（`maps_to`），落不到就标 `unimplemented`。

**威胁模型**（能证明什么、不能证明什么、有哪些已知缺口）：见 [threat-model.md](threat-model.md)。

**非目标**（与 `docs/layers.md` 的四阶边界一致：契约/资产/引擎/出口）：不是计算内核（不跑模型/不做推理调度）、
不是云（不做多租户/SaaS）、不是 DRM、不是检测模型；不承诺载体物理绑定（PNG iTXt / JPEG APP15 只写可见文本段，无水印/无抗转码）、不承诺
CA/TSA 等外部权威、不承诺 K1–K8 内核语义、不承诺联邦/多节点、不用外部盲评作质量判据。
本 ABI 不承诺任何不可计算的性质；逐条触发条件见文末「本季非目标与触发条件」。

## 通用约定

### 编码与规范化

- 载荷一律 UTF-8 JSON；**规范化编码** = `json.dumps(obj, sort_keys=True, ensure_ascii=False,
  separators=(",", ":"))` 的 UTF-8 字节（真源 `desktop/src/core/attest.py::canonical`）。
  任何摘要都只对规范化字节求，不对「文本长得像」求。
- 摘要算法只有 SHA-256（无协商面）；域分隔前缀照 RFC 6962 思路，禁止跨类型复用：
  - 回执/证据叶：`sha256(0x00 || payload)`（`desktop/src/core/receipts.py::leaf_hash`）
  - 内部节点：`sha256(0x01 || left || right)`（同文件 `node_hash`）
  - 透明日志链节：`H(0x01"nf-node:" | prev | leaf)`（`desktop/src/core/transparency_log.py`）
- 时间一律 UTC 秒级 `YYYY-MM-DDTHH:MM:SSZ`；可复现场景用 `SOURCE_DATE_EPOCH` 钉死
  （`attest.issue_stamp`，已实测）。

### 响应信封（所有调用同形）

成功：

```json
{"ok": true, "result": { }, "warnings": []}
```

失败：

```json
{"ok": false, "error": {"code": "cc.<family>.<reason>", "message": "人读一句话",
                        "fix": "修复指引：可执行的动作"}}
```

`error.fix` **必填且以「修复指引：」开头**——这是 check27 对 core 层 raise 文案的同源判据
（缺指引会连锁红 check27/33/35）。错误码登记位 = `protocol/error_codes.json` 的 `codes[]`
（本 ABI 错误面已登记，词法见 `desktop/src/core/error_codes.py`）；ABI 侧码形态固定为 `cc.<syscall>.<reason>`，新增码先登记再抛出。

### 退出码（CLI 面，与 JSON 面等价）

| 码 | 含义 | CI 语义 |
|---|---|---|
| 0 | `ok` | 通过 |
| 1 | `invalid`（任何不可信：摘要不符/签名不符/结构错） | 失败 |
| 2 | `revoked` | 失败（且是吊销，不是「证据弱」） |
| 3 | `expired` | 失败（时效已过，需重签） |
| 4 | 输入不可读/不是证据包 | 用法失败，不是判定 |

判定面**只出这 4 个词**（`ok` / `revoked` / `expired` / `invalid`），不新增形容词。

### 幂等（RFC 9110 §9.2.2 口径，与 `protocol/endpoint_contract.json` 同源）

- 7 个调用**默认 idempotent**：同输入重放 = 同输出、无副作用。
- 例外只在两处，且必须在契约里登记（`mode`/`key`/`why`）：签发类调用若落盘（写 envelope
  文件）由调用方给幂等键；`cc_attest` 的 `issued_at` 走 `SOURCE_DATE_EPOCH` 时**逐字节可复现**，
  不给就是墙钟（此时不承诺字节一致，只承诺语义一致）。
- `cc_verify` `cc_check` `cc_diff` `cc_replay` `cc_resolve` 必须是**纯读**：不写盘、不改仓库
  （只读是「第三方复验」成立的前提）。

## 7 个调用

### 1. `cc_label(obj, contract)` → `label`

**状态：`partial`（声明层 + sidecar 回退 + PNG iTXt / JPEG APP15 载体已实装）**。`maps_to`：
`nf label ir|validate`（形状 = `nf-label/1`）、`nf label write|read|list`
（sidecar 回退 = `nf-label-sidecar/1`，与对象摘要绑定）、`nf label embed|extract`
（**PNG iTXt / JPEG APP15 载体**），见 [label-ir-v0.md](label-ir-v0.md)。载体面只承诺「能读回 /
不改内容面 / 结构合法 + 对象绑定」：**没有**水印、没有其它格式；非 PNG/JPEG 仍走 sidecar 且
`embedded=false`。把可见文本
载体读成「抗转码的标识」是误读。

- 输入：`{obj: <字节或路径>, contract: <契约 id>}`
- 输出：`{label: {contract, standard, fields, carrier, embedded: bool}}`
- 判定：`embedded=false`（回退 sidecar）必须在结果里如实标注，**不得**静默声称已写入载体。
- 错误码：`cc.label.no_contract` / `cc.label.unsupported_carrier` / `cc.label.embed_failed`
- 幂等：idempotent（同 obj + 同 contract → 同 label 字节）。

### 2. `cc_check(obj, policy)` → `verdict`

**状态：`implemented`（v0：封闭词表的单对象策略体检 + 结构化意图编译器）**。maps_to =
`nf check <对象> --policy <策略>`（判定面）与 `nf check --compile <意图.json>`（编译面）；
仓库级判定仍走 `nf conformance`。策略形状与词表见 `docs/ccos/check-policy-v0.md`：
`nf-check-policy/1`，kind 是**封闭集**（utf8 / regex_present / regex_absent /
count_at_least / digest_pin）——不自造 DSL，新增规则 = 加一条数据。

- 输入：`{obj: <单个文件>, policy: <nf-check-policy/1 JSON>}`
- 输出：`{verdict: "ok"|"invalid", policy_id, policy_digest, object{path,sha256,bytes},
  findings: [{rule, kind, severity, ok, detail, fix}], failed, warned}`
- 判定：verdict 只有两个词；`warn` 级违规只进 findings、**不改判定**；坏策略一律带指引拒绝。
- `policy_digest` 必填——**判据版本必须随结论一起走**，否则结论不可复算。
- 幂等：idempotent + 纯读。
- **编译面（`nf-check-intent/1`）**：结构化意图（`explicit_notice` / `forbidden_tokens` /
  `min_bytes` / `require_metadata` / `digest_pinned` / `utf8`）→ 上述封闭词表策略；表达不了的
  意图（模型判内容 / 载体水印 / 视觉要素 / 可信时间 / 身份签发）逐条进 `unsupported` 并写清缺什么。
  **法规原文 → 意图**仍需人写——这是编译器 v0 的边界，不假装有语义层。

### 3. `cc_attest(subject)` → `evidence`

**状态：`implemented`**。maps_to = `nf attest`（三级信任 `digest_only` / `hmac-sha256` /
`sigstore-keyless`，真源 `desktop/src/core/attest.py`，schema `nf-attest/1`）。

- 输入：`{subject: <路径>, issuer?: str, key?: bytes}`
- 输出：envelope `{schema, subject:{path,sha256,bytes,line_count}, producer:{tool,issuer},
  issued_at, envelope_digest, signature?}`
- 关键不变式：`envelope_digest = sha256(canonical({schema,subject,producer,issued_at}))`
  ——签名绑定**信封摘要**，不绑定文件字节，故改签名块不影响摘要、改主体必破摘要。
- 错误码：`cc.attest.no_subject` / `cc.attest.empty_key` / `cc.attest.verifier_missing`
- 幂等：见 §幂等（`SOURCE_DATE_EPOCH` 下逐字节可复现）。

### 4. `cc_verify(evidence)` → `ok | revoked | expired | invalid`

**状态：`implemented`**（三种输入形态 + 38 条攻击矩阵基准；decision 证据绑定 v0 已实装）。
maps_to = `nf evidence verify <target>` / `nf evidence batch <dir>` / `nf evidence bench`；
**两个独立实现**（同一份 18 条向量集必须同判）：零依赖 Python = `scripts/nf_verify.py --evidence`
（纯标准库、不 import 任何 NF 模块、单文件可分发）；**Go 客户端** = `clients/go`
（`nfverify --bundle 包.zip`，`go test ./...` 跑同一份向量集）——用来证明**这个 ABI 不绑定语言**。
本调用是**中立裁判位的地基**：验证方只需要证据本身，**不需要仓库、不需要联网、
不需要复现生产环境**。

- 输入：**三种形态，同一套判定**（形态由文档 `schema` 判，不看扩展名）：
  `bundle`（`nf-evidence/1` 自包含包）/ `receipts`（`nf-receipts/1` 单根 + 包含证明）/
  `attest`（`nf-attest/1`、`nf-attest-set/1` 信封）。容器形态见
  `docs/ccos/evidence-bundle-v0.md`。
- 输出：`{verdict, kind, level, root, head?, count, issues: [], revoked_by?: {...},
  decision?: {...}, decision_status?: absent|declared|bound,
  time_proof: none|pinned, time_basis}

  `time_proof` 是 **G3 诚实面**：本仓没有可信时间源，只能标「这个判定用的时点是本机时钟还是
  调用方给定」，不能标「该时点为真」；包带 `expires_at` 且未给 `--at` 时必给 warning。`
- 判定顺序（**fail-closed**，先失败先返回；不允许「证据弱就放行」）：

  | 序 | 检查 | 不过 → |
  |---|---|---|
  | 1 | 形态/结构/版本（schema 与形态一致） | `invalid` |
  | 2 | 每个成员实体的 sha256 == 记录 | `invalid` |
  | 3 | 叶 → RFC 6962 根 == 记录 root | `invalid` |
  | 4 | 每条 inclusion proof 折叠到同一 root | `invalid` |
  | 5 | 透明日志链必填：head 非空、count 相符、head 重算一致 | `invalid` |
  | 5b | 给了外部锚点（`--anchor`）时：包不得被截断、该位置链头相符 | `invalid` |
  | 6 | 成员集外**不得**多出未登记成员 | `invalid` |
  | 7 | 清单内**每一份**信封都必须通过 + 每个成员都被覆盖 | `invalid` |
  | 8 | hmac 级：密钥在场且 mac 匹配（缺密钥不降级） | `invalid` |
  | 8b | decision（若声明）：形状合法、object 在成员里、与主体摘要相符的信封内同一块、且清单与信封两侧都有 | `invalid` |
  | 9 | 吊销表命中 | **`revoked`** |
  | 10 | 时效（`expires_at` / `--at`）已过 | **`expired`** |

- **期望策略比对（r2）**：`--policy-digest <64hex>` 与包内 `decision.policy_digest` 比对——
  不符即 `invalid`；包内无 decision 时只 warning（`policy_verified=false`），不判死。
- **decision 证据绑定（v0）**：包可带可选 `decision{syscall, policy_digest, verdict,
  object_sha256}`，声明面在 `bundle.json`、绑定面在 `object_sha256` 相符的那份信封里（进信封摘要）。
  只能证「与一次 cc_check 判定自洽且被签发面覆盖」（`decision_status=bound`）；**不证明策略内容正确**——
  正确性需要验方用自己信任的 policy 重算 `policy_digest` 后比对。digest_only 级只算 `declared`。
  包无 decision 时为 `absent`（旧包不因此变红）。
- `level` 如实回填证据强度（`digest_only`/`receipts_only`/`hmac-sha256`/`ssh-sig`/
  `sigstore-keyless`），**不**把 `digest_only` 说成可信签发、不把「一份信封过了」说成整体可信。
- **吊销表分发（G2）**：`--revocations` 吃普通 `nf-revocation/1` 表或签名 `nf-revocation-feed/1`
  （传 feed 时取 table 并读其有效期）；表可由**签名 feed** 合并产出
  （`nf evidence revocations sign|verify|merge`）——合并时验签名、验序号连续性、验前序摘要，
  任何一份不过则整次失败。缺密钥即不可信（不降级），见 [revocation-feed-v0.md](revocation-feed-v0.md)。
- **吊销新鲜度（可选）**：`--require-fresh-revocations` 时吊销表 stale/unknown 判 `invalid`；
  **缺省只 WARN、不改四词判定**（`revocations_fresh` 如实回填；完全没有吊销来源时不判死）。
- **外部锚点（G1 的反截断面）**：打包可用 `--anchor {count, head}` 声明继承的上一条链；复验可用
  `--anchor` 给同一份材料核对「不是被截断的更早版本」。不给材料时**不判死也不抬高**：只在
  `warnings` 里写「无法证明未被截断」，且 `anchor_verified` 为 false。锚点本身的可信来源
  （谁发布、怎么拿到）不在本 ABI 内。
- 机制判据：`nf evidence verify --selfcheck`（四词判定各自可达）+ `nf evidence bench`
  （38 条已知攻击逐条比对，任一条不达期望即 exit 1）。
- 错误码：`cc.verify.not_a_bundle` / `cc.verify.digest_mismatch` / `cc.verify.root_mismatch` /
  `cc.verify.proof_mismatch` / `cc.verify.no_attestation` / `cc.verify.key_required` /
  `cc.verify.revoked` / `cc.verify.expired`
- 幂等：idempotent + **纯读**（严禁因验证而写入任何文件）。

### 5. `cc_replay(evidence)` → `trace`

**状态：`implemented`**。maps_to = `nf evidence replay <target>`——把每一成员的
「字节 → sha256 → RFC 6962 叶 → 每条证明折叠」逐算成步骤，另给链节与信封摘要。
产出「这条证据是怎么算出来的」的可重放轨迹，**不是**重新执行生产。
- 输入：三种形态（同 cc_verify），`entry` 可只看单个成员
- 输出：`{schema: nf-replay/1, kind, entries: [{path, digest, leaf, steps: [{step, rule,
  subject, input, output}]}], recomputed_root, recomputed_head, ok, issues}`
- 稳定性：trace **不含时间戳**，同输入两次 replay 逐字节一致（可 diff、可归档比对）；
  `ok` = 每一步都复算得出且与记录一致（篡改必然在叶/折叠那一步断掉）
- 幂等：idempotent + 纯读。

### 6. `cc_diff(a, b)` → `delta`

**状态：`implemented`**。maps_to = `nf diff <a> <b> --json`（字段级差异 + 兼容判定；
`--history N` 可从 Git 重建契约演进）。`delta` 必须**稳定排序**且自带两侧摘要。
- 输入：`{a: <签名件>, b: <签名件>}`
- 输出：`{delta: [{field, before, after, compat}], digest_a, digest_b}`
- 幂等：idempotent + 纯读。

### 7. `cc_resolve(obj)` → `contract set`

**状态：`implemented`（v0：契约声明面反查）**。maps_to = `nf resolve <对象>`——
方向与既有 `asset_contract.resolve`（声明 → 文件清单）**相反**：那个回答「这份契约管哪些
文件」，这个回答「这个文件该守哪些契约」。
- 输入：`{obj: <仓库相对路径>}`
- 输出：`{schema: nf-contract-resolve/1, object, contracts: [{face, id, files, digest}],
  closure_closed: bool, unclaimed: bool}`
- `closure_closed=false` **必须显式出现**：契约声明是 opt-in，未被认领时给 false 而不是
  空数组——空数组读起来像「查过了没问题」，那是假结论。
- 退出码：0 = 有契约认领；1 = 未被认领（显式判定，不是错误）。
- 幂等：idempotent + 纯读。

## 判据（可证）

```bash
# 1) cc_verify 的机制自检（四词判定各自可达）
python scripts/nf.py evidence verify --selfcheck
# 2) cc_verify 的敏感度基准（38 条已知攻击逐条比对；任一条不达期望即 exit 1）
python scripts/nf.py evidence bench
# 2b) 两套独立实现判据一致（core 版 vs 零依赖单文件版，含真实回执）
python -m unittest desktop.tests.test_evidence.TestStandaloneParity
# 3) 三种形态都能脱离仓库判：自包含包 / 协议回执 / 信封集
python scripts/nf.py evidence verify <包.zip>
python scripts/nf.py evidence verify protocol/RECEIPTS.json --root .
python scripts/nf.py evidence verify <信封集.json> --root <成员根> --key-file <密钥>
# 3b) cc_replay 的轨迹可 diff（同输入两次逐字节一致）+ 篡改必现
python scripts/nf.py evidence replay <包.zip> --json > /tmp/t1.json
python scripts/nf.py evidence replay <包.zip> --json > /tmp/t2.json
cmp /tmp/t1.json /tmp/t2.json
# 3c) cc_check 的单对象判定（ok/invalid 两态）
python scripts/nf.py check 01_核心协议.md --policy <策略.json> --json
# 4) cc_attest 的可复现性（两次运行逐字节一致）
SOURCE_DATE_EPOCH=1700000000 python scripts/nf.py attest 01_核心协议.md --json > /tmp/a1.json
SOURCE_DATE_EPOCH=1700000000 python scripts/nf.py attest 01_核心协议.md --json > /tmp/a2.json
cmp /tmp/a1.json /tmp/a2.json
# 5) 证据强度不冒充：digest_only 级必须报 digest_only
python scripts/nf.py evidence verify <包.zip> --json | grep -q '"level": "digest_only"'
```

判据约定：任一调用的「实装状态」字段与实际能力不符即视为**本文失真**——
文档是结果面，不许把规划和实装混写。

## 一条链复现（ABI 的验收动作）

发布结论的**固定入口**见 [release-conclusion.md](release-conclusion.md)：脏树闸门 → checks-only
→ 分片并行 → 汇总，一条命令给出「这台机器现在能不能发布」。

四环可跑的链条现场验证：`scripts/ccos_chain.py`（`--target <对象>`）。它的判据不是
「四个命令都返回 0」，而是**同一个对象字节的摘要逐个流下去**——体检的 sha256、信封的
subject.sha256、证据包成员 digest、轨迹第一步 output 必须**完全相同**；四个命令各自成功
而链条换了字节，仍不算同一条链。

缺环如实标注：本仓载体写入覆盖 **PNG iTXt 与 JPEG APP15**（2026-11-06 实装，
`nf label embed|extract`），链尚未接 label 环，故链条输出 `missing: ["cc_label"]`——不假装七环
齐全；把可见文本段读成「抗转码标识」是误读。

```bash
python scripts/ccos_chain.py --target STRATEGY.md          # 人读表
python scripts/ccos_chain.py --target STRATEGY.md --json   # 机读（含四份摘要）
python -m unittest desktop.tests.test_ccos_chain            # 7 项：摘要一致 / 缺环标注 / 缺环闭集 / 空对象判否
```

## 未实装差距（如实挂账，不构成立项理由）

| 调用 | 差距 | 阻塞项 |
|---|---|---|
| `cc_label` | 声明层 + sidecar 回退 + **PNG iTXt / JPEG APP15 载体**已有（读回 / 内容面不变 / 结构合法 / 对象绑定）；**仍缺**：水印嵌入、其余格式（MP4/PDF/…）载体、20+ 格式覆盖 | 水印与多格式需要专门的写入子系统；本季只做能自证的两种 |
| `cc_check` | 判定面：封闭词表（5 类规则）；**编译面 v0 已有**（结构化意图 → 规则，不可表达项逐条挂账）；**法规原文 → 意图**仍需人写 | 政策编译的语义层：不承诺自动把法规原文变成意图，缺的意图必须逐条挂账 |
| `cc_resolve` | v0 只认真实声明的契约面（23 条 spec，opt-in）；未声明的对象一律 unclaimed | 契约声明面为人工编纂；未认领给 `unclaimed` 而非放行，不得读成「查过了没问题」 |

本表只记录**内部差距实证**；外部项目的能力不作为开项依据（`STRATEGY.md` §3.3）。

## 本季非目标与触发条件

以下能力**不在本季 ABI 承诺面内**；条件成立前不做，避免把计划写成已实现。
逐条给触发条件（成立 = 重新评估，不等于自动开项）：

| 非目标 | 触发条件 |
|---|---|
| 水印 / 其它格式载体 / C2PA 读写 | 出现真实合规写入需求，且「格式覆盖 × 水印算法 × 验证闭环」选型判据成立；PNG/JPEG 已实装，其余格式不一次铺 20+ |
| CA / TSA / measured boot 等外部权威 | 本仓威胁模型不引外部权威（见 threat-model.md）；无触发条件 |
| K1–K8 内核语义（作业/调度/内存/命名空间/资源治理/启动恢复） | 出现第二个调用面/租户，或长任务取消/断点恢复成为真实需求；届时只允许 K1+K4+K5+K7 最小集（K2 折入 K1、K3/K6 不做、K8 仅 boot 自检） |
| 四类网关 / 联邦 / 多节点 | 出现多节点部署或远程调用面需求；本地 CLI 路径必须无网关亦完整 |
| 多租户 / 计费 / License / 市场 | 出现对外交付通道 |
| 外部盲评作质量判据 | 作者显式解冻外部实测，且 STRATEGY §3.1 同步修订；此前只作 advisory |
| 公开基准 / 外部复验统计 | 同上（外部动作由作者显式触发） |
| Go / WASM 验证器 | 出现无 Python 环境的第三方复验需求；零依赖单文件（scripts/nf_verify.py）是当前基线 |

## 版本与迁移

- ABI 版本 `v0`：**只增不改**——新增调用/字段 = minor；删除或改语义 = 破坏性变更，
  必须 bump 到 `v1` 并留迁移记录（照 `docs/rfc.md` 的 supersede 链口径）。
- 判定词表（`ok/revoked/expired/invalid`）与退出码表是本 ABI 的**稳定面**：
  改它们等于改所有验证方，须按破坏性变更处理。
