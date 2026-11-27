//! `output_forms` 的**格式结构校验器**（真源 `_check_*` 一族 + `_FORM_CHECK` 分派表）。
//!
//! 拆成独立件只为可读：口径与真源逐条对应，判据面不拆。
//!
//! **两个解析器是本线自带的**（真源用标准库，本线不用 Python 运行时）：
//! `jsonmini`（`json.loads` 口径 + 重复键）、`toml` crate（`tomllib` 口径）。
//! 越出子集即 fail-closed。

use crate::output_forms::{read_text, rel_path};
use crate::pyjson::Json;
use crate::pyval;
use std::path::Path;

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
#[path = "generated/output_forms_checks_gen.rs"]
mod output_forms_checks_gen;
