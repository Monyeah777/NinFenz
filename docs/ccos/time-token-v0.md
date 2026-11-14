# 可信时间戳 v0（RFC 3161 · G3 的可落地半边）

> **状态**：已实装（2026-11-07）· 依赖 `openssl`（`ts` 子命令）与 `curl`（申请阶段）
> **实现位置**：`desktop/src/core/timestamp.py` · 判据 `desktop/tests/test_timestamp.py`
> **最后更新：2026-11-13（复核）**：形状/判定/边界**逐项复核不变**；现状数字：CLI 两子命令（`stamp` / `verify`）在册、
> `stamp` 落 **`.tsq` / `.tsr` / `.json`** 三件、`nf evidence verify --time-record --time-ca` 两旗标在位；
> 常驻判据 `test_timestamp` **8 项**（本地 TSA 全链路，缺 `openssl` 整类跳过、不冒充已验）；信任锚**不预置**、
> 响应 **>1 MiB 拒收**、TSA 地址仅 http(s)。见「§现状对照」。

## 解决什么

威胁模型 G3：时效判据此前只吃本机时钟，回拨就能把「已过期」变「未过期」。现在可以接**外部时间权威**：
由 TSA 签发 RFC 3161 时间戳 token，token **绑定被证数据的 sha256**；校验时**不需要联网、不需要 TSA 在线**，
只需要 TSA 的证书链（信任锚）。

只解决一半，写清边界：

| 证得了 | 证不了 |
|---|---|
| 「这份字节在 genTime 那一刻已经存在」 | 内容质量、内容真实性 |
| token 由**信任锚所认可的那把 TSA 密钥**签发 | TSA 自己会不会伪造时间（那是信任锚的问题） |
| 被证对象**换一个字节**就对不上（摘要绑定） | 「现在」到底几点——只能证明存在过，不能证明现在 |

## 怎么用

```bash
# 1) 为证据包申请时间戳（需要网络；默认 TSA = digicert）
nf evidence timestamp stamp 产出/包.zip --ca-file digicert-root.pem
# → 落 包.zip.tsq（请求）/ 包.zip.tsr（token）/ 包.zip.json（记录）三件

# 2) 离线校验（只需要 token + 请求 + 信任锚；不需要网络）
nf evidence timestamp verify 包.zip.tsr --query 包.zip.tsq --ca-file digicert-root.pem --json

# 3) 让证据复验用这个时间锚（有效期判定改用 genTime，而不是本机时钟）
nf evidence verify 产出/包.zip --time-record 包.zip.json --time-ca digicert-root.pem --json
# → time_proof: "tsa"、time_basis: "<genTime>"
```

信任锚**要自己带**：本仓不预置根证书——预置等于替你决定信任谁。DigiCert 的根可在
`https://cacerts.digicert.com/DigiCertTrustedRootG4.crt.pem` 取；freetsa 等其它 TSA 同理。

## 判定（可证）

| 检查 | 不过 |
|---|---|
| `token` 与 `query` 成对且可解析 | invalid |
| TSA 签名链能追到给定信任锚 | invalid |
| 响应 `status` 必须是 `Granted` | invalid |
| 能解析出 `genTime`（统一归一成 ISO 秒级 UTC） | invalid |
| 时间锚记录的 `subject.sha256` == 被证对象实测摘要 | invalid |

`nf evidence verify --time-record` 的语义：**有效期判定用 genTime**（token 证「那时它已存在且在有效期内」），
而不是「本机现在几点」。没有 token 时仍退化为本机时钟 + `time_proof: none` + 显式 warning。

## 判据（自证）

```bash
python -m unittest desktop.tests.test_timestamp    # 8 项：本地 TSA 全链路 + 错锚/篡改/摘要不符必拒
```

测试自己用 `openssl` 起**本地 TSA**（自签 CA + TSA 证书）出 token 再离线验，不依赖外网；
缺 `openssl` 时整类跳过（不冒充已验）。真·外网 TSA 的连通性属于环境问题，不进判据。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 本文声明 | 复核结果（读到本行时请重跑） |
|---|---|---|
| CLI | `nf evidence timestamp` 的 `stamp` / `verify` | **两子命令在册**（`--url/--out-prefix/--ca-file/--untrusted/--json`） |
| 落盘 | `.tsq` + `.tsr` + `.json` 三件 | **不变** |
| 复验接入 | `--time-record` + `--time-ca` → `time_proof: tsa` | **两旗标在位**（`--time-ca` 必给当用 `--time-record`） |
| 判定 | 成对可解析 / 链到信任锚 / Granted / genTime / 摘要相符 | **不变**（任一不过 invalid） |
| 信任锚 | 不预置根证书（要自己带） | **不变**（预置=替你决定信任谁） |
| 失败模式 | 缺 openssl / 缺 curl fail-closed；>1 MiB 拒收；仅 http(s) | **不变** |
| 常驻判据 | 8 项（本地 TSA，缺 openssl 跳过） | **8 项** |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
nf evidence timestamp stamp 产出/包.zip --ca-file digicert-root.pem   # 需网络 + curl + openssl
nf evidence timestamp verify 包.zip.tsr --query 包.zip.tsq --ca-file digicert-root.pem --json
python -m pytest desktop/tests/test_timestamp.py -q   # 8 项（本地 TSA 出 token 再离线验）
```

- 引用本文时：「token 只证『某字节在某时刻已存在』，不证『现在几点』」= 长期口径。
- 锚纪律：信任锚由调用方自带；换锚即换时间来源——本仓不预置、也不替你决定信任谁。

## 依赖与失败模式

- 缺 `openssl`：申请/校验都 fail-closed 并给指引（**不**降级成「本机时钟也算」）。
- 缺 `curl`：申请阶段报错并说明「把 .tsq 交给有网机器」的替代路径。
- TSA 地址只接受 `http(s)`：避免「时间戳」变成某个内网服务的自说自话。
- token 响应 > 1 MiB 直接拒收（拒绝可疑响应）。

