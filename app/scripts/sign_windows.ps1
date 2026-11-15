# Windows 签名 / MSIX 打包（占位闸门，不冒充已签）
# 用法：pwsh -File app/scripts/sign_windows.ps1 -Package <dir> [-Cert <path>] [-Password <pwd>]
# 纪律：无证书/无 signtool 时退出码 4 并打印需要的外部条件；本脚本不生成假签名。
param(
  [Parameter(Mandatory = $true)][string]$Package,
  [string]$Cert = "",
  [string]$Password = "",
  [string]$TimestampUrl = "http://timestamp.digicert.com"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $Package)) { Write-Error "包目录不存在：$Package"; exit 2 }
$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if (-not $signtool) {
  Write-Output "OPEN-EXTERNAL: signtool.exe 不在场（装 Windows SDK 后可签）"
  Write-Output "证据落点：app/scripts/RELEASE_EVIDENCE.md → 状态 OPEN（不宣称已签名）"
  exit 4
}
if ([string]::IsNullOrEmpty($Cert)) {
  Write-Output "OPEN-EXTERNAL: 未提供 Authenticode 证书（-Cert）；不生成假签名"
  exit 4
}
Get-ChildItem -Path $Package -Recurse -Include *.exe,*.dll,*.msix,*.msi | ForEach-Object {
  & $signtool.Source sign /fd SHA256 /tr $TimestampUrl /td SHA256 /f $Cert /p $Password $_.FullName
  if ($LASTEXITCODE -ne 0) { Write-Error "签名失败：$($_.FullName)"; exit 1 }
}
Write-Output "✔ 已签名（证书：$Cert）。请把 signtool 输出与哈希写入 RELEASE_EVIDENCE.md"
