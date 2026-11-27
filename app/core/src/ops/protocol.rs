//! 协议包：protocol-validate / protocol-render（条款占位符 + 封闭规则 DSL）。

use crate::error::{CoreError, OpOutcome};
use crate::ops::{float_issue, ref_id, req_value, usage};
use crate::report::Report;
use crate::schema::regex_matches;
use serde_json::{json, Map, Value};
use std::collections::BTreeSet;

mod validate;
mod eval;
mod render;

pub use validate::*;
pub(crate) use eval::*;
pub use render::*;
