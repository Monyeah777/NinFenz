//! nf-sdir/1：语义文档 IR（导入/校验/差异/三方合并）。
//! 设计约束：块有稳定 id + 内容 hash；关系闭包；可访问性显式 missing；块级溯源。
//! 本模块不猜版式：源适配器必须显式给出 transform 与来源摘要。
//!
//! **文件组织**：实现按职责拆到 `sdir/*.rs`；本文件只留常量、`Node` 出口与 `pub use` 再导出，
//! 故 `nf_app_core::sdir::*` 路径不变。

pub const SDIR_SCHEMA: &str = "nf-sdir/1";
pub const IMPORT_TRANSFORM: &str = "sdir-import/1";

mod imports;
mod markup;
mod merge;
mod node;
mod ops;
mod parse;
mod validate;

pub use self::imports::{import_markdown, source_from_request};
pub use self::markup::import_docx;
pub use self::merge::{diff_op, merge_op};
pub use self::node::Node;
pub use self::ops::{fuse_op, import_doc, import_epub, import_op};
pub use self::validate::{validate_op, validate_sdir_value};
pub(crate) use self::imports::assemble_sdir;
