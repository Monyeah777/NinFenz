# 公共锚 live 证据（Sigstore Rekor，2026-11-14）

> 只读公开日志：验证的是 **Rekor 公共实例的真实条目**，不是本仓自签条目。
> 机器件：[PUBLIC_ANCHOR_LIVE.json](PUBLIC_ANCHOR_LIVE.json) · 公钥：[rekor-public-key.pem](rekor-public-key.pem)

## 条目

| 字段 | 值 |
|---|---|
| log | `rekor.sigstore.dev`（logID = 公钥 DER 的 sha256） |
| log_id | `c0d23d6ad406973f9559f3ba2d1ca01f84147d8ffc5b8445c224f98b9591801d` |
| log_index | `0` |
| tree_size | `4163431` |
| root_hash | `4d006aa46efcb607dd51d900b1213754c50cc9251c3405c6c2561d9d6a2f3239` |
| inclusion proof | 22 个 sibling hash（RFC6962） |
| target_digest（从 hashedrekord body 提取） | `45c7b11fcbf07dec1694adecd8c5b85770a12a6c8dfdcf2580a2db0c47c31779` |
| SET | Rekor 日志 ECDSA-SHA256 签名（openssl 离线验） |

## 复跑

```bash
python scripts/trust_verify.py --verify-public-anchor results/trust/PUBLIC_ANCHOR_LIVE.json \
  --public-log-id c0d23d6ad406973f9559f3ba2d1ca01f84147d8ffc5b8445c224f98b9591801d \
  --public-log-pubkey results/trust/rekor-public-key.pem
# → valid public anchor: log=... tree=4163431 target=45c7...
```

## 边界（不夸大）

- 该条目锚的是**它自己 body 里的 artifact 摘要**，不是本仓链头；本仓链头的公共提交需维护者 Sigstore 身份
  （外部操作，未执行）。
- 本证据证明：公共日志条目的 inclusion proof、SET 签名、目标摘要绑定在本仓实现里可离线验真；
  不证明「内容真实」或「签名者身份可信」（Sigstore 身份策略属另一层）。
