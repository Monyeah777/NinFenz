//! JSON Schema 2020-12 **子集**校验器 —— 与真源 `desktop/src/core/json_schema.py` 对账。
//!
//! 真源是**叶子件**（不 import 任何 core 模块）；本线同形，只依赖 `pyjson` / `pyval`。
//! 调用面：`asset_contract` 的数据面，以及 `output_forms` / `pack_combo`（后者在深度子扫描器里）。
//!
//! 子集边界与真源一致，且**"不支持"绝不等价"通过"**：超出 `_SUPPORTED` 的官方关键字进
//! `unsupported` 清单（调用方若关心可自行取用；`asset_contract` 不取，故不影响其结论）。
//!
//! 三处口径陷阱（都影响逐字节对账）：
//!
//! 1. **`bool` 不是 `number`/`integer`**（Python 里 `isinstance(True, int)` 为真，真源显式排除）。
//! 2. **`const` / `enum` 用 Python 的 `==`**：`True == 1` 成立 ⇒ 本线走 `pyval::py_eq`，
//!    不能用结构相等。
//! 3. **`type(instance).__name__`**：消息里出现的是 `dict` / `list` / `NoneType` 这些
//!    **Python 类型名**，不是 Rust 的。
use crate::pyjson::Json;
use crate::pyval;
mod part1;
mod part2;
pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
#[path = "generated/json_schema_gen.rs"]
mod json_schema_gen;
