# 内容 attestation（`nf attest`）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13

> **复核（2026-11-13）**：三级信任口径与「缺锚即拒绝、不降级」不变；补三处现状：① CLI 还有 **`--selfcheck`**（体检外部验签机制：独立子进程验签 + 篡改必红，**check42 的用户侧入口**）与 **`--json`**（结构化输出）；② `nf library attest <编号> --ssh-key` 是**库条目**签名路径（锚落 `library/anchors/*.sig`），与本文件的三级（内容信封）**不是同一层**，勿混称；③ 常驻判据 `test_attest` **9 例**。见「§现状对照」。

## 为什么有这一层

`nf sig` 产出的是**可复现内容摘要**：它证明「两遍算出来一样」，**不证明这份内容没被换过**
——任何人都能重算同一摘要。`nf attest` 在其上补一层**可对外验证**的信封，判的是
**证据强度**，不是内容质量。

## 三级信任（逐级 fail-closed）

> 层级只升不降：要求 `sigstore-keyless` 而验证器不在场 → **拒绝**（不静默降级成 `digest_only`）。

| 级 | 命令 | 证明了什么 | 没证明什么 |
|---|---|---|---|
| `digest_only` | `nf attest <file>` | 内容与信封一致（未被改动） | 签发方身份（谁都能重算） |
| `hmac-sha256` | `nf attest <file> --key-file <k>` | 信封由持钥方签发且未改 | 密钥外分发的可信度 |
| `sigstore-keyless` | 外部 `cosign` 锚（`signature.bundle`） | 第三方可验证的签发锚 | —— 缺验证器即**拒绝**，不降级 |

## 用法

```bash
# 生成（缺省 = 01/02/06/07 四件集合；不写盘）
python scripts/nf.py attest
python scripts/nf.py attest 01_核心协议.md --out .attest/01.json --issuer "作者"

# 本地密钥签发（stdlib hmac，无第三方依赖）
python scripts/nf.py attest 01_核心协议.md --key-file <密钥文件> --out .attest/01.json

# 校验（信任级与问题逐条输出；exit 0 = 证据成立）
python scripts/nf.py attest --verify .attest/01.json
python scripts/nf.py attest --verify .attest/01.json --key-file <密钥文件>

# 体检「外部验签」机制（独立子进程验签 + 篡改必红；check42 的用户侧入口）
python scripts/nf.py attest --selfcheck
python scripts/nf.py attest --json          # 结构化输出（机读）
```

| 旗标 | 作用 |
|---|---|
| `--out` | 写出 attestation JSON 的路径（缺省不写盘） |
| `--issuer` | 签发方标识（进 `producer.issuer`） |
| `--key-file` | HMAC 密钥文件 → 签发/校验 `hmac-sha256` 级 |
| `--verify` | 校验既有 attestation（缺省 = 生成模式） |
| `--selfcheck` | 体检外部验签（独立子进程 + 篡改必红；check42 用户侧入口） |
| `--json` | 结构化输出 |

## 与门禁的关系

attestation **不是** verify 门禁的一部分：门禁判协议/内容是否合格，attestation 判
「这份内容是不是它声称的那份」。二者互不替代；缺锚时 attestation 拒绝，而门禁可仍为绿。

> 例外关系（不矛盾）：`--selfcheck` 是 **check42 的用户侧入口**——它体检的是「外部验签机制本身是否可信」（独立子进程 + 篡改必红），不是把 attestation 提升为门禁；供应链面门禁（check42）只保证构建/来源证据，不替内容信封判级。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 当时（本文快照） | 现行（读到本行时请重跑确认） |
|---|---|---|
| 三级信任 | digest_only / hmac-sha256 / sigstore-keyless | **不变**（逐级 fail-closed、不降级） |
| CLI 旗标 | --out / --issuer / --key-file / --verify | **+ `--selfcheck` / `--json`** |
| 外部验签体检 | 未提 | `--selfcheck`（独立子进程验签 + 篡改必红），**check42 用户侧入口** |
| 库条目签名 | 未提 | `nf library attest <编号> --ssh-key`（锚 `library/anchors/*.sig`）——**另一层**，不是本文三级 |
| 常驻判据 | 未计 | `test_attest` **9 例** |
| 与门禁关系 | 互不替代 | **不变**（门禁绿 ≠ attestation 成立；缺锚仍拒绝） |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
python scripts/nf.py attest --selfcheck      # 外部验签机制体检（篡改必红）
python scripts/nf.py attest --json           # 机读信封
python -m pytest desktop/tests/test_attest.py -q   # 9 例常驻判据
```

- 引用本文时：三级语义与「不降级」= 长期口径；旗标/行为以 `nf attest --help` 与实现实读为准。
- 别名边界：`nf attest`（内容信封三级）≠ `nf library attest`（库条目 SSH 签名锚）。
