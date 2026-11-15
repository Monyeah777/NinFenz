# ADR-APP-002：共享核心用 Rust，端壳用 Kotlin/Compose Multiplatform

| 项 | 值 |
|---|---|
| 编号 | ADR-APP-002 |
| 状态 | accepted |
| 日期 | 2026-11-15 |
| 范围 | NF APP（Android / Desktop / 平板控制面 + 共享核心） |
| 上位 | `STRATEGY.md` → `app/docs/CONTRACT.md`（A0 冻结）/ `app/docs/CLI.md` |

## 背景

三端（Android/Desktop/平板）必须对同一输入给出同一字节级结果。若每端各写一套语义（Kotlin/Python/Rust 各一份），语义漂移不可避免；Python 端在移动端不可打包；端壳 UI 需要成熟的多平台 UI 栈。

## 决策

1. 语义核心 = Rust crate `nf-app-core`（`crate-type = ["rlib", "cdylib"]`），承载 `CLI.md` §3 全部 op；它是 A0–A5 的**参考实现**。
2. 端壳 = Kotlin + Compose Multiplatform（`app/android`、`app/desktop`）；端壳不实现语义，只做 UI/交互/平台集成，经 C ABI 调核心。
3. Python 控制面（`app/cli/nf_app`）只做编排/IO/脱敏/数据目录，不重写语义；其 `canonical.py` 是**独立 oracle**，用于对账而非权威。
4. FFI 面保持最小（3 函数，见 ADR-APP-011）；核心可重入、无共享可变全局。
5. 确定性是核心的硬要求：同输入同字节，禁止在核心内取时间/随机/环境。

## 后果

**正面**

- 一份语义实现贯穿三端：三端一致性从「约定」变成「同一二进制」。
- Rust 适合做解析/摘要/图算法/确定性渲染；性能与内存可控。
- 端壳可独立演进（UI 迭代不碰语义）；FFI 面小，审计成本低。
- 核心可被 CLI/Python 复用：同一 op 表同时服务 UI 与自动化。

**负面 / 代价**

- 需要 Rust + JDK/Kotlin/Android 双工具链；本机缺 Gradle/Android SDK，端壳证据必然 OPEN-TOOLCHAIN。
- 跨语言调试成本高（FFI 崩溃/pinic 兜底）；ABI 变更需要三端同步。
- 大 JSON 在 FFI 边界上拷贝有开销（影响大包/大装配场景，见 PERF_BUDGET 风险）。

## 替代方案（及否决理由）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. 纯 Kotlin 三端各写 | 否决 | 语义三份必然漂移；与「三端同字节」判据直接冲突 |
| B. 端上嵌 Python | 否决 | 移动端打包/启动/体积不可接受；且与「不复制真源」无益 |
| C. WASM 核心（wasmtime） | 否决（暂） | 本机无 wasm 工具链验证；作为后备方向保留，换向需新 ADR |
| D. 服务端算 | 否决 | 违反离线与无账号定位 |

## 证据落点

| 证据 | 路径 / 判据 |
|---|---|
| 核心 crate 声明（rlib+cdylib、MIT、依赖钉死） | `app/core/Cargo.toml` |
| op 面与 FFI 面 | `app/docs/CLI.md` §3/§5 |
| 契约层（13 格式） | `app/schema/*.schema.json` |
| ABI 先例（版本号 + cdylib，只读快线） | `engine/rust/`（`BINDINGS.md`、`Cargo.toml`） |
| 现状判定「无 UniFFI、Android 工程缺」 | `results/app/BASELINE.md` §3 |

## 复审条件

- 端壳工具链长期不可得（>1 个发布周期）时，重新评估端壳技术栈。
- FFI JSON 拷贝成为性能瓶颈（超出 PERF_BUDGET）时。
- Rust 交叉编译目标（Android aarch64/x86_64、macOS arm64、Windows x64/arm64）不可得时。

> 本 ADR 只声明决策与边界。实现状态以 `app/docs/ARCHITECTURE.md` §5/§11、`app/results/GATES.json` 与现场复跑命令为准；未落地项写 `OPEN`，不得据本 ADR 声称「已实现」。
