# 治理 verify 适配层（WP-31，G3）

> ⛔ 操作指令：本件是 WP-31 治理 verify 适配的人读说明；机读真源 `protocol/governance_adapters.json`（`nf-gov-adapters/1`），判据 `desktop/tests/test_governance_adapters_contract.py`，实现 `desktop/src/core/governance_adapters.py`。缺工具/缺锚必须显式降级，不冒充 T3/T4。
> 状态：v1（G3 · 2026-11-15）· 依据：G3 WP-31（治理 verify：in-toto/Sigstore/RFC3161 适配）

## 适配器注册表

| 编号 | 标准 | 类型 | 本地实现 | 外部工具 | 可用性 |
|---|---|---|---|---|---|
| A-01 | in-toto / DSSE | attestation | `core/trust/dsse.py` | — | **available**（本地可验） |
| A-02 | Sigstore / cosign | signature | `core/trust/keys.py` | `cosign` | **blocked**（工具不在场） |
| A-03 | RFC3161 TSA | timestamp | `core/timestamp.py` | `openssl`/TSA | **external-open**（外部请求未执行，仅离线验 token） |
| A-04 | 透明日志/Rekor | transparency | `core/trust/public_anchor.py` | — | **external-open**（公共锚未提交，仅离线锚校验） |

## 等级计划（`verify_plan`）

- T0：无需适配器；
- T1：A-01（DSSE 本地可验）→ 本机可达 **T1**；
- T2：需 A-03（TSA token）→ 缺 → `degraded=true`、`exit_code=2`、`achievable=T1`；
- T3/T4：需签名/日志/公共锚 → 缺 → 显式 `exit 2`，**不降级冒充**。

## 纪律

- `detect()` 现测工具（与 `results/cq/toolchain.json` 同口径）：声明 available 但工具缺失 → live=blocked；
- 缺适配器 = 不可判定（exit 2），不是通过；
- 外部标准只作接口对齐，**不作质量背书**（STRATEGY §3）；外部提交/见证仍属外部操作（OPEN）。

## 边界

- 本件是「适配层计划与诚实性」；真实签名/TSA/日志请求不在此执行（外部操作）。
- Attachment 模式（WP-32）与治理报告/审计包（WP-33）不在此件。
