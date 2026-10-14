---
id: AUD-0035
title: 类型收敛扩面到 scripts（19 条清零，8 个脚本）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §三·①「存量复杂度/类型分批收敛」；承接 AUD-0034（desktop/src 已清零）。开工依据为内部实测（mypy scripts 错误条数 19）。
verdict: pass
auditor: 本轮执行者
subjects:
  - scripts/rebuild_selfcontained_sample.py:51732ee527c918a6ee2effe4236fb3702ceb474ebed4856ea6aa2ee0c059e5d2
  - scripts/fde_sample_run.py:2826c24da2e3a0e771918eb7fdd56a14e57c893ec4ddaa739f56046a97316d6f
  - scripts/serve_decision_model.py:bbb36dff0e3816c2253150b7de6ab619877c3c78269a644c4c966083df15afee
  - scripts/interop_thirdparty_kit.py:803def645cab2f98a6ef27eed82a8463dcc4ed908b7885c9944158771d3d8900
  - scripts/build_verification_cards.py:14c51ad8b2ba87abcbe1f42ece6feb4cba2a3f77b65736959bea0d5b569b4488
  - scripts/geo_export.py:6ff73fdbd8d6ecd7bb6add47c79cba31dfd76c86ae1c7984824ba4e6f28d8eca
  - scripts/nf.py:97aadeb530bd78fd9cc206ed96d45eab75a61e7f3167fefcb0bc774536cb6257
  - scripts/check_external_links.py:1cbee65ba19a83fbcdf333e35b8d99c2e45f3b400f3a025860357baf7a806b02
  - protocol/code_metrics_baseline.json:3305cd8bbde70f58a66e89555a4527e846a471d4140ba285cce72db94ea36a02
---
> 重审（2026-10-14）：引入 nf audit rebind 命令（core/audit.py + CLI + 顺序纪律 + 两处面收敛）

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI + 顺序纪律）：重审并更新 digest 机器化

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI）：重审并更新 digest 口径机器化，替换手搓脚本

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
> subjects 不含派生物；`protocol/code_metrics_baseline.json` 因 4 个脚本行数或圈复杂度增长按工具指引重冻。

## 一、结果

`python -m mypy scripts --ignore-missing-imports` 错误条数 **19 → 0**。

## 二、交付

| 脚本 | 修法 |
|---|---|
| `scripts/nf.py` | ① `argparse._`/`ngettext` 两处**有意猴补**补 `# type: ignore[attr-defined(,assignment)]`（原 ignore 只盖 assignment）；② daemon bench 的 `rows` 显式 `List[Dict[str, Any]]`；③ `signal.SIGPIPE` 改 `getattr(..., None)` 判空（Windows 无该信号，原靠 except 兜住，行为等价） |
| `scripts/check_external_links.py` | `breaker` 参数如实标 `Optional[DomainBreaker]`（函数内已 `breaker=None 即不熔断`）；报告接收端显式 `Dict[str, Any]`——7 条一并消 |
| `scripts/rebuild_selfcontained_sample.py` | 标记行改为显式循环取 `group`（消 `Match\\|None`）；管线段收尾围栏变量 `cl`→`close_idx`（与上文同名变量解耦） |
| `scripts/fde_sample_run.py` | `module_from_spec` 前补 `spec is None` 守卫（带修复指引） |
| `scripts/serve_decision_model.py` | 进程内单例 `AGENT: Any = None`（加载前恒为 None，`predict` 前由 500 兜底） |
| `scripts/interop_thirdparty_kit.py` | 循环变量 `e`→`ent`（避开同函数 `except ... as e` 的变量删除语义） |
| `scripts/build_verification_cards.py` | 基线两处 `re.search` 结果判空（缺常量即带修复指引退出） |
| `scripts/geo_export.py` | 绑定行显式 `List[Dict[str, Any]]` 后再排序（消 `object` 算术） |

## 三、验收证据（本机实测）

- `mypy scripts` 错误条数 **19 → 0**。
- `python -m unittest`（本批相关 4 组）→ **65 例全绿**。
- `python scripts/code_metrics.py` → 4 脚本按工具指引重冻。
- `python scripts/verify_run.py` → **PASS=72 · WARN=0 · FAIL=0**。

## 四、遗留与设计偏差

1. `desktop/tests` 仍有 66 条 mypy（测试面，未纳入本线）；radon 复杂度仍为存量。
2. `nf.py` 的两处 `# type: ignore` 是**猴补 stdlib** 的必要逃生口（模块级补丁，typeshed 不可能知道）；已在**紧邻注释**里写明短路理由，不建豁免表。
3. 62 §三·② 余量与 §二·2 .NET 重冻不在本件范围。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑ | `scripts` mypy 归零；65 例单测 + 全量 verify 双绿 |
| 动态可执行 | → | 两处守卫收窄到原路径，信号分支语义等价 |
| 架构纯度 | → | 只改类型标注/取值方式 |
| 资产密度 | → | 不新增内容资产 |
| 文档可执行性 | → | 文档未动 |
