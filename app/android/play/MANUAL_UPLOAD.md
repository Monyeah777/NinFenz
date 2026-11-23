# Play Console 手动上传教程

## 0. 当前产物

- 包名：`dev.ninfenz.mobile`
- versionName：`0.2.0`
- versionCode：`2`
- AAB：`app/build/outputs/bundle/release/app-release.aab`
- 当前签名 AAB：`28,608,911 B`，sha256 `93a1d5b1ed5db3d5ceb5fae7004990f6f2a45564c38cefc568bdea97bc1f0fe3`
- upload key：仓库外 `<KEY_DIR>\nf-upload.jks`（不要提交/外发）
- 证书 SHA-256：`F8:54:EF:94:3D:F5:F7:52:9F:BA:B6:40:6E:3C:5E:5F:8E:1B:74:F4:27:D2:DC:BD:B8:5E:2D:79:35:89:69:CA`

## 1. 上传前检查

1. 备份 keystore 与口令文件。丢失 upload key 可向 Play 申请重置；丢失 app signing key 不可恢复。
2. 确认 AAB 已签：
   ```powershell
   & "$env:JAVA_HOME\bin\jarsigner.exe" -verify app\android\app\build\outputs\bundle\release\app-release.aab
   ```
3. 确认 versionCode 比上一版大。当前为 2。
4. 确认包名与 Play Console 应用一致：`dev.ninfenz.mobile`。

## 2. Play Console 创建应用（首次）

1. 打开 Play Console → All apps → Create app。
2. 填应用名、默认语言、应用/游戏、免费/付费。
3. 接受开发者计划政策与出口声明。
4. 进入 App integrity → 选择 **Play App Signing**。
5. 首次上传时，Play 会保存 app signing key；本 keystore 只作为 **upload key**。

## 3. 上传 Internal testing

1. 左侧 Test and release → Testing → Internal testing。
2. Create new release。
3. 如提示上传 key，上传 `<KEY_DIR>\upload_cert.pem`（公钥证书；不要传 jks/口令）。
4. 上传 `app-release.aab`。
5. 填 Release name（如 `0.2.0-internal-1`）与 Release notes。
6. 检查错误：versionCode、包名、签名、target API。
7. Save → Review release → Start rollout to Internal testing。
8. 在 Testers 页添加测试账号，复制 opt-in URL。

## 4. 首次上架前必须填

- App content → Privacy policy（如有）
- Data safety（本应用无网络/无遥测，按实际选择）
- Content rating
- Target audience
- Ads（无）
- Government apps（否）
- News app（否）
- Store listing：短描述、完整描述、图标 512×512、feature graphic 1024×500、手机截图
- Countries/regions

## 5. 从 Internal 升 Production

1. Production → Create new release。
2. 选择已测试的 AAB 或重新上传。
3. 填 release notes。
4. Review → Start rollout。
5. 可先 10% staged rollout，观察后再提高。

## 6. 验证安装

1. 用 internal opt-in URL 在测试账号安装。
2. 确认设置/关于显示 `0.2.0 (versionCode 2)`。
3. 用 `adb shell dumpsys package dev.ninfenz.mobile` 看 `versionName/versionCode`。
4. 用 `apksigner`/Play Console 的 App integrity 核对证书指纹。

## 7. 常见错误

- **版本代码已用过**：提高 `versionCode`，重新构建/签名。
- **包名不匹配**：Play 应用包名必须 `dev.ninfenz.mobile`。
- **AAB 未签名**：用 upload key 重新 `bundleRelease`；不要上传 unsigned。
- **上传 key 不匹配**：确认使用 `nf-upload.jks` 的 `upload` alias；必要时在 Play 重置 upload key。
- **64 位/16KB**：本包含 arm64-v8a + x86_64，target 36；Play 会检查。
- **target API 不足**：targetSdk 36，满足当前要求。

## 8. 无 Play Console 账号时

不能代替你创建应用或上传。需要：
1. Play Console 开发者账号；
2. 应用创建权限；
3. 可选：service account JSON 用于 fastlane 自动上传。

没有以上条件，只能停在“本地已签 AAB”。
