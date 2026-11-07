# CCOS Go 客户端（`nfverify`）

证据复验的 **Go 侧零依赖实现**：证明 ABI 的 `cc_verify` 不绑定语言。
它不 import 本仓任何 Python 代码，也不联网。

## 覆盖面（诚实写清）

| ABI 调用 | Go 侧状态 |
|---|---|
| `cc_verify` | **已移植**：三种形态（bundle / receipts / attest）同一套四词判定 |
| `cc_check` | 未移植（Python 侧封闭词表判定；Go 版待做） |
| `cc_attest` | 未移植（信封验证已在 cc_verify 的 attest 形态里复用） |
| `cc_label` | 未移植（IR 校验 + 载体读写） |
| `cc_diff` | 未移植 |
| `cc_replay` | 未移植 |
| `cc_resolve` | 未移植 |

判据锚点是仓内固定向量集（`results/ccos/evidence_verdict_vectors.json`，**28 条**：18 条自包含包
+ 4 条回执 + 6 条信封）：真源（Python 库）、零依赖 Python 复验器（`scripts/nf_verify.py`）、
本 Go 客户端三者对每条的**判定与退出码**必须一致。

## 用法

```bash
# 编译（Go 1.24+；本仓实测 go1.24.5）
cd clients/go && go build ./...

# 复验（形态由文档 schema 判，不看扩展名）
./nfverify --bundle 包.zip
./nfverify --bundle 回执.zip --json
./nfverify --bundle 包.zip --key-file key.bin --revocations revocations.json \
           --anchor anchor.json --at 2030-01-01T00:00:00Z
```

退出码与仓内一致：`0 ok` · `1 invalid` · `2 revoked` · `3 expired` · `4 用法错`
（4 表示输入不是证据容器，**不属于**判定面）。

## 判据（自证）

```bash
cd clients/go && go test ./...
```

`TestVectorsConformance` 逐条跑向量集，任何一条判定或退出码不符即失败；
`NF_VECTORS=<路径>` 可指向异机的向量集副本。

## 只承诺什么

- **承诺**：成员未改（摘要 + 叶复算）、包含证明折叠到根、链头自洽、信封自洽（含 hmac）、
  吊销命中、时效判定；容器面 fail-closed（重名成员/不安全路径/超限成员一律拒收）。
- **不承诺**：内容质量、内容真实性、抗抵赖、以及**其余 6 个 ABI 调用的 Go 实现**（见上表）。
