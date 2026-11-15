# NF APP 交付与完成定义（DoD）

> ⛔ 操作指令：本件是 APP 的收口口径（计划 §18.3）。每条判据给**证据落点**与**状态**；未跑/不可执行一律 `OPEN` 并带 owner，禁止写成 pass。机读面见 `app/results/GATES.json` / `app/results/SELF_AUDIT.json`；基线见 `results/app/BASELINE.md`。
> 状态：v1（2026-11-15）· 依据：计划 §13（质量门）/§15.3（自扫描）/§18（交付物与验收）。

## 1. 交付物清单（§18.1）

| # | 交付物 | 落点 | 状态 |
|---|---|---|---|
| D-01 | Android 工程（Kotlin/CMP + Rust 核心桥） | `app/android/` | 见 §3 OPEN-TOOLCHAIN |
| D-02 | Desktop 工程（CMP + Rust） | `app/desktop/` | 见 §3 OPEN-TOOLCHAIN |
| D-03 | TUI 集成（现有 + Studio 模块） | `tui/nf.py`（复用）+ `app/desktop` 集成点 | 复用面 pass；Studio 集成见 D-02 |
| D-04 | 数据模型/FFI/解析器/适配器 | `app/schema/`、`app/core/`、`app/cli/` | 进行中（见 RESULTS） |
| D-05 | 测试/golden/负例/设备矩阵 | `app/tests/`、`app/fixtures/`、`app/docs/DEVICE_MATRIX.md` | 进行中 |
| D-06 | 签名/公证/发布脚本 | `app/scripts/` | 脚本 pass；证据 OPEN-EXTERNAL |
| D-07 | 文档/ADR/交接 | `app/docs/`、`results/app/` | 进行中 |

## 2. DoD 判据（§18.3）

| 编号 | 判据 | 证据落点 | 状态 |
|---|---|---|---|
| DOD-01 | QA0–QA6 绿 | `python app/gates/run_gates.py` → `app/results/GATES.json` | 见 GATES（未全绿即不称 pass） |
| DOD-02 | P0=0；P1 有 owner | `app/results/SELF_AUDIT.json.summary.p0/p1` + `open_items[].owner` | 见 SELF_AUDIT |
| DOD-03 | 16KB/ABI/target 36；设备矩阵 | `app/docs/DEVICE_MATRIX.md` + Android 构建证据 | OPEN-TOOLCHAIN（本机无 Android SDK/真机） |
| DOD-04 | 无遥测/密钥不入 APP；分享/导入负例 | `app/docs/PRIVACY.md` + `app/tests/test_security_negative.py` | 负例 pass（见 GATES）；隐私数据地图进行中 |
| DOD-05 | 桌面签名/公证；手机发布材料 | `app/scripts/RELEASE_CHECKLIST.md` + `app/scripts/RELEASE_EVIDENCE.md` | OPEN-EXTERNAL（无证书/无 macOS） |
| DOD-06 | 文档 claims 对应代码/测试；开放项登记 | `app/results/SELF_AUDIT.json.open_items` + 各文档 OPEN 段 | 进行中 |
| DOD-07 | 首闭环（§18.2 七步）可复跑 | `python -m pytest app/tests/test_e2e_first_loop.py -q` | 见 GATES |
| DOD-08 | 确定性（同输入同字节） | `app/tests` 确定性用例 + `app/core` 单测 | 见 GATES |

## 3. OPEN 登记（不因收口关闭）

| id | 内容 | owner | 判据/下一步 |
|---|---|---|---|
| OPEN-TOOLCHAIN | 本机无 Gradle/Android SDK/kotlinc；Android APK 构建与 Compose Multiplatform 构建不可执行 | toolchain-scout → lead | 工具链勘察报告 `app/results/TOOLCHAIN.md`；可行则补构建证据，不可行则保留工程源码 + 可复跑脚本 |
| OPEN-EXTERNAL | 签名/公证/真机/设备矩阵/Play 数据安全提交不在本机能力内 | lead | 发布清单 + 证据模板；不冒充已签/已公证 |
| OPEN-UNIFFI | UniFFI 依赖本机不可得，改用 JSON-C ABI（ADR-APP-011） | lead | 依赖可得时加 UDL 绑定（不破 ABI） |
| OPEN-L2 | L2（仓库协议层）校验依赖 `nf` CLI 子进程，本方案默认 L0/L1 | lead | 环境缺失时 exit 4（NF-VAL-005），已实现语义 |
| OPEN-DOCXPDF | docx/pdf 导出未实现（首版只 md/zip/json） | lead | exit 4 + NF-EXP-004；次版补导出器探测 |

## 4. 完成判定

> 仓库门禁（2026-11-15 实测）：`bash verify.sh --checks-only` → PASS=107 WARN=2 FAIL=0（exit 0）。APP 自有门禁与本条互不替代：前者判 APP 面，后者判仓库面。

- **APP 面完成** = DOD-01/02/04/06/07/08 pass，DOD-03/05 明确 OPEN 且不影响功能面结论。
- **发布面完成** = 追加 DOD-03/05 pass（需外部环境）；在此之前**不得**宣称「可发布/已公证/已上架」。
- 收口报告以 `results/app/RESULTS.md` + `results/app/FINAL_DOD.md` 为准，并以现场复跑命令取证。