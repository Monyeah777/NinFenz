//! 产出形态面（output forms）—— 与真源 `desktop/src/core/output_forms.py` 的 `scan` 对账。
//!
//! ## 移植面按消费者界定（有工具，不是猜的）
//!
//! 用了 [`tools/trace_call_closure.py`](../../tools/trace_call_closure.py) 从入口 `scan` 算模块内
//! 调用闭包（**跟随模块级分派表**——否则会低估，见下）。实测结果：
//!
//! | | |
//! |---|---|
//! | 真源规模 | 1,496 行 / 69 个函数 |
//! | **闭包内** | **67 个函数 / 约 1,113 行** |
//! | 闭包外 | **2 个**：`render_outputs`（写盘）、`write_baseline`（重签基线）——**都属写面** |
//!
//! ⚠️ 闭包必须**跟随 `_FORM_CHECK` 这张模块级分派表**：`_verify_pack` 以
//! `_FORM_CHECK.get(form)` 间接调用 15 个格式校验器；只看函数体内的直接引用会漏掉它们全部
//! （约 270 行）。这正是 `trace_call_closure.py` 里那段「跟随模块级 dict 字面量」的由来。
//!
//! ## 本文件当前进度（分块移植，逐块验证）
//!
//! - ✅ 常量 + `_rel` / `_read_*` / `load_registry` / `registry_verify` / `detect`
//! - ✅ `_check_xml` / `_xml_guard` / `_check_graphml`（用 `xmlmini`）
//! - ⏳ 其余格式校验器（`_check_json` 需 JSON 重复键检测；`_check_toml` 需 TOML 解析）
//! - ⏳ 包级产出清单（`_pack_dirs` / `shared_face_key` / `pack_slice_index` / `_verify_pack` …）
//! - ⏳ `index_verify` / `baseline_verify` / `meter` / 生成器 / `scan`

use crate::pyjson::Json;
use crate::pyval;
use std::path::Path;

pub const REGISTRY_REL: &str = "protocol/output_forms.json";
pub const BASELINE_REL: &str = "protocol/output_forms_baseline.json";
pub const INDEX_REL: &str = "outputs/INDEX.json";

/// 机检档位（递增）；档位 = **本仓可做的判定强度**，不是「格式有多高级」。
pub const TIERS: [&str; 5] = ["T0", "T1", "T2", "T3", "T4"];

/// 形态状态（对外可判定口径）——真源 `STATUSES`。
pub const STATUSES: [&str; 7] = [
    "supported",
    "absorbed",
    "planned",
    "deferred",
    "unfit",
    "reference",
    "unreachable",
];

/// 真源 `_EXT_FORM`。
const EXT_FORM: [(&str, &str); 20] = [
    (".json", "json"),
    (".jsonl", "jsonl"),
    (".ndjson", "jsonl"),
    (".yaml", "yaml"),
    (".yml", "yaml"),
    (".toml", "toml"),
    (".csv", "csv"),
    (".tsv", "csv"),
    (".xml", "xml"),
    (".md", "markdown"),
    (".mmd", "mermaid"),
    (".dot", "graphviz-dot"),
    (".gv", "graphviz-dot"),
    (".graphml", "graphml"),
    (".svg", "svg"),
    (".txt", "text"),
    (".proto", "protobuf-proto3"),
    (".graphql", "graphql-sdl"),
    (".ttl", "turtle"),
    (".sql", "sql-ddl"),
];

/// 真源 `_FORM_MAX_TIER`。
const FORM_MAX_TIER: [(&str, &str); 22] = [
    ("json", "T2"),
    ("jsonl", "T2"),
    ("yaml", "T2"),
    ("toml", "T2"),
    ("csv", "T2"),
    ("xml", "T1"),
    ("svg", "T1"),
    ("markdown", "T1"),
    ("text", "T0"),
    ("json-schema", "T2"),
    ("vega-lite", "T3"),
    ("mermaid", "T3"),
    ("graphviz-dot", "T3"),
    ("graphml", "T3"),
    ("json-graph-format", "T3"),
    ("quant-metrics", "T3"),
    ("performance-report", "T4"),
    ("concept-closure", "T4"),
    ("system-card", "T3"),
    ("domain-spec", "T3"),
    ("domain-report", "T4"),
    ("combo-cert", "T4"),
];

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
#[path = "generated/output_forms_gen.rs"]
mod output_forms_gen;
