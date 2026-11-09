# 领域方法包 v0（十一个域）

状态：**11 个域 / 65 个专家动作 / 31 个证据类目**（截至 2026-11-09，以 `protocol/method_packs/index.json` 为唯一真源）。

## 它是什么

方法包把「某个专业领域里，专家实际会做哪几件事」写成可核结构：每个动作带 `id` / `name` / `why` / `maps_to`，
每类主张带 `claim_kind` 与「必须给出什么证据」。包不是清单模板，也不是评分表——它只描述动作与证据要求。

## 十一个域

| 域 | 方向 | 动作数 | 证据类目 | 可跑入口 |
|---|---|---|---|---|
| `watermarking` | 内容可追溯（水印/鲁棒性/容量） | 5 | robustness / capacity / detectability | `nf sig` / `nf attest` |
| `evidence-audit` | 证据充分性与闭合 | 5 | closure / verification | `nf evidence verify` |
| `metacognition` | 想得对不对（校准/控制） | 5 | calibration / control_effect | `nf cog calibrate --pairs … --json` |
| `evaluation-design` | 测得出吗（效应/成本/可靠性） | 7 | efficacy / cost / reliability | `nf stats` / `nf bench run` |
| `prompt-injection-defense` | 输入可信吗（防御/审计/最小权限） | 7 | defense-efficacy / audit-trail / least-privilege | `nf check`（红队 cases） |
| `data-provenance` | 数据能不能用（说明书/字段/许可） | 6 | data-fit / license / non-leakage | `nf asset ledger` / `nf asset verify` |
| `resilience` | 坏了会怎样（半径/演练/回滚） | 6 | blast-radius / drill / recoverability | `nf doctor` / `nf audit` |
| `handoff` | 换人能不能接（帧/承诺/分离） | 6 | handoff / commitment / separation | `nf cog replay` |
| `privacy` | 守不守规矩（最小化/留存/同意） | 6 | data-minimization / retention / consent | `nf doctor` / `nf evidence verify` |
| `supply-chain` | 交付物从哪来（钉定/可复现/溯源） | 6 | pinning / reproducibility / provenance | `python scripts/sbom.py --check` |
| `operations` | 坏了能不能知道（目标/信号/告警） | 6 | slo / error-budget / incident-review | `python scripts/perf_budget.py --list` |

## 三种用法

1. **看**：`nf cognition --packs-list` 列出域与摘要；
2. **照着做**：`nf cognition --pack-checklist handoff` 把包展开成逐步清单（每动作一条 + 该域证据要求）；
3. **编进主张**：`nf cog claim --pack <ID>` 让主张带上该域的证据义务（缺证据即未就绪）。

三种用法都不评分、不排序；排序只按包内顺序。

## 纪律

- **动作必须有真实锚点**：`test_method_pack` 要求每个动作的 `id` 能指到仓库里的文件 + 关键词，
  指不到就必须写成显式 `CONCEPTUAL` 声明（不允许「看起来像有实现」）。
- **词表单一**：所有 `claim_kind` 必须来自 `protocol/criteria/registry.json` 的 `claim_kinds`，
  新增词先登记，否则判据红（新域不会静默绕过）。
- **包不等于判据**：包说明「该做什么」，判据说明「做了没有」。两者缺一，方法就会退化成口号。

## 边界

- 八个域不等于「完整方法论」：它们只覆盖本仓真正实践过的方向，未实践的域不应先写包。
- 每个动作的 `why` 是可错的断言，不是权威引文；有反例时改包，不要改判据去迁就包。
