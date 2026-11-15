# ADR-APP-009：16KB page / target 36 / ABI 双架构进 CI 门禁

| 项 | 值 |
|---|---|
| 编号 | ADR-APP-009 |
| 状态 | accepted |
| 日期 | 2026-11-15 |
| 范围 | NF APP（Android / Desktop / 平板控制面 + 共享核心） |
| 上位 | `STRATEGY.md` → `app/docs/CONTRACT.md`（A0 冻结）/ `app/docs/CLI.md` |

## 背景

Android 平台已要求 target 36（Android 16）与 16KB 页面（Android 15+ 部分设备/Android 16 起更广）；ABI 覆盖决定设备可达性。若这些只写在发布清单而不进 CI：每条都靠人验收，必然出现「文档写了、产物没做」。本机无 Android SDK/真机，所以必须用「门禁项 + 证据路径」把缺口显式化。

## 决策

1. Android 构建基线：`minSdk 26` / `targetSdk 36` / `compileSdk 36`；ABI = `arm64-v8a` + `x86_64`（NDK abiFilters）。
2. 16KB 页面对齐作为发布判据：`zipalign -c -P 16` 检查 + native 库编译参数（NDK 16KB 支持），证据进发布清单。
3. 三项（target/ABI/16KB）必须作为 CI 或门禁证据存在，不接受「只在 README 写」；本机不可执行时记 `OPEN-TOOLCHAIN` 并给 owner，不写 pass。
4. 门禁登记：`app/gates/gates.json` QA5 的 `q5-device-matrix`（required=false，owner lead）；设备覆盖见 `app/docs/DEVICE_MATRIX.md`。

## 后果

**正面**

- 提前适配 Play 政策与 16KB 设备，避免发布前返工。
- ABI 双架构覆盖真机与模拟器/Chromebook，设备矩阵可核。
- 把「不可实测」显式登记为 OPEN，避免纸面通过。

**负面 / 代价**

- 双 ABI 增加包体（需 AAB split / per-ABI 打包控制体积）。
- 16KB 校验依赖 NDK/Gradle 工具链；本机不可执行，证据链必须靠外部环境。
- target 36 的新行为（前台服务/权限）需要额外适配验证。

## 替代方案（及否决理由）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. 仅 arm64-v8a | 否决 | 模拟器/Chromebook 覆盖缺失；32 位设备不在目标（minSdk 26 已排除多数） |
| B. 不设 target 36 | 否决 | Play 强制；无辩护空间 |
| C. 发布后补 16KB | 否决 | 返工成本高于前置；商店会拒 |
| D. 单 ABI 包 + 分渠道 | 否决（暂） | 发布复杂度上升；ABI 双架构仍是基线 |

## 证据落点

| 证据 | 路径 / 判据 |
|---|---|
| 发布清单 A1/A2（target 36、ABI、16KB 判据） | `app/scripts/RELEASE_CHECKLIST.md` §1 |
| 设备/ABI/16KB 矩阵与证据状态 | `app/docs/DEVICE_MATRIX.md` |
| 门禁登记（required=false + owner） | `app/gates/gates.json` QA5 `q5-device-matrix` |
| 构建入口与缺工具链时的 exit 4 | `app/scripts/build_android.sh` |
| 产物证据落点（模板） | `app/scripts/RELEASE_EVIDENCE.md` |

## 复审条件

- Play 政策（targetSdk/16KB）变化时。
- NDK/Gradle/AGP 主版本升级时（16KB 支持参数可能变）。
- x86_64 或 arm64 需求下降/上升时。

> 本 ADR 只声明决策与边界。实现状态以 `app/docs/ARCHITECTURE.md` §5/§11、`app/results/GATES.json` 与现场复跑命令为准；未落地项写 `OPEN`，不得据本 ADR 声称「已实现」。
