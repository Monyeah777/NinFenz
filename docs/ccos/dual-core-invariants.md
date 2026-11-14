# 双核不变量 v0（九双生层 + 自省闭环）

状态：**9 层全覆盖**（每层都有判定判据 + 变异测试），以 `desktop/tests/fixtures/isomorphism_matrix.json` 为唯一数据源。
> **最后更新：2026-11-13（复核）**——9 层/判据形式/自省闭环口径不变；补四处现状：① 矩阵数据件 `covered` = **9 层**，常驻判据 `test_isomorphism_matrix` **11 例**；② 判定面脚本**显式名单 10 个**（`verifier_version.JUDGE_FILES`，新门禁进名单须显式评审）；③ 自省判据在 **`precheck` 23 门快检**里（脚本 `scripts/precheck.py`；`GATES` 23 + `--full` 追加 2 慢门；其中 `verifier_version` 门即本层判据）；④ `results/ccos/self_audit.json` 在场，判定面一改即需重算。见「§现状对照」。

## 这份文档回答什么

双核设计的核心主张是「同一不变量，两核各自证明一次」。这句话很容易写成口号：
两核各自有时相、各自有授权、各自有观测——**看起来**就对上了。

本文档记录的是「哪些层真的对上了、凭什么算对上、怎么证明判据不是摆设」。

## 判据的形式

每一层都必须答出同一句话：**同一份承诺，在两侧指向同一个证据**。
写不出「同一个证据」的层，就不算对齐——这是本仓与「两层都有」式说法的分界线。

## 九层一览

| 层 | 对齐点 | 变异测试证明什么 |
|---|---|---|
| 时相 | `commitment.ts_digest` 两侧须指向同一 token | 改 token 即 digest 不符 |
| 身份 | `cog_digest ↔ state.digest` | 改 state 即 verify 红 |
| 观测 | 回灌记录与契约失败集逐项同序对应 | 改来源 / 改序 / 改证人，三种都红 |
| 语义 | `claim_kind` 单一词表（包 ⇄ registry） | 去掉一个词 / 加一个死词，两种都红 |
| 负空间 | `abstain` 必带 `searched` 检索边界 | 缺边界即拒 |
| 授权 | 终态算子必带 `authority`，且授权方在允许词表内 | 去授权 / 换授权方 / 非对象，三种都红 |
| 资源 | 两本账并列记（`cog_steps` / `cc_cost_ms`） | 混记聚合键 / 缺账 / 负数 / 非整数，四种都红 |
| 对抗 | 反例必带可复算证人（`file` + `case`） | 指向不存在的文件必须红 |
| 自省 | 结论绑定**验证器摘要**（判定面脚本内容摘要） | 改判定脚本字节，摘要必变 |

逐层的判定位置与详细说明见 [isomorphism-matrix.md](isomorphism-matrix.md)；
判据本身分几族、每族怎么失效，见 [judge-families.md](judge-families.md)。

## 自省闭环（第九层为什么特殊）

其它八层判「产物对不对」，自省层判「**判定这套产物的工具变没变**」：

- 发布结论（`nf-release-conclusion/1`）带 `verifier_digest`；
- 摘要来自判定面脚本（10 个门禁脚本）的内容 sha256 折叠；
- 判定面脚本一改，摘要就变 → `results/ccos/self_audit.json` 过期 → 判据红；
- 该判据本身也在提交前自查（**`precheck` 23 门快检**，脚本 `scripts/precheck.py`；`--full` 追加 2 慢门）里，改判定面会立刻红。
  其中 `verifier_version` 门 = 本层判据的常驻位；判定面脚本改而 `self_audit.json` 未重算 → 该门红。

因此「改了工具但没重跑结论」在本仓是一个**会被判红的状态**，而不是靠人记得。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 本文声明 | 复核结果（读到本行时请重跑） |
|---|---|---|
| 层数 | 9 层全覆盖 | **矩阵 `covered` = 9**（时相/身份/观测/语义/负空间/授权/资源/对抗/自省） |
| 常驻判据 | 每层变异测试 | `test_isomorphism_matrix` **11 例** |
| 唯一数据源 | `desktop/tests/fixtures/isomorphism_matrix.json` | **不变**（矩阵测试拒绝未登记的层） |
| 判定面脚本 | 「10 个门禁脚本」 | **`verifier_version.JUDGE_FILES` 恰 10 项**（新增须显式评审） |
| 提交前自查 | 「precheck 23 门」 | **`scripts/precheck.py`：23 门快检 + `--full` 2 慢门**（含 `verifier_version` 门） |
| 自省产物 | `results/ccos/self_audit.json` | **在场**；判定面改动后不重算即红 |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
python scripts/precheck.py --json            # 23 门快检（--full 追加 2 慢门）
python -m pytest desktop/tests/test_isomorphism_matrix.py -q   # 11 例（矩阵 + 逐层变异）
python -m pytest desktop/tests/test_verifier_version.py -q     # 自省层：判定面摘要稳定性
```

- 引用本文时：「同一份承诺，两侧指向同一个证据」= 对齐判据；「覆盖 ≠ 完备」= 边界。
- 数据真源 = 矩阵数据件；层数/层名以 `covered` 实读为准，勿手改生成区。

## 边界（必须写清）

- **覆盖 ≠ 完备**：九层只证明「每层的同一证据可核」，不证明双核整体一致。
- **摘要不覆盖被测代码**：`verifier_digest` 只覆盖判定脚本；被测内容由结论绑定的 HEAD 负责。
- **同构不等于同值**：资源层两侧量纲不同（步数 vs 毫秒），同构点是「两本账都到场且不混记」，不是数值相等。
- **判据会改**：删层、换判定方法都必须显式改矩阵数据件（矩阵测试拒绝未登记的层）。
