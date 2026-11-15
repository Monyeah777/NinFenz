# NF APP 设备与平台矩阵（Android / Windows / macOS）

> ⛔ 操作指令：本件是设备覆盖与**证据状态**登记表。每格只有两种写法：**本机可实测**（附命令与产物路径）或 **OPEN + owner + 下一步**。禁止把「计划支持」写成「已验证支持」；无真机/无 SDK 的平台一律 `OPEN-TOOLCHAIN` / `OPEN-EXTERNAL`。改本件必须同步 `app/scripts/RELEASE_CHECKLIST.md`（发布判据）与 `app/docs/PERF_BUDGET.md`（性能口径）。
> 状态：v1（2026-11-15）· 性质：设备/平台覆盖登记 · 取证时刻：2026-11-15 16:1x（本机实测，见 §0）。
> 依据：`app/docs/CONTRACT.md`（格式/安全/隐私）、ADR-APP-009（16KB/target36/ABI 进 CI）、ADR-APP-010（Apple Silicon 优先）、`app/scripts/RELEASE_CHECKLIST.md`；基线环境见 `results/app/BASELINE.md` §2.1。

## 0. 实施机环境（本机实测，决定「可实测」边界）

| 项 | 实测值 | 判据命令 | 对矩阵的影响 |
|---|---|---|---|
| 操作系统 | Windows 10.0.26200（Windows 11 内核版本号），AMD64 | `cmd /c ver`；`echo $PROCESSOR_ARCHITECTURE` | Windows x64 只能做**构建级**验证；无 Android 运行时 |
| JDK | OpenJDK 21.0.8 LTS（Microsoft build） | `java -version` | 满足 Android/CMP 的 JDK 要求 |
| Gradle | **不在场**（`gradle` 命令不存在） | `command -v gradle` | Android/Desktop 工程不可构建 → OPEN-TOOLCHAIN |
| Android SDK | **不在场**（`ANDROID_HOME`/`ANDROID_SDK_ROOT` 空；无 SDK 目录） | `env \\| grep -i android` | 无模拟器/无 adb/无 aapt → 全部 Android 运行证据不可得 |
| kotlinc | 不在场 | `command -v kotlinc` | Kotlin 编译器只随 Gradle/IDE 提供 |
| Rust | cargo 1.99.1 / rustc 1.99.1 | `cargo -V` | 共享核心可本机构建（源码占位，待 rust-core） |
| Python | 3.11.9 / pytest 9.1.1 | `python -V` | 控制面/契约/安全负例可本机跑 |
| macOS | **不在场** | — | macOS 构建/签名/公证一律 OPEN-EXTERNAL |
| 真机/模拟器 | 无（无 SDK、无连接设备） | `adb devices`（adb 不存在） | 折叠/平板/Chromebook 运行证据不可得 |

> 结论：本机能力 = **Windows x64 的控制面/核心测试**；Android 与 macOS 全部为 `OPEN`。这是取证边界，不是产品结论。

## 1. 矩阵总表

| # | 平台 / 设备类 | 目标基线 | 构建证据 | 运行证据 | 本机可实测？ | 状态 / owner |
|---|---|---|---|---|---|---|
| M-01 | Android 手机（API 26+，arm64-v8a） | minSdk 26 / targetSdk 36 / compileSdk 36 | `bash app/scripts/build_android.sh release` → APK/AAB + `aapt dump badging` | 真机安装 + 首启动 + 首闭环 | **否**（无 SDK/真机） | OPEN-TOOLCHAIN / toolchain-scout |
| M-02 | Android 手机（API 26+，x86_64） | 同 M-01（ABI x86_64，模拟器） | 同 M-01 + `zipalign -c -P 16` | 模拟器（API 26/30/34/36）安装启动 | **否**（无模拟器） | OPEN-TOOLCHAIN / toolchain-scout |
| M-03 | 16KB page 设备（Android 15+） | 16KB 对齐（native libs + `-P 16`） | `zipalign -c -P 16 <apk>` + NDK 16KB 参数 | 16KB 设备/模拟器启动 | **否** | OPEN-TOOLCHAIN（判据：`RELEASE_CHECKLIST` A2） |
| M-04 | 折叠屏（Foldable） | 大屏适配 + 展开/折叠重建 | 同 M-01 | 真机/模拟器 resize + 旋转 + 多窗口 | **否** | OPEN-EXTERNAL / lead |
| M-05 | 平板（Tablet） | 大屏布局 + 分栏 | 同 M-01 | 模拟器/真机 | **否** | OPEN-EXTERNAL / lead |
| M-06 | Chromebook（Android 容器） | x86_64 + 鼠标/键盘 + 窗口化 | 同 M-02 | Chromebook 安装启动 | **否** | OPEN-EXTERNAL / lead |
| M-07 | 中国渠道（无 GMS） | flavor `cn`（无 GMS 依赖） | `productFlavors { cn }` + 构建 | 无 GMS 设备启动 | **否** | OPEN-TOOLCHAIN（判据：`RELEASE_CHECKLIST` A7） |
| W-01 | Windows 10 x64（22H2+） | CMP Desktop（JVM） | `bash app/scripts/build_desktop.sh package` | 本机启动 + 首闭环 | **部分**（JDK 在场；Gradle 缺 → 构建不可执行） | OPEN-TOOLCHAIN / kotlin-ui |
| W-02 | Windows 11 x64 | 同 W-01 | 同 W-01 | 本机启动 + 首闭环 | **部分**（同上；本机 OS 为 10.0.26200） | OPEN-TOOLCHAIN / kotlin-ui |
| W-03 | Windows 11 arm64 | 同 W-01（arm64 JVM） | 单独构建 | arm64 真机 | **否**（本机 x64） | OPEN-EXTERNAL / lead |
| W-04 | Windows MSIX / EXE 签名 | Authenticode | `MakeAppx` + `signtool`（`app/scripts/sign_windows.ps1`） | 安装/升级/卸载 | **否**（无证书/无 SDK signing） | OPEN-EXTERNAL / lead |
| A-01 | macOS 13+ arm64（Apple Silicon） | CMP Desktop（macOS arm64） | `bash app/scripts/build_desktop.sh package`（macOS 上） | 启动 + 首闭环 | **否**（非 macOS） | OPEN-EXTERNAL / lead（ADR-APP-010） |
| A-02 | macOS 签名/公证 | Developer ID + Hardened Runtime + notarytool + staple | `app/scripts/notarize_macos.sh <App.app>` | Gatekeeper 放行 | **否** | OPEN-EXTERNAL / lead |
| A-03 | macOS 13+ x64（Intel） | 单独构建（非首发） | 同 A-01（x64） | 启动 | **否** | OPEN（ADR-APP-010：Intel 后置） |
| T-01 | TUI（任意平台） | 终端真源（复用） | 源码 + `tui/build_exe.ps1`/`.sh` | `python tui/nf.py --selftest` | **是**（本机 9 项 ✔，见 `results/app/BASELINE.md` §2.1） | partial（复用面在场） |

> 表格中 `T-01` 是既有 TUI 的跨平台条目（非 APP 端壳），列在此处是为了让「终端真源」在设备矩阵里有位置；它不代表 APP 已支持任何终端平台。

## 1.1 端壳工程配置实读（源码证据，**不等于**构建/运行证据）

| 项 | 实读值 | 落点 | 说明 |
|---|---|---|---|
| Android compileSdk / buildTools | 36 / 36.0.0 | `app/android/app/build.gradle.kts` | 与 target 36 基线一致 |
| Android minSdk / targetSdk | 26 / 36 | 同上 | 与 ADR-APP-009 一致 |
| Android ABI | `arm64-v8a` + `x86_64` | 同上（`ndk.abiFilters`） | 与矩阵 M-01/M-02 一致 |
| Android 16KB 相关 | `packaging.jniLibs.useLegacyPackaging = false` | 同上 | 仍需 `zipalign -P 16` 产物级验证（OPEN-TOOLCHAIN） |
| Android 插件版本 | AGP 8.10.1 / Kotlin 2.1.20 / Compose 插件 2.1.20 | `app/android/build.gradle.kts` | 版本已声明；未解析（无 SDK） |
| Android Manifest | 组件导出/权限声明 | `app/android/app/src/main/AndroidManifest.xml` | 安全面判据（exported/权限）待端壳落地后核验 |
| Desktop 依赖声明 | Compose 1.7.3 / Kotlin 2.1.20 / kotlinx-serialization-json 1.8.1 / JNA 5.17.0 / JUnit 4.13.2 | `app/desktop/build.gradle.kts` | 未解析（无 Gradle 发行版） |
| Gradle wrapper | 8.11.1，`distributionUrl` = huaweicloud 镜像 + `distributionSha256Sum` 已钉 | `app/{android,desktop}/gradle/wrapper/gradle-wrapper.properties` | 镜像可用性是构建前置（见 `DEPENDENCIES.md` §5） |
| 原生核心集成 | Android 期望 `src/main/jniLibs/{arm64-v8a,x86_64}/libnf_app_core.so`；Desktop 期望 `app/core/target/{release,debug}/nf_app_core.dll` | `app/android/app/build.gradle.kts`、`app/desktop/build.gradle.kts` | 缺失时不阻断构建但运行时报 `NF-E-005`（设计，不是假数据） |

> 这些是**源码声明**：`build.gradle.kts` 里写了的版本必须由一次真实构建才变成证据。当前本机无法构建 → 全部仍归 `OPEN-TOOLCHAIN`。

## 2. Android 细分口径

| 项 | 口径 | 判据命令（补齐证据时用） | 状态 |
|---|---|---|---|
| minSdk | **26**（Android 8.0） | `aapt dump badging <apk> \\| grep sdkVersion`；构建配置 `minSdk = 26` | OPEN-TOOLCHAIN |
| targetSdk / compileSdk | **36** | `aapt dump badging \\| grep targetSdkVersion`；`grep targetSdk app/android/**/build.gradle.kts` | OPEN-TOOLCHAIN |
| ABI | `arm64-v8a` + `x86_64`（NDK `abiFilters`） | `unzip -l <apk> \\| grep lib/`；`aapt dump badging \\| grep native-code` | OPEN-TOOLCHAIN |
| 16KB page | native 库 16KB 对齐 + zip 对齐 | `zipalign -c -P 16 -v 4 <apk>`；`.so` 的 ELF 段对齐检查（`readelf -l`） | OPEN-TOOLCHAIN（A2） |
| 折叠屏 | 展开/折叠、`onConfigurationChanged` 重建、多窗口 | 模拟器 resize + 旋转 + 分屏 | OPEN-EXTERNAL |
| 平板 | 大屏布局、分栏、横竖屏 | 平板模拟器/真机 | OPEN-EXTERNAL |
| Chromebook | x86_64 + 鼠标键盘 + 窗口化 + ARC++ 限制 | Chromebook 真机 | OPEN-EXTERNAL |
| 无障碍 | TalkBack/RTL/字体缩放/pseudo-locale 抽查 | 设备端手工抽查 + Compose UI 测试 | OPEN-TOOLCHAIN（QA5） |
| 权限 | 仅必要权限；无位置/通讯录/相机/麦克风（设计） | `aapt dump permissions <apk>` | OPEN-TOOLCHAIN |
| 网络安全配置 | 不允许明文；无出站（设计） | `res/xml/network_security_config.xml` 审查 | OPEN-TOOLCHAIN |

## 3. Windows 细分口径

| 项 | 口径 | 判据命令 | 状态 |
|---|---|---|---|
| 最低版本 | Windows 10 22H2 x64 / Windows 11 x64 | 本机 10.0.26200（实测） | 构建 OPEN-TOOLCHAIN |
| 运行时 | JVM 随包（jpackage/CMP packaging） | `java -version` + 产物内 runtime 目录 | OPEN-TOOLCHAIN |
| 安装形态 | MSIX（Store 优先）→ EXE 侧载需 Authenticode | `MakeAppx pack` + `signtool verify /pa` | OPEN-EXTERNAL（无证书） |
| 文件关联 | `.nfproject` / `.nfpack` / `.nftpl` | 安装包 manifest + 双击实测 | OPEN-TOOLCHAIN（W5） |
| arm64 | 独立构建（评估，不承诺首版） | arm64 JVM + 产物 | OPEN-EXTERNAL |
| 高 DPI / 多显示器 / 输入法 | 缩放 100–200%、跨屏、中文输入 | 手工 + Compose 测试 | OPEN-TOOLCHAIN |

## 4. macOS 细分口径

| 项 | 口径 | 判据命令 | 状态 |
|---|---|---|---|
| 最低版本 | macOS 13+（Ventura+），arm64 首发 | `sw_vers`（macOS 上） | OPEN-EXTERNAL（无 macOS） |
| 架构 | arm64；Intel 后置评估 | `file <app>/Contents/MacOS/*`；`lipo -info` | OPEN-EXTERNAL |
| 签名 | Developer ID Application + Hardened Runtime | `codesign -dv --verbose=4 <app>`；`codesign --verify --deep --strict` | OPEN-EXTERNAL |
| 公证 | notarytool 提交 + staple | `xcrun notarytool submit ... --wait`；`xcrun stapler validate <app>` | OPEN-EXTERNAL |
| Gatekeeper | 首次启动放行 | 真机/虚拟机 | OPEN-EXTERNAL |
| 沙箱与文件权限 | 用户选定目录读写（security-scoped bookmark） | 手工验证 | OPEN-EXTERNAL |

## 5. 证据产生方式（补齐矩阵时按此执行，禁止编造）

| 证据类型 | 产生命令 | 落点 | 备注 |
|---|---|---|---|
| Android 构建 | `bash app/scripts/build_android.sh release` | `app/android/app/build/outputs/apk/release/`（构建产物落点，当前不存在） | 缺 SDK 时脚本 exit 4（不假装构建） |
| Android 包信息 | `aapt dump badging <apk>`（记录 sdkVersion/targetSdkVersion/native-code） | `app/scripts/RELEASE_EVIDENCE.md` | 记录原始输出片段 |
| 16KB 判据 | `zipalign -c -P 16 -v 4 <apk>` | 同上 | 期望 `Verification succesful` |
| 启动耗时 | `adb shell am start -W -n <package>/<activity>`（TotalTime/WaitTime） | `PERF_BUDGET.md` 实测表 | 至少 10 次取中位数 |
| 桌面构建 | `bash app/scripts/build_desktop.sh package` | `app/desktop/build/...`（构建产物落点，当前不存在） | 缺 Gradle 发行版时 exit 4 |
| Windows 签名 | `pwsh -File app/scripts/sign_windows.ps1 -Package <dir> -Cert <pfx>` | `RELEASE_EVIDENCE.md`（证书指纹/时间） | 无证书时脚本 exit 4 |
| macOS 公证 | `bash app/scripts/notarize_macos.sh <App.app>` | `RELEASE_EVIDENCE.md`（submission id/staple 输出） | 非 macOS → exit 4 |

## 6. OPEN 登记（不因矩阵表存在而关闭）

| id | 内容 | owner | 下一步 |
|---|---|---|---|
| OPEN-TOOLCHAIN | 无 Gradle/Android SDK/kotlinc → Android/Desktop 构建与运行证据全不可得 | toolchain-scout | 按 `app/results/TOOLCHAIN.md`（待落）结论：可行则补构建证据；不可行保持 OPEN |
| OPEN-EXTERNAL | 真机/模拟器/Chromebook/折叠/平板/macOS/证书/商店账号 | lead | 有外部环境后按 §5 补证；不冒充 |
| OPEN-DEV-01 | 16KB 判据需 NDK/Gradle 参数确认（`zipalign -P 16` 行为随 build-tools 版本） | kotlin-ui | 端壳落地后钉 build-tools 版本并记录 |
| OPEN-DEV-02 | Windows arm64 / macOS Intel 不在首发，覆盖结论未定 | lead | 按 ADR-APP-010 复审条件评估 |
| OPEN-DEV-03 | Android 构建引用 `app/scripts/build_core_android.sh`，但该脚本当前不在 `app/scripts/` 中 | kotlin-ui / rust-core | 补脚本 `app/scripts/build_core_android.sh`（交叉编译 arm64-v8a/x86_64 进 jniLibs）或改引用；不补则 APK 可构建但运行时 `NF-E-005` |

## 7. 判据命令（现状复核）

```bash
cmd /c ver                                  # 本机 OS 版本（Windows）
java -version                               # JDK 21
command -v gradle || echo NO_GRADLE         # 期望：NO_GRADLE（本机）
env | grep -i android || echo NO_ANDROID_ENV # 期望：NO_ANDROID_ENV（本机）
python tui/nf.py --selftest                 # TUI 复用面（9 项）
```

> 代码侧自适应：三档宽度（<600 / 600–839 / ≥840）→ 紧凑单页导航栈 / 常驻 NavigationRail + 内容区（`app/android/.../ui/Adaptive.kt`，JVM 单测 `AdaptiveLayoutTest`）；折叠/平板/多窗口的**真机实测**仍为 `OPEN-TOOLCHAIN`。
>
> 本件为覆盖登记：所有 `OPEN-*` 格都不是「已验证支持」。发布结论必须以 `app/scripts/RELEASE_EVIDENCE.md` 的实测证据为准。

