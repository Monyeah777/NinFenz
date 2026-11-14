# Trust 见证面规格（T3：STH + witness）

> 状态：G4 规格件（2026-11-14）。机器可读校验在 `desktop/src/core/trust/anchor.py` 与 `desktop/tests/test_trust_t3.py`；
> 本文只固定「签什么 / 怎么数 / 什么不算」的口径，不承诺外部 witness 网络的可用性。

## STH 语句

STH 锚（`nf-anchor/1` 的 `transparency-sth`）签的是域分隔摘要：

```
sth_statement = domain_digest("nf:anchor:v1:sth",
                              canonical({log_id, tree_size, root}))
signature     = base64(verifier(log_id)(sth_statement_bytes))
```

- `root` 必须是目标摘要（bundle 规范摘要）；`tree_size` 必须 ≥1；
- 验签材料按 `log_id` 解析（`make_sth_verifier`）；缺材料 = 不可判定（none），不是通过。

## witness 语句

witness 锚签的是：

```
witness_statement = domain_digest("nf:anchor:v1:witness",
                                  canonical({schema:"nf-anchor-witness/1",
                                             target_digest, witness_id, keyid}))
```

- witness 必须绑定目标摘要 + 自己的 witness_id/keyid（防跨对象复用）；
- 验签材料按 keyid 解析（`make_witness_verifier`）。

## 阈值与等级

- `policy.anchors.witness_threshold` 是**有效 witness 数下限**：不足时 `transparency_sth` 记 none（不可判定），
  不是「差一点通过」；
- T3 需要同时满足：签名（T1）、RFC3161 时间戳（T2）、STH 有效、witness 数 ≥ 阈值；
- T4 需要公共锚（Sigstore/Rekor/公共 TSA）——本仓未建，报告必须给 `PUBLIC-ANCHOR-MISSING` 并 exit 2。

## 不做 / 不声称

- 本仓不运营公共 witness 网络；`nf-anchor-witness/1` 是**本仓约定语句**，外部 witness 需按此签名才可互验；
- 不把「同一密钥集的两个视图」当外部见证；分叉检测（`key_transparency.split_witness`）不能替代独立见证；
- 不声称 T4：无公共锚时 any 报告写 T4 都是过度声明。
