//! 装配与校验：assemble（确定性 Markdown 渲染 + nf-assemble-result/1）/ validate（L0/L1/L2）。

use crate::canonical::{digest_value, digest_with_excludes, parse_json_bytes, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::ops::{opt_str, report_level, req_str, req_value, resolve_path, usage};
use crate::report::Report;
use crate::schema::validate as schema_validate;
use crate::ops::spec::{eval_constraint, validate_spec};
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::io::Write;

mod render;
mod assemble;
mod validate;

pub use render::*;
pub use assemble::*;
pub use validate::*;
