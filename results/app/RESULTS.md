# NF APP 实施结果（RESULTS）

> 本件是 APP 实施面的**结果/状态导航**（不是规划件）。开工依据 `NF-APP-Final-方案-2026-11-15.md`；基线 `results/app/BASELINE.md`；收口判据 `app/docs/DOD.md`；机读门禁 `app/results/GATES.json` + `app/results/SELF_AUDIT.json`。
> 现场复跑：`python app/gates/run_gates.py`（QA0–QA6 + S0–S15）。本件不给「应该绿」，只给「现在能跑出什么」。
> 状态：v1（2026-11-15）+ v0.02 增量（2026-11-15）

## 0. v0.02 增量（2026-11-15，Android 端）

> 本段是 v0.02（v2 方案）Android 端增量结果；下方 §1–§6 仍是 v1 快照（core/CLI/桌面口径不变）。v0.02 不改 app/schema、core ABI、CCOS 边界。

### 0.1 交付与提交

| 波次 | 内容 | 提交 |
|---|---|---|
| W1 | 四目的地外壳/设计 token/首启示例/引导/自适应 icon | 5e14b5019 |
| W2 | 新建项目向导/演示项目/搜索/Pack 校验 | e5b2b0bfd, d30db5099, 4a0c9cf09 |
| W3 | 导入产品向导（来源→预览→map-suggest 映射→草稿） | 3ef6db5f2 |
| W4 | 项目态创作台（协议/管线/规格 + 核心校验/渲染） | 6ac657b52 |
| W4b | nf-overlay 作者覆盖保存 + 撤销；项目状态写回 | a14456833, 902789796 |
| W5 | 交付台/视觉壳/Pack 中心/CCOS/Pack zip 更新 | 86191976e, 350285a44, 1dc695125, 4d816f3c5, 6c30f241e |
| W6 | a11y/token/路由测试、Robolectric、三尺寸/九矩阵、外壳 i18n | cbc913478, 07ccf027f, 3eef0a5af, 6614f7301, 本提交 |

### 0.2 实测（本机）

| 项 | 结果 |
|---|---|
| APK | app-debug.apk = 19,049,108 B；sha256 bbe4851689e7e278c12c7ce28d0e581120ea88dfc2f14aca36fc281df688ae05 |
| JVM 测试 | 282 条全绿（v1 基线 42 + v0.02 新增 240；含 Robolectric/Compose/Paparazzi） |
| 构建 | ./gradlew :app:assembleDebug 成功；:app:testDebugUnitTest 123/123 |
| i18n | 全部屏主要文案已资源化 + values-en；「我的」zh/en/跟随系统切换；动态取色开关；库/Pack 中心下拉刷新；节点删除 Snackbar 撤销 + 触觉；expanded 双栏（主列表+详情）；导航 Crossfade（NfMotion.MEDIUM_MS）；统一 loading/skeleton 组件；少量错误/技术提示仍内联（OPEN-I18N-BODY 尾项） |
| 适配 | compact/medium/expanded 三档导航 + 9 组窗口尺寸语义矩阵 |
| a11y | contentDescription/48dp（A11yComposeTest 3）、200% 字号（LargeFont 1）、WCAG AA 对比度（Contrast 3） |
| 截图基线 | Paparazzi 10 张（360/700/900 × 640/800/900/1000），verify 模式下纳入 testDebugUnitTest |
| app/gates | 7/7 gate PASS、FAIL=0（QA0 10 checks、QA5 5 checks；含 v0.02 UX/i18n/测试矩阵检查） |

### 0.3 状态

- W1–W5：已完成（v0.02 范围）。
- W4b：作者覆盖保存/撤销、状态写回、管线/规格编辑+保存（撤销/重做 + 防抖自动保存）已完成；草稿→项目仍 OPEN。
- W6：部分完成（见 0.4）；未跑面不写成 pass。

### 0.4 v0.02 收口（2026-11-15）

- 机读门禁：app/gates **7/7 PASS，FAIL=0**（QA0 10 / QA5 5）；仓库 verify **PASS=107 WARN=2 FAIL=0**。
- 测试/产物：JVM **282/282**；APK 19,049,108 B，sha256 bbe48516…。
- 结论：**v0.02 实现面 pass-with-open-items**；下方 OPEN 不因收口消失，未跑面不写成 pass。

### 0.5 v0.02 OPEN（带 owner+next）

| id | 内容 | owner | next |
|---|---|---|---|
| OPEN-I18N-BODY | 全部屏主要文案已资源化；少量错误/技术提示仍内联；应用内 zh/en 切换已做，系统 per-app locale 入口未做 | lead | 抽取尾项 strings + localeConfig |
| SCREENSHOT | Paparazzi 2.0.0-alpha02 已接入，10 张截图基线随 testDebugUnitTest verify；更新基线用 recordPaparazziDebug | lead | 完成（本提交） |
| DEVICE (partial) | OnePlus PLF110/Android16 已跑：首启/示例导入/创作保存/装配/L1/导出 md+zip，并修复 7 个真机问题（含顶部 insets、分享崩溃/prefill、jniLibs 陈旧致 docx 误报）；docx/TalkBack/主题/CCOS/分享/折叠/性能未跑 | lead | results/app/DEVICE_RESULTS.md |
| OPEN-DEVICE | 剩余真机项（TalkBack、主题/语言、CCOS、分享、折叠、性能） | lead | 继续 DEVICE_RESULTS 清单 |
| OPEN-DRAFT-PROJECT | 导入草稿→项目转换未定义（契约无 import→project 字段） | lead | 需 v1 §15 契约变更评估 |
| OPEN-REVIEWED | CCOS approve 时 exported 项目回写 reviewed；非 exported 项目跳过（不伪造） | lead | 如需强制 reviewed，补 project-validate 前置条件 |

## 1. 结论（先行）


1. **共享契约层 + Rust 核心 + Python 控制面 + Android/Desktop 端壳**四层已落地：13 个共享格式、20 个核心 op（CLI + C ABI）、控制面用户流、Compose 两端 UI。
2. **构建面已实测**：Android APK（含 Rust `.so` 双 ABI，16KB 页对齐通过）与 Windows MSI（含 Rust `cdylib`）均由本机工具链产出；macOS 与签名/公证 = `OPEN-EXTERNAL`。
3. **质量面按门禁取证**：QA0–QA6 与 S0–S15 的机器结论见 `GATES.json`；未完成面全部带 owner+next 的 OPEN，不写成 pass。
4. **仓库层不谎报**：本机 `verify.sh` 仍是红的（历史构建产物 334 FAIL + 干净 clone conformance root 漂移），APP 未把这两条既有红因归到自己身上；APP 自己的门禁是 `app/gates/run_gates.py`。

## 2. 交付物导航

| 层 | 落点 | 说明 |
|---|---|---|
| 契约 | `app/schema/`（13 schema + limits + error_codes） | A0 单一真源；正反夹具 `app/fixtures/schema/` |
| 契约文档 | `app/docs/{CONTRACT,CLI,ARCHITECTURE,DOD,QA_PLAN}.md`、`app/docs/adr/`（11 条） | 操作指令即复跑入口 |
| 核心 | `app/core/`（Rust：canonical/schema/pack/import/protocol/graph/spec/assemble/validate/export/update/ccos/project + CLI + FFI + 扩展口） | 参考实现；20 op；cargo 测试 + golden |
| 控制面 | `app/cli/nf_app`（Python：import/map/project/author/assemble/validate/export/share/pack/ccos/selftest） | 调核心 JSON 面，不复制语义 |
| Android | `app/android/`（Kotlin + Compose；8 屏 + 透明 ShareReceiver + FileProvider + CoreBridge/JNA） | APK 实测构建 |
| Desktop | `app/desktop/`（Compose Multiplatform；7 屏 + JNA 桥 + TUI 终端面板 + 打印） | MSI 实测构建 |
| TUI | `tui/nf.py`（复用，不重写） | `--selftest`/`--list-actions` 已是终端真源 |
| 构建/发布 | `app/scripts/`（build_core/build_android/build_desktop/build_core_android/sign/notarize/RELEASE_*） | 缺证书/平台即 exit 4，不假签 |
| 证据 | `app/results/{GATES,SELF_AUDIT}.json`、`app/results/TOOLCHAIN.md`、`app/docs/DEPENDENCIES.md`、`app/scripts/RELEASE_EVIDENCE.md` | 现场复跑与产物哈希 |

## 3. 需求覆盖矩阵（计划 §7）

> 状态口径：**pass** = 有代码 + 有可复跑测试/构建证据；**partial** = 主路径在、边界面 OPEN；**OPEN** = 未实现或环境不可执行（带 owner）。证据列只写路径/命令。

### 3.1 导入/分享（IMP）

| ID | 需求 | 状态 | 证据 |
|---|---|---|---|
| IMP-01 | 接收 SEND/SEND_MULTIPLE/VIEW/PROCESS_TEXT | pass（工程面） | `app/android/.../share/ShareReceiverActivity.kt` + manifest intent-filter；真机未跑 → OPEN-TOOLCHAIN |
| IMP-02 | SAF 单/多文件/目录 | partial | Import 屏 + `import` 流；SAF 全链路真机未验 |
| IMP-03 | 剪贴板文本/JSON/Markdown | pass | `nf-app import -`（stdin）+ Import 屏剪贴板入口 |
| IMP-04 | sniff + 适配器（文本/MD/JSON/YAML/ZIP/.nftpl/Pack） | pass | `import-sniff`/`import` op + `test_*import*` + security 负例 |
| IMP-05 | DOCX/PDF/HTML/OCR（SHOULD，次版） | OPEN | 核心返回 NF-IMP-004 exit 3（不静默降级），owner: lead |
| IMP-06 | 生成 nf-import/1 + 映射 + 校验 + 草稿 | pass | `nf-import/1` schema + `map-suggest` + DraftProject |
| IMP-07 | 保留原文/来源，不静默覆盖 | pass | `source.text_digest` + 项目只写草稿；e2e 用例 |
| IMP-08 | 授权目录 Inbox 自动解析（SHOULD） | OPEN | WorkManager 骨架在 Android 侧声明，遍历/去重未实现，owner: kotlin-ui |
| IMP-09 | 分享出提示词/MD/.nftpl/JSON/复制 | pass | `nf-app share`（脱敏 + 只读 URI 设计） |
| IMP-10 | DocumentsProvider/打印/文件关联（SHOULD） | partial | Desktop Print + 文件关联声明；DocumentsProvider OPEN |

### 3.2 作者/装配（AUTH/ASM）

| ID | 需求 | 状态 | 证据 |
|---|---|---|---|
| AUTH-01 | 协议整包替换 + 条款表单 + 自定义 pack | pass | `protocol-validate`/`protocol-render` + Protocol 屏 |
| AUTH-02 | 管线 DAG 增删/重排/分支/并行/回退 | partial | `graph-validate`（DAG/环/端口/模式/必需阶段）+ Graph 屏编辑；「回退边」首版按 DAG 校验（循环不做，与计划 D3 一致） |
| AUTH-03 | 模块/资产绑定/替换/多选/权重 | pass | graph `module_ref/asset_refs/weights` + 校验（NF-GRF-005/007） |
| AUTH-04 | MD spec 章节/槽位/约束/示例/验收/预算 | pass | `spec-validate` + `nf-md-spec/1` |
| ASM-01 | 编译 graph→plan；环/端口/必需阶段校验 | pass | `graph-compile` + plan digest 确定性 |
| ASM-02 | 整篇/阶段预览/槽位生成/块编辑 | pass | `assemble --stage/--block` + meta |
| ASM-03 | 失败回灌到 stage/slot | pass | issue `path` 指到 `$.inputs.<slot>`/`$.schema` + fix |
| ASM-04 | 参数化模板/变量；批量（SHOULD） | partial | 变量在 plan/params；批量 = `DslParser/BatchRunner` 扩展口（见 §6） |

### 3.3 校验/导出（VAL/EXP）

| ID | 需求 | 状态 | 证据 |
|---|---|---|---|
| VAL-01 | L0 结构 / L1 契约；L2 可选 NF | pass（L0/L1）/ OPEN（L2 环境） | `validate`；L2 缺 `nf` CLI → exit 4 + NF-VAL-005 |
| VAL-02 | 报告按对象路径定位 + fix | pass | `nf-validate-report/1` + issues path/fix |
| EXP-01 | md/zip/docx/pdf | pass（md/zip/json/docx）/ OPEN（pdf） | md/zip/json 确定性；**docx = 核心直出 OOXML（确定性、CJK）**；pdf = 平台打印（核心 exit 4 + NF-EXP-004，OPEN） |
| EXP-02 | skill/MCP 包（导出模板/脚手架） | pass | `export --format skill` → `SKILL.md` + `mcp.json`（nf-mcp-scaffold/1）+ `README.md` + result 件；测试 `app/tests/test_export_formats.py` 与 `app/core/tests/ops_export.rs` |
| EXP-03 | 导出确定性/manifest | pass | `nf-export-manifest/1` + 固定 zip mtime/顺序 |

### 3.4 Pack/Overlay（PACK）

| ID | 需求 | 状态 | 证据 |
|---|---|---|---|
| PACK-01 | base+overlay 分层；更新不直接改 base | pass | `nf-overlay/1` + `overlay-apply` + base 只读校验 |
| PACK-02 | 新 pack 校验 manifest/hash/版本 | pass | `pack-verify`（NF-PCK-001/002/005） |
| PACK-03 | 自动 diff/合并；冲突 UI | pass（核心+UI 冲突面） | `pack-diff`/`pack-merge` + PackUpdate 屏（冲突决策） |
| PACK-04 | 更新提示/影响/回滚/旧版保留 | pass（回滚见 E2E 用例） | `applied/conflicts/result_tree` + backup/rollback |
| PACK-05 | 模板包内嵌 protocol/spec 快照 | pass | `nf-template/1`（`/nftpl` 适配器） |
| PACK-06 | 目录 Inbox/更新检测（SHOULD） | OPEN | 定期检测默认关；桌面/移动轮询未实现，owner: lead |

### 3.5 桌面/TUI/CCOS（DESK/TUI/CCOS）

| ID | 需求 | 状态 | 证据 |
|---|---|---|---|
| DESK-01 | Compose MP 与 Android 共享模型/核心 | pass | 两端均 JNA 调同一 `nf_app_core` ABI；52 条 JVM 测试（38 Android + 20 Desktop，其中 FFI 真加载） |
| DESK-02 | 完整作者/Graph/DSL/Pack/评审/打印/文件关联 | partial | 7 屏落地；DSL 编辑器文本面 + 校验；文件关联声明未 OS 级验证 |
| DESK-03 | Win MSIX/签名；macOS 签名/公证/Sparkle | OPEN-EXTERNAL | MSI 已产（未签名）；证书/公证/macOS 不在场 → `RELEASE_EVIDENCE.md` |
| TUI-01 | Studio 集成 TUI（selftest/list-actions/exec/demo） | pass | Desktop TuiTerminal（ProcessBuilder）；`python tui/nf.py --selftest` 9 ✔ |
| TUI-02 | 不重写终端/不绕过写盘闸门 | pass | 复用 `tui/nf.py` + `_surface.py`；本波未改 TUI |
| CCOS-01 | APP 生成 ccos-task、导入 ccos-result | pass | `ccos-build-task`/`ccos-import-result` + schema + 人审 |
| CCOS-02 | 密钥/预算/策略只在 CCOS | pass | task 只声明策略；result 导入拒密钥形状（NF-CCOS-003） |

### 3.6 平台/安全/质量（NFR）

| ID | 需求 | 状态 | 证据 |
|---|---|---|---|
| PLAT-01 | target 36/edge-to-edge/预测返回/16KB/ABI | pass（构建面） | `app/android/app/build.gradle.kts` + `zipalign -c -P 16 4` 通过 + 双 ABI `.so`；真机未跑 |
| PLAT-02 | 自适应（手机/折叠/平板/Chromebook/多窗口） | pass（代码侧）/ OPEN-TOOLCHAIN（真机） | 三档宽度（<600 / 600–839 / ≥840）→ 紧凑单页导航栈 / 常驻 NavigationRail + 内容区（`app/android/.../ui/Adaptive.kt`）；JVM 单测 `AdaptiveLayoutTest` 4 条 |
| PLAT-03 | 无障碍/中英/RTL/字体缩放 | partial（代码侧）/ OPEN（真机） | supportsRtl + 中文可读标签（Rail 图标清空语义避免 TalkBack 重复朗读）+ Material sp 排版缩放；TalkBack/字体缩放实测 OPEN-TOOLCHAIN |
| SEC-01 | MASVS/威胁模型/WebView/解析/组件/深链 | partial | THREAT_MODEL（21 控制点）+ 解析负例 47 条；深链/WebView 未启用 |
| SEC-02 | 无遥测/本地诊断/密钥不进 APP | pass | manifest 无网络权限；PRIVACY.md 数据地图；gate `check_no_machine_paths` |
| PERF-01 | 启动/装配/包体/内存预算 | OPEN | 无运行时真机 → PERF_BUDGET no-data + owner |
| TEST-01 | golden/parity/负例/16KB/设备矩阵 | partial | golden/oracle/负例/16KB 已验；设备矩阵 OPEN-TOOLCHAIN |
| LEGAL-01 | AGPL/商业/NOTICE/Play 数据安全 | partial | 实读 LICENSE=MIT（偏差已登记）；NOTICE/Play 表单 OPEN；不构成法律意见 |

## 4. 首闭环验收（计划 §18.2）

| # | 步骤 | 命令 | 状态 |
|---|---|---|---|
| 1 | 安装/打开 sample pack | `nf-app pack install` + `pack-verify` | pass（E2E 6 条） |
| 2 | 文件管理器/分享/剪贴板导入 → 识别/映射/确认 | `nf-app import ...` + `map` | pass（控制面；Android 真机 OPEN-TOOLCHAIN） |
| 3 | 协议参数/列表重排/绑定/权重 | `nf-app author protocol/graph` | pass（E2E 6 条） |
| 4 | 装配/校验/预览 | `nf-app assemble` + `validate` | pass（E2E 6 条） |
| 5 | 分享 Prompt → AI → 复制 → 导入 → 校验/回灌 → 导出 | `nf-app share prompt` + `import`/`validate`/`export` | pass（E2E 6 条） |
| 6 | 导入新 pack → diff/merge/提示/回滚 | `nf-app pack update/apply/rollback` | pass（E2E 6 条） |
| 7 | 平板/桌面同 project；TUI selftest/verify 通过 | 项目文件同源 + `python tui/nf.py --selftest` | 见 E2E + TUI |

**复跑**：`python -m pytest app/tests/test_e2e_first_loop.py -q` → **6 passed**（真调 release 核心；覆盖 §18.2 七步 + 块编辑/导出/更新/回滚/CCOS 人审）；机读结果见 `app/results/GATES.json`。

## 5. 测试与构建证据

> **仓库门禁（实现入仓后实测）**：`bash verify.sh --checks-only` → PASS=107 WARN=2 FAIL=0（exit 0，HEAD `f19e41660`）；conformance conformant；CQ6 3.95/C 与基线一致。APP 未改 check1–57。

| 产物 | 值 | 复跑 |
|---|---|---|
| Android APK | 19,049,108 B；含 `lib/{arm64-v8a,x86_64}/libnf_app_core.so`；`zipalign -c -P 16 4` 通过 | `bash app/scripts/build_android.sh debug` |
| Rust `.so` | arm64 4,478,824 B / x86_64 4,645,976 B（NDK r27，LOAD align 0x4000） | `bash app/scripts/build_core_android.sh` |
| Windows MSI | 66,573,406 B；app jar 内含 `native/nf_app_core.dll` | `bash app/scripts/build_desktop.sh package`（WIX_PATH） |
| Rust CLI / cdylib | `nf-app-core.exe` / `nf_app_core.dll` | `bash app/scripts/build_core.sh --release` |
| 工具链定版 | Gradle 8.11.1 / AGP 8.10.1 / Kotlin 2.1.20 / CMP 1.7.3 / compileSdk 36 / NDK r27 | `app/results/TOOLCHAIN.md` |
| Python 测试 | **490 passed / 0 failed / 0 skipped / 0 xfailed（127s）** | `python -m pytest app/tests -q` |
| Rust 测试 | **182 断言 / 21 二进制 / 0 failed** | `cd app/core && cargo test` |
| 两端 JVM 测试 | Android 42（含自适应分档 4 条）/ Desktop 20（含真实 JNA FFI） | `./gradlew test` / `:app:testDebugUnitTest` |

## 6. 扩展口（计划 §17）

已落接口（`app/core/src/ext.rs`）：`Adapter` / `Provider`（仅 trait，不实现网络）/ `PackPublisher`（本地目录）/ `FeatureGate`（默认全开空实现）/ `TraceRecorder`（no-op 默认）/ `DslParser`（最小子集 + 未知 op fail-closed）/ `BatchRunner`（错误聚合）/ `PluginAdapter`（默认拒绝未注册）。每个有默认行为单测；详见 `app/core/README.md`。

**OPEN 扩展口**（计划 §17 末）：ZK/选择性披露、后量子、联邦、AIBOM、Agent 授权、人类复核凭证、监管映射、撤销、见证、隐私、WASM verifier、WORM 归档——全部 OPEN，不在本波实现；登记于 §7。

## 7. OPEN 清单（不因收口关闭）

| id | 内容 | owner | 下一步 |
|---|---|---|---|
| OPEN-TOOLCHAIN | 真机/模拟器 E2E、MSI 安装启动、CMP 交互运行 | lead | 需设备/模拟器；不阻断构建结论 |
| OPEN-EXTERNAL | 签名/公证/Play 数据安全/macOS 构建 | lead | 证书/平台不在场；`RELEASE_EVIDENCE.md` 留位 |
| OPEN-DOCXPDF | docx/pdf 导出（首版只 md/zip/json） | lead | 导出器探测；缺即 exit 4 + NF-EXP-004 |
| OPEN-L2 | L2 仓库协议层校验（依赖 `nf` CLI 子进程） | lead | 缺环境 exit 4 |
| OPEN-SIGN-PACK | Pack 安装无签名校验（计划 PACK-06/SEC 后续） | lead | 签名格式与信任锚未定 |
| OPEN-MAP-DECISION | map-suggest 决策仅落 sidecar JSON，未接 core 复算 | python-plane | 接 core `map-suggest` 复算并加用例 |
| OPEN-INBOX | 授权目录 Inbox 自动解析（WorkManager） | kotlin-ui | 遍历/去重/撤销 |
| OPEN-DEEPLINK | 深链/QR 传输（计划 §10.2 可选） | kotlin-ui | 未实现 |
| OPEN-A11Y | TalkBack/RTL/字体缩放实测 | kotlin-ui | 需设备 |
| OPEN-PERF | 启动/装配/内存/包体实测预算 | lead | 需 Android 运行时 |
| OPEN-REPRO | 构建可复现（同源二次构建逐字节） | lead | buildinfo 对照 |

## 8. claims 边界

- 「可构建 / 可测试 / 有产物」= 本机实测（命令与哈希见上）；**不等于**可发布/已签名/已公证/已上架。
- 「覆盖计划 §7 的 N 条」按 §3 状态列计数：pass + partial + OPEN 分列，不合并成「全部达成」。
- 未跑面一律 `OPEN`（真机、性能实测、设备矩阵、安全红队深链/分享二次传播、macOS）。
- APP 门禁结论只引用 `app/results/GATES.json`；仓库门禁结论只引用 `bash verify.sh --checks-only` 实测（本机为红，见 BASELINE §2）。

## 9. 复跑入口

```bash
python app/gates/run_gates.py                    # QA0–QA6 + S0–S15（写 app/results/）
python -m pytest app/tests -q                    # 控制面/契约/安全/golden/E2E
cd app/core && cargo test                        # 核心单测 + golden + FFI + 扩展口
bash app/scripts/build_core.sh --release --test  # 核心构建
bash app/scripts/build_android.sh debug          # APK（需 Android SDK）
bash app/scripts/build_desktop.sh package        # MSI（需 WIX_PATH）
python tui/nf.py --selftest                      # 终端面（复用）
```
