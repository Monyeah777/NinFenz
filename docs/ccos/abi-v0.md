# CCOS ABI v0：7 个系统调用
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-04
> **Status**: Draft v0 · **性质**: 正式协议（形状固定；实装状态逐调用如实标注，未实装不许当已实装读）
> **上位**: `STRATEGY.md`（方向与禁令）→ 本文件（ABI 层）。

## 是什么

CCOS（Content Contract Operating System）= 内容契约运行时。本文件把它的**对外表面**压成
7 个系统调用：每个调用给出签名、输入/输出形状、错误码、幂等语义、判定规则与**当下实装状态**。

ABI 只固定「调用长什么样、判什么、错了说什么」，**不**定义内容域、**不**新增真源：
所有调用都必须能落到仓库内**已存在**的产物或命令上（`maps_to`），落不到就标 `unimplemented`。

**非目标**（与 `docs/layers.md` 的 L0–L5 边界一致）：不是计算内核（不跑模型）、不是云、
不是 DRM、不是检测模型；本 ABI 不承诺任何不可计算的性质。

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
（当前空表）；ABI 侧码形态固定为 `cc.<syscall>.<reason>`，实装时按实际错误面登记。

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

**状态：`unimplemented`（无 maps_to）**。本仓当前**没有**任何标识写入/标识驱动子系统
（标识驱动子目录与 `nf labeling` 子命令均不存在，2026-11-04 实测三处独立来源核对）。因此本调用只定
形状，不宣称能力；实装前置见 §未实装差距。

- 输入：`{obj: <字节或路径>, contract: <契约 id>}`
- 输出：`{label: {contract, standard, fields, carrier, embedded: bool}}`
- 判定：`embedded=false`（回退 sidecar）必须在结果里如实标注，**不得**静默声称已写入载体。
- 错误码：`cc.label.no_contract` / `cc.label.unsupported_carrier` / `cc.label.embed_failed`
- 幂等：idempotent（同 obj + 同 contract → 同 label 字节）。

### 2. `cc_check(obj, policy)` → `verdict`

**状态：`implemented`（v0：封闭词表的单对象策略体检）**。maps_to = `nf check <对象> --policy <策略>`；
仓库级判定仍走 `nf conformance`。策略形状与词表见 `docs/ccos/check-policy-v0.md`：
`nf-check-policy/1`，kind 是**封闭集**（utf8 / regex_present / regex_absent /
count_at_least / digest_pin）——不自造 DSL，新增规则 = 加一条数据。

- 输入：`{obj: <单个文件>, policy: <nf-check-policy/1 JSON>}`
- 输出：`{verdict: "ok"|"invalid", policy_id, policy_digest, object{path,sha256,bytes},
  findings: [{rule, kind, severity, ok, detail, fix}], failed, warned}`
- 判定：verdict 只有两个词；`warn` 级违规只进 findings、**不改判定**；坏策略一律带指引拒绝。
- `policy_digest` 必填——**判据版本必须随结论一起走**，否则结论不可复算。
- 幂等：idempotent + 纯读。

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

**状态：`implemented`**（三种输入形态 + 29 条攻击矩阵基准）。
maps_to = `nf evidence verify <target>` / `nf evidence bench`；**零依赖参考实现** = `scripts/nf_verify.py --evidence <target>`（纯标准库、不 import 任何 NF 模块，单文件可分发）。
本调用是**中立裁判位的地基**：验证方只需要证据本身，**不需要仓库、不需要联网、
不需要复现生产环境**。

- 输入：**三种形态，同一套判定**（形态由文档 `schema` 判，不看扩展名）：
  `bundle`（`nf-evidence/1` 自包含包）/ `receipts`（`nf-receipts/1` 单根 + 包含证明）/
  `attest`（`nf-attest/1`、`nf-attest-set/1` 信封）。容器形态见
  `docs/ccos/evidence-bundle-v0.md`。
- 输出：`{verdict, kind, level, root, head?, count, issues: [], revoked_by?: {...}}`
- 判定顺序（**fail-closed**，先失败先返回；不允许「证据弱就放行」）：

  | 序 | 检查 | 不过 → |
  |---|---|---|
  | 1 | 形态/结构/版本（schema 与形态一致） | `invalid` |
  | 2 | 每个成员实体的 sha256 == 记录 | `invalid` |
  | 3 | 叶 → RFC 6962 根 == 记录 root | `invalid` |
  | 4 | 每条 inclusion proof 折叠到同一 root | `invalid` |
  | 5 | 透明日志链（若在包内）自洽且 head 一致 | `invalid` |
  | 6 | 成员集外**不得**多出未登记成员 | `invalid` |
  | 7 | 清单内**每一份**信封都必须通过 + 每个成员都被覆盖 | `invalid` |
  | 8 | hmac 级：密钥在场且 mac 匹配（缺密钥不降级） | `invalid` |
  | 9 | 吊销表命中 | **`revoked`** |
  | 10 | 时效（`expires_at` / `--at`）已过 | **`expired`** |

- `level` 如实回填证据强度（`digest_only`/`receipts_only`/`hmac-sha256`/`ssh-sig`/
  `sigstore-keyless`），**不**把 `digest_only` 说成可信签发、不把「一份信封过了」说成整体可信。
- 机制判据：`nf evidence verify --selfcheck`（四词判定各自可达）+ `nf evidence bench`
  （29 条已知攻击逐条比对，任一条不达期望即 exit 1）。
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
# 2) cc_verify 的敏感度基准（29 条已知攻击逐条比对；任一条不达期望即 exit 1）
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

四环可跑的链条现场验证：`scripts/ccos_chain.py`（`--target <对象>`）。它的判据不是
「四个命令都返回 0」，而是**同一个对象字节的摘要逐个流下去**——体检的 sha256、信封的
subject.sha256、证据包成员 digest、轨迹第一步 output 必须**完全相同**；四个命令各自成功
而链条换了字节，仍不算同一条链。

缺环如实标注：本仓无 labeling 子系统（2026-11-04 实测），链条输出 `missing: ["cc_label"]`，
不假装七环齐全。

```bash
python scripts/ccos_chain.py --target STRATEGY.md          # 人读表
python scripts/ccos_chain.py --target STRATEGY.md --json   # 机读（含四份摘要）
python -m unittest desktop.tests.test_ccos_chain            # 6 项：摘要一致 / 缺环标注 / 空对象判否
```

## 未实装差距（如实挂账，不构成立项理由）

| 调用 | 差距 | 阻塞项 |
|---|---|---|
| `cc_label` | 全无：无载体写入/无 sidecar 回退/无 20+ 格式覆盖 | 需要先有标识驱动子系统（本仓不存在） |
| `cc_check` | v0 只有封闭词表（5 类规则）；法规文本 → 规则的编译器没有 | 需要政策编译（P2–P3 方向） |
| `cc_resolve` | v0 只认真实声明的契约面（23 条 spec，opt-in）；未声明的对象一律 unclaimed | 需要更完整的契约声明面（人工编纂） |

本表只记录**内部差距实证**；外部项目的能力不作为开项依据（`STRATEGY.md` §3.3）。

## 版本与迁移

- ABI 版本 `v0`：**只增不改**——新增调用/字段 = minor；删除或改语义 = 破坏性变更，
  必须 bump 到 `v1` 并留迁移记录（照 `docs/rfc.md` 的 supersede 链口径）。
- 判定词表（`ok/revoked/expired/invalid`）与退出码表是本 ABI 的**稳定面**：
  改它们等于改所有验证方，须按破坏性变更处理。
