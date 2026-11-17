# NF APP 发布清单（Windows / macOS / Android）

> ⛔ 操作指令：发布 = **证据事件**，不是打勾仪式。每项要么给本机可复跑命令与产物路径，要么写 `OPEN` + owner。未签/未公证/未实测一律不得写成 pass（见 `app/docs/DOD.md` §3 `OPEN-EXTERNAL`）。
> 状态：v1（2026-11-15）· 依据：计划 §11.1/§11.2/§18.3。

## 0. 共同前置

```bash
bash app/scripts/build_core.sh --release --test     # 核心：构建 + 单测
python app/gates/run_gates.py                       # APP 门禁（QA0–QA6 + S0–S15）
python -m pytest app/tests -q                       # 控制面/契约/安全/golden/E2E
bash app/scripts/a11y_gate.sh                       # 图标 contentDescription + 48dp 触控目标
python tui/nf.py --selftest                         # TUI（复用面）
```

## 1. Android（NF Mobile）

| # | 项 | 命令/证据 | 状态 |
|---|---|---|---|
| A1 | target 36 / compile 36 / minSdk 26 | `app/android/app/build.gradle.kts` | 见工程 |
| A2 | 16KB page / ABI（arm64-v8a, x86_64） | `android { defaultConfig { ndk { abiFilters } } }` + `zipalign -c -P 16` 证据 | OPEN-TOOLCHAIN |
| A3 | assembleDebug/Release | `bash app/scripts/build_android.sh release` | OPEN-TOOLCHAIN |
| A4 | 签名（Play App Signing / upload key） | `keystore` 不入库；CI secret | OPEN-EXTERNAL |
| A5 | 数据安全表单 | Play Console 提交材料 | OPEN-EXTERNAL |
| A6 | 分层发布（staged rollout） | Play Console 截图/记录 | OPEN-EXTERNAL |
| A7 | 中国渠道 flavor（无 GMS） | `productFlavors { cn }` | OPEN-TOOLCHAIN |
| A8 | 无障碍/本地化抽查（TalkBack/RTL/字体） | 设备矩阵记录 | OPEN-EXTERNAL |

## 2. Windows（NF Studio）

| # | 项 | 命令/证据 | 状态 |
|---|---|---|---|
| W1 | CMP Desktop 构建 | `bash app/scripts/build_desktop.sh package` | OPEN-TOOLCHAIN |
| W2 | MSIX（Store 优先） | `MakeAppx` + `signtool` | OPEN-EXTERNAL |
| W3 | MSI/EXE 侧载需 Authenticode | `pwsh -File app/scripts/sign_windows.ps1 -Package <dir> -Cert <pfx>` | OPEN-EXTERNAL（无证书 → exit 4） |
| W4 | 自动更新签名 | `app/docs/ARCHITECTURE.md` 更新通道节 | OPEN |
| W5 | 文件关联 .nfproject/.nfpack/.nftpl | 安装包 manifest + 双击实测 | OPEN-TOOLCHAIN |

## 3. macOS（NF Studio）

| # | 项 | 命令/证据 | 状态 |
|---|---|---|---|
| M1 | Apple Silicon 构建 | `bash app/scripts/build_desktop.sh package`（macOS 上） | OPEN-EXTERNAL（无 macOS） |
| M2 | Developer ID + Hardened Runtime | `codesign --options runtime` | OPEN-EXTERNAL |
| M3 | notarytool + staple | `bash app/scripts/notarize_macos.sh <App.app>` | OPEN-EXTERNAL（非 macOS → exit 4） |
| M4 | Sparkle 更新通道 | `app/desktop` 更新配置 | OPEN |
| M5 | Intel 评估 | 单独构建 | OPEN（ADR-APP-010：Apple Silicon 优先） |

## 4. 发布结论口径

- 只有 A1–A3/W1–W2/M1–M3 全部有**本机可复跑证据**时，才允许写「可发布」。
- 任何一项 OPEN，发布结论只能是「实现完成、发布材料未完成（OPEN-EXTERNAL）」。
- 证据统一落 `app/scripts/RELEASE_EVIDENCE.md`，由 `nf approve` 式的双要素（对象 digest + 签收人）收口（拟 A6 后补）。
