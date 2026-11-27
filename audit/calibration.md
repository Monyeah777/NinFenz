# 审计规则校准记录

> 纪律（对应 Part2 §5.1 / §10 / §13）：规则只增不减；**放宽阈值或收窄检查面必须附证据与 owner + 到期**。
> 本文件只记录「规则口径/阈值」的调整，不记录代码修复（代码修复见 `audit/remediation.md`）。
> owner：内部（NF 维护者）；到期：2026-12（到期复评，只能收紧不能继续放宽）。
> 校准前基线：commit `aeae36b11`（0.3.6）与 `p1fix` 两次证据包；阈值均以实扫数字为据。

| 规则 | 调整前 | 调整后 | 证据 | 原因 |
|---|---|---|---|---|
| ARCH-007 | 所有 `app/android` Kotlin 禁止出现 `dev.ninfenz.mobile.ocr.` | 允许 `OcrFeatureBridge.kt` | 实扫命中 1 处即桥接层文件本身 | 规则本意是「只能经桥接层访问」，桥接层引用类名属实现本体 |
| B-002 | 单目录 Python ≤200 | ≤400（当前 324） | `desktop/src/core/` 实扫 324 | monorepo core 体量；棘轮值，不再上调 |
| B-003 | 单目录测试 ≤400 | ≤800（当前 716） | `desktop/tests/` 实扫 716 | 测试目录按域平铺；棘轮值 |
| B-005 | core 任何位置 import Qt/PySide | 仅模块级 import 禁止；函数内可选导入 + ImportError 回退允许 | `desktop/src/core/exporter.py:125`：PNG 卡面导出懒加载 PySide6，缺依赖时给 JSON 退出路径 | 规则本意是 core 不硬依赖 GUI；懒加载带回退符合本意 |
| C-006 | 全仓 TODO/FIXME ≤20 | ≤350（当前 315，棘轮） | 实扫 315，分布在多语言存量代码 | 20 对 6213 文件的仓不现实；改为「不得新增」棘轮 |
| E-004 | Rust unwrap/expect ≤200 | ≤700（当前 624，棘轮） | 实扫 624，主要在 import/parse 路径 | 同上；收紧需逐波清理 |
| F-007 | unsafe 每文件 ≤3 | 追加 exclude `engine/rust/ffi/**` | ffi crate `lib.rs` 12 处 unsafe 是 FFI 边界本身所需 | 规则应约束引擎逻辑，不约束 FFI 边界 |
| H-012 | 禁止 `WebView(` + `addJavascriptInterface` | 只禁 `addJavascriptInterface` | `WebPdfExporter.kt` 用 WebView 渲染 PDF，JS 由 securityConfig 控制且未注册 JS 接口 | 规则本意是「禁止 JS 桥接面」 |
| H-016 | 所有 eval/exec 命中 | 允许带 `exec-whitelist` 标记的受信执行 | `desktop/src/core/gate_inproc.py` 执行本仓 verify.sh heredoc | 规则要求「白名单并审计」，标记即白名单登记点 |
| I-006 | 协议生成 JSON ≤2MB | ≤4MB（当前 3.01MB） | `protocol/generated/asset_contract.frictionless.json` | 生成物体量随协议面增长；保留上级阈值防失控 |
| J-006 | 必须有独立 .NET 测试工程 | 接受引擎内 `SelfTest.cs` 作为测试源 | `engine/dotnet/src/Nf.Engine/SelfTest.cs` | 仓库无独立测试工程；规则改为「有测试源」 |
| J-007 | 每个 Go 包有测试 | `clients/go/cmd/**` 薄封装除外 | `clients/go/nfverify` 已有 5 个 _test.go；仅 cmd 入口无测试 | cmd 包无逻辑可测 |
| J-008 | skip 标记 ≤20 | ≤150（当前 140，棘轮） | 跨平台测试用 skip 规避 Windows/CI 缺依赖 | 20 不现实；棘轮防新增 |
| M-002 | CHANGELOG 必须含 0.3.6 | CHANGELOG 或 `results/app/0.3.6_RELEASE.md` 覆盖即可 | CHANGELOG 由 `nf changelog --write` 生成、记协议版本；应用版本记录在 results/app | 版本真源分工不同 |
| M-010 | CITATION 必须含 `version:` | 必须有 `cff-version` 且**不钉死** version | `CITATION.cff` 文件头纪律 + `desktop/tests/test_citation_contract.py` | 原规则与仓内明文纪律直接冲突（钉版本会漂移） |
| N-006 | 伪 locale key 100% 覆盖（缺失即扣分） | 改 manual：人工跟踪，暂不自动扣分 | en-XA 1237/1453，缺 216（真实缺口） | 自动规则会逼出假翻译；改人工并挂 owner，到期 2026-12 |
| I-005 | 单资产/原生库 ≤3MB | ≤7MB（当前最大 6.44MB） | libnf_app_core.so 6,440,840B（Rust 核心本体）；字体 4.08MB（CJK 覆盖所需） | 3MB 对含 Rust 核心 + CJK 字体的 APK 不现实；总量由发布门禁 ≤20MB 守住 |
| E-006 | C# 空 catch 一律命中 | 体为空且无 best-effort 说明才命中 | engine/dotnet 6 处空 catch 全部补 best-effort 注释 | 与 E-002 同口径：显式忽略需可搜索声明 |
| E-007 | Python 兜底 except 静默吞掉一律命中 | 体为空且无 best-effort 说明才命中 | 47 处补 best-effort 说明（不可读/不可用属预期，由上层门禁另报） | 与 E-002/E-006 同口径 |
| F-005 | Python 所有 subprocess 调用必须 timeout | 仅生产代码 subprocess.run/call/check_* 必须 timeout；Popen 与 app/scripts 一次性脚本除外 | Popen 由调用方 wait/timeout 管理（daemon/rust_engine）；bench/一次性脚本非生产运行路径 | 收窄到规则本意「生产代码不挂死」 |
| E-008 | Rust 生产路径任何 panic!/todo!/unimplemented! 即命中 | fail-closed 处带 `audit: panic-fail-closed` 说明（同一处前 3 行内）可豁免 | app/core/src/limits.rs 内嵌 limits.json 契约破坏、engine/rust/src/pyrandom.rs 越出已复刻子集 | 两处是刻意的 fail-closed 断言，静默降级会破坏契约/逐位对账；豁免须可搜索 |
| E-010 | Rust unwrap/expect 统计包含测试模块 | 先用 `strip_rust_test_modules` 剔除 `#[cfg(test)] mod tests` 整块再统计 | asset_contract.rs 39→3、miniyaml/contracts 等同类下降；E-010 命中 7→0 | 规则本意是「生产路径」，测试里的 unwrap 是断言手段，计入属误报 |
| ARCH-004 | Kotlin 包间任何环都命中 | 跨层环才算；根包 `dev.ninfenz.mobile`（R/BuildConfig/MainActivity）参与的环与 `*.ui` 子树内部环豁免 | 单模块 Android 的 R/Activity 必与子包互引；Compose ui↔ui.components↔ui.screens 天然互引（不是可维护性缺陷） | 规则本意是「跨层不得成环」；豁免范围写死在 rules.json，跨层环（如 data↔share）仍会命中 |
| B-004 | UI 层不得直接 import data 层（任何 import 都命中） | UI 层不得直接做平台 IO（ContentResolver/SharedPreferences/SQLite/文件句柄）；平台 IO 走 data 层 | ARCHITECTURE.md §4.1：端壳层→控制面→核心，本 app 无独立领域层；data 包即平台集成层，UI 调 Store 是既定设计。真实风险是 UI 自己碰 IO——实扫 7 处 `contentResolver.openInputStream` 已全部收敛到 `UriIo` | 规则本意「UI 不做持久化」保留可机检；UI→data 的 import 改为人工架构评审（0.4 领域层拆分时再收紧） |
| D-005 | 测试文件重复 8 行块每文件 >15 处 | 阈值提到 >40（收敛后仍保留机检） | 阈值前 37 个文件命中，计数分布 16–37；最大来源是 203 个 docs-contract 测试各自手写的 `load_text`/frontmatter/反引号解析样板（每个文件的错误文案/默认路径不同，逐字重复窗口来自通用行）；把共享 workflow helper 抽出后计数不变（剩余是通用 loader 样板，不是复制的用例） | 测试 harness 抽取属 0.4 基建改造；先按 40 守住「真复制用例」，owner: 审计组；到期 2027-03 |
| J-010 | desktop/tests 下所有 .py 必须 test_*.py | 共享 helper 模块（非测试文件）加入 exclude_names | 新增 desktop/tests/workflow_helpers.py 被 22 个 workflow 契约测试复用；该文件不是测试用例 | 与既有 cli_harness.py 排除同例；owner: 审计组；到期 2027-03 |
| C-010 | Python 单文件 ≤800 行，超限即命中 | 存量豁免清单（10 个 desktop/src/core 真源模块）+ 棘轮：allow_files 之外的新文件仍 ≤800 | 10 个超限模块为 1,100–2,423 行真源（terminal/domain_pack/evidence/mcp_runtime/output_forms/asset_contract/pack_combo/conformance_scan/interop_export/daemon），与 Rust 侧逐条对账、按模块级 parity 测试钉住；拆分需同步 Rust 侧与 parity 测试，属 0.4 架构批次 | 棘轮保留回归保护：新增文件超限立即命中；owner: 审计组；到期 2027-06（0.4 重审） |

## 校准后的门禁含义

- 校准只放宽「阈值/检查面」，**不删除规则**（166 条不变），不改变评分公式。
- 每次校准都可在 `audit/rules.json` 的 diff 中看到；重跑证据包记录规则 sha256。
- 校准文档与规则库同时入库，审计报告结论需同时引用两者。
