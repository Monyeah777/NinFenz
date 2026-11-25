# NF APP 工具链勘察与构建证据

> ⛔ 操作指令：本件是 APP 构建能力的**结果落档**。每条结论给可复跑命令与产物；未做的面（真机/模拟器/安装启动）写 `OPEN`，不冒充。原始勘察报告在作者本机 `D:\tmp\app-toolchain\REPORT.md`（416 行，不入仓；本文是仓库侧摘要与判据入口）。
> 状态：v1（2026-11-15）· 执行：toolchain-scout · 复核：lead。

## 1. 结论表

| # | 结论 | 证据（本机） | 状态 |
|---|---|---|---|
| T-01 | Android Compose 工程可构建出 APK | 最小工程 `android-min/app-debug.apk`（10,089,694 B）；**本仓真实工程** `app/android/app/build/outputs/apk/debug/app-debug.apk`（17,973,649 B） | **pass（本机）** |
| T-02 | CMP Desktop Windows 可打包 MSI / 可执行发行版 | 最小工程 `CmpMin-1.0.0.msi`（61,340,146 B）+ 可执行发行版 126 MB；**本仓** `app/desktop/build/compose/binaries/main/msi/NFStudio-0.1.0.msi`（66,573,406 B，jar 内含 `native/nf_app_core.dll`） | **pass** |
| T-03 | Rust 核心 → Android `.so`（arm64-v8a / x86_64）可构建（裸 NDK，不依赖 cargo-ndk） | `rust-android-demo/dist/android/<abi>/libnf_app_core.so`（260,304 / 289,488 B，`file` 显示 "for Android 21, built by NDK r27"，导出 3 个 C 符号） | **pass** |
| T-04 | 本仓 APK 内含 Rust 核心 | `app/android/app/src/main/jniLibs/{arm64-v8a,x86_64}/libnf_app_core.so`（4,478,824 / 4,645,976 B） | **pass** |
| T-05 | 真机/模拟器 adb 运行、APK 安装启动、MSI 安装双击、CMP `run`（弹窗） | — | **未做 → OPEN-TOOLCHAIN**（owner: lead） |

## 2. 定版工具链（已验证组合）

| 组件 | 版本 | 落地 |
|---|---|---|
| JDK | Microsooft OpenJDK **21.0.8** | `C:\Users\<user>\AppData\Local\Programs\Microsoft\jdk-21.0.8.9-hotspot` |
| Gradle | **8.11.1**（sha256 `f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6`） | `D:\tmp\app-toolchain\gradle\gradle-8.11.1`（`GRADLE_USER_HOME=D:\tmp\app-toolchain\gradle-home`，1.3 GB 热缓存） |
| Android SDK | platforms;android-36 (rev 2) / build-tools;36.0.0 / platform-tools 37.0.1 / **NDK r27 (27.0.12077973)** | `D:\tmp\app-toolchain\android-sdk`（2.7 GB） |
| AGP | **8.10.1** | Gradle 插件 |
| Kotlin | **2.1.20**（+ compose plugin 同版本） | — |
| Compose BOM | **2025.05.00** | — |
| Compose Multiplatform | **1.7.3** | — |
| JNA | 5.17.0 | Desktop/Android FFI |
| APK 目标 | compileSdk 36 / targetSdk 36 / minSdk 26（本仓） | `app/android/app/build.gradle.kts` |

**环境脚本**：`D:\tmp\app-toolchain\env.sh` / `env.ps1`（JAVA_HOME / GRADLE_HOME / ANDROID_HOME / GRADLE_USER_HOME / WIX_PATH / 清死代理）。

## 3. 本仓工程的构建（复跑）

```bash
source D:/tmp/app-toolchain/env.sh          # 或等价导出 JAVA_HOME/ANDROID_HOME/GRADLE_USER_HOME

# Rust 核心（CLI + cdylib）
bash app/scripts/build_core.sh --release

# Rust → Android .so（写入 jniLibs；需 NDK）
bash app/scripts/build_core_android.sh

# Android APK
bash app/scripts/build_android.sh debug      # → app/android/app/build/outputs/apk/debug/
bash app/scripts/build_android.sh release    # 需签名（OPEN-EXTERNAL）

# Desktop CMP（Windows MSI）
bash app/scripts/build_desktop.sh package    # 需 WIX_PATH + -Pcompose.desktop.application.downloadWix=false
```

**已知坑（全部实测，必须照做）**：

1. **死代理**：系统/git 全局 `http.proxy=127.0.0.1:65532` 不可用；cargo/git 会中招。命令前 `unset HTTP(S)_PROXY/ALL_PROXY` 或 `NO_PROXY=*`；`env.sh` 已处理。
2. **Gradle 分发包**：`services.gradle.org` 307→GitHub 实测 13.8–22.5 KB/s（不可用）；用华为镜像 `mirrors.huaweicloud.com/gradle/gradle-8.11.1-bin.zip`（带官方 sha256）。腾讯镜像会对 Java 客户端返回 985 B 反爬 JS（`zip END header not found`），**不可用**。
3. **Maven 仓库顺序**：`dl.google.com/dl/android/maven2` 对大文件间歇 `Connection reset`；仓库顺序必须**阿里云优先**（`maven.aliyun.com/repository/google` → `/public` → `google()` → `mavenCentral()`）。
4. **CMP MSI 的 WiX**：默认 `downloadWix` 从 GitHub 拉 34.6 MB（~20 KB/s）。必须预置 WiX 3.11 并 `WIX_PATH=...` + `-Pcompose.desktop.application.downloadWix=false`。
5. **Android NDK + Rust linker**：Windows 上 rustc 不能执行 NDK 的 `*.cmd`；linker 要指到 `.../toolchains/llvm/prebuilt/windows-x86_64/bin/clang.exe`，并加 `-C link-arg=--target=aarch64-linux-android21`（x86_64 同理）。模板：`D:\tmp\app-toolchain\rust-android-demo/.cargo/config.toml`；本仓 `app/scripts/build_core_android.sh` 按其实现。
6. **cargo 镜像**：crates.io 直连被死代理拦截；本机用 `rsproxy.cn` sparse 镜像（模板 `app/core/.cargo/config.toml.example`，真文件 gitignored；**CI 用默认 crates.io**，供应链纪律见 `app/docs/DEPENDENCIES.md`）。

## 3.5 Android 单测

本机 Gradle 缺 `com.android.tools.layoutlib:layoutlib-resources:15.2.3` 的 jar，在线解析会卡住。运行 `python app/scripts/setup_android_tests.py` 会把 SDK 的 `platforms/android-*/data/res` 打成 jar 放入 mavenLocal，配合 `settings.gradle.kts` 的 `mavenLocal()` 可跑 Robolectric + Paparazzi；无 SDK 时回退空 jar（只能跑非渲染测试）。

## 4. 证据哈希（本机）

| 产物 | 大小 | sha256（前缀） |
|---|---|---|
| 最小工程 APK | 10,089,694 B | `5514f79a…cb0c1d` |
| 最小工程 MSI | 61,340,146 B | `ba5e08ee…4e02` |
| 本仓 APK | 17,973,649 B | `zipalign -c -P 16 4` 通过（16KB 页对齐） |
| 本仓 MSI | 66,573,406 B | 未签名（OPEN-EXTERNAL） |
| 本仓 arm64 .so | 4,478,824 B | LOAD align 0x4000 |
| 本仓 x86_64 .so | 4,645,976 B | 同上 |

> 本仓产物的 sha256 在**每次构建后**可能变化（未做可复现构建，见 `app/docs/DEPENDENCIES.md` SC-04）；发布证据以 `RELEASE_EVIDENCE.md` 现场记录为准。

## 5. 未做（OPEN）

| id | 内容 | owner | 下一步 |
|---|---|---|---|
| OPEN-TOOLCHAIN | 真机/模拟器运行、APK 安装启动、MSI 安装双击、CMP `run` 交互 | lead | 需 adb 设备或模拟器（本机无）；不阻断构建结论 |
| OPEN-REPRO | 构建可复现（同源码二次构建逐字节一致） | lead | 记录 Gradle 缓存/时间戳面，后续做 buildinfo 对照 |
| OPEN-SIGN | Android release 签名 / Windows Authenticode / macOS 公证 | lead | 证书与 macOS 不在场 → `OPEN-EXTERNAL`（见 RELEASE_EVIDENCE） |