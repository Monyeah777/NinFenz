//! 集成测试公共工具：唯一临时目录、op 调用、断言辅助。

use nf_app_core::error::Envelope;
use nf_app_core::ops;
use serde_json::Value;
use std::path::PathBuf;
use std::sync::atomic::{AtomicUsize, Ordering};

static COUNTER: AtomicUsize = AtomicUsize::new(0);

/// 测试临时根：必须位于工作区内（DSH 宿主的进程级沙箱按可执行文件路径生效，
/// 工作区内的测试二进制只能写工作区；这也保证测试不污染系统临时目录）。
pub fn tmpdir(tag: &str) -> PathBuf {
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    let pid = std::process::id();
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("target")
        .join("nf-test-tmp")
        .join(format!("{tag}_{pid}_{n}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).expect("建临时目录");
    dir
}

pub fn dispatch(op: &str, req: &Value) -> Envelope {
    ops::dispatch(op, req)
}

pub fn run_ok(op: &str, req: &Value) -> Value {
    let env = dispatch(op, req);
    assert!(env.ok, "{op} 应成功，实际 exit={} error={:?}", env.exit, env.error);
    assert_eq!(env.exit, 0, "{op} 退出码应为 0");
    assert!(env.error.is_none(), "{op} 成功不应有 error");
    env.result.expect("成功必须有 result")
}

pub fn run_err(op: &str, req: &Value, exit: i32, code: &str) -> Envelope {
    let env = dispatch(op, req);
    assert_eq!(env.exit, exit, "{op} 期望 exit {exit}，实际 {}", env.exit);
    assert!(!env.ok, "{op} 失败时 ok 必须 false");
    let err = env.error.as_ref().expect("失败必须有 error");
    assert_eq!(
        err["code"].as_str().unwrap_or(""),
        code,
        "{op} 错误码不符；error={err}"
    );
    if exit == 1 {
        assert!(env.result.is_some(), "exit 1 必须带 nf-validate-report");
        assert_eq!(
            env.result.as_ref().unwrap()["schema"].as_str(),
            Some("nf-validate-report/1")
        );
    } else {
        assert!(env.result.is_none(), "exit {exit} 时 result 必须为 null");
    }
    env
}

pub fn canon_bytes(value: &Value) -> Vec<u8> {
    nf_app_core::canonical::canonical_bytes(value).expect("canonical")
}

pub fn canon(value: &Value) -> String {
    String::from_utf8(canon_bytes(value)).expect("utf8")
}

pub fn write_file(dir: &PathBuf, rel: &str, content: &str) -> PathBuf {
    let p = dir.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR));
    if let Some(parent) = p.parent() {
        std::fs::create_dir_all(parent).expect("建父目录");
    }
    std::fs::write(&p, content.as_bytes()).expect("写文件");
    p
}

pub fn pstr(p: &PathBuf) -> String {
    p.to_string_lossy().to_string()
}

pub fn assert_exit(env: &Envelope, exit: i32) {
    assert_eq!(env.exit, exit, "exit 期望 {exit}，实际 {} error={:?}", env.exit, env.error);
}
