# 同构判据矩阵 v0（九双生层）

状态：**9 覆盖 / 0 缺失**（截至 2026-11-09，以 `desktop/tests/fixtures/isomorphism_matrix.json` 为唯一数据源）。

本件是**判定细节**；九层的整体结论与自省闭环见 [dual-core-invariants.md](dual-core-invariants.md)。

## 为什么需要它

双核设计里最容易骗自己的一句话是「两侧都有这一层」。两核各自有时相、各自有授权、各自有观测——看起来对齐了，
实际上可能一个用 TSA token、一个用本地时钟，一个查权限表、一个凭自觉。

同构判据只认一种对齐：**同一份承诺，在两侧指向同一个证据**。写不出「同一个证据」的层，就是没对齐。

## 判据表

| 层 | 判据形式 | 判定位置 | 变异测试（能被改坏打死） |
|---|---|---|---|
| 时相 | `commitment.ts_digest` 两侧须指向同一 token；改 token 即 digest 不符 | `test_cognition_bridge` | `test_commitment_binds_timestamp_reference`（改 token 即 digest 不符） |
| 身份 | `cog_digest ↔ state.digest`；discourse 变了即红 | `test_cognition_bridge` | `test_verify_detects_state_change`（改 state 即红） |
| 观测 | 回灌记录与契约失败集逐项同序对应，且 `witness_digest` 可复算 | `test_cognition_bridge` | `test_observation_correspondence_can_be_killed`（改来源/改序/改证人） |
| 语义 | 方法包 `claim_kind` 必须来自 `protocol/criteria/registry.json` 的单一词表；死词也红 | `test_method_pack` | `test_vocabulary_check_can_be_killed`（去词/加死词） |
| 负空间 | `abstain` 必须带 `searched` 检索边界；缺边界即拒 | `test_cognition_control` | `test_abstain_requires_search_boundary`（缺 searched 即拒） |
| 授权 | 终态算子（stop / abstain）必带 `authority`，且授权方在允许词表内 | `test_cognition_control` | `test_authority_check_can_be_killed`（去授权 / 换授权方 / 非对象） |
| 资源 | 两本账并列记（`cog_steps` / `cc_cost_ms`），混记聚合键即红 | `test_cognition_bridge` | `test_resource_accounting_can_be_killed`（混记 / 缺账 / 负数 / 非整数） |
| 对抗 | 反例必须带可复算证人（`file` + `case`）；给 root 时还核对文件真在场 | `test_cognition_workspace` | `test_counterexample_witness_file_must_exist`（指向不存在的文件必须红） |
| 自省 | 结论绑定**验证器摘要**（判定面脚本内容摘要）；摘要陈旧即红 | `test_verifier_version` | `test_digest_changes_when_a_judge_file_changes`（改脚本字节摘要必变） |

另有两条结构守卫（不属于同构，但防同一类变形）：

- 桥只允许两类信封（`nf-bridge-commitment/1`、`nf-bridge-obligation/1`），新增通道须显式评审；
- 矩阵自身：每个「已覆盖」条目必须反射到真实测试方法，缺失条目必须点名具体字段。

## 缺失层（当前为空）

九层都已覆盖。**注意**：覆盖 ≠ 完备——每层只证明「同一证据可核」，不证明双核整体一致；
新增层或替换判定方法时，必须先在这里显式登记（矩阵测试会拒绝未登记的层）。

## 怎么跑

`python -m unittest desktop.tests.test_isomorphism_matrix`

矩阵是数据 + 反射校验：测试改名/删除会红，覆盖数变化必须显式改矩阵。

## 边界

- 覆盖不等于完备：5 条判据只说明这 5 个层有「同一证据」可核，不说明双核整体一致。
- 判据不产生新真源：全部读既有产物（commitment / registry / control 记录）。
- 同构判据不能替代真实测量：它证明的是「结构对得上」，不是「结论对」。
