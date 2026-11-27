# NF APP 发布证据（模板，现状如实）

> ⛔ 操作指令：本件是发布证据的**唯一落点**。填证据时只写实测输出/哈希/证书指纹；没有就保留 `OPEN`，**不得**填「已签/已公证/已上架」。
> 状态：v1（2026-11-15）· 机读摘要由 `python app/gates/run_gates.py` 的 QA6 `q6-signing` 项读本文件。

## 摘要

| 平台 | 构建 | 签名 | 公证/上架 | 结论 |
|---|---|---|---|---|
| Android | 构建 pass（debug/release；upload AAB 已签） | upload key 已生成；Play Console 未创建 | 未上架 | 未发布 |
| Windows | OPEN-TOOLCHAIN | OPEN-EXTERNAL | — | 未发布 |
| macOS | OPEN-EXTERNAL | OPEN-EXTERNAL | OPEN-EXTERNAL | 未发布 |

## 明细

### Android
- assembleDebug：**pass**（2026-11-22，Android SDK 36 / build-tools 36.0.0）
- app-debug.apk：52,687,317 B；SHA-256 `078f8841e9762a253537c823e23ef16ad1966d84b6fa73b7e9ba4cbb96e90a1c`
- assembleRelease（unsigned）：pass；44,781,530 B；SHA-256 `a7e38f3ca8152ddc6efb2eaa9ab440c844e27ca97160d1de85089064b71c2ba8`
- debug 签名 APK（仅内部安装）：52,687,317 B；SHA-256 `078f8841e9762a253537c823e23ef16ad1966d84b6fa73b7e9ba4cbb96e90a1c`；证书 CN=Android Debug；**不是 upload key**
- bundleRelease（unsigned）：pass；28,549,355 B；SHA-256 `37fc8201b7e654055751a2a874a30dae864a4983b943a32d90e9aa558dc3fe08`；`jarsigner -verify` 显示未签名
- lintRelease：**0 errors / 0 warnings（No issues found）**
- Release manifest：package `dev.ninfenz.mobile`、versionName `0.2.0`、minSdk 26、target/compileSdk 36、`extractNativeLibs=false`、无 `android:debuggable`（apkanalyzer manifest print）
- 16KB 对齐：`zipalign -c -P 16 4` exit 0（APK；AAB 未用 bundletool 复核）
- 签名证书指纹（SHA-256）：`F8:54:EF:94:3D:F5:F7:52:9F:BA:B6:40:6E:3C:5E:5F:8E:1B:74:F4:27:D2:DC:BD:B8:5E:2D:79:35:89:69:CA`（CN=NF Mobile Upload；upload key，非 Play app signing key）
- bundleRelease（upload 签名）：**pass**；28,608,831 B；SHA-256 `25b8b96a281dd094deac1e91625244320abd75464525d543d39e1b6ff2967ce0`；`jarsigner -verify` 通过
- 签名材料：`<KEY_DIR>\nf-upload.jks`（仓库外，ACL 仅当前用户）；口令文件与 PEM 同目录，未入库
- Play 配置：`app/android/fastlane/` + `app/android/play/README.md`；service account JSON 与 Play Console 应用未创建
- 签名流程内部自测：`app/scripts/sign_release.sh` 以本机 debug keystore 跑通（仅验证流程，非生产签名）；`apksigner verify` 通过，证书 SHA-256 `8a52a549c3081795cecb0f1424d21684933fb21d3afe76508dab736e688b10fb`。
- 真机安装（2026-11-22）：OnePlus PLF110 / Android 16 / 1080×2392；`adb install -r` Success。冷启动 `am start -W` COLD 573ms（首装）/320ms（升级后）/188ms（force-stop 后）。
- 真机闭环：示例 Pack → 演示项目 → 创作台 → graph-compile（steps 2 · slots 4）→ 必填 3/3 → assemble → L1 pass（error=0 warn=0 info=3）→ 导出 md → 契约三项全绿 → 签收（当版 hash 签收；ECDSA 版本仅 JVM 测试）；SEND text/plain 分享导入预览通过；logcat 无 FATAL/ANR。
- 真机修复：契约「必填槽位已填」曾把选填 SLT-04 也当必填，导致 3/3 仍 ✗；改为按 spec slot.required 过滤后复测三项全绿。
- 真机未测：长文本/中文输入法（未做完整输入法验收）、PDF/EPUB/DOCX/HTML 导出、分享文件、杀进程恢复、TalkBack、横屏、Play 上传。
- 数据安全表单提交：**未提交**

### 0.3.7-preview.1（2026-11-27）

- versionCode 10 / versionName 0.3.7-preview.1；package dev.ninfenz.mobile；minSdk 26；compile/target 36。
- Daily debug APK 54MB；Pro debug APK 55MB；debug AAB 32MB（历史构建，未签）。
- release base APK **18MB**（on-demand OCR feature；R8 + resource shrink）；SHA-256 `6ab06178350652a6acfc724afd8ac8f759168207a7615d2a10842e2022daf05b`。
- release AAB **31MB**（base 模块约 11.1MB + OCR feature 11.3MB）；SHA-256 `510cd8a8a72785b550a9451450a7d4369141593b780fba792c469a27657ea04a`；`jarsigner -verify` 未签名。
- bundletool get-size total（debug 签名 APK set，base/on-demand feature 不含默认安装）：**8,915,346–9,138,051 B**，≤18MB。
- 16KB：`zipalign -c -P 16 4` exit 0（release base APK）；AAB 未用 bundletool 复核。
- 权限：aapt 仅 `dev.ninfenz.mobile.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`，无 INTERNET。
- 签名：**OPEN-SIGN**；`NF_UPLOAD_*` 未设置；无 upload AAB。
- 内部可审阅 APK：`results/app/0.3.7-preview.1-internal-debugsigned.apk`；18MB；debug 证书 SHA-256 `8a52a549c3081795cecb0f1424d21684933fb21d3afe76506dab736e688b10fb`；**不是 upload key**。
- 真机：**OPEN-PERF-DEVICE**；当前 adb 无设备，未做安装/启动/TalkBack/RTL/10k。
- Play：未上传；未做 staged rollout/rollback 演练。

### Windows
- CMP app-image：pass；`NFStudio.exe` 551,936 B；SHA-256 `780a2dc2e152e7b5f6eaebc6b59890a48d9dbe52d81ed0309c0a2edfb5742e81`；目录总 137,150,938 B；**启动冒烟通过**：进程存活 10s、RSS 约 10,063,872 B，随后主动关闭；未做 UI 交互
- MSI：未跑通（WiX 下载阻塞）
- MSIX/EXE 路径：`app/desktop/build/compose/binaries/main/app/NFStudio/NFStudio.exe`
- Authenticode 证书指纹：—
- signtool 输出：—

### macOS
- 构建：**不可执行**（本机非 macOS）
- Developer ID：—
- notarytool submission id：—
- staple 输出：—

## 外部条件（补齐后可翻状态）

1. Android SDK 36 + build-tools + 真机/模拟器（ANDROID_HOME）。
2. Windows Authenticode 证书（EV/OV）+ Windows SDK signtool。
3. macOS 机器 + Apple Developer Program（Developer ID Application）+ `NOTARY_PROFILE`。
4. Play Console 账号、service account JSON、商店素材与数据安全材料。
