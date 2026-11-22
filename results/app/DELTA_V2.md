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
- 全量 `python -m pytest app/tests -q` → **524 passed**。

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

## 真机收口（2026-11-22）

- OnePlus PLF110 / Android 16 安装 debug 签名 APK；冷启动 573/320/188ms。
- 完整闭环通过：示例 Pack → 项目 → 创作台 → graph-compile → 槽位 → assemble → L1 pass → 导出 md → 契约三项 → 签收（当版 hash 签收；M35 ECDSA 版本只跑 JVM）。
- 分享 SEND text/plain 导入预览通过。
- 真机修复：验收「必填槽位已填」只应由 spec.required 槽位决定，不能把选填 SLT-04 算进去。
- 仍未测：中文长文/完整输入法、PDF/EPUB/DOCX/HTML 导出、分享文件、杀进程恢复、TalkBack、横屏、AAB 上传签名。

## M24 Policy-as-Code（P0 部分）

- `FeaturePolicy` 规则表：Free 能力、Pro 能力、CCOS 能力；按 tier 判定。
- `FeatureGate` 委托规则；默认 Free，Free 永远放行，未知能力默认 Free。
- 5 条 Kotlin 单测；JVM 502。
- `FeatureGate.setTierForDebug`：调试构建可在 Settings「功能层级」切 Free/Pro/CCOS。
- 发布构建只显示层级与规则数，不含购买/授权入口；默认 Free。
- **未**接计费/真实 entitlement。

## M25 Capability-Scoped Sharing（P0 原型）

- `app/prototypes/capability`：read/comment/reassemble/export/share 与 admin。
- 到期、撤销、未知能力/未知 cap 的判定。
- 8 条 unittest；pytest wrapper 纳入全量。
- APP 已有 `ShareRedactor` 脱敏分享；不是权限/期限控制。
- Kotlin `CapabilityGrant`：read/comment/reassemble/export/share + admin；到期/撤销判定。
- preservation.zip 携带 `grant.json`（默认 read+export），verifier 校验 schema/caps。
- `CapabilityGrantStore` 按项目保存；交付台「分享授权」可选 5 类能力与 0/7/30 天期限，preserve 时写入 grant.json。
- `PreservationVerifier` 返回 grant；导入页仅在 `read` 可用时允许恢复归档。
- 分享授权对话框显示当前到期日；重新打开按剩余天数回显 7/30 天。
- 默认 grant 改为 read+reassemble+export；恢复归档要求 reassemble，只有 read 时仅允许只读预览。
- 分享授权对话框新增「撤销此授权」；撤销后 `allows` 全部拒绝，随包 revoked 生效。
- 导入页新增「导出归档内容」，仅 `export` 可用时显示；写入 exports/preserve。
- **未**接网络/密码学身份；授权仍是随包声明。

## M15 Property/Differential Testing（P0 原型）

- `app/prototypes/property_test`：对 canonical 生成 100 个确定性值做 roundtrip/稳定性性质检查。
- 覆盖浮点拒绝、键序无关、Unicode 码点保留。
- 4 条 unittest；pytest wrapper 纳入全量。
- Kotlin `PropertyHarness` + `AppSelfCheck`：Settings「属性自检」跑 150 条确定性 property（M1 推断/M12 MUS/M25 到期）。
- **未**做跨实现差分/模型比较。

## M12 Constraint Satisfiability/MUS（P0 原型）

- `app/prototypes/mus/mus.py`：min/max、required/forbidden_empty、must_include/must_avoid 的不可满足判定。
- 穷举最小不可满足子集（MUS），不返回非最小超集。
- 8 条 unittest；pytest wrapper 纳入全量。
- `ConstraintMUS` Kotlin 引擎 + `SpecConstraintAudit`：交付台显示约束自检冲突（min>max、required+max0）。
- **未**进 Rust；未覆盖任意表达式/引用图。

## M6 Constraint Lens（P0 部分）

- 槽位分配时显示当前字数/maxChars；超长/必填/最小字数/前后缀/pattern 不满足则标红并禁用。
- 分配前按 kind 清洗并截到 maxChars。
- 新增「约束面板」：逐槽位显示当前值、必填/可选、长度、前后缀、pattern 与问题列表。
- 面板内可直接编辑每个槽位；写入走同一 `inputs` 与 kind/maxChars 收敛。
- 约束问题随输入实时刷新。

## M2 Progressive Formalization（P0 部分）

- 预览块编辑器对短段落/引用给「这像主题句，要变成槽位吗？」提示。
- 可「形式化」进入现有槽位分配，或「忽略」。
- 新增 `FormalizationSuggester`：按槽位名/标题/正文的字符与词重叠给候选，可在块内直接「填入」。
- 叠加 spec 槽位 examples 的字符重叠；仍是本地关键词/标题/示例启发式，不是语义模型。

## M1 Flash Fill（P0 原型）

- `app/prototypes/flash_fill/flash_fill.py`：前缀/后缀/去前缀/去后缀/替换/截断白名单。
- 9 条 unittest；pytest wrapper 纳入全量。
- 预览块编辑器新增「批量变换」：replace/加前缀/加后缀/截断 四种模式，可撤销/重做。
- 推断白名单新增：转小写、转大写、去首尾空白、空白折叠为单空格。
- 预览块编辑器新增「手动变换」：8 种变换可显式选择并应用到全部块，带参数输入。
- 手动变换参数校验：截断需正整数，前后缀/替换需非空值；无效时禁用应用。
- 「从本次修改推断」：只改一个块时合成前后缀/去前后缀/替换/截断，并批量应用。
- 可「保存为变换」到项目；再次进入可「应用已保存变换」。
- 多例推断：同一变换必须解释多个 before→after；块编辑器可一次处理多个已改块。
- 未进独立推理引擎；UI 已有四模式 + 多例推断 + 项目级保存/复用。

## M35 Content Contract（P0 部分）

- 交付台验收清单：L1 通过 / 必填槽位已填 / 至少一次导出。
- 全绿后可签收；`ContractStore` 用 Android Keystore 的 EC P-256 设备密钥对验收载荷做 SHA256withECDSA。
- 载荷含 schema/project_id/accepted/signed_at/artifact_sha256；`load` 重新验签，篡改或换密钥即返回空。
- 归档包存在签收时附带 `contract.json` 并纳入 manifest；页面显示设备密钥指纹。
- **不是** CA/时间戳/实名身份；卸载/清密钥后旧签收失效；无变更单/异议/多方评审。

## M38 Preservation（P1 部分）

- `PreservationExporter`：document.md + document.nfdoc.json + oais.json + preservation.json（SHA-256/bytes）。
- oais.json：`nf-oais/1` 信息包，含 package_id/title/agent/rights/fixity/events；fixity 覆盖内容文件。
- Zip 固定时间，可复算；交付台「preserve」按钮导出。
- `PreservationVerifier` 校验 schema/条目/字节数/sha256，并校验 oais schema/package_id/fixity；导入页「校验归档包」按钮。
- 解压前限制条目数/单文件 20MB/总量 40MB，防 zip 炸弹。
- 校验通过后可「恢复为导入稿」（document.md → ImportScreen），不直接写项目。
- `PreservationLineageStore` 记录上次包 sha；再次 preserve 会写入 `predecessor_sha256` 到 preservation/oais，形成本地产线。
- verifier 校验 lineage 摘要格式及 oais/preservation 一致。
- `PreservationVerifier.chain`：校验 next 的 predecessor 等于 previous 文件摘要；Settings「归档迁移链」可选两包校验。
- 导出文件名带内容摘要，避免覆盖前包。
- `PreservationUpgrader` 把旧 preservation 包升级为当前 oais/grant 格式，并接 predecessor；Settings「归档升级」入口。
- **未**做自动升级/外部校验工具对接。

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
- Android 导入页在 doc 变化时自动调用 zero-slice；显示 coverage/映射/例外卡。
- 置信度 ≥60 且 to_id 命中的切片映射自动加入 acceptedMappings；另有「采用切片映射」手动入口。
- zero-slice 结果按 source digest 落盘，进程恢复时还原；新导入/清空时清除。
- 草稿旁写 zero-slice sidecar；DraftProjectBinder 把它带进项目 authoring/zero-slice.json。
- 创作台合并 zero-slice slotValues，项目字段可被切片结果直接预填。
- Android 包内 `libnf_app_core.so` 已重编译并含 `zero-slice` op；分享导入不再报「未知 op」。
- `zero-slice` 响应新增 `project`（`nf-project/1`）；Kotlin 解析 `project.slots` 并优先用于 `slotValues` 预填。
- 切片会话卡新增「用切片建项目」：保存草稿+sidecar 后直接走快速建项目。
- 该落盘逻辑抽到 `ZeroSliceProjectDraft`，单测覆盖主草稿/sidecar/mapping。
- 仍是 nf-import/1 会话；未切到 nf-zero-slice-draft/to_project，也未替换核心 map-suggest。
- **2026-11-23 真机端到端**：分享 3 heading Markdown → 自动切片 100% / 3 映射 / 0 例外 → 「用切片建项目」→ 创作台「已从导入映射预填 6 个字段」→ 交付 3/3 → L1 pass（error=0 warn=0 info=3）→ 导出 md 173 B（sha256 `b4542200…`）→ 签收（设备密钥 `4408787f9108b2a9`）→ 连续两份 preserve.zip 均通过。

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
