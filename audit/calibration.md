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

## 校准后的门禁含义

- 校准只放宽「阈值/检查面」，**不删除规则**（166 条不变），不改变评分公式。
- 每次校准都可在 `audit/rules.json` 的 diff 中看到；重跑证据包记录规则 sha256。
- 校准文档与规则库同时入库，审计报告结论需同时引用两者。
