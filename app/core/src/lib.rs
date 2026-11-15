//! nf-app-core：NF APP 共享核心（A0–A5 参考实现）。
//! 规范：app/docs/CONTRACT.md、app/docs/CLI.md；schema/limits/错误码均在编译期内嵌。

pub mod backup;
pub mod canonical;
pub mod cli;
pub mod error;
pub mod ext;
pub mod ffi;
pub mod fixtures;
pub mod fsutil;
pub mod golden;
pub mod limits;
pub mod markdown;
pub mod ops;
pub mod report;
pub mod schema;
pub mod yaml;
pub mod zipsec;

/// C ABI 版本（CLI.md §5）。
pub const ABI_VERSION: &str = "nf-app-core/1";

/// crate 版本。
pub const CORE_VERSION: &str = env!("CARGO_PKG_VERSION");
