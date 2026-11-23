# Play 上传配置

## 已生成的本机凭据（不在仓库内）

- keystore：`<KEY_DIR>\nf-upload.jks`
- alias：`upload`
- 证书：`<KEY_DIR>\upload_cert.pem`
- 口令文件：`<KEY_DIR>\upload-credentials.txt`
- SHA-256：`F8:54:EF:94:3D:F5:F7:52:9F:BA:B6:40:6E:3C:5E:5F:8E:1B:74:F4:27:D2:DC:BD:B8:5E:2D:79:35:89:69:CA`

这四件都在仓库外；不要提交、不要上传到聊天。

## 本机构建签名 AAB

```powershell
$env:JAVA_HOME='<JDK>'
$env:ANDROID_HOME='<ANDROID_SDK>'
$env:GRADLE_USER_HOME='<GRADLE_HOME>'
Get-Content '<KEY_DIR>\upload-credentials.txt' | ForEach-Object {
  if ($_ -match '^([^=]+)=(.*)$') { Set-Item -Path ("Env:" + $matches[1]) -Value $matches[2] }
}
Set-Location app/android
.\gradlew.bat :app:bundleRelease
```

产物：`app/build/outputs/bundle/release/app-release.aab`。未设置 `NF_UPLOAD_*` 时仍构建未签名 AAB。

## Play Console 一次性配置

1. 用 Play Console 创建应用，包名必须是 `dev.ninfenz.mobile`。
2. 在 **App integrity** 选择 Play App Signing；本 keystore 只作为 **upload key**，不是 app signing key。
3. 上传第一次 AAB 到 Internal testing；Play 会保存 app signing key。
4. 填 Data safety、Content rating、Target audience、Privacy policy。
5. 需要自动化时，在 Google Cloud 建 service account，授予 Play Console 的 release 权限，下载 JSON，设置：
   ```powershell
   $env:NF_PLAY_JSON_KEY='<KEY_DIR>\play-service-account.json'
   ```
6. 安装 fastlane 后在本目录运行：
   ```powershell
   fastlane internal
   ```

## 注意

- 没有 Play 账号/服务账号 JSON，本仓库无法替你创建 Play Console 应用或上传。
- fastlane metadata 只含文字；截图、图标、feature graphic 仍需人工补齐。
- 若启用 Play App Signing，上传 key 丢失可由 Play 重置；app signing key 丢失则无法恢复。
