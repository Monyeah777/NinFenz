# engine/wasm/ · 微内核插件面（计划第五部分 P5）

> **定位**：把「按测得成本分配语言」落成可运行、可拒绝、可回退的一段机制。
> 计划项：P5-01（微内核/插件隔离）· P5-02（WASI 能力面）· P5-03（WIT/装载时校验）·
> P5-04（wasmtime 宿主）· P5-05（fuel/超时）· P5-06（能力收窄）· P5-10（晋升门）。
> 依据：.rivet/private_archive/64_复合型MoE门禁方案.md §18/§20.5（内部档案，不入公开面）。

## 件

| 件 | 作用 |
|---|---|
| sha256/ | **参考插件（CLI 形态）**：Rust std-only，编到 wasm32-wasip1 |
| sha256-component/ | **参考插件（Component Model 形态）**：WIT 类型接口 + Canonical ABI，编到 wasm32-unknown-unknown 再组件化 |
| ninfenz-plugin.wit | 插件接口契约（P5-03.1）；装载期用它校验清单声明的方法名 |
| manifests/sha256.json | 插件清单：方法 / I-O / 能力 / 确定性 / 成本 / 燃料 / 版本 |
| ../../scripts/plugin_host.py | **宿主**（适配器侧）：装载校验 + wasmtime 执行 + 能力收窄 + 回退 |
| ../../scripts/plugin_reference.py | Python **参考实现**（恒在；回退面与字节等价对照物） |
| ../../scripts/plugin_promote.py | 晋升门取数：真测量 → 第三部分仲裁 → 三判据判定 |
| ../../desktop/src/core/plugin_manifest.py | 装载期校验（纯判定，stdlib 零依赖） |
| ../../desktop/src/core/plugin_gate.py | 晋升门规则（纯判定，stdlib 零依赖） |

**红线**：wasmtime 只在适配器侧（scripts/）；core/ 不 import 任何宿主设施。

## ABI 与能力面

契约形态是 **WASI preview 1 的 CLI 程序**：

    argv    --method <name>
    stdin   原始字节（**唯一**输入通道）
    stdout  结果字节（本参考插件为小写十六进制 + LF）
    stderr  报因；退出码 2 = 用法/未知方法

宿主一律**显式 deny**（不靠默认值）：

| 面 | 做法 | 效果 |
|---|---|---|
| 文件系统 | 不给 `--dir` | 无 preopens，读不到任何宿主文件 |
| 网络 | 不给 `-S inherit-network` | 无网络 |
| 环境变量 | `-S inherit-env=n` | 连 `PATH` 都看不到 |
| 时钟/随机 | 清单必须声明 `clocks/random = deny`（deterministic 时） | 结果可复现 |
| 算力 | `-W fuel=<预算>` | 耗尽即 trap |
| 墙钟 | `-W timeout=<ms>` + `epoch-interruption=y` 双保险 | 超时即中断 |

## 燃料：实测数字与一条被数据纠正的设计

实测（wasmtime 49.0.2，本机）：燃料消耗**线性**，约 **138,776 / KiB**。

最初清单只声明了一个固定 `per_call`。32 MiB 输入时它「恰好」耗尽 4e9 燃料并回退——
即那个固定数字变成了**隐式的输入长度上限**。修法：线性的方法必须声明 `per_kib`，
宿主按 `base + per_kib × ceil(bytes/1024)` 计预算，`hard_cap` 兜底。
（装载期校验现在会拒绝「linear 成本却没有 per_kib」的清单。）

## 晋升门：允许判不通过（本机真实结果）

§18.4 的三条缺一不可。`python scripts/plugin_promote.py --json` 的输出（2026-10-12 本机）：

| 输入 | 字节等价 | 工具链成本 | 加速 | 判定 |
|---|---|---|---|---|
| 1 MiB | 仲裁 PASS | 在场 · 1 | **2.77×** | **晋升** |
| 32 MiB | 仲裁 PASS | 在场 · 1 | **0.80×** | **不晋升** |

读法：小输入时启动成本占主导（wasm 程序小、Python 解释器启动贵），插件赢；输入一大，
算法成本占主导，hashlib 走 OpenSSL（SHA-NI 指令）反超，插件输。**这正是 §18.2 要的结果**——
语言分配必须看实测成本，而不是看偏好。门的两侧都由 `desktop/tests/test_plugin_gate.py` 钉住。

## 失败隔离（§18.5）

崩溃 / 超时 / 燃料耗尽 / 宿主缺席 / 产物缺席 → 一律**回退 Python 参考实现**并返回
machine-readable 的 `reason`（如 `fuel_exhausted`），**绝不静默**。宿主自身不抛异常。
判据：`desktop/tests/test_plugin_wasm_host.py`（含真燃料耗尽的强制触发）。

## 边界（不宣称）

- 当前产出的是 **CLI 形态**插件，**尚未**产出 Component Model 的二进制组件；WIT 里写的
  接口语义是同一个 world，但装载期校验落在「方法名 + I/O 形状 + 能力 + 确定性」上，
  还**没有**收紧到二进制的类型段（P5-03.2 的剩余项，等组件形态落地）。
- 本目录的插件是**参考实现**，不是对某个热点的加速结论；是否晋升由晋升门按测量判。
- 插件永不进正确性关键路径：参考实现恒在（§18.7）。

## 两种形态：为什么都留着

| | CLI 形态（sha256/） | 组件形态（sha256-component/） |
|---|---|---|
| 接口 | argv + stdin/stdout 的**约定** | **WIT 类型**（装载期可从二进制类型段读出） |
| 输入通道 | stdin 管道 | Canonical ABI 具名调用（WAVE 字面量经 argv） |
| 隔离/计量 | wasmtime 的 `-S` / `-W` 开关全套可用 | 同上（不带 WASI import ⇒ 能力面结构化地不存在） |
| 适合 | 跑量（大输入） | 类型校验 + 小样本互证 |

**实测（2026-10-12）**：组件形态可被 `wasm-tools component wit` 读出

    export ninfenz:plugin/methods@0.1.0;
    sha256: func(data: list<u8>) -> result<list<u8>, string>;

与仓级 WIT 逐字一致；经宿主调用 `--invoke 'ninfenz:plugin/methods.sha256@0.1.0([97,98,99])'`
得 `ok([186,120,22,191,...])`，即 SHA-256("abc")。两条形态的摘要由
`desktop/tests/test_plugin_component.py` 断言**逐字节相同**。

## 同一轨道的相邻面（不在本目录，但同属 P5）

| 项 | 位置 | 说明 |
|---|---|---|
| P5-07 绑定层 | engine/rust/ffi（C ABI）+ engine/rust/pyo3（PyO3 + maturin wheel） | 见 engine/rust/BINDINGS.md；本机实测两条路径都真装载并报同一 ABI 版本 |
| P5-08 NativeAOT | engine/dotnet/tools/nf-canonical（dist-aot） | AOT 单文件 1,478,656 B；14 条向量与规范逐字节等价，且无需 DOTNET_ROOT |
| P5-09 剖析 | scripts/hotspot_profile.py | cProfile 取数 + 可复算排名；py-spy/hyperfine 缺席如实记 UNKNOWN |
| P5-10 晋升门 | desktop/src/core/plugin_gate.py + scripts/plugin_promote.py | 三判据缺一不可 |

实测小结（2026-10-12）：插件在 1 MiB 输入上快 2.77×（启动成本主导）⇒ 晋升；
在 32 MiB 输入上慢 0.80×（算法成本主导，hashlib 走 SHA-NI）⇒ **不晋升**。
语言分配按测得成本，不按偏好——这是 §18.2 的判据，不是例外。
