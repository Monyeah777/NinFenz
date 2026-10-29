# 实验单：判据账本落地后的 code_metrics 基线重冻（2026-10-22）

- 假设：新增 `core/check_registry.py` 与 verify.sh check35 的判据账本段后，`scripts/nf.py`
  与 `desktop/src/core/gate_engine.py` 的模块行数会超过 2026-10-14 冻结值；这些行是
  「判据可核」所需的最小增量，不是复杂度劣化。重冻后棘轮继续「只降不升」。
- 指标：`code_metrics.scan` 的模块行数；重冻前后各文件 `lines / max_fn_lines / max_fn_cc`。
- 阈值：仅允许本次涉及的模块行数上调（`scripts/nf.py` +9、`gate_engine.py` +2），其余
  任何模块不得放宽；函数长度/圈复杂度不得超过 `LIMITS`（120 行 / 25）。
- 回滚点：`git revert <本提交>`（回滚后 code_metrics 基线回到冻结值，判据账本一并回滚）。
