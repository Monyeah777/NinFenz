//! Pack 更新 / Overlay：pack-diff / pack-merge / overlay-apply（A4）。

use crate::canonical::{canonical_bytes, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::ops::pack::{dir_tree, parse_semver, verify_manifest};
use crate::ops::{ensure_out_dir, float_issue, ref_id, req_str, req_value, resolve_path, schema_report};
use crate::report::{failure_report, Report};
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

mod plan_conflict;
mod diff;
mod merge;
mod overlay;

pub(crate) use plan_conflict::*;
pub use diff::*;
pub use merge::*;
pub use overlay::*;
