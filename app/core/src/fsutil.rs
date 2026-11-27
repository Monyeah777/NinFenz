//! 文件系统纪律：POSIX 相对路径、符号链接拒绝、确定性遍历、tree 摘要、pack items。
//! 路径安全判据（绝对路径 / .. / 盘符 / UNC / NUL / 保留设备名 / 控制字符 / 反斜杠）。

use crate::canonical::{canonical_bytes, sha256_hex};
use crate::error::CoreError;
use crate::limits::limits;
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};

mod path_guard;
mod pack_io;

pub use path_guard::*;
pub use pack_io::*;
