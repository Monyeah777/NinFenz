//! 差分对账 / 报告 / schema（pyval · verify-report · schema-lint · schema-validate · density）。
//!
//! 自 `main.rs` 按命令族拆出：实现逐字搬运，逻辑与文案未改；分派仍在 `main.rs::run_inner`。

use crate::{asset_density, emit, jsonread, pyfloat, pyjson, require_dir, schema_lint, verify_report};
use std::path::PathBuf;
use std::process::ExitCode;

// ---------------------------------------------------------------- pyval 面

/// `nf-rs pyval reprf --in <位模式清单> --out <repr 清单>`：逐行读十六进制位模式，
/// 逐行写 `repr(float)`。用于与真源做**穷举式**浮点口径对账（见 `check_parity.ps1` 面 7）。
pub(crate) fn run_pyval(args: &[String]) -> Result<ExitCode, String> {
    let sub = args.first().map(|s| s.as_str()).ok_or("pyval 后缺子命令")?;
    if sub != "reprf" {
        return Err(format!("pyval 未知子命令：{}（修复指引：reprf）", sub));
    }
    let (input, out) = super::parse_in_out(
        args,
        "缺 --in（修复指引：给十六进制位模式清单，每行一个）",
    )?;
    let text = std::fs::read_to_string(&input)
        .map_err(|e| format!("读 {} 失败：{}", input.display(), e))?;
    let mut lines = String::new();
    for raw in text.lines() {
        let h = raw.trim();
        if h.is_empty() {
            continue;
        }
        let bits = u64::from_str_radix(h, 16)
            .map_err(|e| format!("位模式不是十六进制：{}（{}）", h, e))?;
        lines.push_str(&pyfloat::repr(f64::from_bits(bits)));
        lines.push('\n');
    }
    emit(lines.as_bytes(), &out)?;
    Ok(ExitCode::SUCCESS)
}

// ---------------------------------------------------------------- verify-report 面

/// `nf-rs verify-report --root <仓库根> [--results <json>] [--json] [--check] [--fresh] [--out <文件>]`。
///
/// `--results` 喂入**未移植**判据的 `(issues, warns, stats)`；本线自算 `schema` / `doc_markers` /
/// `baseline` / `self_stats` 四条。写面（`--write`）不实现。
pub(crate) fn run_verify_report(args: &[String]) -> Result<ExitCode, String> {
    let (root, results, out, check_mode) = parse_verify_report_args(args)?;
    require_dir(&root)?;
    let supplied = load_supplied(&results)?;

    let report = if check_mode {
        let (issues, live) = verify_report::check(&root, &supplied);
        eprintln!("  {}", verify_report::summary_line(&live));
        for x in &issues {
            eprintln!("  ✗ {}", x);
        }
        if !issues.is_empty() {
            emit(&verify_report::render(&live), &out)?;
            return Ok(ExitCode::from(1));
        }
        live
    } else {
        verify_report::build(&root, &supplied)
    };
    emit(&verify_report::render(&report), &out)?;
    Ok(ExitCode::SUCCESS)
}

/// 参数面：--root / --results / --out / --check|--fresh。
fn parse_verify_report_args(
    args: &[String],
) -> Result<(PathBuf, Option<PathBuf>, Option<PathBuf>, bool), String> {
    let mut root: Option<PathBuf> = None;
    let mut results: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut check_mode = false;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            "--results" => {
                i += 1;
                results = Some(PathBuf::from(args.get(i).ok_or("--results 后缺路径")?));
            }
            "--json" => {}
            "--check" | "--fresh" => check_mode = true,
            "--write" => {
                return Err("本线不实现 --write（写面仍在 Python 侧；修复指引：`python scripts/verify_report.py --write`）".into())
            }
            "--out" => {
                i += 1;
                out = Some(PathBuf::from(args.get(i).ok_or("--out 后缺路径")?));
            }
            other => return Err(format!("未知参数：{}", other)),
        }
        i += 1;
    }
    let root = root.ok_or("缺 --root（修复指引：传仓库根目录）")?;
    Ok((root, results, out, check_mode))
}

/// 喂入的未移植判据结果（--results）。
fn load_supplied(
    results: &Option<PathBuf>,
) -> Result<std::collections::HashMap<String, verify_report::Supplied>, String> {
    let mut supplied: std::collections::HashMap<String, verify_report::Supplied> =
        std::collections::HashMap::new();
    if let Some(p) = results {
        let text =
            std::fs::read_to_string(p).map_err(|e| format!("读 {} 失败：{}", p.display(), e))?;
        let v: serde_json::Value = serde_json::from_str(&text)
            .map_err(|e| format!("{} 不是合法 JSON：{}", p.display(), e))?;
        let to_strs = |x: Option<&serde_json::Value>| -> Vec<String> {
            x.and_then(|a| a.as_array())
                .map(|a| {
                    a.iter()
                        .map(|e| match e {
                            serde_json::Value::String(s) => s.clone(),
                            other => other.to_string(),
                        })
                        .collect()
                })
                .unwrap_or_default()
        };
        if let Some(obj) = v.as_object() {
            for (k, entry) in obj {
                let stats = entry
                    .get("stats")
                    .and_then(|s| jsonread::convert(s).ok())
                    .unwrap_or_else(|| pyjson::Json::Object(Vec::new()));
                supplied.insert(
                    k.clone(),
                    verify_report::Supplied {
                        issues: to_strs(entry.get("issues")),
                        warns: to_strs(entry.get("warns")),
                        stats,
                        status: entry
                            .get("status")
                            .and_then(|s| s.as_str())
                            .map(|s| s.to_string()),
                    },
                );
            }
        }
    }
    Ok(supplied)
}

// ---------------------------------------------------------------- schema 面

/// `nf-rs schema-lint --root <仓库根> [--json] [--out <文件>]`：
/// check28 协议件子集校验（真源无独立 CLI 面，对账走 `schema_lint.scan` 返回值的投影）。
pub(crate) fn run_schema_lint(args: &[String]) -> Result<ExitCode, String> {
    let mut root: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            "--json" => {}
            "--out" => {
                i += 1;
                out = Some(PathBuf::from(args.get(i).ok_or("--out 后缺路径")?));
            }
            other => return Err(format!("未知参数：{}", other)),
        }
        i += 1;
    }
    let root = root.ok_or("缺 --root（修复指引：传仓库根目录）")?;
    require_dir(&root)?;
    let (issues, s) = schema_lint::scan(&root);
    let doc = pyjson::Json::Object(vec![
        (
            "issues".to_string(),
            pyjson::Json::Array(
                issues
                    .iter()
                    .map(|x| pyjson::Json::Str(x.clone()))
                    .collect(),
            ),
        ),
        (
            "stats".to_string(),
            pyjson::Json::Object(vec![
                (
                    "schema_files".to_string(),
                    pyjson::Json::Int(s.schema_files as i64),
                ),
                (
                    "module_docs".to_string(),
                    pyjson::Json::Int(s.module_docs as i64),
                ),
                (
                    "contract_covered".to_string(),
                    pyjson::Json::Int(s.contract_covered as i64),
                ),
                (
                    "pipelines".to_string(),
                    pyjson::Json::Int(s.pipelines as i64),
                ),
                (
                    "protocols".to_string(),
                    pyjson::Json::Int(s.protocols as i64),
                ),
                (
                    "asset_entries".to_string(),
                    pyjson::Json::Int(s.asset_entries as i64),
                ),
            ]),
        ),
    ]);
    emit(doc.dumps_file().as_bytes(), &out)?;
    Ok(ExitCode::SUCCESS)
}

/// `nf-rs schema-validate --schema <schema.json> --instance <instance.json> [--out <文件>]`：
/// **差分校验入口**。check28 在真仓库是全绿的（0 issues），只靠对账**抓不到校验器自身的 bug**；
/// 本入口让两侧在同一批合成 (instance, schema) 上逐条比对消息（同 `pyval reprf` 的路数）。
pub(crate) fn run_schema_validate(args: &[String]) -> Result<ExitCode, String> {
    let mut schema_p: Option<PathBuf> = None;
    let mut instance_p: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--schema" => {
                i += 1;
                schema_p = Some(PathBuf::from(args.get(i).ok_or("--schema 后缺路径")?));
            }
            "--instance" => {
                i += 1;
                instance_p = Some(PathBuf::from(args.get(i).ok_or("--instance 后缺路径")?));
            }
            "--out" => {
                i += 1;
                out = Some(PathBuf::from(args.get(i).ok_or("--out 后缺路径")?));
            }
            other => return Err(format!("未知参数：{}", other)),
        }
        i += 1;
    }
    let s_path = schema_p.ok_or("缺 --schema")?;
    let i_path = instance_p.ok_or("缺 --instance")?;
    let s_raw: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(&s_path)
            .map_err(|e| format!("读 {} 失败：{}", s_path.display(), e))?,
    )
    .map_err(|e| format!("schema 不是合法 JSON：{}", e))?;
    let i_raw: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(&i_path)
            .map_err(|e| format!("读 {} 失败：{}", i_path.display(), e))?,
    )
    .map_err(|e| format!("instance 不是合法 JSON：{}", e))?;
    let schema = jsonread::convert(&s_raw).map_err(|e| e.to_string())?;
    let instance = jsonread::convert(&i_raw).map_err(|e| e.to_string())?;
    let msgs = schema_lint::subset_validate(&instance, &schema, "instance");
    let doc = pyjson::Json::Object(vec![(
        "messages".to_string(),
        pyjson::Json::Array(msgs.iter().map(|m| pyjson::Json::Str(m.clone())).collect()),
    )]);
    emit(doc.dumps_file().as_bytes(), &out)?;
    Ok(ExitCode::SUCCESS)
}

// ---------------------------------------------------------------- density / score 面

/// `nf-rs density --root <仓库根> [--json] [--out <文件>]`：资产密度扫描。
/// 真源无独立 CLI 面，故对账走 `asset_density.scan` 返回值的投影（见 `check_parity.ps1` 面 8）。
pub(crate) fn run_density(args: &[String]) -> Result<ExitCode, String> {
    let mut root: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            "--json" => {}
            "--out" => {
                i += 1;
                out = Some(PathBuf::from(args.get(i).ok_or("--out 后缺路径")?));
            }
            other => return Err(format!("未知参数：{}", other)),
        }
        i += 1;
    }
    let root = root.ok_or("缺 --root（修复指引：传仓库根目录）")?;
    require_dir(&root)?;
    let (issues, s) = asset_density::scan(&root);
    let doc = pyjson::Json::Object(vec![
        (
            "issues".to_string(),
            pyjson::Json::Array(
                issues
                    .iter()
                    .map(|x| pyjson::Json::Str(x.clone()))
                    .collect(),
            ),
        ),
        (
            "stats".to_string(),
            pyjson::Json::Object(vec![
                ("files".to_string(), pyjson::Json::Int(s.files as i64)),
                ("keys".to_string(), pyjson::Json::Int(s.keys as i64)),
                ("unkeyed".to_string(), pyjson::Json::Int(s.unkeyed as i64)),
                ("tiny".to_string(), pyjson::Json::Int(s.tiny as i64)),
                (
                    "avg_keys_per_file".to_string(),
                    pyjson::Json::Float(s.avg_keys_per_file),
                ),
            ]),
        ),
    ]);
    emit(doc.dumps_file().as_bytes(), &out)?;
    Ok(ExitCode::SUCCESS)
}

