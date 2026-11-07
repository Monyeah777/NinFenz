# CCOS Go 客户端（`nfverify`）

证据包（`nf-evidence/1`）的 **Go 侧零依赖复验器**：证明 ABI 的 `cc_verify` 不绑定语言。
它不 import 本仓任何 Python 代码，也不联网。

## 为什么要有

`docs/ccos/abi-v0.md` 把「同一份证据、任何实现给出同一结论」当作可证承诺。
判据是仓内那份固定向量集（`results/ccos/evidence_verdict_vectors.json`）：
真源（Python 库）、零依赖 Python 复验器（`scripts/nf_verify.py`）、本 Go 客户端
三者对每一条向量的**判定与退出码**必须一致。

## 用法

```bash
# 编译（Go 1.24+；本仓实测 go1.24.5）
cd clients/go && go build ./...

# 复验一个证据包
./nfverify --bundle 包.zip
./nfverify --bundle 包.zip --key-file key.bin --json
./nfverify --bundle 包.zip --revocations revocations.json --anchor anchor.json \
           --at 2030-01-01T00:00:00Z
```

退出码与仓内一致：`0 ok` · `1 invalid` · `2 revoked` · `3 expired` · `4 用法错`
（4 表示输入不是证据包，**不属于**判定面）。

## 判据（自证）

```bash
cd clients/go && go test ./...
```

`TestVectorsConformance` 逐条跑向量集，任何一条判定或退出码不符即失败；
`NF_VECTORS=<路径>` 可指向异机的向量集副本。

## 只承诺什么

- **承诺**：成员未改（摘要 + 叶复算）、包含证明折叠到根、链头自洽、信封自洽（含 hmac）、
  吊销命中、时效判定；容器面 fail-closed（重名成员/不安全路径/超限成员一律拒收）。
- **不承诺**：内容质量、内容真实性、抗抵赖（时间不可证——见威胁模型 G3）、签名之外的信任链。
