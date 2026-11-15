//! nf-app-core 命令行入口。

use nf_app_core::cli;
use nf_app_core::error::{CoreError, Envelope};
use std::io::Read;
use std::process::ExitCode;

fn fail(msg: impl Into<String>) -> ExitCode {
    let err = CoreError::new("NF-E-003").with_message(msg.into()).with_exit(2);
    let env = Envelope::failure(&err, None);
    print!("{}", String::from_utf8_lossy(&cli::envelope_bytes(&env)));
    ExitCode::from(2)
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() {
        return fail("用法：nf-app-core <op> [--in <req.json|->]；--help 查看帮助");
    }
    if args[0] == "--abi-version" {
        let value = cli::abi_version();
        let bytes = nf_app_core::canonical::canonical_bytes(&value).unwrap_or_default();
        print!("{}\n", String::from_utf8_lossy(&bytes));
        return ExitCode::SUCCESS;
    }
    if args[0] == "--help" || args[0] == "-h" {
        print!("{}", cli::help_text());
        return ExitCode::SUCCESS;
    }
    if args[0] == "--version" {
        println!("nf-app-core {}", nf_app_core::CORE_VERSION);
        return ExitCode::SUCCESS;
    }
    if args[0] == "golden-gen" {
        return golden_gen(&args[1..]);
    }
    let op = args[0].clone();
    let mut input_path: Option<String> = None;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--json" => {}
            "--in" => {
                i += 1;
                if i >= args.len() {
                    return fail("--in 缺少参数");
                }
                input_path = Some(args[i].clone());
            }
            other if other.starts_with("--") => {
                return fail(format!("未知参数 {other}"));
            }
            other => {
                input_path = Some(other.to_string());
            }
        }
        i += 1;
    }
    let input = match read_input(input_path.as_deref()) {
        Ok(b) => b,
        Err(e) => {
            let env = Envelope::failure(&e, None);
            print!("{}", String::from_utf8_lossy(&cli::envelope_bytes(&env)));
            return ExitCode::from(e.exit as u8);
        }
    };
    let env = cli::run(&op, &input);
    let exit = env.exit;
    print!("{}", String::from_utf8_lossy(&cli::envelope_bytes(&env)));
    ExitCode::from(exit as u8)
}

fn read_input(path: Option<&str>) -> Result<Vec<u8>, CoreError> {
    match path {
        None | Some("-") => {
            let mut buf = Vec::new();
            std::io::stdin()
                .read_to_end(&mut buf)
                .map_err(|e| {
                    CoreError::new("NF-E-004")
                        .with_message(format!("读 stdin 失败: {e}"))
                        .with_exit(2)
                })?;
            Ok(buf)
        }
        Some(p) => std::fs::read(p).map_err(|e| {
            CoreError::new("NF-E-004")
                .with_message(format!("读请求文件失败 {p}: {e}"))
                .with_exit(2)
        }),
    }
}
fn golden_gen(args: &[String]) -> ExitCode {
    let mut out: Option<String> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--out" => {
                i += 1;
                if i >= args.len() {
                    return fail("golden-gen --out 缺少目录");
                }
                out = Some(args[i].clone());
            }
            other => return fail(format!("golden-gen 未知参数 {other}")),
        }
        i += 1;
    }
    let out = match out {
        Some(o) => o,
        None => return fail("golden-gen 需要 --out <dir>"),
    };
    match nf_app_core::golden::generate(&out) {
        Ok(n) => {
            let value = serde_json::json!({"generated": n, "out": out});
            let bytes = nf_app_core::canonical::canonical_bytes(&value).unwrap_or_default();
            print!("{}\n", String::from_utf8_lossy(&bytes));
            ExitCode::SUCCESS
        }
        Err(e) => {
            let env = Envelope::failure(&e, None);
            print!("{}", String::from_utf8_lossy(&cli::envelope_bytes(&env)));
            ExitCode::from(e.exit as u8)
        }
    }
}
