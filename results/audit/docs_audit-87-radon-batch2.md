---
id: AUD-0039
title: 复杂度收敛第二批（decisions/endpoint 两 F 拆净，≥C −2 · ≥D −3）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §三·①「存量复杂度/类型分批收敛」复杂度面；承接 AUD-0037。开工依据为内部实测（radon desktop/src：≥C 319 / ≥D 99 / F 20）。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/decisions.py:0aba977ce21067d5ca9e60d64e48160c1d0cd0f237da7441384882598550abb8
  - desktop/src/core/endpoint.py:118113277f5a325434470516507fd932e28188c52610d340f667745163265e6f
  - protocol/code_metrics_baseline.json:d41261e1f6a3de30120cf123a0ff5d13dd971071a62de18994d1c284b9d67463
---
> 重审（2026-10-14 · ADR-0006 职能坐标）：被审对象随本波改动（protocol/LAYERS.json 增 roles 段 / core/layer_model.py 由 nf layers --write 联动刷新职能投影 / code_metrics 基线重冻），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · ADR-0006 L11 职能坐标）：被审对象随本波改动（protocol/LAYERS.json 增 roles 段 / desktop/src/core/layer_model.py 接 L11 / docs/layers.md 生成区刷新 / protocol/code_metrics_baseline.json 按工具指引重冻），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。


> 重审（2026-10-14 · ADR-0006）：`decisions.py` 的模块自述按「取代链互指由测层常驻判」更正（**行数不变**，仅同一行换文案，函数拆法未动），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects 不含派生物；`protocol/code_metrics_baseline.json` 因两模块行数增长按工具指引重冻（见「设计偏差」）。

## 一、内部差距（开工依据）

- `decisions.scan` 复杂度 **48（F）**：单函数内混了「单条目四类校验 + 取代链 + 反向引用」三件事。
- `endpoint.scan` 复杂度 **59（F）**：单函数内混了「契约头 + 逐端点四类校验 + 幂等例外」。

## 二、交付

| 模块 | 拆法 | 结果 |
|---|---|---|
| `decisions.py` | 抽出 `_check_entry_id` / `_check_required_fields` / `_check_sections` / `_check_entry_fields` / `_check_entry_evidence` / `_check_entry_lifecycle` / `_check_supersede_chains` / `_check_supersedes` | `scan` 48(F) → **无 ≥C 函数**（最大 10） |
| `endpoint.py` | 抽出 `_check_ep_basics` / `_check_ep_maps_to` / `_check_deprecated_marked` / `_check_ep_deprecated` / `_check_idem_mode` / `_check_idempotency_exceptions` / `_scan_endpoints` / `_check_contract_header` / `_load_ep_tools` / `_ep_stats` | `scan` 59(F) → **无 ≥C 函数**（最大 9） |

## 三、验收证据（本机实测）

- `radon cc desktop/src`：**≥C 319 → 317 · ≥D 99 → 96 · F 20 → 17**。
- 逐模块 radon：`decisions.py` / `endpoint.py` 均**无 ≥C 函数**（前值 48 / 59）。
- `python -c "from core.endpoint import scan; ..."` → **issues 空**（端点契约门禁行为不变）。
- `python -m unittest`（decisions / decision_layer / governance_faces 等）→ 除**待重签的 conformance 报告**两例外全绿；重签后本批以全量 verify 判。
- `python scripts/verify_run.py` → **PASS=72 · WARN=0 · FAIL=0**。

## 四、遗留与设计偏差

1. **顺带修掉一处真缺陷**：`_scan_endpoints` 初版把 `ids` 留在原函数作用域，`_check_idempotency_exceptions` 引用成未定义名（`NameError`）——由本机直跑 `endpoint.scan` 当场抓出，已改为显式返回 `ids`。
2. **指标张力（如实记）**：拆函数必然**增加模块行数**（185→231 / 146→207），已按工具指引重冻。要同时压「模块行数」与「函数复杂度」，只能做**消解式**重构（合并分支/改查表），不能只切分——下批优先选后者。
3. 余量：`desktop/src` 仍有 **17 个 F**（`interop_export.verify` 168 / `world_model.validate_contract` 105 / `layer_model._rule_issues` 87 …）。
4. 62 §三·②「量化门违反」与 §二·2 .NET 重冻不在本件范围。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑ | 复杂度降幅可量（≥C −2 / ≥D −3）；verify 双绿 |
| 动态可执行 | → | 不涉执行面（判定语义逐条对齐；端点门禁直跑空 issues） |
| 架构纯度 | ↑ | 单函数不再混三件事，边界按「面」切开 |
| 资产密度 | → | 不新增内容资产 |
| 文档可执行性 | → | 文档未动 |
