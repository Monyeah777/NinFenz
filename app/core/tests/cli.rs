//! CLI 进程面：--abi-version / stdin / 退出码。

use serde_json::Value;
use std::io::Write;
use std::process::{Command, Stdio};

fn bin() -> &'static str {
    env!("CARGO_BIN_EXE_nf-app-core")
}

fn run(args: &[&str], stdin: &str) -> (i32, String) {
    let mut child = Command::new(bin())
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("启动二进制");
    child
        .stdin
        .as_mut()
        .unwrap()
        .write_all(stdin.as_bytes())
        .unwrap();
    let out = child.wait_with_output().unwrap();
    (
        out.status.code().unwrap_or(-1),
        String::from_utf8(out.stdout).unwrap(),
    )
}

fn parse(line: &str) -> Value {
    serde_json::from_str(line.trim()).expect("stdout 必须是单行 JSON")
}

#[test]
fn cli_abi_version() {
    let (code, out) = run(&["--abi-version"], "");
    assert_eq!(code, 0);
    let v = parse(&out);
    assert_eq!(v["abi"], "nf-app-core/1");
    assert_eq!(v["version"], "0.1.0");
}

#[test]
fn cli_canonical_via_stdin() {
    let (code, out) = run(&["canonical", "--in", "-"], r#"{"value":{"a":[1,null]}}"#);
    assert_eq!(code, 0);
    let v = parse(&out);
    assert_eq!(v["ok"], true);
    assert_eq!(v["result"]["canonical"], "{\"a\":[1,null]}");
}

#[test]
fn cli_validation_failure_exit1() {
    let (code, out) = run(&["canonical", "--json"], r#"{"value":{"a":1.5}}"#);
    assert_eq!(code, 1);
    let v = parse(&out);
    assert_eq!(v["ok"], false);
    assert_eq!(v["error"]["code"], "NF-E-006");
    assert_eq!(v["result"]["schema"], "nf-validate-report/1");
}

#[test]
fn cli_unknown_op_exit2() {
    let (code, out) = run(&["does-not-exist"], "{}");
    assert_eq!(code, 2);
    let v = parse(&out);
    assert_eq!(v["error"]["code"], "NF-E-003");
}

#[test]
fn cli_bad_request_exit2() {
    let (code, out) = run(&["canonical"], "{bad");
    assert_eq!(code, 2);
    let v = parse(&out);
    assert_eq!(v["ok"], false);
}

#[test]
fn cli_pack_hash_root_missing_exit2() {
    let (code, out) = run(
        &["pack-hash", "--in", "-"],
        r#"{"root":"Z:/no/such/dir"}"#,
    );
    assert_eq!(code, 2);
    let v = parse(&out);
    assert_eq!(v["error"]["code"], "NF-E-004");
}

#[test]
fn cli_no_args_exit2() {
    let (code, out) = run(&[], "");
    assert_eq!(code, 2);
    assert!(!out.trim().is_empty());
    let _ = parse(&out);
}
