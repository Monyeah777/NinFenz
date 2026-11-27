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
mod subject_docs;
mod jsonx;
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
mod cli;
#[cfg(test)]
mod testutil;

use std::io::Write;
use std::path::PathBuf;
use std::process::ExitCode;
use std::sync::Mutex;

use crate::cli::*;

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

pub(crate) fn emit(bytes: &[u8], out: &Option<PathBuf>) -> Result<(), String> {
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

pub(crate) fn require_dir(root: &PathBuf) -> Result<(), String> {
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
