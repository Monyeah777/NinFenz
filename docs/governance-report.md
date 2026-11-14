# 治理报告与审计包（WP-33，G3）

> ⛔ 操作指令：本件是 WP-33 治理报告/审计包的人读说明；机读真源 `results/governance/{report,audit}.json`（`nf-gov-report/1` / `nf-gov-audit/1`），判据 `desktop/tests/test_governance_report_contract.py`，实现 `desktop/src/core/governance_report.py`。committed 必须 == 实时重算（check51 守）。
> 状态：v1（G3 · 2026-11-15）· 依据：G3 WP-33（治理报告/审计包 + 判别门禁）

## 内容

- **report**：各级 `achievable/ok/missing/exit_code`（T0–T4）、适配器状态（available/blocked/external-open）、附件模式（阻塞/min_level）、契约状态词表、SELF_AUDIT p0、独立性 forbidden_edges、OPEN（带 owner）、claims 边界。
- **audit**：7 项审计 check（适配器/契约/附件注册表、SELF_AUDIT、边界、T3-T4 不冒称、附件独立性）+ 证据路径 + 汇总 + OPEN。

## 诚实规则

- 报告只**复算**既有事实，不新造结论；
- T3/T4 缺适配器 → `ok=false`、`missing` 非空、`exit_code=2`；**声称可达即红**（check51）；
- OPEN 项必须有 owner；外部标准不作质量背书。

## 复核命令

```bash
python -c "import sys;sys.path.insert(0,'desktop/src');from core import governance_report as g;g.write('.')"
bash verify.sh --checks-only   # check51：committed==live + 审计 7/7 + 等级诚实
python -m pytest desktop/tests/test_governance_report_contract.py -q
```

## 边界

本件只汇总治理面事实；治理 verify 适配（WP-31）与附件模式（WP-32）的语义不在本件重复定义。
