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
| OPEN-TOOLCHAIN | 真机/模拟器 E2E、APK 安装启动、MSI 安装双击、CMP 交互运行（构建面已在本机工具链验证） | lead | 需 adb 设备/模拟器；不阻断构建结论 |
| OPEN-EXTERNAL | 签名/公证/Play 数据安全/macOS 构建（无证书/无 macOS） | lead | `app/scripts/RELEASE_EVIDENCE.md` 留位，不冒充 |
| OPEN-UNIFFI | UniFFI 依赖本机不可得，改用 JSON-C ABI（ADR-APP-011） | lead | 依赖可得时加 UDL 绑定（不破 ABI） |
| OPEN-L2 | L2（仓库协议层）校验依赖 `nf` CLI 子进程，本方案默认 L0/L1 | lead | 缺环境 exit 4（NF-VAL-005），语义已实现 |
| OPEN-PDF | PDF 导出不内置（docx 已实现；pdf 走平台打印另存为 PDF） | lead | 平台打印（Android PrintManager / 桌面 javax.print）；核心 exit 4 + NF-EXP-004，不冒充 |
| OPEN-CHECK58 | APP 门禁未接入仓库 `verify.sh`（check58） | lead | 前置已满足（`bash verify.sh --checks-only` = PASS=107 WARN=2 FAIL=0）；接入需改 check1–57 之外新增 58 + 版本面/README 三语/PASS 基线联动 + 冻结链——本波未做（可选下一波） |
| OPEN-DATADIR | 数据目录保留窗口/崩溃恢复（进程死亡恢复）未实现 | lead | 保留策略与恢复测试（A6/Q 后补） |
| OPEN-MAP-DECISION | map-suggest 决策仅落 sidecar JSON，未接 core 复算 | python-plane | 接 core `map-suggest` 复算并加用例 |
| OPEN-INBOX | 授权目录 Inbox 自动解析（WorkManager 遍历/去重/撤销） | kotlin-ui | 需 Android 运行时 |
| OPEN-DEEPLINK | 深链/QR 传输（计划 §10.2 可选） | kotlin-ui | 未实现 |
| OPEN-A11Y | TalkBack/RTL/字体缩放实测 | kotlin-ui | 需设备 |
| OPEN-PERF | 启动/装配/内存/包体实测预算 | lead | 需 Android 运行时；`PERF_BUDGET.md` 已给口径 |
| OPEN-REPRO | 构建可复现（同源二次构建逐字节） | lead | buildinfo 对照 |

## 4. 完成判定

> 仓库门禁（2026-11-15 实测）：`bash verify.sh --checks-only` → PASS=107 WARN=2 FAIL=0（exit 0）。APP 自有门禁与本条互不替代：前者判 APP 面，后者判仓库面。

- **APP 面完成** = DOD-01/02/04/06/07/08 pass，DOD-03/05 明确 OPEN 且不影响功能面结论。
- **发布面完成** = 追加 DOD-03/05 pass（需外部环境）；在此之前**不得**宣称「可发布/已公证/已上架」。
- 收口报告以 `results/app/RESULTS.md` + `results/app/FINAL_DOD.md` 为准，并以现场复跑命令取证。