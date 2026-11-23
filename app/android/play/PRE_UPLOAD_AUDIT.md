# 上传前审计（Go / No-Go）

结论：**NO-GO**。代码与构建已收口，但 Play 账号/隐私政策公网 URL/真机矩阵未完成，不能上传生产。

## 1. 身份与版本

| 项 | 值 | 状态 |
|---|---|---|
| package | `dev.ninfenz.mobile` | PASS |
| versionName | `0.2.0` | PASS |
| versionCode | `2` | PASS（首版） |
| minSdk | `26` | PASS |
| targetSdk | `36` | PASS |
| ABI | `arm64-v8a`、`x86_64` | PASS |
| AAB | `28,608,831 B`，sha256 `25b8b96a…` | PASS |

## 2. 权限 / 隐私面

- **已移除**依赖合并进来的 `android.permission.INTERNET` 与 `ACCESS_NETWORK_STATE`。
- release APK 仅剩：
  - `dev.ninfenz.mobile.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`
- `allowBackup=false`，`fullBackupContent=false`。
- release 未声明 `debuggable=true`。
- 无网络权限 = Play Data safety 可填“不收集/不共享”；本机数据不上传。
- 仍需：**隐私政策公网 URL**（仓库有 `PRIVACY.md`，Play 要求可访问 URL）。

## 3. 签名

- upload key：`upload` alias，keystore 在仓库外。
- upload 证书 SHA-256：
  `F8:54:EF:94:3D:F5:F7:52:9F:BA:B6:40:6E:3C:5E:5F:8E:1B:74:F4:27:D2:DC:BD:B8:5E:2D:79:35:89:69:CA`
- Play App Signing：首次上传时启用；本 keystore 仅作 upload key。
- AAB 已用 upload key 签名。

## 4. 构建与质量门禁

| 项 | 结果 |
|---|---|
| Android JVM | 508/508 |
| Rust zero_slice | 15 + op 3 |
| lintRelease | 0 errors / 0 warnings |
| app gates | QA0–QA6 27/27 PASS |
| verify.sh | PASS=107 WARN=2 FAIL=0 |
| zipalign 16KB | Verification successful |
| release APK | 44,781,530 B |
| debug APK | 52,687,317 B |

## 5. 商店素材

已生成在 `play/listing/`：

| 文件 | 尺寸 | 用途 |
|---|---|---|
| `icon-512.png` | 512×512 | Play 应用图标 |
| `feature-graphic-1024x500.png` | 1024×500 | Feature graphic |
| `phone-1-library.png` | 1080×2400 | 手机截图 |
| `phone-2-onboarding.png` | 1080×2400 | 手机截图 |
| `phone-3-author.png` | 1080×2400 | 手机截图 |

注意：截图来自英文 API36 模拟器；中文商店可后续替换为中文截图。

## 6. 真机 / 模拟器

| 设备 | 结果 |
|---|---|
| OnePlus PLF110 / Android 16 | 快捷粘贴 100%；切片→项目 10 字段；交付 3/3；preserve 两份通过/revoked 被拒 |
| Pixel 7 AVD / Android 36 x86_64 | 首启 onboarding；sample 1 project/1 pack；快捷粘贴 100%；切片→项目预填 1 字段 |

未完成真机：导出 md、CSV、搜索正文、评审/CCOS、Pack 回滚、TalkBack/1.3x/横屏、SEND_MULTIPLE/PROCESS_TEXT/VIEW file://。

## 7. Data safety 建议答案

- 是否收集/共享用户数据：**否**（无网络权限，内容仅本机）。
- 是否使用广告/分析 SDK：**否**。
- 数据是否加密传输：不适用（不传输）。
- 用户能否删除数据：应用内删除项目/清空；卸载清除。
- 隐私政策 URL：**待提供**。

## 8. 上传前仍缺

1. Play Console 应用与上传权限。
2. 隐私政策公网 URL。
3. 中文商店截图（可选但建议）。
4. 真机矩阵剩余项。
5. Play 上传后内部测试安装验证。

## 9. 结论

**NO-GO**：本地 AAB 已可上传，但账号/隐私 URL/剩余真机验证未闭环。  
满足第 8 节 1–2 后可先走 Internal testing，不要直接 Production。
