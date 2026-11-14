# 稳定性 / 长稳证据（WP-51，G5）

> ⛔ 操作指令：本件是 WP-51 稳定性证据的人读说明；机读真源 `protocol/stability.json`（`nf-stability/1`），判据 `desktop/tests/test_stability_contract.py`，实现 `desktop/src/core/stability.py`，报告 `results/stability/report.json`。**只证明进程内重复/并发确定性，不是长稳 soak**。
> 状态：v1（G5 · 2026-11-15）· 依据：G5 WP-51（稳定性/长稳证据）

## 覆盖的纯管线（7 条）

| ID | 管线 | 摘要对象 |
|---|---|---|
| S-01 | assembly runtime | `nf-assembly-run/1` 渲染 |
| S-02 | output validation | `nf-output-report/1` 渲染 |
| S-03 | delivery | manifest 字节 |
| S-04 | production metrics | `nf-production-metrics/1` 渲染 |
| S-05 | docs claims | `nf-docs-claims-report/1` 渲染 |
| S-06 | AIBOM 导出 | CycloneDX + SPDX 渲染拼接 |
| S-07 | AI 证据链 | 三件样例 + check 结果 |

## 方法

- 每个 check：串行跑 `runs`（默认 5）次 + 4 路并发跑 5 次 → 共 10 个摘要；
- 要求全部逐字节一致、`mismatches=0`（tolerance 0）；
- 报告 committed == 实时重算（check 判据断言）。

## 诚实边界

- **不是长稳 soak**（小时级/外部环境），`scope.soak_hours=false`；
- 不代表真实模型/外部环境稳定，不声称 SLA/可用性；长稳观测属外部操作（OPEN）；
- 若出现 mismatch，先查非确定性来源（时钟/随机/并发共享状态），不加宽 tolerance。

## 复核命令

```bash
python -c "import sys;sys.path.insert(0,'desktop/src');from core import stability as s;s.write('.')"
python -m pytest desktop/tests/test_stability_contract.py -q
```
