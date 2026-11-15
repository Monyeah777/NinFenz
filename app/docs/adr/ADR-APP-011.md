# ADR-APP-011：JSON-C ABI 替代 UniFFI（accepted-with-deviation）

| 项 | 值 |
|---|---|
| 编号 | ADR-APP-011 |
| 状态 | accepted-with-deviation |
| 日期 | 2026-11-15 |
| 范围 | NF APP（Android / Desktop / 平板控制面 + 共享核心） |
| 上位 | `STRATEGY.md` → `app/docs/CONTRACT.md`（A0 冻结）/ `app/docs/CLI.md` |

## 背景

计划 §5.1 把 Core Bridge 写成 `UniFFI / JSON`（两者并列）。本次实施环境的硬约束：本机离线，crates.io 直连被失效代理拦截（`results/app/BASELINE.md` §2.4），UniFFI 相关依赖无法获取与验证；若强行引入，核心将不可构建，三端契约测试全部无法运行。

## 决策

1. 采用 **JSON over C ABI**：`nf_app_core_abi_version()`（静态字符串 `nf-app-core/1`）、`nf_app_core_call(const char* req_json)`（返回堆 JSON，响应同 CLI 信封）、`nf_app_core_free(char* ptr)`。
2. 请求形如 `{op, in}`；正常错误一律走信封（`ok=false` + `error.code`），`NULL` 只用于 panic 兜底且 stderr 留诊断。
3. 核心必须可重入（无共享可变全局）；`limits` 只读加载；ABI 变更 = 新增函数 + 新 ADR，不改既有 3 函数语义。
4. **偏差登记**：与计划字面「UniFFI / JSON」不一致；本条是「等价实现 + 显式偏差」，不是静默替换。
5. **回切条件**：当 UniFFI 依赖可得且能离线构建时，在**不破 ABI** 的前提下加 UDL 生成绑定，保留 3 函数作为兼容层；回切必须重跑 golden/契约/三端一致性测试。

## 后果

**正面**

- 零额外依赖：离线可构建，核心可先跑起来。
- 与 CLI 同一信封：一份契约两种传输（子进程 / FFI），测试可复用。
- ABI 面只有 3 个函数：审计面小；Kotlin(JNA/cinterop) 与 Python(ctypes) 均可调。

**负面 / 代价**

- 手写绑定与内存生命周期管理（谁 free、何时 free）由端壳负责，易错。
- 大 JSON 在 FFI 边界拷贝有开销；无零拷贝通道。
- 无 UDL：类型映射与文档生成需手写，跨语言类型漂移风险高于 UniFFI。
- panic 跨 FFI 是未定义行为，必须兜底且视为缺陷（不得常态化）。

## 替代方案（及否决理由）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. UniFFI（计划首选） | 暂缓（回切路径保留） | 依赖本机不可得；引入即不可构建。依赖可得后按回切条件上线，不破 ABI |
| B. JSON over stdin/stdout 子进程 | 否决 | 无 FFI 但有进程启动/状态成本；端壳频繁调用不划算（仍保留为 CLI 形态） |
| C. WASM 组件 | 否决（暂） | 本机无 wasm 工具链可验证 |
| D. 平台原生绑定（JNI 手写） | 否决 | 绑定面 = 全部 op，维护成本高于 3 函数 ABI |

## 证据落点

| 证据 | 路径 / 判据 |
|---|---|
| FFI 契约与 3 函数签名、线程要求、panic 兜底口径 | `app/docs/CLI.md` §5 |
| `crate-type = ["rlib", "cdylib"]` | `app/core/Cargo.toml` |
| FFI 入口落点（取证时刻：`app/core/src/ffi.rs` 111 行 + `bin/nf-app-core.rs` 89 行；核心编译未过） | `app/core/src/ffi.rs`、`app/core/src/bin/nf-app-core.rs` |
| 环境约束（crates.io 不可直连、镜像可达） | `results/app/BASELINE.md` §2.4 |
| 偏差状态登记 | `app/docs/DOD.md` §3 `OPEN-UNIFFI` |
| 依赖离线拉取与锁文件 | `app/core/Cargo.lock`、`app/docs/DEPENDENCIES.md` |

## 复审条件

- UniFFI 依赖可得且可离线构建时（执行回切条件）。
- 需要新增第 4 个 ABI 函数时（新 ADR + 三端同步）。
- panic 兜底被触发（先修根因，再评估 ABI 设计）。
- ABI 性能成为瓶颈时（评估零拷贝/共享内存通道）。

> 本 ADR 只声明决策与边界。实现状态以 `app/docs/ARCHITECTURE.md` §5/§11、`app/results/GATES.json` 与现场复跑命令为准；未落地项写 `OPEN`，不得据本 ADR 声称「已实现」。
