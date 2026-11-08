# 同构判据矩阵 v0（九双生层）

状态：**6 覆盖 / 3 缺失**（截至 2026-11-09，以 `desktop/tests/test_isomorphism_matrix.py` 为唯一数据源）。

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

另有两条结构守卫（不属于同构，但防同一类变形）：

- 桥只允许两类信封（`nf-bridge-commitment/1`、`nf-bridge-obligation/1`），新增通道须显式评审；
- 矩阵自身：每个「已覆盖」条目必须反射到真实测试方法，缺失条目必须点名具体字段。

## 缺失三层：缺的是对象，不是文案

| 层 | 缺什么 |
|---|---|
| 对抗 | 缺 `witness_ref`：反例目前无法被契约核复算成一条 fail witness |
| 资源 | 认知侧 `discourse.budget` 有账实相符校验；验证侧只有阈值，没有逐次记账，两本账缺一本 |
| 自省 | ADR 有 `falsifier`，但没有 `version_chain`（旧版验新版）可核对象 |

## 怎么跑

`python -m unittest desktop.tests.test_isomorphism_matrix`

矩阵是数据 + 反射校验：测试改名/删除会红，覆盖数变化必须显式改矩阵。

## 边界

- 覆盖不等于完备：5 条判据只说明这 5 个层有「同一证据」可核，不说明双核整体一致。
- 判据不产生新真源：全部读既有产物（commitment / registry / control 记录）。
- 同构判据不能替代真实测量：它证明的是「结构对得上」，不是「结论对」。
