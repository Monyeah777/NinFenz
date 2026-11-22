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
- 全量 `python -m pytest app/tests -q` → **520 passed**。

## J6 nf-doc/1

- 新增 `app/schema/nf-doc.schema.json` 与 `NfDocModel`（blocks 保留章节/表格/代码/来源）。
- 批量装配为每个成功项目写 `.nf-doc.json`；多成功另写 `merged.nf-doc.json`。
- 交付台新增 `nf-doc` 导出按钮（`NfDocExporter`），可直接得到可再装配的结构化文件。
- `NfDocMerger` 合并：同名章节保留双方、重复块去重、冲突写入 manifest `doc_conflicts`。
- Settings 新增「合并 nf-doc」：选择 2+ 文件、合并、查看冲突、分享结果。
- 冲突可逐项选择「保留左/右/双方」；选择后保存/分享。
- 合并结果可展开块列表、删除单块；删除后保存/分享。
- 块可上下移动/删除；跨章节拖拽仍 OPEN。

## Markdown 块类型修正

- 有序列表只认 `1. `/`1) `，不再把「2026 年…」误判为 list。
- Kotlin + Rust 同步；各加一条回归测试。

## M12 Constraint Satisfiability/MUS（P0 原型）

- `app/prototypes/mus/mus.py`：min/max、required/forbidden_empty、must_include/must_avoid 的不可满足判定。
- 穷举最小不可满足子集（MUS），不返回非最小超集。
- 8 条 unittest；pytest wrapper 纳入全量。
- **未**进 Rust/Kotlin/UI。

## M6 Constraint Lens（P0 部分）

- 槽位分配时显示当前字数/maxChars；超长/必填/最小字数/前后缀/pattern 不满足则标红并禁用。
- 分配前按 kind 清洗并截到 maxChars。
- 未做就地编辑/约束面板联动。

## M2 Progressive Formalization（P0 部分）

- 预览块编辑器对短段落/引用给「这像主题句，要变成槽位吗？」提示。
- 可「形式化」进入现有槽位分配，或「忽略」。
- 启发式仅按类型/长度，不判断语义；导出不要求先形式化。

## M1 Flash Fill（P0 原型）

- `app/prototypes/flash_fill/flash_fill.py`：前缀/后缀/去前缀/去后缀/替换/截断白名单。
- 9 条 unittest；pytest wrapper 纳入全量。
- 预览块编辑器新增「批量变换」：replace/加前缀/加后缀/截断 四种模式，可撤销/重做。
- 「从本次修改推断」：只改一个块时合成前后缀/去前后缀/替换/截断，并批量应用。
- 可「保存为变换」到项目；再次进入可「应用已保存变换」。
- **未**进 Kotlin/Rust 推理引擎；UI 只覆盖 replace 一种白名单变换。

## M25 Capability-Scoped Sharing（P0 部分）

- `ShareRedactor`：分享前移除 HTML 注释与 source/来源 行。
- 交付台「脱敏分享」按钮；不是权限/期限控制。

## M35 Content Contract（P0 部分）

- 交付台验收清单：L1 通过 / 必填槽位已填 / 至少一次导出。
- 全绿后可本地签收，`ContractStore` 落盘 accepted + signed_at + 导出物 sha256。
- 归档包存在签收时附带 `contract.json` 并纳入 manifest。
- **不是**密码学签名；导出物哈希变化时页面显示签收失效并要求重签。
- 无变更单/异议/多方评审。

## M38 Preservation（P1 部分）

- `PreservationExporter`：document.md + document.nfdoc.json + preservation.json（SHA-256/bytes）。
- Zip 固定时间，可复算；交付台「preserve」按钮导出。
- `PreservationVerifier` 校验 schema/条目/字节数/sha256；导入页「校验归档包」按钮。
- 解压前限制条目数/单文件 20MB/总量 40MB，防 zip 炸弹。
- 校验通过后可「恢复为导入稿」（document.md → ImportScreen），不直接写项目。
- **未**做 OAIS 迁移/版本升级链/外部校验工具对接。

## M4 Semantic Patch（P0 部分）

- 新增 `nf-patch/1` schema（replace/insert/delete/move/set-slot）。
- Kotlin `NfPatchModel`：解析、blockId 应用、稳定 ID；set-slot 写入槽位映射；4 条单测。
- 新增 Settings「应用 nf-patch」页：粘贴 Markdown+JSON，逐条勾选，应用/复制结果。
- 交付台入口带 projectId：自动载入 DeliveryDraftStore 的当前稿，应用后可写回项目稿。
- 每次应用前入栈，可多步「撤销应用」；保存到项目稿后清空撤销栈。
- 结果页显示每条 op 的 before→after 变更预览（文本级，不内联高亮）。
- 有 projectId 时应用后自动 graph-compile + validate L1，显示通过/失败；失败展示前 3 条 issue。
- **未**做内联语义 diff，也未把校验失败逐条映射回补丁。

## zero_slice Rust 参考

- `app/core/src/zero_slice.rs`：Markdown 解析、标题映射、<0.6 例外、freeform、coverage。
- 10 条 Rust 单测：解析/映射/例外/freeform + Session/reset/undo + DraftStore 同源覆盖 + to_project 参考形状。
- 新 `zero-slice` op：输入 text/spec，输出 title/sections/mappings/exceptions/coverage（0–100 整数）；3 条 op 测试。
- DraftStore 已落盘（同源覆盖）；**未**移植 to_project FFI/Android 接线。
- Android 导入页新增「自动切片」预览：调用 zero-slice，显示 coverage/例外数；仍不切换现有 ImportSession。

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
