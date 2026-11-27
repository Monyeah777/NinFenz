//! 手写 JSON Schema 语义校验器：只覆盖 app/schema/*.json 实际使用的关键字子集
//!（type/const/enum/pattern/minLength/minimum/maximum/minItems/items/properties/
//! required/additionalProperties/$ref/$defs/oneOf），不依赖 jsonschema crate。

use crate::canonical::obj_path;
use regex::Regex;
use serde_json::Value;
use std::collections::BTreeMap;
use std::sync::OnceLock;

pub const SCHEMA_NAMES: &[&str] = &[
    "nf-pack",
    "nf-import",
    "nf-doc",
    "nf-md-spec",
    "nf-pipeline-graph",
    "nf-protocol-pack",
    "nf-assembly-plan",
    "nf-validate-report",
    "nf-assemble-result",
    "nf-export-manifest",
    "nf-backup",
    "nf-template",
    "nf-pack-update",
    "nf-overlay",
    "nf-project",
    "ccos-task",
    "ccos-result",
    "nf-sdir",
    "nf-build-graph",
    "nf-evidence",
    "nf-extension",
    "nf-claim-ledger",
    "nf-budget",
    "nf-migration",
    "nf-audit",
    "nf-trust-root",
    "nf-report",
    "nf-preset",
    "nf-portable",
    "nf-review",
    "nf-handoff",
    "nf-library",
    "nf-activity",
    "nf-contract-ir",
    "nf-contract-result",
    "nf-build",
    "nf-fragment",
    "nf-composition",
    "nf-source",
    "nf-source-chain",
    "nf-macro",
    "nf-ai-run",
];

macro_rules! embed_schemas {
    ($($name:literal => $path:literal),* $(,)?) => {{
        let mut m: BTreeMap<&'static str, Value> = BTreeMap::new();
        $(
            m.insert($name, serde_json::from_str(include_str!($path)).expect(concat!("schema ", $name, " 非法 JSON")));
        )*
        m
    }};
}

pub fn schemas() -> &'static BTreeMap<&'static str, Value> {
    static S: OnceLock<BTreeMap<&'static str, Value>> = OnceLock::new();
    S.get_or_init(|| {
        embed_schemas!(
            "nf-pack" => "../../schema/nf-pack.schema.json",
            "nf-import" => "../../schema/nf-import.schema.json",
            "nf-doc" => "../../schema/nf-doc.schema.json",
            "nf-md-spec" => "../../schema/nf-md-spec.schema.json",
            "nf-pipeline-graph" => "../../schema/nf-pipeline-graph.schema.json",
            "nf-protocol-pack" => "../../schema/nf-protocol-pack.schema.json",
            "nf-assembly-plan" => "../../schema/nf-assembly-plan.schema.json",
            "nf-validate-report" => "../../schema/nf-validate-report.schema.json",
            "nf-assemble-result" => "../../schema/nf-assemble-result.schema.json",
            "nf-export-manifest" => "../../schema/nf-export-manifest.schema.json",
            "nf-backup" => "../../schema/nf-backup.schema.json",
            "nf-template" => "../../schema/nf-template.schema.json",
            "nf-pack-update" => "../../schema/nf-pack-update.schema.json",
            "nf-overlay" => "../../schema/nf-overlay.schema.json",
            "nf-project" => "../../schema/nf-project.schema.json",
            "ccos-task" => "../../schema/ccos-task.schema.json",
            "ccos-result" => "../../schema/ccos-result.schema.json",
            "nf-sdir" => "../../schema/nf-sdir.schema.json",
            "nf-build-graph" => "../../schema/nf-build-graph.schema.json",
            "nf-evidence" => "../../schema/nf-evidence.schema.json",
            "nf-extension" => "../../schema/nf-extension.schema.json",
            "nf-claim-ledger" => "../../schema/nf-claim-ledger.schema.json",
            "nf-budget" => "../../schema/nf-budget.schema.json",
            "nf-migration" => "../../schema/nf-migration.schema.json",
            "nf-audit" => "../../schema/nf-audit.schema.json",
            "nf-trust-root" => "../../schema/nf-trust-root.schema.json",
            "nf-report" => "../../schema/nf-report.schema.json",
            "nf-preset" => "../../schema/nf-preset.schema.json",
            "nf-portable" => "../../schema/nf-portable.schema.json",
            "nf-review" => "../../schema/nf-review.schema.json",
            "nf-handoff" => "../../schema/nf-handoff.schema.json",
            "nf-library" => "../../schema/nf-library.schema.json",
            "nf-activity" => "../../schema/nf-activity.schema.json",
            "nf-contract-ir" => "../../schema/nf-contract-ir.schema.json",
            "nf-contract-result" => "../../schema/nf-contract-result.schema.json",
            "nf-build" => "../../schema/nf-build.schema.json",
            "nf-fragment" => "../../schema/nf-fragment.schema.json",
            "nf-composition" => "../../schema/nf-composition.schema.json",
            "nf-source" => "../../schema/nf-source.schema.json",
            "nf-source-chain" => "../../schema/nf-source-chain.schema.json",
            "nf-macro" => "../../schema/nf-macro.schema.json",
            "nf-ai-run" => "../../schema/nf-ai-run.schema.json",
        )
    })
}

pub fn schema(name: &str) -> Option<&'static Value> {
    schemas().get(name)
}

mod validate;

pub use validate::*;
