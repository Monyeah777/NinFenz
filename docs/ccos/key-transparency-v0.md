# 密钥透明目录 v0（`nf-key-transparency/1`）

> **状态**：已实装（2026-11-08）· 机制来源：IETF Key Transparency 协议（draft-keytrans-mcmillion-protocol，**正文关键段已读**）

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

## 与既有件的关系

- `nf-revocation-trust/1`：判「公钥归属」；本件判「归属一致」——两者叠加才挡住「换公钥冒充 + 只骗一方」；
- `nf-evidence`/`transparency`：本件是密钥目录的透明日志，不自建新日志通道；
- 后续（未做）：把目录根锚进 TSA 时间戳（已有 `nf evidence timestamp`）与吊销 feed 的 `prev_digest` 链。
