//! NF 引擎 C ABI 出口（cdylib）+ **纯函数原语出口**（rlib）。
//!
//! 用途分两半：
//!   - C ABI（cdylib）：给 core/engine_loader.py 一个可 dlopen 的共享库，暴露 ABI 版本号；
//!   - 原语（rlib）：给 engine/rust/pyo3（PyO3 扩展）做进程内绑定，暴露**逐字节对账过**的
//!     纯函数（Merkle sha256 / CPython float repr）——同进程、零子进程、内存直接交互。
//!
//! 纪律：C ABI 符号名必须与 Python 侧 core/engine_loader.py 的 ABI_SYMBOL 一致；
//! 这里只暴露**纯函数**（不读盘、不写盘、无外部状态），业务面仍在 bin（main.rs）。

/// RFC 6962 风格 Merkle 哈希（与 `desktop/src/core/receipts.py` 同规则）。
pub mod merkle;
/// CPython `float.__repr__` 复刻（与 `desktop/src/core` 浮点口径逐字节一致）。
pub mod pyfloat;

/// C ABI：引擎 ABI 版本号（Python 侧按 ABI_SYMBOL 取此符号）。
#[no_mangle]
pub extern "C" fn nf_engine_abi_version() -> u32 {
    1
}
