# 评测效度协议（EVAL PROTOCOL）

> ⛔ 操作指令：本件是评测效度规则的人读面；机读真源 `protocol/eval_validity.json`（`nf-eval-validity/1`），具体预注册协议 = `protocol/eval/protocol.json`，判据 `desktop/tests/test_ai_eval_contract.py`。改规则必须同步真源。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §3A D15（BL-05）
> 纪律：只计数不打分；内部**永不产出盲评 pass**；指标必须挂反指标（防 Goodhart）；不钉死当前 kappa 数值（现算）。

## 预注册（跑前冻结）

- 协议必须含字段：schema / version / registered_at / question / conditions / tasks / dimensions / samples_per_task / analysis_plan / prohibitions / frozen_before_run。
- `frozen_before_run=true` 才允许录数据；跑完再改协议 = 新协议 + 新版本号（不原地改）。
- 机检入口：`desktop/src/core/eval_harness.py::validate_protocol`（本仓的 `protocol/eval/protocol.json` 必须过）。

## 样本量与统计口径

- `min_samples_per_task=3`；样本 <3 只报描述统计，**不做差异/显著性宣称**。
- 统计口径只写「计数差 + 中位数」，不给 p 值、不做显著性宣称（见具体协议 `analysis_plan`）。

## inter-rater（评分者一致性）

- 方法：Cohen's kappa；两名评分者对同一批样本独立盲评；`min_kappa=0.6`。
- 低于阈值 ⇒ 盲评不可用，重训/重采，不得继续拿它当证据。
- 样本：`results/eval/interrater_sample.json`；现算入口：`desktop/src/core/eval_validity.py::interrater`（示例数据，不冒充真实外部盲评）。

## 反指标（countermetrics）

| 编号 | 防什么 | 反指标 | 证据 |
|---|---|---|---|
| CM-01 | 被菜单/框架窄化 | `table_external_mechanisms`（表外新机制数，越低越可能被窄化） | `protocol/eval/protocol.json` |
| CM-02 | 内部自评自嗨 | 盲评与门禁交付**分两份报告、不合并** | `protocol/eval/protocol.json` |
| CM-03 | 计数/覆盖率 Goodhart | 结果指标 + 抽样人工复核 + 反指标趋势 | `docs/eval/EVAL_PROTOCOL.md` |

每个指标必须挂一个存在的反指标（机检）；反指标不参与奖励/排序。

## 指标 → 反指标映射

| 指标 | 反指标 |
|---|---|
| ME-01 frame_change | CM-01 |
| ME-02 assumption_explicit | CM-01 |
| ME-03 counterexample_quality | CM-02 |
| ME-04 coherence | CM-02 |
| ME-05 depth | CM-02 |
| ME-06 deliverable | CM-03 |
| ME-07 table_external_mechanisms | CM-01 |

## 效度威胁

| 编号 | 威胁 | 检查 | 证据 |
|---|---|---|---|
| VT-01 | Goodhart：指标变目标 | 每个 metric 挂反指标；反指标不参与奖励/排序 | `protocol/eval_validity.json` |
| VT-02 | 预注册后挑指标/改协议 | frozen_before_run=true；改协议走新版本号 | `desktop/src/core/eval_harness.py` |
| VT-03 | 评分者一致性未测 | Cohen's kappa ≥0.6（样本现算） | `results/eval/interrater_sample.json` |
| VT-04 | 样本量不足却宣称差异 | min_samples_per_task=3；不足只描述统计 | `protocol/eval/protocol.json` |
| VT-05 | 自评打分写回运行时 | no_scoring 恒真（ADR-010） | `protocol/trust/verify.schema.json` |

## 与具体评测协议的关系

- `protocol/eval/protocol.json` 是本仓一次具体预注册（菜单/方法包/工作台四条件 × 4 任务 × 3 样本），必须满足本协议的预注册与反指标规则；改它 = 改版本号并重冻。
- 本协议只定**效度规则**，不写具体任务提示词（那属于具体协议）。

## 复核命令

```bash
python -m pytest desktop/tests/test_ai_eval_contract.py -q
python -c "import json;d=json.load(open('results/eval/interrater_sample.json',encoding='utf-8'));print(len(d['items']))"
```
