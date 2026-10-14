---
id: AUD-0040
title: 复杂度收敛第三批（terminal.dispatch 查表化，55→2）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §三·①「存量复杂度/类型分批收敛」复杂度面；承接 AUD-0039。开工依据为内部实测（radon desktop/src：≥C 317 / ≥D 96 / F 20）。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/terminal.py:58713319d677b6450d5c6bf949c77d7c555b8fd9d62e7bfbed2f4f2505e4ea03
  - protocol/code_metrics_baseline.json:3305cd8bbde70f58a66e89555a4527e846a471d4140ba285cce72db94ea36a02
---
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
> subjects 不含派生物；`protocol/code_metrics_baseline.json` 因 terminal 模块行数增长按工具指引重冻（见「设计偏差」）。

## 一、内部差距

> 重审（2026-10-14 · 终端基线并发与 argv 唯一性）：被审对象随本轮改动（`baseline_tmp_dir()` 改为按进程唯一；`baseline_argv_issues()` 补 argv 唯一性；基线表 20→19 行）而变，subjects 依「重审并更新 digest」处置——**机械重绑**，既有结论不变。
（开工依据）

- `Session.dispatch` 复杂度 **55（F）**：一个 18 分支的 if/elif 链（empty/quit/help/menu/zone/search/commands/map/complete/set/form/cancel/replay/replay-list/history/unknown/run），每加一个意图就要动控制流。

## 二、交付（本批刻意选「消解式」而非「切分式」）

| 面 | 落点 |
|---|---|
| 查表替代分支链 | `_handlers()` 返回「意图 → 处理器」表；`dispatch` 本体只剩 **2** 个判定（表单抢占 + 查表分派） |
| 处理器归一 | `_h_empty`/`_h_quit`/`_h_help` + `_view`（菜单/分区/检索/命令表/地图/补全/重放清单七种只读视图）· `_set_cmd` · `_form_cmd`（含 form/cancel）· `_replay` · `_history_cmd` · `_unknown` · `_run` |
| 横切面抽出 | `_form_preempt`（表单进行中把输入当回答）· `_record`（落历史 + 可重放类别登记）——两者原先都压在 dispatch 尾部 |

## 三、验收证据（本机实测）

- `radon cc desktop/src/core/terminal.py`：`Session.dispatch` **55(F) → 2(A)**；`_handlers` 1(A)；新处理器最大 10（`_run_block`）。
- `radon cc desktop/src`：**≥C 317 → 315 · ≥D 96 → 95 · F 20 → 16**（第三批含前两批累计）。
- `python -m unittest desktop.tests.test_terminal desktop.tests.test_nf_tui` → **189 例全绿**。
- `python scripts/verify_run.py` → **PASS=72 · WARN=0 · FAIL=0**。

## 四、遗留与设计偏差

1. **过程实证（值得记）**：首版漏搬 `set` 意图分支，`/set` 当场落到 run 分支（测试判 `('set', 2) != ('set', 0)`）——查表化重构的典型风险是「表漏项」，本批靠既有 189 例单测兜住。现已把 `set` 补回处理器表。
2. **指标张力（如实记）**：即便用查表，处理器拆分仍使模块行数 2341→2394（+53），已按工具指引重冻。彻底两全需**减少总行数**（合并重复文案/共享渲染），属另一类工程。
3. 余量：`desktop/src` 仍有 **16 个 F**（`interop_export.verify` 168 / `world_model.validate_contract` 105 / `layer_model._rule_issues` 87 …）。
4. 62 §三·②「量化门违反」与 §二·2 .NET 重冻不在本件范围。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑ | 最大降幅一批（dispatch 55→2）；189 例单测 + 全量 verify 双绿 |
| 动态可执行 | → | 不涉执行面（终端分派语义逐条对齐） |
| 架构纯度 | ↑↑ | 「新增意图只加一行」——扩展点从控制流变为数据 |
| 资产密度 | → | 不新增内容资产 |
| 文档可执行性 | → | 文档未动 |
