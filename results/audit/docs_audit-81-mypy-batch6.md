---
id: AUD-0033
title: 类型分批收敛第六批（terminal / assemble_plan / asset_ledger / atomic_write 归零）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §三·①「存量复杂度/类型分批收敛」；承接 AUD-0032。开工依据为内部实测（mypy desktop/src 错误条数 68）。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/terminal.py:58713319d677b6450d5c6bf949c77d7c555b8fd9d62e7bfbed2f4f2505e4ea03
  - desktop/src/core/assemble_plan.py:2c73997d32e042ac41ed642e63c9404497925868465f0f1d30b5115672c60f35
  - desktop/src/core/asset_ledger.py:245d911c417e3d37944a834e0a408ddf33b7491803edd7fe5bfaf132e8f8a6ba
  - desktop/src/core/atomic_write.py:6fae42fb839915e37d65e4d499486e2e98987de0f95bf2407e9c3ed45cd6cb6f
  - protocol/code_metrics_baseline.json:267b25adfbb626685f11fad715837b9061464ae1cba45fafedc800f8c7e1320a
---
> 重审（2026-10-14）：收口：长行/导入序/静默跳过理由/风格基线重冻（评审）

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI + 顺序纪律）：重审并更新 digest 机器化

> 重审（2026-10-14 · 数字资产契约 S 档：包自述对账 / Frictionless 导出 / 可移植 schema）：被审对象随本波改动（组合包 INDEX 补登 SYSTEM_CARD 契约 / receipts 锚定面续扩 / CHANGELOG 条目），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · ADR-0006 职能坐标）：被审对象随本波改动（protocol/LAYERS.json 增 roles 段 / core/layer_model.py 由 nf layers --write 联动刷新职能投影 / code_metrics 基线重冻），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · ADR-0006 L11 职能坐标）：被审对象随本波改动（protocol/LAYERS.json 增 roles 段 / desktop/src/core/layer_model.py 接 L11 / docs/layers.md 生成区刷新 / protocol/code_metrics_baseline.json 按工具指引重冻），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects 不含派生物；`protocol/code_metrics_baseline.json` 因 `assemble_plan`/`atomic_write`/`terminal` 行数增长按工具指引评审后重冻。

## 一、内部差距

> 重审（2026-10-14 · 终端基线并发与 argv 唯一性）：被审对象随本轮改动（`baseline_tmp_dir()` 改为按进程唯一；`baseline_argv_issues()` 补 argv 唯一性；基线表 20→19 行）而变，subjects 依「重审并更新 digest」处置——**机械重绑**，既有结论不变。
（开工依据）

- 承接 AUD-0032：`mypy desktop/src` 错误条数 68；本批取 `terminal`（25，最大块）+ `assemble_plan`/`asset_ledger`/`atomic_write`（各 3/3/6）。

## 二、交付

| 模块 | 修前 | 修法 |
|---|---|---|
| `desktop/src/core/terminal.py` | 25 | **根因是四张模块级声明表**（`ZONES`/`FAMILIES`/`FORMS`/`TERMINAL_BASELINE` + `SLASH_WORDS`）无标注，值被推成 `object` 并沿调用面扩散；补 `tuple[dict[str, Any], ...]` 后一次性消掉 17 条。余：`seen`/`history`/`commands` 标注、`self.active_form` 显式可空、两处表单取值改写 |
| `desktop/src/core/assemble_plan.py` | 3 | `questions`/`answers` 参数由 `List[str]` 改 `Sequence[str]`（默认 `()` 合法）；`pkg`/`pipeline` 显式可空；`if pkg is None or not matched` 收窄 |
| `desktop/src/core/asset_ledger.py` | 3 | `_load_for_update` 的 `ledger_path` 如实标 `str \\| None`（函数内本就 `or default_...`）；`issues` 标注 |
| `desktop/src/core/atomic_write.py` | 6 | 读回函数由「`**kwargs` 三元」拆成 binary/text 两分支（消 `open` 重载歧义）；`fcntl` 两行加 `# type: ignore[attr-defined]`（typeshed 平台面） |

## 三、验收证据（本机实测）

- `python -m mypy desktop/src --ignore-missing-imports` → 错误条数 **68 → 31**（四受改模块各自 rc=0）。
- `python -m unittest desktop.tests.test_terminal desktop.tests.test_nf_tui desktop.tests.test_assemble_build desktop.tests.test_asset_ledger desktop.tests.test_atomic_write` → **237 例**（中途一次 1 例红，见下）。
- **过程实证（值得记）**：`terminal` 两处表单取值首版写成 `active.get("answers") or {}`——空字典是假值，`or` 会返回**新字典**，于是 `_answer_form` 的写入不再落回 `self.active_form["answers"]`，`FormTest.test_session_form_flow_executes_after_confirm` 当场判红；改为 `active["answers"] if active else {}`（保留原对象引用）后转绿。这条正是「行为不变」承诺的看门判据。
- `python scripts/code_metrics.py` → 三模块行数增长按工具指引重冻。
- `python scripts/verify_run.py` → **PASS=72 · WARN=0 · FAIL=0**。

## 四、遗留与设计偏差

1. 余 **31 条**（`nf.py`/`scripts` 面与零散 core）；radon 复杂度未动。
2. `atomic_write` 的 `fcntl` 用**两处** `# type: ignore`（仓库首次引入该逃生口）：理由是 typeshed 的 `fcntl` 面随平台收窄，而该分支只在 Unix 执行；已就地写明，不建豁免表。
3. 62 §三·② 余量与 §二·2 .NET 重冻不在本件范围。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑↑ | 四模块 mypy 归零（含最大块 terminal）；237 例单测 + 全量 verify 双绿 |
| 动态可执行 | → | 不涉执行面 |
| 架构纯度 | → | 只改类型写法与取值方式（含一处别名回归的修正） |
| 资产密度 | → | 不新增内容资产 |
| 文档可执行性 | → | 文档未动 |
