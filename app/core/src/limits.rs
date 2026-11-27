//! app/schema/limits.json 的只读加载（单一真源，编译期内嵌）。

use serde_json::Value;
use std::sync::OnceLock;

#[derive(Clone, Debug)]
pub struct Limits {
    pub json_max_depth: u64,
    pub json_max_bytes: u64,
    pub yaml_max_alias_expansions: u64,
    pub yaml_max_depth: u64,
    pub text_max_chars: u64,
    pub markdown_max_fence_lines: u64,
    pub zip_max_entries: u64,
    pub zip_max_total_unpacked_bytes: u64,
    pub zip_max_file_bytes: u64,
    pub zip_max_compression_ratio: u64,
    pub zip_max_nesting: u64,
    pub pack_max_items: u64,
    pub pack_max_file_bytes: u64,
    pub pack_max_total_bytes: u64,
    pub import_max_headings: u64,
    pub import_max_code_blocks: u64,
    pub import_max_tables: u64,
}

fn get_u64(v: &Value, path: &[&str]) -> u64 {
    let mut cur = v;
    for p in path {
        cur = &cur[*p];
    }
    // audit: panic-fail-closed —— limits.json 是编译期内嵌的单一真源；缺整数路径属构建期契约破坏，
    // 宁可 fail-closed 暴露，也不静默取默认值。
    cur.as_u64().unwrap_or_else(|| panic!("limits.json 缺少整数路径 {path:?}"))
}

pub fn limits() -> &'static Limits {
    static L: OnceLock<Limits> = OnceLock::new();
    L.get_or_init(|| {
        let raw = include_str!("../../schema/limits.json");
        let v: Value = serde_json::from_str(raw).expect("limits.json 必须是合法 JSON");
        Limits {
            json_max_depth: get_u64(&v, &["json", "max_depth"]),
            json_max_bytes: get_u64(&v, &["json", "max_bytes"]),
            yaml_max_alias_expansions: get_u64(&v, &["yaml", "max_alias_expansions"]),
            yaml_max_depth: get_u64(&v, &["yaml", "max_depth"]),
            text_max_chars: get_u64(&v, &["text", "max_chars"]),
            markdown_max_fence_lines: get_u64(&v, &["markdown", "max_fence_lines"]),
            zip_max_entries: get_u64(&v, &["zip", "max_entries"]),
            zip_max_total_unpacked_bytes: get_u64(&v, &["zip", "max_total_unpacked_bytes"]),
            zip_max_file_bytes: get_u64(&v, &["zip", "max_file_bytes"]),
            zip_max_compression_ratio: get_u64(&v, &["zip", "max_compression_ratio"]),
            zip_max_nesting: get_u64(&v, &["zip", "max_nesting"]),
            pack_max_items: get_u64(&v, &["pack", "max_items"]),
            pack_max_file_bytes: get_u64(&v, &["pack", "max_file_bytes"]),
            pack_max_total_bytes: get_u64(&v, &["pack", "max_total_bytes"]),
            import_max_headings: get_u64(&v, &["import", "max_headings"]),
            import_max_code_blocks: get_u64(&v, &["import", "max_code_blocks"]),
            import_max_tables: get_u64(&v, &["import", "max_tables"]),
        }
    })
}

pub fn limits_value() -> Value {
    serde_json::from_str(include_str!("../../schema/limits.json")).expect("limits.json 合法")
}
