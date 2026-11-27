//! nf-build-graph/1：内容寻址构建图 + 确定性渲染 + 增量计划。

use crate::canonical::{digest_value, sha256_hex};
use crate::docx;
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::ops::{ensure_out_dir, opt_str, req_value, usage};
use crate::report::Report;
use crate::schema::validate;
use crate::sdir;
use crate::zipsec;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

#[path = "build_plan_render.rs"]
mod plan_render;
#[path = "build_run_export.rs"]
mod run_export;
#[path = "build_block_ops.rs"]
mod block_ops;

pub use plan_render::*;
pub use run_export::*;
pub use block_ops::*;
