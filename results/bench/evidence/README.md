# Benchmark 证据件（`results/bench/evidence/`）

结果行 `evidence_path` 指向这里的**原始证据 JSON**；榜单脚本会现场复算
`contract_digest = sha256:<hex>`，不一致即拒收（手改数字必红）。

约定：

- 一件证据对应一条结果行（`<submission slug>__<profile>.json`，与
  `results/bench/results/` 同名不同目录）；
- 证据内容由台架（`scripts/gate_defect_bench.py`）可复算产出，至少包含台架报告摘要或逐类
  明细；不接受「只有结论没有数据」的纯声明件；
- 提交步骤见 `results/bench/results/README.md` 与 `results/bench/LEADERBOARD.md`。
