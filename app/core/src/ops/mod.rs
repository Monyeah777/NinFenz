//! Op 分派与请求/响应公共工具。

pub mod assemble;
pub mod ccos;
pub mod export;
pub mod graph;
pub mod import_ops;
pub mod pack;
pub mod project;
pub mod protocol;
pub mod spec;
pub mod update;

use crate::canonical::{canonical_string, digest_value, find_float_path, parse_json_bytes};
use crate::error::{CoreError, Envelope, OpOutcome};
use crate::report::Report;
use crate::schema::validate;
use serde_json::Value;
use std::path::{Path, PathBuf};

pub fn usage(msg: impl Into<String>) -> CoreError {
    CoreError::new("NF-E-003").with_message(msg)
}

pub fn req_object<'a>(
    req: &'a Value,
    key: &str,
) -> Result<&'a serde_json::Map<String, Value>, CoreError> {
    match req.get(key) {
        Some(Value::Object(m)) => Ok(m),
        Some(_) => Err(usage(format!("请求字段 {key} 必须是 object"))),
        None => Err(usage(format!("请求缺字段 {key}"))),
    }
}

pub fn req_str<'a>(req: &'a Value, key: &str) -> Result<&'a str, CoreError> {
    match req.get(key) {
        Some(Value::String(s)) => Ok(s),
        Some(_) => Err(usage(format!("请求字段 {key} 必须是 string"))),
        None => Err(usage(format!("请求缺字段 {key}"))),
    }
}

pub fn opt_str<'a>(req: &'a Value, key: &str) -> Result<Option<&'a str>, CoreError> {
    match req.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(s)) => Ok(Some(s)),
        Some(_) => Err(usage(format!("请求字段 {key} 必须是 string"))),
    }
}

pub fn req_value<'a>(req: &'a Value, key: &str) -> Result<&'a Value, CoreError> {
    req.get(key)
        .ok_or_else(|| usage(format!("请求缺字段 {key}")))
}

pub fn opt_bool(req: &Value, key: &str) -> Result<bool, CoreError> {
    match req.get(key) {
        None | Some(Value::Null) => Ok(false),
        Some(Value::Bool(b)) => Ok(*b),
        Some(_) => Err(usage(format!("请求字段 {key} 必须是 bool"))),
    }
}

pub fn resolve_path(p: &str) -> PathBuf {
    PathBuf::from(p.replace('\\', "/"))
}

pub fn ensure_out_dir(p: &str) -> Result<PathBuf, CoreError> {
    let path = resolve_path(p);
    crate::fsutil::ensure_dir(&path)?;
    Ok(path)
}

/// 内嵌 schema 校验 → 有 issue 时构造报告。
pub fn schema_report(
    schema_name: &str,
    value: &Value,
    code: &str,
    level: &str,
    kind: &str,
    ref_str: &str,
) -> Option<Value> {
    let issues = validate(schema_name, value);
    if issues.is_empty() {
        return None;
    }
    let mut report = Report::new(level, value, kind, ref_str);
    report.extend_schema_issues(code, &issues);
    Some(report.to_value())
}

/// canonical 禁浮点（artifact 级）。
pub fn float_issue(report: &mut Report, value: &Value, code: &str) -> bool {
    match find_float_path(value, "$") {
        Some(path) => {
            report.error(
                code,
                &path,
                "canonical 禁浮点：产物中的数值必须是整数（需要小数用整数定点或字符串）",
            );
            true
        }
        None => false,
    }
}

pub fn ref_id(value: &Value, key: &str) -> String {
    value
        .get(key)
        .and_then(|v| v.as_str())
        .unwrap_or("$")
        .to_string()
}

pub fn report_level(value: &str) -> String {
    match value {
        "L0" | "L1" | "L2" => value.to_string(),
        _ => "L0".to_string(),
    }
}

/// 报告信封（exit 1）：ok=false，result=report，error 取首条 error issue。
pub fn report_envelope(report: Value) -> Envelope {
    let mut code = "NF-VAL-001".to_string();
    let mut path = "$".to_string();
    let mut message = "校验失败".to_string();
    if let Some(issues) = report.get("issues").and_then(|v| v.as_array()) {
        for i in issues {
            if i.get("severity").and_then(|v| v.as_str()) == Some("error") {
                code = i
                    .get("code")
                    .and_then(|v| v.as_str())
                    .unwrap_or("NF-VAL-001")
                    .to_string();
                path = i
                    .get("path")
                    .and_then(|v| v.as_str())
                    .unwrap_or("$")
                    .to_string();
                message = i
                    .get("message")
                    .and_then(|v| v.as_str())
                    .unwrap_or("校验失败")
                    .to_string();
                break;
            }
        }
    }
    let err = CoreError::new(&code)
        .with_message(format!("{path}: {message}"))
        .at(path)
        .with_exit(1);
    Envelope::failure(&err, Some(report))
}

fn maybe_fail(outcome: OpOutcome) -> OpOutcome {
    match outcome {
        Ok((0, result)) => {
            let verdict = result.get("verdict").and_then(|v| v.as_str()).unwrap_or("pass");
            if verdict == "fail" {
                Ok((1, result))
            } else {
                Ok((0, result))
            }
        }
        other => other,
    }
}

pub fn dispatch(op: &str, req: &Value) -> Envelope {
    let outcome: OpOutcome = match op {
        "canonical" => op_canonical(req),
        "pack-hash" => pack::pack_hash(req),
        "pack-verify" => maybe_fail(pack::pack_verify(req)),
        "import-sniff" => import_ops::import_sniff(req),
        "import" => import_ops::import(req),
        "map-suggest" => import_ops::map_suggest(req),
        "zero-slice" => import_ops::zero_slice(req),
        "protocol-validate" => maybe_fail(protocol::protocol_validate(req)),
        "protocol-render" => protocol::protocol_render(req),
        "graph-validate" => maybe_fail(graph::graph_validate(req)),
        "graph-compile" => graph::graph_compile(req),
        "graph-typecheck" => maybe_fail(graph::graph_typecheck(req)),
        "spec-validate" => maybe_fail(spec::spec_validate(req)),
        "assemble" => assemble::assemble(req),
        "validate" => maybe_fail(assemble::validate(req)),
        "export" => export::export(req),
        "pack-diff" => update::pack_diff(req),
        "pack-update" => crate::pack_release::update_op(req),
        "pack-release-create" => crate::pack_release::create_op(req),
        "pack-release-verify" => maybe_fail(crate::pack_release::verify_op(req)),
        "pack-release-freeze" => crate::pack_release::freeze_op(req),
        "pack-merge" => update::pack_merge(req),
        "overlay-apply" => update::overlay_apply(req),
        "ccos-build-task" => ccos::ccos_build_task(req),
        "ccos-import-result" => ccos::ccos_import_result(req),
        "project-validate" => maybe_fail(project::project_validate(req)),
        "sdir-import" => crate::sdir::import_op(req),
        "layout-import" => crate::layout::layout_import_op(req),
        "sdir-validate" => maybe_fail(crate::sdir::validate_op(req)),
        "sdir-diff" => crate::sdir::diff_op(req),
        "sdir-merge" => maybe_fail(crate::sdir::merge_op(req)),
        "sdir-fuse" => maybe_fail(crate::sdir::fuse_op(req)),
        "sdir-repair" => crate::repair::repair_op(req),
        "claim-add" => crate::claim::claim_add_op(req),
        "claim-verify" => crate::claim::claim_verify_op(req),
        "budget-check" => crate::budget::budget_check_op(req),
        "migrate-plan" => crate::migration::migrate_plan_op(req),
        "migrate-apply" => crate::migration::migrate_apply_op(req),
        "audit-append" => crate::audit::audit_append_op(req),
        "audit-verify" => crate::audit::audit_verify_op(req),
        "trust-root-add" => crate::trust::trust_root_add_op(req),
        "trust-root-rotate" => crate::trust::trust_root_rotate_op(req),
        "trust-root-verify" => crate::trust::trust_root_verify_op(req),
        "trust-root-revoke" => crate::trust::trust_root_revoke_op(req),
        "report-fidelity" => crate::report_ops::fidelity_report_op(req),
        "report-a11y" => crate::report_ops::a11y_report_op(req),
        "extension-list" => crate::extension::extension_list_op(req),
        "extension-verify" => crate::extension::extension_verify_op(req),
        "extension-apply" => crate::extension::extension_apply_op(req),
        "preset-list" => crate::preset::preset_list_op(req),
        "preset-apply" => crate::preset::preset_apply_op(req),
        "portable-export" => crate::portable::portable_export_op(req),
        "portable-import" => crate::portable::portable_import_op(req),
        "portable-exit" => crate::portable::portable_exit_op(req),
        "build-plan" => crate::build::build_plan_op(req),
        "build-run" => crate::build::build_run_op(req),
        "build-incremental" => crate::build::build_incremental_op(req),
        "block-plan" => crate::build::block_plan_op(req),
        "block-incremental" => crate::build::block_incremental_op(req),
        "compose-run" => crate::compose::compose_op(req),
        "export-profile" => crate::build::export_profile_op(req),
        "export-accessible" => crate::build::export_accessible_op(req),
        "sdir-export" => crate::sdir_io::sdir_export_op(req),
        "sdir-load" => crate::sdir_io::sdir_load_op(req),
        "evidence-create" => crate::evidence::evidence_create_op(req),
        "evidence-verify" => maybe_fail(crate::evidence::evidence_verify_op(req)),
        "evidence-pack" => crate::evidence::evidence_pack_op(req),
        "evidence-verify-package" => maybe_fail(crate::evidence::evidence_verify_package_op(req)),
        "evidence-freeze" => crate::evidence::evidence_freeze_op(req),
        "evidence-keygen" => crate::evidence::evidence_keygen_op(req),
        "reuse-index" => crate::reuse::reuse_index_op(req),
        "reuse-impact" => crate::reuse::reuse_impact_op(req),
        "template-induce" => crate::template::induce_op(req),
        "schema-induce" => crate::template::induce_spec_op(req),
        "template-migrate" => crate::template::migrate_op(req),
        "plan-solve" => crate::solve::plan_solve_op(req),
        "plan-explain" => crate::solve::plan_explain_op(req),
        other => Err(usage(format!("未知 op {other}（见 app/docs/CLI.md §3）"))),
    };
    match outcome {
        Ok((1, report)) => report_envelope(report),
        Ok((exit, result)) => {
            if exit == 0 {
                Envelope::success(result)
            } else {
                Envelope {
                    ok: false,
                    exit,
                    result: Some(result),
                    error: None,
                }
            }
        }
        Err(err) => {
            if err.exit == 1 {
                let report = crate::report::failure_report(
                    "L0",
                    &Value::Null,
                    "unknown",
                    "$",
                    &err.code,
                    err.path.as_deref().unwrap_or("$"),
                    &err.message,
                );
                report_envelope(report)
            } else {
                Envelope::failure(&err, None)
            }
        }
    }
}

fn op_canonical(req: &Value) -> OpOutcome {
    let value = req_value(req, "value")?;
    let canonical = canonical_string(value)?;
    let digest = digest_value(value)?;
    Ok((0, serde_json::json!({"canonical": canonical, "digest": digest})))
}

/// 请求体解析（CLI/FFI 共用）：单次 JSON，UTF-8 无 BOM，大小/深度上限。
pub fn parse_request(bytes: &[u8]) -> Result<Value, CoreError> {
    let v = parse_json_bytes(bytes)?;
    if !v.is_object() {
        return Err(usage("请求体必须是 JSON object"));
    }
    Ok(v)
}

pub fn load_artifact_path(req: &Value, key: &str) -> Result<Value, CoreError> {
    let p = req_str(req, key)?;
    crate::fsutil::load_json_file(Path::new(&resolve_path(p)))
}
