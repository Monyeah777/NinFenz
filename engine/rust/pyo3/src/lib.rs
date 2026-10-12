//! NF Python 扩展（PyO3）—— P5-07.1 绑定层 / P5-07.2 构建面。
//!
//! 与 engine/rust/ffi（C ABI + ctypes）是**两条并存路径**，刻意都在场：
//!   - C ABI 路径：不依赖 Python 开发头，任何语言/任何运行时都能载；
//!   - PyO3 路径：Python 侧零 ctypes 样板，但把「Python 开发工具链」变成构建前提。
//! 晋升门（P5-10）对「工具链维护成本」计数时后者成本更高——本模块的存在让这条权衡**可测**，
//! 而不是靠偏好断言。
use pyo3::prelude::*;
use pyo3::types::PyBytes;

#[pyfunction]
fn abi_version() -> u32 {
    1
}

#[pyfunction]
fn reverse_bytes<'py>(py: Python<'py>, data: &[u8]) -> Bound<'py, PyBytes> {
    let flipped: Vec<u8> = data.iter().rev().copied().collect();
    PyBytes::new_bound(py, &flipped)
}

#[pymodule]
fn nf_pyengine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("ABI_VERSION", abi_version())?;
    m.add_function(wrap_pyfunction!(abi_version, m)?)?;
    m.add_function(wrap_pyfunction!(reverse_bytes, m)?)?;
    Ok(())
}
