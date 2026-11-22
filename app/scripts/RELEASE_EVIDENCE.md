# NF APP 发布证据（模板，现状如实）

> ⛔ 操作指令：本件是发布证据的**唯一落点**。填证据时只写实测输出/哈希/证书指纹；没有就保留 `OPEN`，**不得**填「已签/已公证/已上架」。
> 状态：v1（2026-11-15）· 机读摘要由 `python app/gates/run_gates.py` 的 QA6 `q6-signing` 项读本文件。

## 摘要

| 平台 | 构建 | 签名 | 公证/上架 | 结论 |
|---|---|---|---|---|
| Android | 构建 pass（debug/release unsigned） | OPEN-EXTERNAL | OPEN-EXTERNAL | 未发布 |
| Windows | OPEN-TOOLCHAIN | OPEN-EXTERNAL | — | 未发布 |
| macOS | OPEN-EXTERNAL | OPEN-EXTERNAL | OPEN-EXTERNAL | 未发布 |

## 明细

### Android
- assembleDebug：**pass**（2026-11-22，Android SDK 36 / build-tools 36.0.0）
- app-debug.apk：52,640,520 B；SHA-256 `9d955120b4d9c689b589e258bf58466fb3680798ccd03a9d24a68c23f515c6f3`
- assembleRelease（unsigned）：pass；44,584,270 B；SHA-256 `239caf9177f582beb6c711930374cdd11d07b8f82eea7072fe8e4c2e00690dea`
- debug 签名 APK（仅内部安装）：44,648,613 B；SHA-256 `ad3945cdd037b1f98aacf025667af7ac580e17c157a3ff274fbc105039d43c28`；证书 CN=Android Debug；**不是 upload key**
- bundleRelease（unsigned）：pass；28,410,686 B；SHA-256 `47c016db7ba64f04efdb3d87bf799b06577fb90665935f3cf92104fbdc12a594`；`jarsigner -verify` 显示未签名
- lintRelease：**0 errors / 0 warnings（No issues found）**
- Release manifest：package `dev.ninfenz.mobile`、versionName `0.2.0`、minSdk 26、target/compileSdk 36、`extractNativeLibs=false`、无 `android:debuggable`（apkanalyzer manifest print）
- 16KB 对齐：`zipalign -c -P 16 4` exit 0（APK；AAB 未用 bundletool 复核）
- 签名证书指纹（SHA-256）：—（生产 upload key 未提供，OPEN-EXTERNAL）
- 签名流程内部自测：`app/scripts/sign_release.sh` 以本机 debug keystore 跑通（仅验证流程，非生产签名）；`apksigner verify` 通过，证书 SHA-256 `8a52a549c3081795cecb0f1424d21684933fb21d3afe76506dab736e688b10fb`。
- 真机安装（2026-11-22）：OnePlus PLF110 / Android 16 / 1080×2392；`adb install -r` Success。冷启动 `am start -W` COLD 573ms（首装）/320ms（升级后）/188ms（force-stop 后）。
- 真机闭环：示例 Pack → 演示项目 → 创作台 → graph-compile（steps 2 · slots 4）→ 必填 3/3 → assemble → L1 pass（error=0 warn=0 info=3）→ 导出 md → 契约三项全绿 → 签收（当版 hash 签收；ECDSA 版本仅 JVM 测试）；SEND text/plain 分享导入预览通过；logcat 无 FATAL/ANR。
- 真机修复：契约「必填槽位已填」曾把选填 SLT-04 也当必填，导致 3/3 仍 ✗；改为按 spec slot.required 过滤后复测三项全绿。
- 真机未测：长文本/中文输入法（未做完整输入法验收）、PDF/EPUB/DOCX/HTML 导出、分享文件、杀进程恢复、TalkBack、横屏、AAB 上传签名。
- 数据安全表单提交：**未提交**

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
4. Play Console / App Store Connect 账号与数据安全材料。
