# v2 增量补丁应用记录（D21–D24 / Free-Pro-CCOS / zero_slice）

> 输入：`NF-APP-v2-增量补丁-SelfContained-2026-11-19.md`；v2 Complete 基线继续有效。
> 本件只记录“增量补丁”的落地，不重写 v2 已派发内容。

## 已应用

| 增量 | 落点 | 证据 |
|---|---|---|
| D21–D24 | `app/docs/DECISIONS.md` | 四条决策表 + 落地链接 |
| Free/Pro/CCOS 边界 | `app/docs/FEATURES.md` | Free 永不锁 / Pro 加深度 / CCOS 执行面 |
| FeatureGate 空实现 | `app/android/.../data/FeatureGate.kt` | 默认 `FREE`；Pro/CCOS 关闭不锁 Free；`allows()` 全开 |
| WP-0.9 zero_slice 原型 | `app/prototypes/zero_slice/` | 附录 P 全文落盘；14 测试；夹具与结果 |
| S18 Free/Pro/CCOS 自扫描 | 本件 + FeatureGate 测试 | 默认全开，不误锁 |
| S19 机制采用证据 | 本件 | 仅 WP-0.9 原型；其余 M 原型 OPEN |

## zero_slice 实测

- `python -m unittest -v test_zero_slice.py` → **14/14 OK**（`app/prototypes/zero_slice/results/unittest.log`）。
- 真实简报 + 匹配 spec → **4/4 节映射，coverage 100%**（`results/brief-mapping.json`）。
- 不匹配 spec → 全部内容进 `exceptions`，coverage 100%（`results/brief-mismatch.json`）。
- 无 spec 自由稿 → 1 节 1 槽，coverage 92.12%（`results/brief-freeform.json`）。
- 语义：EMPTY→SOURCE→PREVIEW→MAPPING→DRAFT；`reset(current|all)` 后不自动恢复；同源草稿覆盖不生成 `-2`；`undo()` 内存快照；`to_project()` 出 `nf-project/1`。

## i18n 修复（2026-11-21）

- `BatchAssembler` 与 `ImportScreen` 的硬编码中文移入 `strings.xml` / `values-en`。
- `python -m pytest app/tests/test_ui_strings_localized.py -q` → 1 passed。
- 全量 `python -m pytest app/tests -q` → **501 passed**。

## J6 nf-doc/1

- 新增 `app/schema/nf-doc.schema.json` 与 `NfDocModel`（blocks 保留章节/表格/代码/来源）。
- 批量装配为每个成功项目写 `.nf-doc.json`；多成功另写 `merged.nf-doc.json`。
- 交付台新增 `nf-doc` 导出按钮（`NfDocExporter`），可直接得到可再装配的结构化文件。
- `NfDocMerger` 合并：同名章节保留双方、重复块去重、冲突写入 manifest `doc_conflicts`。
- Settings 新增「合并 nf-doc」：选择 2+ 文件、合并、查看冲突、分享结果。
- 冲突可逐项选择「保留左/右/双方」；选择后保存/分享。
- 按章节裁剪（只删某段）仍 OPEN。

## A0-14 Daily 入口

- 库首屏常驻「粘贴一段，直接成稿」输入卡；提交后用 `ImportSeed` 一次性交给导入页。
- 不自动恢复旧预览；进程死亡不保留 seed。
- 保留快速粘贴（剪贴板）与导入向导。

## A0-8 草稿→项目映射

- `ImportPrefill.bySlotName` 把导入槽位 ID 映射到 spec 槽位名，再与协议字段 `label` 精确匹配。
- 优先级：草稿 → 直接字段 ID → 槽位名 → 模板示例 → 默认值。
- 单测覆盖；映射仍是精确名匹配，不做相似度猜测。

## 未完成 / OPEN

| id | 内容 | owner | next |
|---|---|---|---|
| M-P0 | Phase M P0 原型 M1/M2/M4/M12/M15/M24/M25/M35/M38 | lead | 逐个原型+负例；通过后再进 Rust/Kotlin |
| S19 | 机制采用证据仅 zero_slice | lead | 每新增 M 原型补测试/负例/OPEN |
| ANDROID | FeatureGate 尚未被 UI 调用（当前无计费面） | kotlin-ui | 引入 Pro 时再接入口；不得锁 Free |

## 判定

增量补丁的 **WP-0.9 + 分层空实现** 已落地；v2 主体（P0/A–G）继续按既有结果执行。未把 Phase M 全量实现写成已完成。
