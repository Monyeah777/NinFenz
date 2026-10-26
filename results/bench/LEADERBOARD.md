# NF Benchmark 榜（gate profile 缺陷注入台）

> 本文件是**生成物**，勿手改：`python scripts/bench_leaderboard.py --write` 生成，`--check` 对账（漂移即红）。
> 台架：`scripts/gate_defect_bench.py`（T5.3，10 类 × 8 负 + 2 正 × profile）；结果行 schema：`protocol/schema/bench_result.schema.json`（`nf-bench-result/1`）。
> 判定阈值：负例检出率 ≥90% 且清洁件误报率 ≤10%（`verdict=pass`）。

## 状态

- 真实模型结果：**0 条** —— 尚无真实模型结果（诚实空榜：不伪造排名、不用基线冒充）
- 台架基线：2 行（**baseline ≠ 模型成绩**；仅标定台架自身口径）

## 模型榜 · regulatory-strict

尚无真实模型结果（诚实空榜）：本 profile 暂无可比的模型提交。

## 模型榜 · techdoc-strict

尚无真实模型结果（诚实空榜）：本 profile 暂无可比的模型提交。

## 台架基线（baseline ≠ 模型成绩）

| profile | 来源 | 负例 | 检出 | 误报 | 检出率 | 误报率 | 判定 | 证据 |
|---|---|---|---|---|---|---|---|---|
| regulatory-strict | baseline | 72 | 72 | 0 | 100.00% | 0.00% | pass | `results/bench/gate_defect_report.json` |
| techdoc-strict | baseline | 80 | 80 | 0 | 100.00% | 0.00% | pass | `results/bench/gate_defect_report.json` |

## 如何提交（目录规范）

1. 把原始证据（台架可复算的 JSON）放 `results/bench/evidence/`；
2. 结果行放 `results/bench/results/<submission slug>__<profile>.json`（schema：`nf-bench-result/1`；`contract_digest` = 证据件 sha256）；
3. 一条命令重生成并自检：`python scripts/bench_leaderboard.py --write`；
   CI/复核用：`python scripts/bench_leaderboard.py --check`（结果与榜面不一致即红）。

> 诚实边界：本榜只聚合**在盘、可复算、数字自洽**的结果行；未提交证据的分数不进榜，
> 台架基线不参与模型排名。
