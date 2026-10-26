//! `nf-rs` —— NF 只读快线的可执行入口。
//!
//! **边界（与 .NET 线同纪律，见 decisions/ADR-0005.md）**：只读判据面，**不写盘**。
//! 本工具输出字节，由调用方决定落哪；任何 `--write` 类语义一律不实现——真源仍在 Python 侧。
//!
//! 用法：
//!   nf-rs receipts build     --root <仓库根> [--scope protocol] [--out <文件>]
//!   nf-rs receipts subjects  --root <仓库根> [--out <文件>]
//!   nf-rs receipts selfcheck --root <仓库根> [--scope protocol]
//!   nf-rs stats              --root <仓库根> [--json] [--out <文件>]
//!   nf-rs purity-facts       --root <仓库根> [--out <文件>]
//!   nf-rs purity-scan        --root <仓库根> [--out <文件>]
//!   nf-rs code-metrics       --root <仓库根> [--out <文件>]
//!   nf-rs conformance seal   --in <裁决行.json> [--out <文件>]
//!   nf-rs layers             --root <仓库根> --verify [--json] [--out <文件>]

mod asset_code;
mod asset_contract;
mod asset_density;
mod asset_ledger_projection;
mod audit;
mod baseline;
mod concept_graph;
mod conformance;
mod conformance_scan;

mod code_metrics;
mod contracts;
mod coupling_metrics;
mod decisions;
mod declaration;
mod depth_small;
mod doc_hygiene;
mod doc_tables;
mod domain_metrics;
mod domain_pack;
mod drill_fidelity;
mod endpoint;
mod glob;
mod handover;
mod instruction_step_audit;
mod intake;
mod io_types;
mod json_schema;
mod jsonmini;
mod jsonread;
mod judgement_coverage;
mod key_naming;
mod knowledge;
mod layers;
mod library;
mod library_entries;
mod license_gate;
mod machine_contract;
mod mcp_package;
mod mcp_tables;
mod mdblocks;
mod merkle;
mod miniyaml;
mod modeling;
mod module_signature;
mod output_forms;
mod output_forms_checks;
mod output_forms_gen;
mod output_forms_verify;
mod output_tables;
mod pack_combo;
mod pack_combo_core;
mod paths;
mod patterns;
mod payload_harvest;
mod payload_registry;
mod pipeline_loader;
mod pipelinerun;
mod postmortem;
mod public_surface;
mod purity;
mod py_stdlib;
mod pyast;
mod pyconsts;
mod pyfloat;
mod pyjson;
mod pyrandom;
mod pysrc;
mod pyval;
mod quality_depth_scan;
mod quant_metrics;
mod rating_gate;
mod receipts;
mod receipts_verify;
mod registry_cross;
mod repo_paths;
mod schema_lint;
mod score;
mod verify_report;
mod workflow_policy;
mod world_model;
mod xmlmini;

mod serve;
mod stats;
#[cfg(test)]
mod testutil;

use std::io::Write;
use std::path::PathBuf;
use std::process::ExitCode;
use std::sync::Mutex;

const USAGE: &str = "\
nf-rs —— NF 只读快线（与 Python 真源逐字节对账）

用法：
  nf-rs receipts build     --root <仓库根> [--scope <名>] [--out <文件>]
  nf-rs receipts subjects  --root <仓库根> [--out <文件>]
  nf-rs receipts selfcheck --root <仓库根> [--scope <名>]
  nf-rs stats              --root <仓库根> [--json] [--out <文件>]
  nf-rs conformance seal   --in <裁决行.json> [--out <文件>]

说明：
  --out 缺省写标准输出（**原始字节**，不经任何换行转换）。
  receipts build 的输出与 Python 真源 write_scope 的落盘字节相同（LF、末尾换行、无 BOM）。
  stats 与 `nf stats --json` 同形；退出码同真源（有 issue ⇔ 1）。
  conformance seal 只做「契约裁决 → 封缄报告」；27 条契约的扫描实现未移植。
";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match run(&args) {
        Ok(code) => code,
        Err(msg) => {
            eprintln!("nf-rs: {}", msg);
            ExitCode::from(2)
        }
    }
}

/// 常驻 worker 的 stdout 捕获缓冲（仅 `serve` 模式置位；CLI 模式恒为 None）。
///
/// 这是「零分叉面逻辑」的关键：worker 复用 `run()` 整段分派，只把 stdout 从真实流换成
/// 内存缓冲。任何新增只读面自动可被 worker 服务，字节一致性天然继承。
static STDOUT_CAPTURE: Mutex<Option<Vec<u8>>> = Mutex::new(None);
/// 并发连接共享同一捕获缓冲/全局缓存 ⇒ 判据执行串行（确定性优先，仅网络等待可并发）。
static RUN_LOCK: Mutex<()> = Mutex::new(());
/// worker 捕获缓冲复用池（容量上限 4 MiB；大输出不复用，避免常驻膨胀）。
static REUSE_BUF: Mutex<Vec<u8>> = Mutex::new(Vec::new());
const REUSE_BUF_CAP: usize = 4 * 1024 * 1024;

fn emit(bytes: &[u8], out: &Option<PathBuf>) -> Result<(), String> {
    match out {
        Some(p) => std::fs::write(p, bytes).map_err(|e| format!("写 {} 失败：{}", p.display(), e)),
        None => {
            let mut cap = STDOUT_CAPTURE.lock().unwrap_or_else(|e| e.into_inner());
            if let Some(buf) = cap.as_mut() {
                buf.extend_from_slice(bytes);
                return Ok(());
            }
            drop(cap);
            let stdout = std::io::stdout();
            let mut lock = stdout.lock();
            lock.write_all(bytes)
                .map_err(|e| format!("写标准输出失败：{}", e))?;
            lock.flush().map_err(|e| format!("刷新标准输出失败：{}", e))
        }
    }
}

/// 在捕获模式下跑一遍 `run()`，取回 stdout 字节与退出码。
///
/// 只给常驻 worker（`serve`）用：CLI 正常路径的 `emit` 仍走真实 stdout（捕获恒为 None）。
/// 退出码口径与 `run()` 一致：`Err` 折算 2（与 `main` 的兜底同款）。
pub(crate) fn run_capture(args: &[String]) -> (Vec<u8>, i32) {
    let _run_guard = RUN_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let mut reused = {
        let mut slot = REUSE_BUF.lock().unwrap_or_else(|e| e.into_inner());
        std::mem::take(&mut *slot)
    };
    reused.clear();
    {
        let mut cap = STDOUT_CAPTURE.lock().unwrap_or_else(|e| e.into_inner());
        *cap = Some(reused);
    }
    let code = match run(args) {
        // `ExitCode` 的数值面在稳定 Rust 里不可读回，故用「是否 SUCCESS」还原：
        // 本线 faces 只产 SUCCESS(0) 或 from(1)（有 issue）；usage 错误走 Err（main 折算 2）。
        Ok(c) => {
            if c == ExitCode::SUCCESS {
                0
            } else {
                1
            }
        }
        Err(msg) => {
            eprintln!("nf-rs: {}", msg);
            2
        }
    };
    let out = {
        let mut cap = STDOUT_CAPTURE.lock().unwrap_or_else(|e| e.into_inner());
        cap.take().unwrap_or_default()
    };
    (out, code)
}

/// 把捕获缓冲交回复用池（仅保留 ≤ 4 MiB 容量）。
pub(crate) fn recycle_capture_buf(mut buf: Vec<u8>) {
    if buf.capacity() > REUSE_BUF_CAP {
        return;
    }
    buf.clear();
    let mut slot = REUSE_BUF.lock().unwrap_or_else(|e| e.into_inner());
    if slot.capacity() < buf.capacity() {
        *slot = buf;
    }
}

fn require_dir(root: &PathBuf) -> Result<(), String> {
    if root.is_dir() {
        Ok(())
    } else {
        Err(format!("--root 不是目录：{}", root.display()))
    }
}

fn run(args: &[String]) -> Result<ExitCode, String> {
    // 一次命令/请求内共享 glob 缓存：27 契约、多面扫描不再各自重枚举目录。
    glob::begin_request_cache();
    let result = run_inner(args);
    glob::end_request_cache();
    result
}

fn run_inner(args: &[String]) -> Result<ExitCode, String> {
    if args.is_empty() || args[0] == "--help" || args[0] == "-h" {
        print!("{}", USAGE);
        return Ok(ExitCode::SUCCESS);
    }
    if args[0] == "--version" {
        println!("nf-rs {}", env!("CARGO_PKG_VERSION"));
        return Ok(ExitCode::SUCCESS);
    }
    match args[0].as_str() {
        "receipts" => run_receipts(&args[1..]),
        "stats" => run_stats(&args[1..]),
        "purity-facts" => run_purity_facts(&args[1..]),
        "purity-scan" => run_purity_scan(&args[1..]),
        "code-metrics" => run_code_metrics(&args[1..]),
        "conformance" => run_conformance(&args[1..]),
        "density" => run_density(&args[1..]),
        "depth-scan" => run_depth_scan(&args[1..]),
        "layers" => run_layers(&args[1..]),
        "schema-lint" => run_schema_lint(&args[1..]),
        "schema-validate" => run_schema_validate(&args[1..]),
        "score" => run_score(&args[1..]),
        "verify-report" => run_verify_report(&args[1..]),
        "pyval" => run_pyval(&args[1..]),
        "serve" => crate::serve::run_serve(&args[1..]),
        other => Err(format!("未知命令：{}（修复指引：nf-rs --help）", other)),
    }
}

// ---------------------------------------------------------------- 纵深汇总面

/// `quality_depth_scan.scan` 的入口：导出 `{issues, stats}`（13 个子扫描器 + 4 个后置项）。
///
/// 这也是那批子扫描器的**生产消费者**——没有它，它们的 `scan` 只有测试引用
/// （同行常驻判据 `test_rust_module_wiring` 会当场判 FAIL）。
fn run_depth_scan(args: &[String]) -> Result<ExitCode, String> {
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
fn run_code_metrics(args: &[String]) -> Result<ExitCode, String> {
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
fn run_purity_scan(args: &[String]) -> Result<ExitCode, String> {
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
fn run_purity_facts(args: &[String]) -> Result<ExitCode, String> {
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

fn run_receipts(args: &[String]) -> Result<ExitCode, String> {
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

fn run_stats(args: &[String]) -> Result<ExitCode, String> {
    let mut root: Option<PathBuf> = None;
    let mut json = false;
    let mut out: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            "--json" => json = true,
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
fn run_conformance_contract(args: &[String]) -> Result<ExitCode, String> {
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

// ---------------------------------------------------------------- pyval 面

/// `nf-rs pyval reprf --in <位模式清单> --out <repr 清单>`：逐行读十六进制位模式，
/// 逐行写 `repr(float)`。用于与真源做**穷举式**浮点口径对账（见 `check_parity.ps1` 面 7）。
fn run_pyval(args: &[String]) -> Result<ExitCode, String> {
    let sub = args.first().map(|s| s.as_str()).ok_or("pyval 后缺子命令")?;
    if sub != "reprf" {
        return Err(format!("pyval 未知子命令：{}（修复指引：reprf）", sub));
    }
    let mut input: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--in" => {
                i += 1;
                input = Some(PathBuf::from(args.get(i).ok_or("--in 后缺路径")?));
            }
            "--out" => {
                i += 1;
                out = Some(PathBuf::from(args.get(i).ok_or("--out 后缺路径")?));
            }
            other => return Err(format!("未知参数：{}", other)),
        }
        i += 1;
    }
    let input = input.ok_or("缺 --in（修复指引：给十六进制位模式清单，每行一个）")?;
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
fn run_verify_report(args: &[String]) -> Result<ExitCode, String> {
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
    require_dir(&root)?;

    let mut supplied: std::collections::HashMap<String, verify_report::Supplied> =
        std::collections::HashMap::new();
    if let Some(p) = &results {
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

// ---------------------------------------------------------------- schema 面

/// `nf-rs schema-lint --root <仓库根> [--json] [--out <文件>]`：
/// check28 协议件子集校验（真源无独立 CLI 面，对账走 `schema_lint.scan` 返回值的投影）。
fn run_schema_lint(args: &[String]) -> Result<ExitCode, String> {
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
fn run_schema_validate(args: &[String]) -> Result<ExitCode, String> {
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
fn run_density(args: &[String]) -> Result<ExitCode, String> {
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

/// `nf-rs score --root <仓库根> --signals <json> [--baseline <rel>] [--tolerance <f>]
/// [--exceptions <json>] [--json] [--out <文件>]`。
///
/// `--signals` 提供**尚未移植**的 4 个扫描器计数；缺键 = 扫描器不可用（真源 `_count` 的哨兵语义）。
fn run_score(args: &[String]) -> Result<ExitCode, String> {
    let mut root: Option<PathBuf> = None;
    let mut signals: Option<PathBuf> = None;
    let mut baseline_rel: Option<String> = None;
    let mut exceptions_path: Option<PathBuf> = None;
    let mut tolerance = 0.0f64;
    let mut out: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            "--signals" => {
                i += 1;
                signals = Some(PathBuf::from(args.get(i).ok_or("--signals 后缺路径")?));
            }
            "--baseline" => {
                i += 1;
                baseline_rel = Some(args.get(i).ok_or("--baseline 后缺值")?.clone());
            }
            "--exceptions" => {
                i += 1;
                exceptions_path =
                    Some(PathBuf::from(args.get(i).ok_or("--exceptions 后缺路径")?));
            }
            "--tolerance" => {
                i += 1;
                tolerance = args
                    .get(i)
                    .ok_or("--tolerance 后缺值")?
                    .parse::<f64>()
                    .map_err(|e| format!("--tolerance 不是数字：{}", e))?;
            }
            "--json" => {}
            "--write-baseline" => {
                return Err("本线不实现 --write-baseline（写面仍在 Python 侧；修复指引：`python scripts/nf.py score --write-baseline`）".into())
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

    let sup = match &signals {
        Some(p) => {
            let text = std::fs::read_to_string(p)
                .map_err(|e| format!("读 {} 失败：{}", p.display(), e))?;
            let v: serde_json::Value = serde_json::from_str(&text)
                .map_err(|e| format!("{} 不是合法 JSON：{}", p.display(), e))?;
            let n = |k: &str| v.get(k).and_then(|x| x.as_i64());
            score::Supplied {
                depth_clean: n("depth_clean"),
            }
        }
        None => score::Supplied::default(),
    };

    let current = score::evaluate(&root, &sup);

    let base_rel = baseline_rel.unwrap_or_else(|| score::DEFAULT_BASELINE.to_string());
    let base_path = if PathBuf::from(&base_rel).is_absolute() {
        PathBuf::from(&base_rel)
    } else {
        root.join(&base_rel)
    };
    let baseline = if base_path.is_file() {
        let text = std::fs::read_to_string(&base_path)
            .map_err(|e| format!("读 {} 失败：{}", base_path.display(), e))?;
        let raw: serde_json::Value =
            serde_json::from_str(&text).map_err(|e| format!("基线不是合法 JSON：{}", e))?;
        jsonread::convert(&raw).map_err(|e| format!("基线含不支持的值：{}", e))?
    } else {
        pyjson::Json::Object(vec![(
            "schema".to_string(),
            pyjson::Json::Str(score::SCHEMA.to_string()),
        )])
    };

    let exceptions: Vec<(String, String)> = match &exceptions_path {
        Some(p) => {
            let text = std::fs::read_to_string(p)
                .map_err(|e| format!("读 {} 失败：{}", p.display(), e))?;
            let v: serde_json::Value =
                serde_json::from_str(&text).map_err(|e| format!("例外表不是合法 JSON：{}", e))?;
            v.as_array()
                .map(|a| {
                    a.iter()
                        .filter_map(|e| {
                            let s = e.get("signal").and_then(|x| x.as_str())?;
                            let r = e.get("reason").and_then(|x| x.as_str()).unwrap_or("");
                            Some((s.to_string(), r.to_string()))
                        })
                        .collect()
                })
                .unwrap_or_default()
        }
        None => Vec::new(),
    };

    emit(
        &score::render_bytes(&current, &baseline, tolerance, &exceptions),
        &out,
    )?;
    if score::is_ok(&current, &baseline, tolerance, &exceptions) {
        Ok(ExitCode::SUCCESS)
    } else {
        Ok(ExitCode::from(1))
    }
}

// ---------------------------------------------------------------- layers 面

/// `nf layers --verify`（阶梯体检）。**只读**：`--write`（刷新 docs/layers.md 生成区）不实现。
fn run_layers(args: &[String]) -> Result<ExitCode, String> {
    let mut root: Option<PathBuf> = None;
    let mut verify = false;
    let mut json = false;
    let mut out: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            "--verify" => verify = true,
            "--json" => json = true,
            "--write" => {
                return Err(
                    "本线不实现 --write（写面仍在 Python 侧；修复指引：`python scripts/nf.py layers --write`）"
                        .into(),
                )
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
    if !verify {
        return Err(
            "本线只实现 --verify（修复指引：nf-rs layers --root <仓库根> --verify）".into(),
        );
    }

    let (issues, stats) = layers::scan(&root);
    if json {
        // 与真源同一条合成路径：这里直接复用 verify_bytes 的构造，避免两份输出口径
        emit(&layers::verify_bytes(&root), &out)?;
    } else {
        let mut s = String::new();
        s.push_str("== nf layers --verify（阶梯体检 · 与 verify check27 R7 同源）==\n");
        for i in &issues {
            s.push_str(&format!("  [FAIL] {}\n", i));
        }
        s.push_str(&format!(
            "  阶 {} · 资产子级 {} · 入口面 {} · 纵切件 {} · 规则 {} → {}\n",
            int_field(&stats, "tiers"),
            int_field(&stats, "asset_levels"),
            int_field(&stats, "surfaces"),
            int_field(&stats, "crosscut"),
            int_field(&stats, "rules"),
            if issues.is_empty() {
                "通过".to_string()
            } else {
                format!("FAIL {}", issues.len())
            }
        ));
        emit(s.as_bytes(), &out)?;
    }
    if issues.is_empty() {
        Ok(ExitCode::SUCCESS)
    } else {
        Ok(ExitCode::from(1))
    }
}

fn int_field(j: &pyjson::Json, k: &str) -> i64 {
    match pyval::get(j, k) {
        Some(pyjson::Json::Int(i)) => *i,
        _ => 0,
    }
}

// ---------------------------------------------------------------- conformance 封缄内核

/// 裁决行 → 封缄报告。输入可以是**契约行数组**，也可以是含 `contracts` 的真源报告对象；
/// 行内若自带 `digest` 则顺带做差分核对（**不信任输入摘要**）。
/// `nf-rs conformance run --root <仓库根> --json [--out <文件>]`：
/// 全量实时重算 27 条契约 → 封缄报告 + 与在盘报告比对（真源 `nf conformance --json` 的同形物）。
/// 人类可读面留在 Python 真源；本线只服务机器面（`--json`）。
fn run_conformance_run(args: &[String]) -> Result<ExitCode, String> {
    let mut root: Option<PathBuf> = None;
    let mut json = false;
    let mut out: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            "--json" => json = true,
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
    if !json {
        return Err(
            "本线只实现 --json（修复指引：nf-rs conformance run --root <根> --json）".into(),
        );
    }
    let live = conformance::run_live(&root);
    let (issues, _stats) = conformance::verify_committed_with(&root, &live);
    let ok_verdict = match pyval::get(&live, "verdict") {
        Some(pyjson::Json::Str(s)) => s == "conformant",
        _ => false,
    };
    let doc = pyjson::Json::Object(vec![
        (
            "kind".to_string(),
            pyjson::Json::Str("conformance".to_string()),
        ),
        ("report".to_string(), live),
        (
            "issues".to_string(),
            pyjson::Json::Array(
                issues
                    .iter()
                    .map(|s| pyjson::Json::Str(s.clone()))
                    .collect(),
            ),
        ),
    ]);
    emit(doc.dumps_file().as_bytes(), &out)?;
    if issues.is_empty() && ok_verdict {
        Ok(ExitCode::SUCCESS)
    } else {
        Ok(ExitCode::from(1))
    }
}

fn run_conformance(args: &[String]) -> Result<ExitCode, String> {
    let sub = args
        .first()
        .map(|s| s.as_str())
        .ok_or("conformance 后缺子命令")?;
    if sub == "run" {
        return run_conformance_run(&args[1..]);
    }
    if sub == "contract" {
        return run_conformance_contract(&args[1..]);
    }
    if sub == "list" {
        let mut s = String::new();
        for id in contracts::PORTED {
            s.push_str(id);
            s.push('\n');
        }
        emit(s.as_bytes(), &None)?;
        return Ok(ExitCode::SUCCESS);
    }
    if sub != "seal" {
        return Err(format!(
            "conformance 未知子命令：{}（修复指引：run | seal | contract <id> | list）",
            sub
        ));
    }
    let mut input: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--in" => {
                i += 1;
                input = Some(PathBuf::from(args.get(i).ok_or("--in 后缺路径")?));
            }
            "--out" => {
                i += 1;
                out = Some(PathBuf::from(args.get(i).ok_or("--out 后缺路径")?));
            }
            other => return Err(format!("未知参数：{}", other)),
        }
        i += 1;
    }
    let input = input.ok_or("缺 --in（修复指引：给契约裁决行 JSON）")?;
    let text = std::fs::read_to_string(&input)
        .map_err(|e| format!("读 {} 失败：{}", input.display(), e))?;
    let v: serde_json::Value = serde_json::from_str(&text)
        .map_err(|e| format!("{} 不是合法 JSON：{}", input.display(), e))?;

    let rows = parse_rows(&v)?;
    let mismatches = conformance::digest_mismatches(&rows);
    emit(&conformance::seal_bytes(&rows), &out)?;
    for m in &mismatches {
        eprintln!("  [FAIL] {}", m);
    }
    if mismatches.is_empty() {
        Ok(ExitCode::SUCCESS)
    } else {
        Ok(ExitCode::from(1))
    }
}

/// 解析契约裁决行（真源 `run()` 的报告对象亦可直接喂入）。
fn parse_rows(v: &serde_json::Value) -> Result<Vec<conformance::Row>, String> {
    let arr = match v {
        serde_json::Value::Array(a) => a,
        serde_json::Value::Object(o) => o
            .get("contracts")
            .and_then(|c| c.as_array())
            .ok_or("输入对象缺 contracts 数组（修复指引：给契约行数组或真源报告对象）")?,
        _ => return Err("输入必须是契约行数组或含 contracts 的对象".into()),
    };
    let mut rows = Vec::with_capacity(arr.len());
    for (i, item) in arr.iter().enumerate() {
        let o = item
            .as_object()
            .ok_or_else(|| format!("第 {} 行不是对象", i))?;
        let id = o
            .get("id")
            .and_then(|x| x.as_str())
            .ok_or_else(|| format!("第 {} 行缺 id（字符串）", i))?;
        let ok = o
            .get("ok")
            .and_then(|x| x.as_bool())
            .ok_or_else(|| format!("第 {} 行缺 ok（布尔）", i))?;
        rows.push(conformance::Row {
            id: id.to_string(),
            ok,
            detail: o
                .get("detail")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            description: o
                .get("description")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            recorded_digest: o
                .get("digest")
                .and_then(|x| x.as_str())
                .map(|s| s.to_string()),
        });
    }
    Ok(rows)
}
