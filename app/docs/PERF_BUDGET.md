# NF APP 性能预算与测量口径

> ⛔ 操作指令：本件只做两件事——(1) 给出**可核的预算目标与测量方法**；(2) 如实登记**当前数据**（`no-data` 就是 no-data，禁止编造，禁止把预算写成实测）。任何一行要改数字，必须先按 §3 口径实测并把原始输出落 `app/scripts/RELEASE_EVIDENCE.md`。
> 状态：v1（2026-11-15）· 性质：预算 + 测量口径 · 取证时刻：2026-11-15 16:2x。
> 依据：ADR-APP-009（target 36/ABI/16KB）、ADR-APP-010（Apple Silicon 优先）、`app/docs/DEVICE_MATRIX.md`（设备覆盖）、`app/docs/CONTRACT.md` §7（确定性：禁时间戳进产物，性能数据只进本地证据）。

## 0. 前提（决定什么能测、什么不能测）

| 项 | 状态 | 影响 |
|---|---|---|
| 参考设备（Android 中档机，API 26+） | **未定** → OPEN-PERF-01 | 无参考设备 = Android 预算无法验收；只能先给目标 |
| Android SDK / 模拟器 | **不在场**（本机实测：无 `ANDROID_HOME`、无 `gradle`） | Android 启动/内存/包体：本机 `no-data` |
| 桌面构建工具链 | **不在场**（Gradle 缺，JDK 21 在场） | Desktop 启动/内存/包体：本机 `no-data` |
| 共享核心源码 | 进行中（`app/core/src` 已有模块，测试证据以 `cargo test` 实跑为准） | 核心 op 耗时：待实现稳定后测 |
| 控制面测试 | 可跑（本机实测：安全负例 47 passed / schema 87 of 88 passed） | 门禁时延可测 |

**预算不是实测**：下表 `预算` 列是目标值（团队承诺的上限），`当前数据` 列才是事实；两者不得混用。

## 1. 预算表（目标 × 口径 × 方法）

| 编号 | 指标 | 预算（目标） | 测量口径 | 方法 | 当前数据 | 状态 / owner |
|---|---|---|---|---|---|---|
| P-01 | Android 冷启动到首帧可见 | P50 ≤ **1.5 s**，P90 ≤ **2.5 s** | 冷启动（`am force-stop` 后）、单次取 TotalTime，≥10 次取 P50/P90 | `adb shell am start -W -n <pkg>/<act>`；或 Macrobenchmark `StartupTimingMetric` | `no-data`（无 SDK/真机） | OPEN-TOOLCHAIN / toolchain-scout |
| P-02 | Android 温启动（已驻留→可交互） | P50 ≤ **0.5 s** | 预热 ≥3 次后测，≥10 次 | 同上 | `no-data` | OPEN-TOOLCHAIN |
| P-03 | Desktop 启动到可交互 | Windows/macOS P50 ≤ **2.0 s**，P90 ≤ **3.0 s** | 进程启动→主窗口可点击，≥10 次 | 手工秒表/系统日志 + 重复 10 次 | `no-data`（无端壳构建） | OPEN-TOOLCHAIN / kotlin-ui |
| P-04 | 首次装配（sample pack） | P50 ≤ **3.0 s**，P90 ≤ **5.0 s** | 输入 = `app/fixtures/sample-pack`（spec ≤200 KiB、槽位 ≤50）、无 UI；核心 `assemble` 进程内耗时至产物写出 | `Measure-Command { python -m nf_app assemble ... }`（Windows）/ `time`（POSIX），≥10 次（含 1 次预热） | `no-data`（核心实现进行中） | OPEN-PERF-02 / rust-core |
| P-05 | 块级重装配（单节替换） | ≤ **0.5 s** | 同上但只替换 1 个 section | 同 P-04 | `no-data` | OPEN-PERF-02 |
| P-06 | 导出 md | ≤ **0.2 s**（≤200 KiB 产物） | 单次导出耗时（不含 UI） | 同 P-04（`export --format md`） | `no-data` | OPEN-PERF-02 |
| P-07 | 导出 zip | ≤ **1.0 s**（≤1000 entries、总量 ≤64 MiB） | 同上；记录 entries/bytes | 同 P-04（`export --format zip`） | `no-data` | OPEN-PERF-02 |
| P-08 | L0+L1 校验 | ≤ **1.0 s**（sample pack 规模） | `validate` 单次耗时 | 同 P-04 | `no-data` | OPEN-PERF-02 |
| P-09 | Android 峰值内存（PSS，首闭环） | ≤ **200 MB** | 首闭环完成后 `dumpsys meminfo` 的 TOTAL PSS 峰值（采样 ≥3 次） | `adb shell dumpsys meminfo <pkg>` + 手工操作脚本 | `no-data` | OPEN-TOOLCHAIN |
| P-10 | Desktop 峰值 RSS（首闭环） | ≤ **500 MB** | 进程 RSS 峰值 | Windows: `Get-Process`/性能计数器；macOS: `ps -o rss`；采样 ≥3 次 | `no-data` | OPEN-TOOLCHAIN / kotlin-ui |
| P-11 | Android APK（单 ABI） | ≤ **25 MB** | release APK 文件字节数（每 ABI 分别记） | `ls -l <apk>`；`aapt dump badging` | `no-data` | OPEN-TOOLCHAIN |
| P-12 | Android AAB 下载体积 | ≤ **20 MB**（Play 报告的下载大小） | Play Console 下载大小 / `bundletool get-size total` | `bundletool get-size total --apks=...` | `no-data` | OPEN-EXTERNAL |
| P-13 | Windows MSIX | ≤ **60 MB** | 安装包字节数 | `ls -l <msix>` | `no-data` | OPEN-TOOLCHAIN / lead |
| P-14 | macOS dmg | ≤ **80 MB** | 安装包字节数 | `ls -l <dmg>` | `no-data` | OPEN-EXTERNAL |
| P-15 | 控制面测试门禁时延 | ≤ **120 s**（`python -m pytest app/tests -q`） | 单次全量耗时 | 计时命令（见 §3） | 部分可测（当前 tests 子集实测秒级） | partial / python-plane |
| P-16 | 核心构建（release） | ≤ **180 s**（干净 target、单机冷构建） | `cargo build --release` 墙钟 | `time cargo build --release` | `no-data`（实现进行中） | OPEN-PERF-02 / rust-core |
| P-17 | 确定性开销 | 两次同输入装配耗时偏差 ≤ **10%** | 同一输入连续两次耗时 | 同 P-04 | `no-data` | OPEN-PERF-02 |

## 2. 本机实测（这些数字是真的，但不是上面任何预算的实测）

> 口径：本机实测只用于「当前实现规模/门禁速度」的事实登记；**不得**当作 P-01…P-17 的实测值，也不得外推为发布结论。

| # | 项 | 实测值（2026-11-15） | 命令 |
|---|---|---|---|
| S-01 | 契约层总字节 | 78,759 B（`app/schema`，15 件 JSON） | `du -sb app/schema` |
| S-02 | 共享核心源码规模 | 取证时刻 25 文件 / 7,715 行 / 270,873 B（实现进行中，数字随提交变动） | `find app/core/src -name "*.rs" \| xargs wc -l` |
| S-03 | 核心 debug 产物 | 5,092,650 B（`app/core/target/debug/nf-app-core.exe`；**debug 构建，非发布包体**） | `ls -l app/core/target/debug/nf-app-core.exe` |
| S-04 | 安全负例耗时 | 47 passed，≈0.5 s（多次运行 0.2–0.5 s，随机器负载浮动） | `python -m pytest app/tests/test_security_negative.py -q -p no:cacheprovider` |
| S-05 | schema 正反夹具耗时 | 87 passed / 1 failed，≈1.8 s | `python -m pytest app/tests/test_schema_valid.py app/tests/test_schema_negative.py -q -p no:cacheprovider` |
| S-06 | 控制面源码规模 | 取证时刻 27 文件 / 4,252 行（`app/cli/**/*.py`，数字随提交变动） | `find app/cli -name "*.py" \| xargs wc -l` |

## 3. 测量方法细则（复跑时照做，否则数据不可比）

| 规则 | 要求 |
|---|---|
| 次数与统计 | 每项 ≥10 次；报告 P50 与 P90（不报均值）；先做 1 次预热并丢弃 |
| 冷启动定义 | `adb shell am force-stop <pkg>` 后启动；温启动 = 进程已驻留 |
| 记录字段 | 时间/设备型号/OS 版本/构建号（git HEAD）/ABI/是否 debug/输入夹具 digest |
| 输入固定 | 装配类固定 `app/fixtures/sample-pack`（并记其 tree digest）；导出类固定产物字节数 |
| 环境隔离 | 关掉其它大内存进程；Windows 电源计划高性能；移动端保持电量充足 |
| 日志落点 | `app/scripts/RELEASE_EVIDENCE.md` 追加「性能实测」小节（原始输出片段 + P50/P90） |
| 禁止 | 不得把 debug 构建数字当发布数字；不得只测 1 次；不得改夹具后不记 digest；不得把预算当实测 |

**命令模板**：

```bash
# Android 冷启动（10 次）
for i in 1 2 3 4 5 6 7 8 9 10; do
  adb shell am force-stop <pkg>
  adb shell am start -W -n <pkg>/<activity> | grep TotalTime
done
# 装配/导出（POSIX）
time python -m nf_app assemble --plan <plan> --spec <spec> --inputs <inputs.json> --out-dir <dir>
# Windows 计时
Measure-Command { python -m nf_app assemble ... } | Select-Object TotalSeconds
# 包体
ls -l <apk|msix|dmg>
```

## 4. no-data 登记（逐项，禁止编造）

| 编号 | 为什么 no-data | owner | 解除条件 |
|---|---|---|---|
| P-01/P-02/P-09/P-11 | 本机无 Android SDK/模拟器/真机（实测：无 `ANDROID_HOME`、无 `gradle`） | toolchain-scout | 工具链 + 设备到位后按 §3 实测 |
| P-03/P-10/P-13 | 桌面端壳未构建（无 Gradle） | kotlin-ui | CMP 工程可构建后实测 |
| P-12/P-14 | 商店/公证外部条件不可得 | lead | 有 Play/Apple 账号后实测 |
| P-04…P-08/P-16/P-17 | 核心实现进行中，稳定性不足 | rust-core | 核心 op 全绿 + 固定夹具后实测 |
| P-15 | 全量 tests 未落地（当前只有 schema/安全子集） | python-plane | `app/tests` 全量落地后计时 |

## 5. OPEN 清单

| id | 内容 | owner | 下一步 |
|---|---|---|---|
| OPEN-PERF-01 | 参考设备档位未定（Android 中档机具体型号/Android 版本） | lead | 定 1 台参考机（记录型号/SoC/API/内存）写入本件 §0 |
| OPEN-PERF-02 | 核心 op 实测缺失（装配/校验/导出/构建） | rust-core | 核心稳定后按 §3 实测并回填 §1 |
| OPEN-TOOLCHAIN | 无 Android/桌面运行环境 | toolchain-scout | 见 `app/results/TOOLCHAIN.md`（待落）；不可行保持 OPEN |
| OPEN-PERF-03 | 首闭环总时延（端到端，含 UI）未定义预算 | kotlin-ui | 端壳可运行后补 P-18（首闭环 ≤30 s 目标，见 `ARCHITECTURE.md` QAS-6） |

## 6. 判据命令（现状复核）

```bash
# 本机跑得动的门禁时延
time python -m pytest app/tests -q -p no:cacheprovider
# 契约层/核心规模（不是性能，只做规模登记）
du -sb app/schema; find app/core/src -name "*.rs" | xargs wc -l | tail -1
# 构建与运行时能力探测（期望本机：NO_GRADLE / NO_ANDROID_ENV）
command -v gradle || echo NO_GRADLE; env | grep -i android || echo NO_ANDROID_ENV
```

> 本件不承诺任何未实测的性能结论；`no-data` 项在 `RELEASE_EVIDENCE.md` 出现实测数据前，发布结论只能是「性能未实测」。

