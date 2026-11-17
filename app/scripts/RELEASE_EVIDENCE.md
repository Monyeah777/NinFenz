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
- assembleDebug：**pass**（2026-11-16，Android SDK 36 / build-tools 36.0.0）
- app-debug.apk：19,193,287 B；SHA-256 `56fd935ae10f2298ac0e83f67a432d6411e8fe586ae652f78271c3d7ee575b89`
- assembleRelease（unsigned）：pass；15,393,349 B；SHA-256 `849f82e34285731b9ede5a492cf51e393ac0ffe51aae871b19ed329e52b79ea1`
- 16KB 对齐：`zipalign -c -P 16 4` exit 0
- 签名证书指纹（SHA-256）：—（未签名，OPEN-EXTERNAL）
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
