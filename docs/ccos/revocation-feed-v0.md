# 吊销分发件 v0（`nf-revocation-feed/1`）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-05
> **Status**: v0 已实装（`core/revocations.py` + `nf evidence revocations`）· 仍是**拉取式**分发

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
  "prev_digest": "<上一份 feed 的 digest>",
  "table": {"schema": "nf-revocation/1", "revoked": [{"digest": "…", "reason": "…"}]},
  "signature": {"alg": "hmac-sha256", "mac": "<hex>"}
}
```

签名体 = **除 `signature` 外的全部字段**（`sort_keys + ensure_ascii=false + 紧凑分隔符` 规范化后求
hmac-sha256）；`digest` = 对签名体求 sha256（前序链用）。

## 怎么用

```bash
# 签发（首份 seq=1；之后每份 +1 并把上一份给 --prev）
nf evidence revocations sign --table table.json --key-file k.bin --issuer acme --seq 1 --out f1.json
nf evidence revocations sign --table table2.json --key-file k.bin --issuer acme --seq 2 \
    --prev f1.json --out f2.json

# 校验（缺密钥即 invalid，不降级；给了 --prev 时同时核对序号与前序链）
nf evidence revocations verify f2.json --key-file k.bin --prev f1.json

# 合并（多份按任意顺序给，内部按 seq 排；任何一份不过则整次失败）→ 普通表
nf evidence revocations merge f2.json f1.json --key-file k.bin --out revocations.json

# 合并结果直接喂证据复验
nf evidence verify bundle.zip --revocations revocations.json
```

## 判定（可证）

| 检查 | 不过 |
|---|---|
| schema ∈ {feed, table}；feed 必带 `table`（只放条目不算） | invalid |
| `seq` 为非负整数；`prev_digest` 为 64 位十六进制 | invalid |
| 有 `signature` 时：算法只认 hmac-sha256、**必须有密钥**、mac 必须匹配 | invalid（缺密钥**不**降级） |
| 无 `signature` | ok + warning（形状可判、来源与回滚判不了） |
| 给了 `--prev`：`seq` 必须恰好 +1 且 `prev_digest` 等于上一份的 digest | invalid |
| 合并：任何一份验不过 | 整次 invalid（半可信的合并结果比没有更危险） |

## 边界（仍缺什么）

- **没有自动分发**：本仓不发布、不订阅、不轮询；「签发方已撤销但你没收到」仍然无解。
- **hmac 是对称的**：拿到密钥的人能伪造任意 feed。要跨组织证明来源，需要公钥签名（ssh-sig/sigstore 面
  已有实现，但吊销件还没走那条线）。
- **没有撤销时间语义**：feed 只说「哪些被吊销」，不说「从何时起」；时效仍由证据包的 `expires_at` 承担。

## 复核

```bash
python -m unittest desktop.tests.test_revocations    # 17 项：签名/篡改/缺密钥/回滚/分叉/合并
```
