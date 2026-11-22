# NF APP 基线（v2 Complete + delta，2026-11-22）

> 本件是当前检出的事实基线，替代 `BASELINE.md` 中“APP 面此前为零”的历史快照；旧件保留作历史。
> 输入：`NF-APP-Final-方案-v2-Complete-SelfContained-2026-11-.md` + `NF-APP-v2-增量补丁-SelfContained-2026-11-19.md`。

## 0. 检出

| 项 | 值 |
|---|---|
| 分支 / HEAD | `work/l4-floors` / 本提交 |
| 工作树 | clean；真机截图在 `results/app/device_*.png` |
| 输入文档 | 不在仓（作者本地） |
| 设备 | OnePlus PLF110 / Android 16 / 1080×2392；serial `3B65AR0183V00000` |

## 1. 环境

| 面 | 值 |
|---|---|
| JDK | 21.0.8（Microsoft） |
| Android SDK | `D:\tmp\app-toolchain\android-sdk` |
| Gradle user home | `D:\tmp\app-toolchain\gradle-home` |
| Python | 3.11.9 |
| Rust | cargo/rustc 1.99.1 |
| 网络 | crates.io 代理受限；本机缓存可用 |

## 2. 测试/门禁

| 面 | 结果 | 命令 |
|---|---|---|
| Rust core | **212 passed / 21 suites / 0 failed** | `cd app/core && cargo test -q` |
| Python app | **524 passed / 1 warning / 0 failed** | `python -m pytest app/tests -q` |
| Android JVM | **495/495** | `:app:testDebugUnitTest` |
| Desktop JVM | **20/20** | `cd app/desktop && ./gradlew test --rerun-tasks` |
| TUI selftest | **9/9** | `python tui/nf.py --selftest` |
| Desktop app-image | pass | `NFStudio.exe` 551,936 B；目录 137,150,938 B；启动存活 10s |
| MSI 打包 | **未跑通** | `build_desktop.sh package` 卡在 WiX 下载，已中止 |
| zero_slice 原型 | **14/14** | `python -m unittest -v test_zero_slice.py` |
| app gates | **QA0–QA6 全 PASS；FAIL=0；P0=0** | `python app/gates/run_gates.py` |
| 仓库门禁 | **PASS=107 WARN=2 FAIL=0** | `bash verify.sh --checks-only` |
| 真机闭环 | **pass**：安装、冷启动、交付、L1、导出 md、契约三项、签收、分享导入 | `adb` / 截图 `device_*.png` |

## 3. 构建

| 产物 | 大小 | sha256 | 备注 |
|---|---|---|---|
| debug APK | 51,662,441 B | `e14a1d51…` | 双 ABI |
| release unsigned | 44,661,834 B | `c85618ac…` | `zipalign -c -P 16` 通过 |
| lintRelease | pass | 0 errors / 0 warnings |
| Release manifest | pass | 0.2.0；minSdk 26 / target 36；无 debuggable |
| debug-signed APK | 44,697,765 B | `49e882b2…` | 仅内部安装；证书 CN=Android Debug |
| release AAB unsigned | 28,461,785 B | `246441e8…` | `jarsigner -verify` 未签名；AAB 16KB 未用 bundletool 复核 |

发布签名/公证/Play 材料仍无输入。

## 4. Phase 0 P0 代码面复核

| ID | 状态 | 证据 |
|---|---|---|
| A0-1 列表刷新 | pass（代码面） | `NfMobileApp` 写后刷新 + `LibraryStore` 重扫 |
| A0-2 plan 持久 | pass | `DeliveryDraftStore.loadPlan/save`；交付页恢复 |
| A0-3 失败禁导出 | pass | `DeliveryScreen.exportMarkdown` 在 needsRevalidate/report fail 时为 null |
| A0-4 主题持久 | pass（测试面） | `AppPrefs` + 主题测试 |
| A0-5 键盘遮挡 | pass（代码面） | Author/Delivery `imePadding()` + 滚动/CTA |
| A0-6 分享页主题 | pass（代码面） | `ShareReceiverActivity` 主题/insets |
| A0-7 导入清空 | pass | `clearCurrentImport` + `ImportDraftStore.clear` + 5s 撤销 |
| A0-8 草稿→项目 | pass（代码面） | 对话框/创建在；ImportPrefill.bySlotName 按槽位名映射协议 label |
| A0-9 可编辑预览 | pass | 块级编辑/撤销/重做/上移下移/删除/入槽 |
| A0-10 槽位裸 ID | pass | 槽位卡显示名称/约束/示例 |
| A0-11 长标题 | pass（代码面） | 库卡片换行/最大行 |
| A0-12 i18n | pass | `app/tests/test_ui_strings_localized.py` + 498 全量 |
| A0-13 空态 CTA | pass | 库/导入/交付空态入口 |
| A0-14 入口成本 | pass（代码面） | 库首屏 Daily 粘贴卡 + 快速粘贴 + 导入向导 |

## 5. 增量补丁落点

- D21–D24：`app/docs/DECISIONS.md`
- Free/Pro/CCOS：`app/docs/FEATURES.md`、`FeatureGate.kt`
- zero_slice：`app/prototypes/zero_slice/`（14 测试 + 真实简报结果）
- S18/S19：`app/gates/dimensions.json`（S18 covered，S19 open）
- 记录：`results/app/DELTA_V2.md`

## 6. 判定

**可继续实施**：契约/核心/Android/桌面/原型均有可核证据，P0 代码面无阻断。
**不可声称**：发布就绪、真机矩阵通过、Phase M 全量完成、A0-8/A0-14 已完整闭环。
