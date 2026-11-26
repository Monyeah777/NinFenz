//! nf-app-core：NF APP 共享核心（A0–A5 参考实现）。
//! 规范：app/docs/CONTRACT.md、app/docs/CLI.md；schema/limits/错误码均在编译期内嵌。

pub mod zero_slice;
pub mod backup;
pub mod audit;
pub mod budget;
pub mod build;
pub mod contract;
pub mod canonical;
pub mod claim;
pub mod compose;
pub mod composition;
pub mod evidence;
pub mod extension;
pub mod docx;
pub mod cli;
pub mod error;
pub mod ext;
pub mod ffi;
pub mod fixtures;
pub mod fsutil;
pub mod golden;
pub mod layout;
pub mod limits;
pub mod markdown;
pub mod migration;
pub mod ops;
pub mod pack_release;
pub mod repair;
pub mod report;
pub mod report_ops;
pub mod reuse;
pub mod preset;
pub mod portable;
pub mod schema;
pub mod solve;
pub mod sdir;
pub mod sdir_io;
pub mod template;
pub mod skillpack;
pub mod trust;
pub mod yaml;
pub mod zipsec;

/// C ABI 版本（CLI.md §5）。
pub const ABI_VERSION: &str = "nf-app-core/1";

/// crate 版本。
pub const CORE_VERSION: &str = env!("CARGO_PKG_VERSION");