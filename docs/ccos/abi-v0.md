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
（`desktop/src/core/labeling/` 与 `nf labeling` 均不存在，2026-11-04 实测）。因此本调用只定
形状，不宣称能力；实装前置见 §未实装差距。

- 输入：`{obj: <字节或路径>, contract: <契约 id>}`
- 输出：`{label: {contract, standard, fields, carrier, embedded: bool}}`
- 判定：`embedded=false`（回退 sidecar）必须在结果里如实标注，**不得**静默声称已写入载体。
- 错误码：`cc.label.no_contract` / `cc.label.unsupported_carrier` / `cc.label.embed_failed`
- 幂等：idempotent（同 obj + 同 contract → 同 label 字节）。

### 2. `cc_check(obj, policy)` → `verdict`

**状态：`partial`**。maps_to = `nf conformance`（契约 → Merkle 根 + verdict，
`protocol/conformance_report.json`）与 `nf run` 的三态质量门（PASS/WARN/FAIL）。
缺的是「单对象 × 单策略」的入口——现状是仓库级。

- 输入：`{obj: <路径>, policy: <策略 id 或策略文件>}`
- 输出：`{verdict: "ok"|"invalid", findings: [{rule, severity, path, message}], policy_digest}`
- 判定：`policy_digest` 必填——**判据版本必须随结论一起走**，否则结论不可复算。
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

**状态：`implemented`（本文配套 MVP）**。maps_to = `nf evidence verify <bundle>`。
本调用是**中立裁判位的地基**：验证方只需要证据包本身，**不需要仓库、不需要联网、
不需要复现生产环境**。

- 输入：一个证据包（`.zip` 或目录，布局见 `docs/ccos/evidence-bundle-v0.md`）
- 输出：`{verdict, level, root, head?, findings: [], revoked_by?: {...}, expiring: {...}}`
- 判定顺序（**fail-closed**，先失败先返回；不允许「证据弱就放行」）：

  | 序 | 检查 | 不过 → |
  |---|---|---|
  | 1 | 包结构/版本（`bundle.json.schema == nf-evidence/1`） | `invalid` |
  | 2 | 每个 payload 的 sha256 == manifest 记录 | `invalid` |
  | 3 | manifest 叶 → RFC 6962 根 == 记录 root | `invalid` |
  | 4 | receipts 每条 inclusion proof 折叠到同一 root | `invalid` |
  | 5 | 透明日志链（若在包内）自洽且 head 一致 | `invalid` |
  | 6 | 至少一条 attestation 通过（含信封摘要自洽） | `invalid` |
  | 7 | hmac 级：密钥在场且 mac 匹配 | `invalid` |
  | 8 | 吊销表命中 | **`revoked`** |
  | 9 | 时效（`expires_at` / `--at`）已过 | **`expired`** |

- `level` 如实回填证据强度（`digest_only`/`hmac-sha256`/`ssh-sig`/`sigstore-keyless`），
  **不**把 `digest_only` 说成可信签发。
- 错误码：`cc.verify.not_a_bundle` / `cc.verify.digest_mismatch` / `cc.verify.root_mismatch` /
  `cc.verify.proof_mismatch` / `cc.verify.no_attestation` / `cc.verify.key_required` /
  `cc.verify.revoked` / `cc.verify.expired`
- 幂等：idempotent + **纯读**（严禁因验证而写入任何文件）。

### 5. `cc_replay(evidence)` → `trace`

**状态：`partial`**。maps_to = `nf receipts --entry <path> --json`（单条 → inclusion proof 折叠
路径）+ `nf transparency --json`（链节重放）。产出「这条证据是怎么被算出来的」的可重放轨迹，
不是重新执行生产。
- 输入：证据包 / 单条回执
- 输出：`{trace: [{step, input_digest, output_digest, rule}]}`（确定性、可 diff）
- 幂等：idempotent + 纯读。

### 6. `cc_diff(a, b)` → `delta`

**状态：`implemented`**。maps_to = `nf diff <a> <b> --json`（字段级差异 + 兼容判定；
`--history N` 可从 Git 重建契约演进）。`delta` 必须**稳定排序**且自带两侧摘要。
- 输入：`{a: <签名件>, b: <签名件>}`
- 输出：`{delta: [{field, before, after, compat}], digest_a, digest_b}`
- 幂等：idempotent + 纯读。

### 7. `cc_resolve(obj)` → `contract set`

**状态：`partial`**。maps_to = `nf market`（依赖闭包 + 挂载冲突预检）与 `nf spec`（版本化
spec 查询）。缺「给一个对象，返回答它该用哪套契约」的单入口。
- 输入：`{obj: <路径或类型>}`
- 输出：`{contracts: [{id, version, digest}], closure_closed: bool}`（`closure_closed=false`
  必须显式出现，不得用空数组代替）
- 幂等：idempotent + 纯读。

## 判据（可证）

```bash
# 1) cc_verify 的形状自检（本仓基线）
python scripts/nf.py evidence verify --selfcheck
# 2) cc_attest 的可复现性（两次运行逐字节一致）
SOURCE_DATE_EPOCH=1700000000 python scripts/nf.py attest 01_核心协议.md --json > /tmp/a1.json
SOURCE_DATE_EPOCH=1700000000 python scripts/nf.py attest 01_核心协议.md --json > /tmp/a2.json
cmp /tmp/a1.json /tmp/a2.json
# 3) 证据强度不冒充：digest_only 级必须报 digest_only
python scripts/nf.py evidence verify <bundle> --json | grep -q '"level": "digest_only"'
```

判据约定：任一调用的「实装状态」字段与实际能力不符即视为**本文失真**——
文档是结果面，不许把规划和实装混写。

## 未实装差距（如实挂账，不构成立项理由）

| 调用 | 差距 | 阻塞项 |
|---|---|---|
| `cc_label` | 全无：无载体写入/无 sidecar 回退/无 20+ 格式覆盖 | 需要先有标识驱动子系统（本仓不存在） |
| `cc_check` | 仓库级 verdict 有，单对象 × 单策略入口无 | 需要 policy 编译器（P2–P3 方向） |
| `cc_replay` | 单条回执可折叠，整链 trace 未串 | 需要 trace 形态定稿 |
| `cc_resolve` | 依赖闭包可查，对象→契约集映射无 | 需要对象类型判定 |

本表只记录**内部差距实证**；外部项目的能力不作为开项依据（`STRATEGY.md` §3.3）。

## 版本与迁移

- ABI 版本 `v0`：**只增不改**——新增调用/字段 = minor；删除或改语义 = 破坏性变更，
  必须 bump 到 `v1` 并留迁移记录（照 `docs/rfc.md` 的 supersede 链口径）。
- 判定词表（`ok/revoked/expired/invalid`）与退出码表是本 ABI 的**稳定面**：
  改它们等于改所有验证方，须按破坏性变更处理。
