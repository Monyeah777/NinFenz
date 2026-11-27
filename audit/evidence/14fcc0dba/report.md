# NF 审计报告（离线可复现）

- 审计对象：NF 0.3.6 源码（mobile 0.3.6 / 内核 1.0.5）
- 源码根：D:/NinFenz
- commit：14fcc0dba
- 规则库版本：2；scoring 版本：1
- Python：3.11.9；执行器：nf-audit-runner/1.0（sha256 b33b87793a71604b）
- 规则总数：166（script 135 / tool 14 / manual 17）

## 评分总览

| 维度 | 名称 | 权重 | 扣分 | 命中数 | 维度分 |
|---|---|---|---|---|---|
| A | 架构与依赖方向 | 0.10 | 11 | 17 | 89 |
| B | 模块边界与内聚 | 0.06 | 9 | 242 | 91 |
| C | 规模与复杂度 | 0.10 | 23 | 1212 | 77 |
| D | 重复与抽象 | 0.06 | 6 | 49 | 94 |
| E | 错误处理与失败语义 | 0.10 | 21 | 152 | 79 |
| F | 并发与资源 | 0.06 | 6 | 21 | 94 |
| G | 状态与恢复 | 0.06 | 0 | 0 | 100 |
| H | 安全与隐私 | 0.12 | 3 | 3 | 97 |
| I | 性能与规模 | 0.08 | 3 | 7 | 97 |
| J | 测试充分性 | 0.08 | 3 | 3 | 97 |
| K | 依赖与供应链 | 0.05 | 0 | 0 | 100 |
| L | 构建与可复现 | 0.05 | 2 | 4 | 98 |
| M | 文档一致性 | 0.04 | 3 | 3 | 97 |
| N | 可访问性与 i18n | 0.04 | 2 | 4 | 98 |

**总分：92.1**（= Σ 维度分 × 权重）

问题命中（按规则实际上报）：P0=0 / P1=85 / P2=1376 / P3=256，合计 1717

证据包 issues.json 按单规则最多保留 200 条（防超大文件），实际保留 1074 条；完整命中数见 meta.json 的 rule_status.hits。截断不影响评分与门禁。

## 规则执行状态

script 规则：pass=83 / fail=52 / error=0 / no_targets=0；tool+manual 未执行（not-run）=31

口径：tool / manual 规则记 not-run，不计扣分、不写成 pass；no_targets（无目标文件）与 error（执行异常）同样不计扣分、不算通过。

## P0/P1 命中清单

| 规则 | 级别 | 位置 | 说明 |
|---|---|---|---|
| ARCH-002 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/model/ProjectFilter.kt:3 | 越界 import: dev.ninfenz.mobile.data.ProjectEntry（禁止前缀 dev.ninfenz.mobile.data.） |
| ARCH-002 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/model/ProjectSorter.kt:3 | 越界 import: dev.ninfenz.mobile.data.ProjectEntry（禁止前缀 dev.ninfenz.mobile.data.） |
| ARCH-002 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/model/SearchFilter.kt:3 | 越界 import: dev.ninfenz.mobile.data.SearchHit（禁止前缀 dev.ninfenz.mobile.data.） |
| ARCH-002 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/model/SearchFilter.kt:4 | 越界 import: dev.ninfenz.mobile.data.SearchKind（禁止前缀 dev.ninfenz.mobile.data.） |
| ARCH-003 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/data/EditionPolicy.kt:3 | 越界 import: dev.ninfenz.mobile.ui.shell.Detail（禁止前缀 dev.ninfenz.mobile.ui.） |
| ARCH-003 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/data/EditionPolicy.kt:4 | 越界 import: dev.ninfenz.mobile.ui.shell.ShellState（禁止前缀 dev.ninfenz.mobile.ui.） |
| ARCH-003 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/data/RecentProjectShortcuts.kt:8 | 越界 import: dev.ninfenz.mobile.MainActivity（禁止前缀 dev.ninfenz.mobile.MainActivity） |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/NfMobileApp.kt:220 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/NfMobileApp.kt:701 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/NfMobileApp.kt:798 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/NfMobileApp.kt:808 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/NfMobileApp.kt:849 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/NfMobileApp.kt:875 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/components/MarkdownPreview.kt:80 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/CcosScreen.kt:79 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/CcosScreen.kt:80 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/CcosScreen.kt:81 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryMacroExecutor.kt:82 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:394 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:625 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:654 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:665 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:1487 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:1502 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:1517 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:1541 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:2096 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:2280 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:2313 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ExtensionCenterScreen.kt:175 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:373 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:385 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:386 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:412 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:425 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:438 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:539 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:608 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:1298 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:1921 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:1977 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/PackBuilderScreen.kt:363 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/PackBuilderScreen.kt:457 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/PackBuilderScreen.kt:525 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/PackUpdateScreen.kt:343 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/PatchScreen.kt:137 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/PatchScreen.kt:201 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/PatchScreen.kt:234 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/SettingsMacroSection.kt:102 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/SettingsMacroSection.kt:234 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/SettingsMacroSection.kt:255 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/SettingsScreen.kt:377 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/SettingsScreen.kt:432 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/TemplateGalleryScreen.kt:59 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/TemplateGalleryScreen.kt:60 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/TopLevelScreens.kt:159 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/TopLevelScreens.kt:607 | 命中禁用模式 /getOrNull\(\)/ |
| E-001 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/WorkflowHubScreen.kt:73 | 命中禁用模式 /getOrNull\(\)/ |
| E-002 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/data/FileAccess.kt:54 | 空 catch（无恢复/上报） |
| E-002 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/data/PackInstaller.kt:74 | 空 catch（无恢复/上报） |
| E-002 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/data/PackStore.kt:90 | 空 catch（无恢复/上报） |
| E-002 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/data/PackStore.kt:121 | 空 catch（无恢复/上报） |
| E-002 | P1 | app/android/app/src/main/java/dev/ninfenz/mobile/data/PdfFontProvider.kt:37 | 空 catch（无恢复/上报） |
| E-002 | P1 | desktop/src/core/daemon.py:180 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/daemon.py:185 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/daemon.py:190 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/daemon.py:549 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/daemon.py:570 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/daemon.py:631 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/daemon.py:721 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/daemon.py:888 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/interop_export.py:907 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/interp_diet.py:31 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/library.py:92 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/mvu_adapter.py:100 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/retriever.py:100 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/retriever.py:127 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/rust_engine.py:76 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/storage.py:137 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/watch.py:347 | 空 except（仅 pass，兜底异常被吞） |
| E-002 | P1 | desktop/src/core/workloop.py:143 | 空 except（仅 pass，兜底异常被吞） |
| E-003 | P1 | app/android/app/src/test/java/dev/ninfenz/mobile/model/CorrectionPromptTest.kt:13 | 错误码未在册: NF-VAL-101 |
| E-003 | P1 | app/android/app/src/test/java/dev/ninfenz/mobile/model/CorrectionPromptTest.kt:21 | 错误码未在册: NF-VAL-101 |
| E-003 | P1 | desktop/src/core/assemble_plan.py:127 | 错误码未在册: NF-FIELD-001 |
| E-009 | P1 | app/schema/error_codes.json:1 | 错误码重复: NF-PCK-007 |

## 未执行项（tool / manual）

| 规则 | 级别 | 类型 | 工具/方式 | 说明 |
|---|---|---|---|---|
| C-004 | P2 | tool | detekt | 离线不可用（缺 detekt jar）；CI 跑 audit/tools/detekt.yml |
| D-001 | P2 | tool | jscpd | 离线不可用（缺 node 依赖）；CI 跑 jscpd |
| D-006 | P2 | manual | 人工抽样 |  |
| E-012 | P2 | manual | 人工抽样 |  |
| F-001 | P1 | manual | 人工抽样 |  |
| F-008 | P2 | manual | 人工抽样 |  |
| F-009 | P2 | tool | android-strictmode | 离线不可用，需真机 StrictMode 报告 |
| F-010 | P2 | tool | android-lint | 离线缺 android.tools:lint-gradle，CI 跑 |
| G-001 | P1 | manual | 人工抽样 |  |
| G-009 | P2 | manual | 人工抽样 |  |
| G-010 | P2 | manual | 人工抽样 |  |
| H-007 | P2 | manual | 人工抽样 |  |
| H-013 | P2 | tool | pip-audit | 离线不可用，CI 跑 |
| H-014 | P1 | tool | codeql | 离线不可用，CI 跑 .github/workflows/codeql.yml |
| H-015 | P1 | tool | gitleaks | 离线不可用，CI 跑 |
| I-001 | P1 | tool | macrobenchmark | 真机 macrobenchmark 尚被测试 APK 混淆冲突阻断，未接入 |
| I-007 | P2 | manual | 人工抽样 |  |
| I-008 | P2 | tool | macrobenchmark | 同 I-001，未接入 |
| I-009 | P2 | manual | 人工抽样 |  |
| I-012 | P3 | manual | 人工抽样 |  |
| J-001 | P1 | tool | jacoco | 离线不可用，CI 跑 |
| J-013 | P3 | tool | pit | 离线不可用，CI 跑 |
| J-015 | P2 | manual | 人工抽样 |  |
| K-014 | P2 | tool | cyclonedx | 离线不可用，CI 跑 |
| K-015 | P2 | tool | cargo-audit | 离线不可用，CI 跑 |
| L-001 | P2 | tool | reproducible-build | 需两次构建+比对，CI 跑 |
| M-001 | P2 | manual | 人工抽样 |  |
| N-002 | P2 | manual | 人工抽样 |  |
| N-003 | P3 | manual | 人工抽样 |  |
| N-010 | P2 | manual | 人工抽样 |  |
| N-011 | P3 | manual | 人工抽样 |  |

## 复现

    python audit/runner.py --root D:/NinFenz --commit 14fcc0dba --out audit/evidence/14fcc0dba

同一输入重跑：文件遍历与命中排序均为确定性，issues.json / meta.json / report.md 逐字节一致。
