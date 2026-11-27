//! 导入/嗅探/映射（A3）：import-sniff / import / map-suggest。
//! 置信度为整数百分比 0–100（禁浮点，见 nf-import/1 schema 修订）。

use crate::canonical::{parse_json_bytes, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::limits::limits;
use crate::markdown;
use crate::ops::{float_issue, opt_str, req_str, req_value, resolve_path, schema_report, usage};
use crate::report::Report;
use crate::yaml;
use crate::zipsec;
use serde_json::{json, Map, Value};
use std::collections::BTreeMap;
use std::path::Path;

mod sniff;
mod extract;
mod mapping;

pub use sniff::*;
pub use extract::*;
pub use mapping::*;
