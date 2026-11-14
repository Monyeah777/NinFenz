# 密钥透明目录 v0（`nf-key-transparency/1`）

> **状态**：已实装（2026-11-08，2026-11-13 复核）· 机制来源：IETF Key Transparency 协议（draft-keytrans-mcmillion-protocol，**正文关键段已读**）
> **实现位置**：`desktop/src/core/key_transparency.py` · CLI `nf evidence revocations trust` 的 **4 个子命令**：`kt-build` / `kt-verify` / `kt-lookup` / `kt-split` · 判据 `desktop/tests/test_key_transparency.py`
> **最后更新：2026-11-13（复核）**：形状/判定/边界**复核不变**；**修一处失效 CLI 引用**——原文写 `kt-build/kt-verify/kt-witness`，其中 **`kt-witness` 并不存在**（实际第 4 个子命令是 `kt-split`，`kt-lookup` 也未列）；常驻判据 **15 例**。见「§现状对照」。

## 解决什么

吊销信任锚（`nf-revocation-trust/1`，钉根 + 有界委派）能判「这把公钥是否被某个根承认」，
但**判不了分叉**：两个验证方可能看到不同的密钥集（一方被喂了伪造目录），被骗的一方无从发现。
密钥透明目录补这一环：版本化根 + 只追加日志 + 包含证明 + **分叉见证**。

## 形状

```json
{"schema":"nf-key-transparency/1","version":2,
 "keys":{"org-a/key-1":"<64 hex>","org-b/key-1":"<64 hex>"},
 "root":"<64 hex>",
 "log":[{"seq":1,"root":"…","prev":""},{"seq":2,"root":"…","prev":"…"}],
 "note":"版本链只证追加；分叉检测需与另一份目录对比"}
```

- 叶 = `sha256(0x00 ‖ canonical{"id": key_id, "pub": pub})`（与 receipts 同算法）；根 = RFC 6962 风格 Merkle 根；
- `log[i].prev` 必须等于 `log[i-1].root`；`len(log) == version`；最新 log 根必须等于 keys 重算根。

## 用法

```bash
# 造第一版（key_id → 公钥 hex）
nf evidence revocations trust kt-build keys-v1.json --out kt1.json
# 追加新版本（接链）
nf evidence revocations trust kt-build keys-v2.json --prev kt1.json --out kt2.json
# 校验自洽
nf evidence revocations trust kt-verify kt2.json --json
# 单键查找 + 包含证明（客户端只需 proof 与 root 即可离线验）
nf evidence revocations trust kt-lookup kt2.json --id org-b/key-1 --json
# 分叉检测（谁都不是谁的合法延伸 → split + witness）
nf evidence revocations trust kt-split --a kt2.json --b fake2.json
```

## 判定（可证）

| 面 | 判据 | 不过 |
|---|---|---|
| 目录自洽 | schema / keys 形状（64 hex）/ version 与 log 等长 / 链不断 / 根可复算 | invalid |
| 包含证明 | proof 折叠回 root，且 leaf 与 {id,pub} 同源 | 证明失败 |
| 一致性 | 新版本第 old_version 条的根 == 旧根 | fork |
| 分叉 | 两份目录同版本不同根，或互不为延伸 | split + witness |

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 本文声明 | 复核结果（读到本行时请重跑） |
|---|---|---|
| 实装状态 | 已实装（2026-11-08） | **不变**（`core/key_transparency.py` 在场） |
| CLI 子命令 | 原写「kt-build/kt-verify/kt-witness」 | **4 个真实子命令**：kt-build / kt-verify / kt-lookup / kt-split（**无 kt-witness**，已修正） |
| 形状不变量 | 叶 0x00+canonical / 根 RFC6962 / `log[i].prev == log[i-1].root` / `len(log)==version` | **不变** |
| 判定面 | 自洽 / 包含证明 / 一致性 / 分叉 | **不变**（invalid / 证明失败 / fork / split+witness） |
| 常驻判据 | 15 项 | **15 例**（`test_key_transparency.py`） |
| 不做项 | 前缀树 / abridged proof+审计者 / 隐私 | **不变**（如实挂账） |
| 外部权威 | 客户端仍需知道哪份目录权威 | **不变**（分叉能发现，不能裁决） |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 边界（诚实写清）

- **不做前缀树**：查找是 O(n)，目录大小会暴露——KT 的「可搜索且不泄漏」未实现；
- **不做 abridged proof / 审计者角色**：无历史状态者无法仅凭单条证明验证全链；
- **不做隐私**：键名与公钥在目录里是明文；
- 客户端仍需知道「哪份目录是权威」——分叉检测能**发现**不一致，不能自动裁决谁对（那需要外部锚或审计者）。

## 判据（自证）

```bash
python -m unittest desktop.tests.test_key_transparency   # 15 项
```

覆盖：确定性构建 / 篡改 keys 与 log 必红 / 版本与 log 等长 / 包含证明与错公钥必拒 /
同版本不同根的伪造目录（自身自洽）必被判 split / 历史改写必被判 fork / CLI 全链路。

## 复现与引用口径

```bash
nf evidence revocations trust kt-build keys-v1.json --out kt1.json   # 造版
nf evidence revocations trust kt-verify kt1.json --json             # 自洽校验
nf evidence revocations trust kt-lookup kt1.json --id org-b/key-1 --json  # 包含证明
nf evidence revocations trust kt-split --a kt1.json --b fake2.json  # 分叉检测
```

- 引用本文时：「形状不变量 + 四类判定 + 「发现分叉≠裁决谁对」」= 长期口径；子命令名以 `nf evidence revocations trust --help` 实读为准。
- 新能力若加子命令，须同步本表与判据（本页曾有 `kt-witness` 失效引用，2026-11-13 已修）。

## 与既有件的关系

- `nf-revocation-trust/1`：判「公钥归属」；本件判「归属一致」——两者叠加才挡住「换公钥冒充 + 只骗一方」；
- `nf-evidence`/`transparency`：本件是密钥目录的透明日志，不自建新日志通道；
- 后续（未做）：把目录根锚进 TSA 时间戳（已有 `nf evidence timestamp`）与吊销 feed 的 `prev_digest` 链。
