//! 语义文档 IR 的块节点（Node）。
//!
//! 自 `sdir.rs` 按职责拆出：实现逐字搬运，逻辑与文案未改；公共 API 由父模块 `pub use` 保持原路径。

use serde_json::{json, Value};

#[derive(Clone, Debug)]
pub struct Node {
    pub id: String,
    pub btype: String,
    pub text: String,
    pub attrs: Value,
    pub children: Vec<Node>,
    pub page: Option<u64>,
    pub bbox: Option<Value>,
}

impl Node {
    pub(crate) fn new(btype: &str, text: impl Into<String>) -> Self {
        Node {
            id: String::new(),
            btype: btype.to_string(),
            text: text.into(),
            attrs: json!({}),
            children: Vec::new(),
            page: None,
            bbox: None,
        }
    }
}
