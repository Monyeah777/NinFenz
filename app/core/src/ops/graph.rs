//! 管线图：graph-validate（L0+L1）/ graph-compile（→ nf-assembly-plan/1）。

use crate::canonical::digest_with_excludes;
use crate::error::{CoreError, OpOutcome};
use crate::ops::{float_issue, ref_id, req_value};
use crate::report::Report;
use crate::schema::validate;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet, VecDeque};

mod validate;
mod compile;

pub use validate::*;
pub use compile::*;
