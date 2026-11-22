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
- assembleDebug：**pass**（2026-11-21，Android SDK 36 / build-tools 36.0.0）
- app-debug.apk：51,548,013 B；SHA-256 `de0724fc76b5c5cd808503e7f9666b79c98b1e4b14438761575271ddd14a3cbb`
- assembleRelease（unsigned）：pass；44,540,010 B；SHA-256 `11d2d24cc3b3ab4eaafa350ebf97958b140a21b7bb2b8b86f143055fe2bbd791`
- debug 签名 APK（仅内部安装）：44,603,557 B；SHA-256 `4836df65ad6a0482a7f1c7b2a2a4fe48d8e8ab1afe10516a1e0063c67ce5b52a`；证书 CN=Android Debug；**不是 upload key**
- bundleRelease（unsigned）：pass；28,372,870 B；SHA-256 `e2c1ce56445b2569dbca3ee5c6469597367847080e650994bf9ffb5d838cd384`；`jarsigner -verify` 显示未签名
- lintRelease：**0 errors / 0 warnings（No issues found）**
- Release manifest：package `dev.ninfenz.mobile`、versionName `0.2.0`、minSdk 26、target/compileSdk 36、`extractNativeLibs=false`、无 `android:debuggable`（apkanalyzer manifest print）
- 16KB 对齐：`zipalign -c -P 16 4` exit 0（APK；AAB 未用 bundletool 复核）
- 签名证书指纹（SHA-256）：—（生产 upload key 未提供，OPEN-EXTERNAL）
- 签名流程内部自测：`app/scripts/sign_release.sh` 以本机 debug keystore 跑通（仅验证流程，非生产签名）；`apksigner verify` 通过，证书 SHA-256 `8a52a549c3081795cecb0f1424d21684933fb21d3afe76506dab736e688b10fb`；内部 signed APK 安装成功，冷启动 926ms，PDF 1 页校验通过。
- 数据安全表单提交：**未提交**

### Windows
- CMP 构建：**未跑**
- MSIX/EXE 路径：—
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
