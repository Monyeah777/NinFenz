# Benchmark 结果行（`results/bench/results/`）

这里放**真实模型/系统的提交结果行**，每条一个 JSON，schema 见
`protocol/schema/bench_result.schema.json`（`nf-bench-result/1`）。

## 命名与落点

```
results/bench/results/<submission_id 的安全 slug>__<profile>.json
results/bench/evidence/<submission_id 的安全 slug>__<profile>.json   # 原始证据（可由台架重算）
```

- `profile` ∈ `techdoc-strict` / `regulatory-strict`（台架在册 profile）。
- `evidence_path` 必须指向 `results/bench/evidence/` 下的**实际文件**；`contract_digest` 是它的
  `sha256:<hex>`——榜单脚本会现场复算，手改数字必红。
- 数字自洽由榜单脚本复算（`detection_rate == round(detected/cases,4)`、
  `fp_rate == round(false_positives/clean_cases,4)`）；`verdict` 也按台架阈值复算，不采信手填。

## 提交一步

```bash
python scripts/bench_leaderboard.py --write   # 校验全部结果行 + 重生成 results/bench/LEADERBOARD.md
```

没有真实模型结果时**保持空目录**即可：榜单会显式标注「尚无真实模型结果（诚实空榜）」，
不会用台架基线冒充模型成绩。
