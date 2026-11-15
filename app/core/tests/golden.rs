//! golden 回归：逐 case 用二进制跑请求，stdout 与 expected.json 逐字节比对。
//! 同时校验「golden-gen 重新生成 == 已提交夹具」（防漂移）。

use serde_json::Value;
use std::path::PathBuf;
use std::process::{Command, Stdio};

fn bin() -> &'static str {
    env!("CARGO_BIN_EXE_nf-app-core")
}

fn golden_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("fixtures")
        .join("golden")
        .canonicalize()
        .expect("golden 夹具目录不存在：先 cargo run -- golden-gen --out ../fixtures/golden")
}

fn collect_files(root: &std::path::Path) -> Vec<(String, Vec<u8>)> {
    fn walk(dir: &std::path::Path, root: &std::path::Path, out: &mut Vec<(String, Vec<u8>)>) {
        let mut entries: Vec<_> = std::fs::read_dir(dir).unwrap().flatten().collect();
        entries.sort_by_key(|e| e.file_name());
        for e in entries {
            let p = e.path();
            if p.is_dir() {
                walk(&p, root, out);
            } else {
                let rel = p
                    .strip_prefix(root)
                    .unwrap()
                    .to_string_lossy()
                    .replace('\\', "/");
                out.push((rel, std::fs::read(&p).unwrap()));
            }
        }
    }
    let mut out = Vec::new();
    walk(root, root, &mut out);
    out
}

#[test]
fn golden_cases_match_expected_bytes() {
    let root = golden_root();
    let mut dirs: Vec<_> = std::fs::read_dir(root.join("golden"))
        .unwrap()
        .flatten()
        .map(|e| e.path())
        .collect();
    dirs.sort();
    assert!(dirs.len() >= 25, "golden case 太少：{}", dirs.len());
    for case in dirs {
        let meta: Value =
            serde_json::from_slice(&std::fs::read(case.join("meta.json")).unwrap()).unwrap();
        let op = meta["op"].as_str().unwrap().to_string();
        let request = std::fs::read(case.join("request.json")).unwrap();
        let expected = std::fs::read(case.join("expected.json")).unwrap();
        let expected_value: Value = serde_json::from_slice(&expected).unwrap();
        let expected_exit = expected_value["exit"].as_i64().unwrap() as i32;
        // 写盘 op：在 golden 根下建 out_dir（生成时已清理）
        let mut req_value: Value = serde_json::from_slice(&request).unwrap();
        // 写盘 op：out_dir 改到 target 临时目录，避免污染已提交夹具（期望字节不含路径）
        let scratch = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("target")
            .join("golden-out")
            .join(case.file_name().unwrap());
        if req_value.get("out_dir").is_some() {
            let _ = std::fs::remove_dir_all(&scratch);
            std::fs::create_dir_all(&scratch).unwrap();
            req_value["out_dir"] = Value::String(scratch.to_string_lossy().to_string());
        }
        let request = serde_json::to_vec(&req_value).unwrap();
        let mut child = Command::new(bin())
            .args([&op, "--in", "-"])
            .current_dir(&root)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("启动二进制");
        {
            use std::io::Write;
            child.stdin.as_mut().unwrap().write_all(&request).unwrap();
        }
        let output = child.wait_with_output().unwrap();
        let code = output.status.code().unwrap_or(-1);
        assert_eq!(
            code,
            expected_exit,
            "case {} 退出码不符；stderr={}",
            case.file_name().unwrap().to_string_lossy(),
            String::from_utf8_lossy(&output.stderr)
        );
        assert_eq!(
            output.stdout,
            expected,
            "case {} 响应字节不符（expected.json 是 golden 真源）",
            case.file_name().unwrap().to_string_lossy()
        );
        let _ = std::fs::remove_dir_all(&scratch);
    }
}

#[test]
fn golden_gen_preserves_ops_subtree() {
    // 与 Python 侧共存契约：golden-gen 不得删除 app/fixtures/golden/ops/
    let tmp = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("target")
        .join("golden-ops-guard");
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(tmp.join("ops").join("canonical")).unwrap();
    std::fs::write(tmp.join("ops").join("canonical").join("case.json"), b"{\"op\":\"x\"}\n")
        .unwrap();
    let status = Command::new(bin())
        .args(["golden-gen", "--out", tmp.to_str().unwrap()])
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .status()
        .expect("运行 golden-gen");
    assert!(status.success());
    assert!(
        tmp.join("ops").join("canonical").join("case.json").is_file(),
        "golden-gen 删除了 Python 侧 ops/ 子树"
    );
    assert_eq!(
        std::fs::read(tmp.join("ops").join("canonical").join("case.json")).unwrap(),
        b"{\"op\":\"x\"}\n"
    );
    let _ = std::fs::remove_dir_all(&tmp);
}

#[test]
fn golden_regeneration_matches_committed() {
    let root = golden_root();
    let tmp = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("target")
        .join("golden-regen");
    let _ = std::fs::remove_dir_all(&tmp);
    let status = Command::new(bin())
        .args([
            "golden-gen",
            "--out",
            tmp.to_str().unwrap(),
        ])
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .status()
        .expect("运行 golden-gen");
    assert!(status.success(), "golden-gen 失败");
    let generated = collect_files(&tmp);
    // README.md 是目录说明，不在 golden-gen 产物内；比对只覆盖 fixtures/ 与 golden/
    let committed: Vec<(String, Vec<u8>)> = collect_files(&root)
        .into_iter()
        .filter(|(p, _)| p.starts_with("fixtures/") || p.starts_with("golden/"))
        .collect();
    assert_eq!(
        generated.len(),
        committed.len(),
        "golden 文件数不一致：重新生成 {}，已提交 {}",
        generated.len(),
        committed.len()
    );
    for ((ga, gb), (ca, cb)) in generated.iter().zip(committed.iter()) {
        assert_eq!(ga, ca, "golden 文件集合不一致");
        assert_eq!(gb, cb, "golden 文件内容漂移：{ga}");
    }
    let _ = std::fs::remove_dir_all(&tmp);
}