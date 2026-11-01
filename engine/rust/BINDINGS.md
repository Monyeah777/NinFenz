# engine/rust/ · 绑定层（计划第五部分 P5-07）

> 目的：把「同进程 FFI 装载」从**计划承诺**落成**可装载、可调用、版本对得上**的实现。
> 依据：.rivet/private_archive/64_复合型MoE门禁方案.md §16.4（快路径）/ §20.5 P5-07（内部档案）。

## 两条路径，都在场

| 路径 | 件 | 产物（本机实测） | 装载方 |
|---|---|---|---|
| C ABI（P5-07.3） | ffi/ | `nf_ffi.dll` 1,216,134 B | `core/engine_loader.py` + ctypes |
| PyO3（P5-07.1） | pyo3/ | `nf_pyengine.dll` 1,647,957 B | CPython `import nf_pyengine` |
| maturin wheel（P5-07.2） | pyo3/pyproject.toml | `ninfenz_pyengine-0.1.0-cp311-cp311-win_amd64.whl` 615,758 B | `pip install` |

**为什么两条都留着**：晋升门（P5-10）把「工具链维护成本」计作判据之一。C ABI 路径不依赖 Python
开发头、任何运行时都能载；PyO3 路径在 Python 侧零 ctypes 样板，但把「Python 开发工具链」变成
构建前提。两条并存 = 这条权衡**可测**，而不是靠偏好断言。

## C ABI 契约（导出的符号面，逐条枚举）

| 符号 | 签名 | 语义 |
|---|---|---|
| `nf_engine_abi_version` | `() -> u32` | ABI 版本；`engine_loader.engine_abi()` 读的就是它 |
| `nf_engine_abi_self_test` | `() -> u32` | 自证一次；把「装载成功」与「版本对」分开判 |
| `nf_engine_abi_tag` | `() -> *const c_char` | `nf-ffi/1` |
| `nf_reverse_bytes` | `(in, len, out, cap) -> usize` | 成功返回 `len`；**非法输出缓冲（out 空 / cap<len）拒绝并返回 0**（不写、不暗示所需长度，VULN-02 F1）；输入空指针返回 0 |

版本升级判据：**导出面**（符号名 / 签名 / 语义）任一变化即 +1；纯内部重构不动它。

```
python scripts/engine_status.py --abi          # 平台 C 运行库装载探针
python -m unittest tests.test_engine_ffi_binding   # 两条绑定路径的真装载判据（9 例）
```

## 构建（本机实测命令）

```
cargo test  --manifest-path engine/rust/ffi/Cargo.toml      # 4 例
cargo build --release --manifest-path engine/rust/ffi/Cargo.toml
cargo build --release --manifest-path engine/rust/pyo3/Cargo.toml
maturin build --release --manifest-path engine/rust/pyo3/Cargo.toml --out engine/rust/pyo3/dist
```

## 实测踩到的两个宿主问题（留档，供复现）

1. **cargo 注册表缓存里有一个打不开的 `.crate`**（`portable-atomic-1.15.0.crate` → os error 5），
   `maturin` 的 `cargo metadata` 因此失败。处置：**不删用户的缓存**，改用独立 `CARGO_HOME`
   （`.rivet/scratch/cargo-home`，复制镜像配置），重下一次依赖树即通。
2. **宿主 `%TEMP%` 下创建临时目录被拒**（`os error 5 at ...\Temp\.tmpXXXX`），maturin 打包失败并
   留下 22 B 的空 wheel。处置：把 `TEMP/TMP` 指到工作区内目录（`.rivet/scratch/tmp`）即通。

两条都不是本仓代码的问题，故只留档、不改仓；复现命令在 `.rivet/scratch/build_maturin3.ps1`。

## 边界（不宣称）

- 绑定层只做**搬运**（版本号 + 一个可验证的纯函数），不做业务语义；跨语言**语义**等价仍由
  `scripts/cross_lang_verify.py` 的规范向量判定（§16.8：ABI/FFI 噪声不得混进语义判定）。
- `nf_reverse_bytes` 是**契约载体**而非有用算法：它的作用是让「装载 → 调用 → 长度契约 → 失败语义」
  四件事各有判据，而不是靠 `--version` 一句话。
