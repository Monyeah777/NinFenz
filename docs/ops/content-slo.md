# 内容 SRE：SLI / SLO 口径与实测

> 面向运行的观测面（T11.1）。**只从真实产物采集**：没有数据就记 `UNKNOWN`，不编造、不判绿；
> 已知无数据（真实模型 0 行、M2 记录 0 条）同样不冒充通过。
> 采集实现：`desktop/src/core/content_ops.py`（只读；不写任何既有产物）。
> 复现：`python scripts/nf.py ops report --json`（现场只读扫描约 5 s）；
> 门禁用法：`python scripts/nf.py ops check`（缺源/不可解析/值非法 → 非零退出）。

## 1. 状态语义

| status | 含义 | 门禁行为 |
|---|---|---|
| `OK` | 来源在场、可解析、满足阈值且未过期 | 通过 |
| `WARN` | 来源在场但越阈值，或新鲜度超预算（`reason=stale_source`） | 报告为告警（不因此单独判红） |
| `UNKNOWN` | 来源缺失/不可解析，或**已知无数据** | `check` 对「缺失/坏源/值非法」fail-closed；`no_real_model_rows` / `no_m2_records` / `live_disabled` 不算失败 |

报告顶层 `overall` 取最差：有 `UNKNOWN` → `UNKNOWN`；否则有 `WARN` → `WARN`；否则 `OK`。

## 2. SLI 清单与当前实测（`nf ops report`，2026-10-26 本工作树）

| id | SLI | 口径（真实载体） | 阈值 / SLO | 实测 | status |
|---|---|---|---|---|---|
| `gate_defect_detection_rate` | 门禁缺陷检出率 | `results/bench/gate_defect_report.json` → `overall.detection_rate` | ≥ `thresholds.min_detection_rate`(0.90) 且 `verdict.ok` | 1.0（detected 152 / negatives 152） | OK |
| `gate_defect_fp_rate` | 门禁误报率 | 同上 → `overall.fp_rate` | ≤ `thresholds.max_fp_rate`(0.10) | 0.0（fail_flagged_clean 0） | OK |
| `conformance_passed` | 契约符合面 | `protocol/conformance_report.json` → passed/total + verdict | passed==total 且 verdict=conformant | 1.0（27/27） | OK |
| `receipts_root` | 协议层回执根 | `protocol/RECEIPTS.json` → entries/root | 条数>0 且 root 为 64hex | 69 件（root `f4ad6f73…`） | OK |
| `audit_count` | 审计件数 | `results/audit/*.md` 计数 | >0（新鲜度 ≤90 天） | 57 件 | OK |
| `verify_report_fail` | verify 判据面失败数 | `protocol/verification_report.json` → summary fail+error | ==0 | 0（pass 28） | OK |
| `verify_report_warn` | verify 判据面告警数 | 同上 → summary.warn | ==0 | 3 | WARN |
| `benchmark_real_model_rows` | 真实模型结果行数 | `results/bench/LEADERBOARD.md` 表格中来源≠baseline 的行数 | >0 才判 OK | **0 行**（baseline 2 行） | UNKNOWN |
| `exec_records_m2` | M2 真实执行记录 | `protocol/exec_records/*.json`（排除 `_TEMPLATE.json` 与 `template:true`） | >0 才判 OK | **0 条**（仅模板） | UNKNOWN |
| `registry_index` | 契约注册表索引 | `protocol/registry_index.json` → entries/root | 条数>0 且 root 64hex（新鲜度 ≤30 天） | 111 件（root `ac72feef…`） | OK |
| `concept_index` | 资产本体索引 | `protocol/concept_graph_index.json` → nodes/root | 条数>0 且 root 64hex（≤30 天） | 1306 条（root `7d18bb3c…`） | OK |
| `security_critical` | 内容安全 critical 数 | 现场只读 `core.content_security.scan`（community/ + library/ 等内容面） | critical==0 且 undecidable==0 | 0（findings 7 全为 warn） | OK |
| `modelcheck_verdict` | 模型检查 verdict | 现场只读 `core.model_check.run`（`protocol/WORLD_MODEL.md` 相位图） | verdict==pass | **warn**（2 条不可判定项） | WARN |
| `knowledge_graph_check` | 知识图索引一致性 | 现场只读 `core.concept_index.check` | issues==0 | 0 | OK |

**当前 overall = `UNKNOWN`**（OK 10 · WARN 2 · UNKNOWN 2）——两个 UNKNOWN 是「已知无数据」：
真实模型没跑过、M2 没执行过。这是现实，不是可判绿的通过。

## 3. 新鲜度预算（超预算 → WARN，`reason=stale_source`）

| 来源 | 预算 |
|---|---|
| bench 缺陷报告 / conformance / 回执 / verify 判据面 / 两个索引 | 30 天 |
| LEADERBOARD / 审计件 / M2 执行记录 | 90 天 |

## 4. 未覆盖（如实声明）

- **无生产流量**：本仓是离线工具链，SRE 面是 on-demand 采样，不是连续监控/告警分页。
- **无真实模型执行**：benchmark 真实模型 0 行、M2 记录 0 条（模板不算证据；不伪造）。
- **无长期窗口**：没有 7d/30d SLO 达成率历史，也没有多版本趋势。
- **安全面范围**：只含内容供应链扫描（注入/可执行内容/凭据/结构），不含主机、依赖漏洞、运行时 RCE 面。
- **模型检查**：含「不可判定项」时 verdict=warn（不判 pass）；不可判定本身不是缺陷，但也不能当通过。
- **无成本/延迟 SLI**：本地离线执行，无请求级时延/成本可观测。
