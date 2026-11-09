# 吊销分发件 v0（`nf-revocation-feed/1`）

状态：**已实装**（CLI：`nf evidence verify` 的四词判定含 `revoked`）。
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-06
> **Status**: v0 已实装（`core/revocations.py` + `nf evidence revocations`）· 仍是**拉取式**分发
> **实现位置**：`desktop/src/core/revocations.py` · 判据 `desktop/tests/test_revocations.py`

## 解决什么（威胁模型 G2 的可落地部分）

此前吊销表只有两种形态：包内嵌、或侧载一份裸 JSON。拿到手你判不了两件事：

1. **来源**——这份表是谁出的？改过没有？
2. **回滚**——攻击者给你一份**更早**的吊销表，读起来完全合法，于是已吊销的错签又「生效」了。

`nf-revocation-feed/1` 在表外面套一层信封：`issuer` + 单调 `seq` + `prev_digest` + hmac 签名。
校验不过即不可信；序号与前序摘要接不上即不可信。**分发本身**（谁来发布、你怎么拿到）仍不在本仓。

## 形状

```json
{
  "schema": "nf-revocation-feed/1",
  "issuer": "acme",
  "seq": 2,
  "issued_at": "2026-11-05T03:00:00Z",
  "expires_at": "2026-12-05T03:00:00Z",
  "prev_digest": "<上一份 feed 的 digest>",
  "table": {"schema": "nf-revocation/1", "revoked": [{"digest": "…", "reason": "…"}]},
  "signature": {"alg": "hmac-sha256", "mac": "<hex>"}
}
```

签名体 = **除 `signature` 外的全部字段**（`sort_keys + ensure_ascii=false + 紧凑分隔符` 规范化后求
hmac-sha256）；`digest` = 对签名体求 sha256（前序链用）。`expires_at` 在下节说明，是**可选**字段：
不给就不写（不写 null），旧 feed 原样可用。

## 怎么用

```bash
# 签发（首份 seq=1；之后每份 +1 并把上一份给 --prev）
nf evidence revocations sign --table table.json --key-file k.bin --issuer acme --seq 1 --out f1.json
nf evidence revocations sign --table table2.json --key-file k.bin --issuer acme --seq 2 \
    --prev f1.json --out f2.json

# 签发时给有效期与分发指针（都只在给出时写入；status_uri 只记录，本仓不联网取）
nf evidence revocations sign --table table3.json --key-file k.bin --seq 3 \
    --expires-at 2026-12-06T00:00:00Z --status-uri https://example.invalid/revocations/3.json \
    --out f3.json
# 也可以用 --ttl 86400（正整数秒 ≤ 31536000；与 --expires-at 并存时以 --expires-at 为准）

# 校验（缺密钥即 invalid，不降级；给了 --prev 时同时核对序号与前序链）
nf evidence revocations verify f2.json --key-file k.bin --prev f1.json
nf evidence revocations verify f3.json --key-file k.bin --at 2026-11-06T00:00:00Z   # 新鲜度时点

# 合并（多份按任意顺序给，内部按 seq 排；任何一份不过则整次失败）→ 普通表
nf evidence revocations merge f2.json f1.json --key-file k.bin --out revocations.json

# 合并结果直接喂证据复验；--revocations 也直接吃签名 feed（会读它的有效期）
nf evidence verify bundle.zip --revocations revocations.json
nf evidence verify bundle.zip --revocations f3.json
nf evidence verify bundle.zip --revocations f3.json --require-fresh-revocations   # 表不新鲜即 invalid
```

### 非对称签名（ed25519，2026-11-07 起）

hmac-sha256 是**对称**的：把验证能力交给别人，就等于把伪造能力一起交出去——跨组织时「谁吊销的」
不成立。现在可以用 ed25519：发布方持 32 字节种子、只把 **32 字节公钥**交给验证方。

```bash
# 发布方：生成种子（一次），导出公钥交给验证方
openssl rand -out seed.bin 32
nf evidence revocations pubkey seed.bin                 # 打印 32 字节公钥（hex）

# 发布方：用种子签（签名确定性：同 key+msg 永远同字节，故可进向量集）
nf evidence revocations sign --table table.json --key-file seed.bin \
    --scheme ed25519 --issuer acme --seq 1 --out f1.json

# 验证方：只持公钥即可验（缺公钥 fail-closed，不降级）
nf evidence revocations verify f1.json --key-file pub.bin
```

- 签名体仍是「除 `signature` 外全部字段」的规范字节；`signature = {alg: ed25519, pub, sig}`——
  声明里的 `pub` 与验证方给的公钥不一致即 invalid（换密钥必须重签，不能只改声明）。
- 实现是**纯标准库**（`core/ed25519.py`，RFC 8032），判据含 RFC 黄金向量（TEST 1）与和
  `cryptography` 库的交叉验证（该库不在场时跳过，不冒充已验）。
- hmac 路径完全保留（本机/单组织场景仍最省事）；两种方案在同一个 `verify()` 里按 `alg` 分派。

### 信任锚（钉根 + 有界委派，2026-11-07 起）

公钥签名只解决「给验证能力 ≠ 给伪造能力」，没解决「这把公钥是谁的」——攻击者换一把公钥重签 feed，
验证方照样验得过。信任锚补这一层：验证方钉一份清单（根公钥），组织公钥必须由根**签发委派**才被承认。

```bash
# 1) 初始化清单：把根公钥登记为根，并签一条到组织公钥的委派
nf evidence revocations trust grant root.seed --subject-pub <ORG_PUB_HEX> \
    --expires-at 2027-01-01T00:00:00Z --root --trust trust.json --out trust.json

# 2) 验证 feed：ed25519 公钥必须被信任根覆盖（不给 --trust 只给 warning；--require-trust 则判死）
nf evidence revocations verify feed.json --key-file org.pub --trust trust.json --require-trust

# 3) 看清单 / 现场核对一把公钥
nf evidence revocations trust show --trust trust.json --check-pub <ORG_PUB_HEX>
```

形状（`nf-revocation-trust/1`）：

| 字段 | 含义 |
|---|---|
| `roots[]` | `{id, pub}`：钉住的根公钥 |
| `delegations[]` | `{issuer, subject, scope, expires_at, sig}`：委派条目（签名体 = 四个字段的规范 JSON） |

**判据约束**（都在 `test_trust_anchor.py`）：

- 只允许 `scope=revocations`（这把钥匙不能拿去签别的东西）；
- `expires_at` 必填且必须是 UTC 秒级（不允许永久授权），过期即不认；
- 链深上限 **2 级委派**（root → org → team），超过不认；
- 委派签名被改 / issuer 对不上 → 不认；
- 未被根覆盖的公钥 → 判 invalid 并给修复指引。

残留（诚实写）：根公钥怎么分发到验证方仍靠带外渠道（邮件/公告/配对指纹）；本仓不建 PKI，也不假装有。

**分叉面**：钉根方案判不了「两个验证方看到不同密钥集」——已另做密钥透明目录（版本化根 + 只追加日志 + 包含证明 + 分叉见证），见 [key-transparency-v0.md](key-transparency-v0.md)。

## 判定（可证）

| 检查 | 不过 |
|---|---|
| schema ∈ {feed, table}；feed 必带 `table`（只放条目不算） | invalid |
| `seq` 为非负整数；`prev_digest` 为 64 位十六进制 | invalid |
| 有 `signature` 时：算法只认 hmac-sha256、**必须有密钥**、mac 必须匹配 | invalid（缺密钥**不**降级） |
| 无 `signature` | ok + warning（形状可判、来源与回滚判不了） |
| 给了 `--prev`：`seq` 必须恰好 +1 且 `prev_digest` 等于上一份的 digest | invalid |
| `expires_at` / `ttl` / `status_uri` 给了时形状必须合法（见下节） | invalid |
| `expires_at` 早于 `issued_at` | invalid |
| 合并：任何一份验不过 | 整次 invalid（半可信的合并结果比没有更危险） |

## 新鲜度（可选字段，TSL 语义子集）

feed 可带三个**可选**字段（只在给出时写入；`nf-revocation/1` 表 schema 不变）：

| 字段 | 口径 | 用途 |
|---|---|---|
| `expires_at` | UTC 秒级 `YYYY-MM-DDTHH:MM:SSZ`，且不得早于 `issued_at` | 有效期；在场时以它为准 |
| `ttl` | 正整数秒，≤ 31536000（1 年） | 有效期 = `issued_at + ttl`（`expires_at` 在场时被它压过） |
| `status_uri` | 非空字符串 | 分发指针；**只记录，不联网取、不验可达性** |

三个字段都在**签名体**里（签名体 = 除 `signature` 外全部字段）——改一个字节即破签名，`digest` 随之
变化；旧读者用同一 body 定义重算，seq/prev 链仍接得上（回滚判定口径不变）。

**新鲜度只进输出，不改四词判定**：`nf evidence revocations verify|merge` 输出 `freshness{state,
expires_at, basis}`（`basis` = `expires_at|ttl|none`）；`nf evidence verify` 输出
`revocations_fresh`（`fresh|stale|unknown`）、`revocations_source`（`external|embedded|none`）与
`revocations_basis`。默认只给 WARN，要硬拒须显式开关 `--require-fresh-revocations`：

| 条件 | 默认 | `--require-fresh-revocations` |
|---|---|---|
| 表 fresh | ok | ok |
| 表 stale（已过有效期） | ok + WARN | invalid（`吊销表已过期`） |
| 表 unknown（没给 `expires_at`/`ttl`，或来源是裸表） | ok + WARN | invalid（`吊销表未给有效期`） |
| **完全没有吊销来源** | ok | ok（没做吊销检查 ≠ 陈旧，不得判死） |
| 命中吊销条目 | revoked | revoked（事实优先，压过新鲜度） |
| 证据本身已过期 | expired | expired（压过新鲜度） |

判定优先级：`revoked > expired > 新鲜度不足(invalid) > ok`。三处调用点（bundle / receipts / attest）
共用同一段判定。

`--revocations` 现在**同时接受** `nf-revocation/1` 表与签名 `nf-revocation-feed/1`（传 feed 时取
它的 table 并读其有效期）；形状不对一律 fail-closed（不会静默当成「无吊销」）。包内嵌
`revocations.json` 仍只认表。

## 边界（仍缺什么）

- **没有自动分发**：本仓不发布、不订阅、不轮询；「签发方已撤销但你没收到」仍然无解。
- **hmac 是对称的**：拿到密钥的人能伪造任意 feed。要跨组织证明来源，需要公钥签名（ssh-sig/sigstore 面
  已有实现，但吊销件还没走那条线）。
- **没有撤销时间语义**：feed 只说「哪些被吊销」，不说「从何时起」；时效仍由证据包的 `expires_at` 承担。
- **新鲜度不是分发**：`expires_at`/`ttl` 只说明这份表**声称**多新，`status_uri` 只是一个指针；
  本仓仍不轮询、不自动取，也不验证指针可达性。

## 复核

```bash
python -m unittest desktop.tests.test_revocations    # 43 项：签名/篡改/缺密钥/回滚/分叉/合并/新鲜度/ed25519
```
