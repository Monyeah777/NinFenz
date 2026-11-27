//! 纵深 / 度量 / 纯度 / 回执 / 统计 / 单契约（depth-scan · code-metrics · purity · receipts · stats · conformance contract）。
//!
//! 自 `main.rs` 按命令族拆出：实现逐字搬运，逻辑与文案未改；分派仍在 `main.rs::run_inner`。

use super::{parse_root_json_out, RootJsonOut};
use crate::{emit, conformance, contracts, jsonread, pyjson, quality_depth_scan, receipts, require_dir, stats};
use std::path::PathBuf;
use std::process::ExitCode;

// ---------------------------------------------------------------- 纵深汇总面

/// `quality_depth_scan.scan` 的入口：导出 `{issues, stats}`（13 个子扫描器 + 4 个后置项）。
///
/// 这也是那批子扫描器的**生产消费者**——没有它，它们的 `scan` 只有测试引用
/// （同行常驻判据 `test_rust_module_wiring` 会当场判 FAIL）。
pub(crate) fn run_depth_scan(args: &[String]) -> Result<ExitCode, String> {
    let mut root = std::path::PathBuf::from(".");
    let mut out: Option<String> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                root = std::path::PathBuf::from(args.get(i + 1).ok_or("--root 后缺值")?);
                i += 2;
            }
            "--out" => {
                out = Some(args.get(i + 1).ok_or("--out 后缺值")?.clone());
                i += 2;
            }
            other => return Err(format!("未知参数：{}", other)),
        }
    }
    let (issues, stats) = quality_depth_scan::scan(&root);
    let doc = pyjson::Json::Object(vec![
        (
            "issues".to_string(),
            pyjson::Json::Array(
                issues
                    .iter()
                    .map(|s| pyjson::Json::Str(s.clone()))
                    .collect(),
            ),
        ),
        ("stats".to_string(), stats),
    ]);
    let text = doc.dumps_file();
    // 统一走 emit：CLI 写 stdout/文件，常驻 worker 写捕获缓冲（print! 绕过捕获会返回空字节）。
    emit(text.as_bytes(), &out.map(PathBuf::from))?;
    if issues.is_empty() {
        Ok(ExitCode::SUCCESS)
    } else {
        Ok(ExitCode::from(1))
    }
}

// ---------------------------------------------------------------- code-metrics 面

/// `code_metrics.scan` 的**差分对账入口**：导出 `{issues, warns, stats}`。
pub(crate) fn run_code_metrics(args: &[String]) -> Result<ExitCode, String> {
    let mut root = std::path::PathBuf::from(".");
    let mut out: Option<String> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                root = std::path::PathBuf::from(args.get(i + 1).ok_or("--root 后缺值")?);
                i += 2;
            }
            "--out" => {
                out = Some(args.get(i + 1).ok_or("--out 后缺值")?.clone());
                i += 2;
            }
            other => return Err(format!("未知参数：{}", other)),
        }
    }
    let (issues, warns, stats) = crate::code_metrics::scan(&root);
    let arr = |v: Vec<String>| {
        crate::pyjson::Json::Array(v.into_iter().map(crate::pyjson::Json::Str).collect())
    };
    let doc = crate::pyjson::Json::Object(vec![
        ("issues".to_string(), arr(issues)),
        ("warns".to_string(), arr(warns)),
        ("stats".to_string(), stats),
    ]);
    let bytes = doc.dumps_file().into_bytes();
    emit(&bytes, &out.map(PathBuf::from))?;
    Ok(ExitCode::SUCCESS)
}

// ---------------------------------------------------------------- purity-scan 面

/// `purity_scan.scan` 的**差分对账入口**：导出 `{issues, stats}`（`sort_keys` 规范化），
/// 供与真源背靠背比对。判据面本身经 `verify-report` 的 `purity` 判据落地。
pub(crate) fn run_purity_scan(args: &[String]) -> Result<ExitCode, String> {
    let mut root = std::path::PathBuf::from(".");
    let mut out: Option<String> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                root = std::path::PathBuf::from(args.get(i + 1).ok_or("--root 后缺值")?);
                i += 2;
            }
            "--out" => {
                out = Some(args.get(i + 1).ok_or("--out 后缺值")?.clone());
                i += 2;
            }
            other => return Err(format!("未知参数：{}", other)),
        }
    }
    let (issues, stats) = crate::purity::scan(&root);
    let doc = crate::pyjson::Json::Object(vec![
        (
            "issues".to_string(),
            crate::pyjson::Json::Array(issues.into_iter().map(crate::pyjson::Json::Str).collect()),
        ),
        ("stats".to_string(), stats),
    ]);
    // 落盘走 `dumps_file`（带尾换行），与真源侧 json.dumps(...) + "\n" 同形
    let bytes = doc.dumps_file().into_bytes();
    emit(&bytes, &out.map(PathBuf::from))?;
    Ok(ExitCode::SUCCESS)
}

// ---------------------------------------------------------------- purity-facts 面

/// AST 事实的**差分对账入口**：把 `purity_scan._ast_facts` 的等价结果导成 JSON，
/// 供与真源**逐文件**背靠背比对。**不是**判据面的一部分，只为把最高风险的一段
/// （BFS 遍历序 + 调用目标名重建）单独钉住。
pub(crate) fn run_purity_facts(args: &[String]) -> Result<ExitCode, String> {
    let mut root = std::path::PathBuf::from(".");
    let mut out: Option<String> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                root = std::path::PathBuf::from(args.get(i + 1).ok_or("--root 后缺值")?);
                i += 2;
            }
            "--out" => {
                out = Some(args.get(i + 1).ok_or("--out 后缺值")?.clone());
                i += 2;
            }
            other => return Err(format!("未知参数：{}", other)),
        }
    }
    let doc = crate::pyast::facts_dump(&root);
    let bytes = doc.dumps().into_bytes();
    emit(&bytes, &out.map(PathBuf::from))?;
    Ok(ExitCode::SUCCESS)
}

// ---------------------------------------------------------------- receipts 面

pub(crate) fn run_receipts(args: &[String]) -> Result<ExitCode, String> {
    let sub = args
        .first()
        .map(|s| s.as_str())
        .ok_or("receipts 后缺子命令")?;
    let mut root: Option<PathBuf> = None;
    let mut scope = "protocol".to_string();
    let mut out: Option<PathBuf> = None;
    let mut json = false;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            "--scope" => {
                i += 1;
                scope = args.get(i).ok_or("--scope 后缺值")?.clone();
            }
            "--out" => {
                i += 1;
                out = Some(PathBuf::from(args.get(i).ok_or("--out 后缺路径")?));
            }
            "--json" => json = true,
            other => return Err(format!("未知参数：{}", other)),
        }
        i += 1;
    }
    let root = root.ok_or("缺 --root（修复指引：传仓库根目录）")?;
    require_dir(&root)?;

    match sub {
        "subjects" => {
            let mut s = String::new();
            for rel in receipts::protocol_subjects(&root) {
                s.push_str(&rel);
                s.push('\n');
            }
            emit(s.as_bytes(), &out)?;
            Ok(ExitCode::SUCCESS)
        }
        "build" => {
            emit(&receipts::build_scope_bytes(&root, &scope), &out)?;
            Ok(ExitCode::SUCCESS)
        }
        "selfcheck" => {
            let issues = receipts::self_check(&root, &scope);
            for i in &issues {
                eprintln!("[FAIL] {}", i);
            }
            if issues.is_empty() {
                Ok(ExitCode::SUCCESS)
            } else {
                Ok(ExitCode::from(1))
            }
        }
        // `nf receipts --json` 的同形物：在盘回执 == 实时重算（根 + 逐件摘要 + 包含证明）。
        "verify" => {
            if !json {
                return Err("本线只实现 receipts verify --json（修复指引：加 --json）".into());
            }
            let p = root.join("protocol/RECEIPTS.json");
            let raw = std::fs::read_to_string(&p)
                .map_err(|e| format!("读 {} 失败：{}", p.display(), e))?;
            let v: serde_json::Value = serde_json::from_str(&raw)
                .map_err(|e| format!("{} 不是合法 JSON：{}", p.display(), e))?;
            let doc =
                jsonread::convert(&v).map_err(|e| format!("{} 转换失败：{}", p.display(), e))?;
            let (issues, stats) = receipts::verify_scope(&doc, &root);
            let out_doc = pyjson::Json::Object(vec![
                (
                    "kind".to_string(),
                    pyjson::Json::Str("receipts".to_string()),
                ),
                (
                    "issues".to_string(),
                    pyjson::Json::Array(
                        issues
                            .iter()
                            .map(|s| pyjson::Json::Str(s.clone()))
                            .collect(),
                    ),
                ),
                ("stats".to_string(), stats),
            ]);
            emit(out_doc.dumps_file().as_bytes(), &out)?;
            if issues.is_empty() {
                Ok(ExitCode::SUCCESS)
            } else {
                Ok(ExitCode::from(1))
            }
        }
        other => Err(format!("receipts 未知子命令：{}", other)),
    }
}

// ---------------------------------------------------------------- stats 面

pub(crate) fn run_stats(args: &[String]) -> Result<ExitCode, String> {
    let RootJsonOut { root, json, out } = parse_root_json_out(args)?;

    let (issues, st) = stats::check(&root);
    if json {
        emit(st.to_json().dumps_file().as_bytes(), &out)?;
    } else {
        let mut s = String::new();
        s.push_str("== nf stats（自述数字实算 · 真源 protocol/repo_stats.json）==\n");
        s.push_str(&format!(
            "  官方核心：模块 {} · 管线 {}\n",
            st.core_modules,
            if st.core_pipelines.is_empty() {
                String::new()
            } else {
                st.core_pipelines.join(" / ")
            }
        ));
        s.push_str(&format!(
            "  社区规模：登记包 {} · 资产档 {} · 概念图 {} · 域包 {}/{} 细分\n",
            st.registered_packs,
            st.pack_assets,
            st.concept_graphs,
            st.domain_packs,
            st.subdivisions_total
        ));
        s.push_str(&format!(
            "  标准目录：{} 条（可达 {} / 不可达 {} · 机构 {} · {} 边） · 绑定 {} 条\n",
            st.standards_total,
            st.standards_reachable,
            st.standards_unreachable,
            st.standards_bodies,
            st.standards_edges,
            st.standard_bindings
        ));
        s.push_str(&format!(
            "  质量凭证：verify check1-{} 常驻（脚本 v{}） · 馆藏 {} 件\n",
            st.verify_checks, st.verify_version, st.library_items
        ));
        s.push_str("  模式：check（只校验）\n");
        emit(s.as_bytes(), &out)?;
    }
    for i in &issues {
        eprintln!("  [FAIL] {}", i);
    }
    if issues.is_empty() {
        Ok(ExitCode::SUCCESS)
    } else {
        Ok(ExitCode::from(1))
    }
}

/// 单条已移植契约 → 与真源同形的行对象（`{id, ok, detail, description, digest}`）。
pub(crate) fn run_conformance_contract(args: &[String]) -> Result<ExitCode, String> {
    let id = args.first().filter(|a| !a.starts_with("--")).ok_or(
        "contract 后缺契约 id（修复指引：如 st-quality；未移植的 id 会显式报错而非伪造结论）",
    )?;
    let mut root: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
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
    require_dir(&root)?;

    let Some((ok, detail)) = contracts::run(id, &root) else {
        return Err(format!(
            "契约 {} 未移植（修复指引：见 engine/rust/README.md「覆盖现状」；本线对未移植项显式缺席，不伪造空结论）",
            id
        ));
    };
    let row = conformance::Row {
        id: id.to_string(),
        ok,
        detail,
        description: contracts::description(id).unwrap_or("").to_string(),
        recorded_digest: None,
    };
    emit(conformance::row_json(&row).dumps_file().as_bytes(), &out)?;
    if ok {
        Ok(ExitCode::SUCCESS)
    } else {
        Ok(ExitCode::from(1))
    }
}
