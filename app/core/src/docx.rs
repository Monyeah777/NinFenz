//! DOCX 导出（OOXML / WordprocessingML，最小但可被 Word/LibreOffice 打开）。
//!
//! 目的：EXP-01 的 md/zip/docx 出口。全部字节由本模块确定性生成：
//! - 固定 zip 时间戳/权限（见 zipsec::fixed_options）
//! - docProps 的 created/modified 固定为 1980-01-01T00:00:00Z（不写运行时间）
//! - 段落顺序 = Markdown 行序；样式用内置 Heading1–6 / Code / Normal

use crate::error::CoreError;
use crate::zipsec;
use regex::Regex;

mod inline;
mod package;

pub(crate) use inline::*;
pub use package::*;
