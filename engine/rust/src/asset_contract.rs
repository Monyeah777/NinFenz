//! 数字资产契约层（数据 / 代码 / 脚本三面 · 声明即契约）—— 与真源
//! `desktop/src/core/asset_contract.py` 的 `scan` 对账。
//!
//! **不移植**：`freeze()`（重冻 sha256）与 `run_tests()` / `_run_test_file()`（执行被声明脚本）
//! ——前者是写面、后者是执行层，按目标纪律都不碰。
//!
//! 三面口径见真源模块文档。本文件按面拆成三段：数据面 / 代码面 / 脚本面。
//!
//! ## 已知偏差（两处，都是**外来输入的报错文本**）
//!
//! 1. **JSON 解析失败的文本**：真源给 CPython `json` 的报错，本线给 `serde_json` 的。
//! 2. **读件失败的文本**：真源给 `OSError` / `UnicodeDecodeError` 的 repr，本线给 `std::io` 的。
//!
//! 二者都只在**坏输入**时出现在消息里；真语料上这两支都不触发。分支判据里做**归一**后比较，
//! 不假装文本相同（同 `code_metrics` 的语法支处理）。

use crate::json_schema;
use crate::pyjson::Json;
use crate::pyval;
use std::path::Path;

pub const DECL_REL: &str = "protocol/asset_contracts.json";
pub const SCHEMA: &str = "nf-asset-contracts/1";
/// 真源 `SCHEMA_REL`：可移植 schema（⑤ 声明自检用）。
pub const SCHEMA_REL: &str = "protocol/schema/asset_contracts.schema.json";
/// 真源 `EXPORT_REL`：Frictionless Data Package 导出件（④ 漂移判据用）。
pub const EXPORT_REL: &str = "protocol/generated/asset_contract.frictionless.json";
pub const FACES: [&str; 4] = ["data", "code", "script", "index"];
pub const LANGS: [&str; 3] = ["python", "bash", "vba"];
/// 真源 `FORMATS`（D3 写通道契约化后扩到 9 个：yaml/toml/jsonl/graphml/mmd 逐条对应
/// `asset_contracts.json` 里新增的数据件声明）。顺序须与真源元组**逐字同序**——
/// 报错文案里 `"/".join(FORMATS)` 会进判据。
pub const FORMATS: [&str; 9] = [
    "json", "csv", "markdown", "text", "yaml", "toml", "jsonl", "graphml", "mmd",
];
/// 真源 `_MMD_KINDS`：Mermaid 首关键词词表（结构判据：只认「这是一张什么图」）。
pub const MMD_KINDS: [&str; 17] = [
    "graph",
    "flowchart",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "erDiagram",
    "gantt",
    "pie",
    "mindmap",
    "timeline",
    "journey",
    "gitGraph",
    "quadrantChart",
    "xychart-beta",
    "requirementDiagram",
    "C4Context",
    "block-beta",
];

mod part1;
mod part2;
mod part3;
mod part4;
mod part5;
mod part6;
mod part7;
mod part8;

pub(crate) use part1::*;
pub(crate) use part2::*;
pub(crate) use part3::*;
pub(crate) use part4::*;
pub(crate) use part5::*;
pub(crate) use part6::*;
pub(crate) use part7::*;
pub(crate) use part8::*;

#[cfg(test)]
mod tests {
    use super::*;
    // ---------------------------------------------------------------- 手写：F3 契约注入自证
    // （非生成器段：生成器的 BEGIN/END 标记都在它之前，重跑生成器不会覆盖这里）

    fn ffi_warn_spec() -> Json {
        // 与 protocol/asset_contracts.json 的 engine-rust-ffi 同构。**直接构造 Json**：
        // 走 JSON 文本要跨三层转义（Rust 字面量 → JSON → 正则），极易错；且本文件位于
        // engine/rust/src/** 的禁用式面内，禁用词必须用 concat! 拼，不能出现字面量。
        let rule = |pairs: Vec<(&str, Json)>| {
            Json::Object(pairs.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
        };
        let s = |v: &str| Json::Str(v.to_string());
        let n = |v: i64| Json::Int(v);
        let warn_rules = rule(vec![
            (
                "export_no_panic",
                rule(vec![
                    (
                        "forbid",
                        Json::Array(vec![
                            s("panic!"),
                            s(".unwrap("),
                            s(".expect("),
                            s("assert!"),
                        ]),
                    ),
                    ("pattern", s("#\\[no_mangle\\]")),
                    ("skip_after", s("#[cfg(test)]")),
                ]),
            ),
            (
                "null_guard_before",
                rule(vec![
                    ("guard", s("is_null")),
                    ("pattern", s("from_raw_parts")),
                    ("skip_after", s("#[cfg(test)]")),
                    ("within", n(20)),
                ]),
            ),
            (
                "unsafe_safety_comment",
                rule(vec![
                    ("marker", s("SAFETY:")),
                    (
                        "pattern",
                        Json::Str(concat!(r"\bun", r"safe\b").to_string()),
                    ),
                    ("skip_after", s("#[cfg(test)]")),
                    ("within", n(3)),
                ]),
            ),
        ]);
        rule(vec![
            ("glob", s("ffi/src/**/*.rs")),
            ("id", s("engine-rust-ffi")),
            ("lang", s("rust")),
            ("warn_rules", warn_rules),
        ])
    }

    /// F3（VULN-02）契约注入自证：三类违规各注入一处 → `code_warns` 必须各报一条；
    /// 补齐（SAFETY 注释 + 空指针守卫 + 导出面不 panic）→ 必须清零。
    ///
    /// 只注入 **WARN 面**：不进 issues、不 FAIL（先 WARN 起步；存量清零后才升 FAIL）。
    #[test]
    fn ffi_warn_rules_fire_and_clear() {
        let root = crate::testutil::fixture("asset-contract-ffi-warn");
        std::fs::create_dir_all(root.join("ffi/src")).expect("夹具目录可建");
        let spec = ffi_warn_spec();

        let bad = concat!(
            "pub ",
            "un",
            "safe",
            " fn raw(p: *const u8, len: usize) -> u8 {\n",
            "    let s = std::slice::from_raw_parts(p, len);\n",
            "    s[0]\n}\n",
            "#[no_mangle]\npub extern \"C\" fn boom() -> u32 { panic!() }\n"
        );
        std::fs::write(root.join("ffi/src/lib.rs"), bad).expect("写夹具件");
        let warns = code_warns(&root, &spec);
        assert_eq!(warns.len(), 3, "三类违规应各报一条：{:?}", warns);
        assert!(
            warns.iter().any(|w| w.contains("SAFETY:")),
            "缺 SAFETY 注释应被抓：{:?}",
            warns
        );
        assert!(
            warns.iter().any(|w| w.contains("from_raw_parts")),
            "缺空指针检查应被抓：{:?}",
            warns
        );
        assert!(
            warns.iter().any(|w| w.contains("panic!")),
            "导出面 panic 应被抓：{:?}",
            warns
        );

        let good = concat!(
            "// SAFETY: 调用方保证 p 有效；本块只读而不写。\n",
            "pub ",
            "un",
            "safe",
            " fn raw(p: *const u8, len: usize) -> u8 {\n",
            "    if p.is_null() { return 0; }\n",
            "    let s = std::slice::from_raw_parts(p, len);\n",
            "    s[0]\n}\n",
            "#[no_mangle]\npub extern \"C\" fn ok() -> u32 { ABI_VERSION }\n"
        );
        std::fs::write(root.join("ffi/src/lib.rs"), good).expect("写夹具件");
        let cleared = code_warns(&root, &spec);
        assert!(cleared.is_empty(), "补齐后 WARN 面应清零：{:?}", cleared);
    }

    /// 真语料上 F3 告警面当前应为空（清零状态）——它是 WARN 面、不参与 issues/FAIL，
    /// 但**不许靠沉默过关**：真有存量时这里会红在断言上，逼人看见。
    #[test]
    fn ffi_warn_rules_are_clean_on_real_corpus() {
        let root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        let (doc, _issues) = load(&root);
        let mut warns: Vec<String> = Vec::new();
        if let Some(Json::Array(specs)) = obj_get(&doc, "code") {
            for spec in specs {
                warns.extend(code_warns(&root, spec));
            }
        }
        assert!(warns.is_empty(), "真语料 FFI 告警面应已清零：{:?}", warns);
    }
}

#[cfg(test)]
#[path = "generated/asset_contract_gen.rs"]
mod asset_contract_gen;
