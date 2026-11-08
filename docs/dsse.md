# DSSE v1 签名信封
> ⛔ 操作指令：本文含可直接执行的签名与验签命令。DSSE 只证明“某受信密钥签署了这些字节”，不自动证明签发者身份。

## 命令

```bash
python scripts/nf.py dsse sign \
  --payload statement.json \
  --payload-type application/vnd.in-toto+json \
  --key-file signer.key \
  --keyid release-key \
  --out statement.dsse.json

python scripts/nf.py dsse verify \
  --envelope statement.dsse.json \
  --key-file verifier.key \
  --payload-type application/vnd.in-toto+json \
  --out verified-statement.json \
  --json
```

当前内置基线算法为 `hmac-sha256`。HMAC 密钥必须在签名方和验签方之外带外共享；它适合单发布方和离线复验，不等同于 Sigstore 的公钥身份信任。

## 判据

- PAE 必须逐字节为 `DSSEv1 <type-len> <type> <payload-len> <payload>`，长度按 UTF-8/二进制字节计。
- `payloadType`、`payload`、`signatures` 与每条 `sig` 必须在场；未知扩展字段忽略。
- 标准 Base64 与 URL-safe Base64 都接受，但非法字符、混用字母表、错误 padding 和非规范 pad bits 一律拒绝。
- `keyid` 仅用于缩小候选密钥，不参与信任决策。
- 多签名按唯一受信密钥计数，达到调用方声明的阈值才通过。
- 验签返回的 payload 字节必须原样交给后续消费方；禁止验签后重新编码或重新解析 envelope 来替换 payload。

## 边界

DSSE 是签名信封协议，不规定签名算法、公钥身份或透明日志。本实现不把 HMAC 说成第三方身份证明，也不因信封通过就宣称 Sigstore、SLSA 或 in-toto 供应链等级。Sigstore/cosign、SSH 签名和透明日志仍应由各自的信任策略裁决。
