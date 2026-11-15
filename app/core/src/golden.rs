//! golden 夹具生成（隐藏子命令 golden-gen --out <dir>）：
//! 每个 case 目录含 meta.json（op）/ request.json / expected.json；expected = CLI 响应信封 canonical 字节 + LF。

use crate::canonical::canonical_bytes;
use crate::error::CoreError;
use crate::fixtures;
use crate::ops;
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

fn io_err(ctx: &str, e: std::io::Error) -> CoreError {
    CoreError::new("NF-E-004")
        .with_message(format!("{ctx}: {e}"))
        .with_exit(2)
}

fn write(dir: &Path, rel: &str, bytes: &[u8]) -> Result<(), CoreError> {
    let p = dir.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR));
    if let Some(parent) = p.parent() {
        std::fs::create_dir_all(parent).map_err(|e| io_err("建目录失败", e))?;
    }
    std::fs::write(&p, bytes).map_err(|e| io_err("写 golden 文件失败", e))
}

/// 请求文件按 JSON 原样写（允许 float，例如 canonical 负例）；不用 canonical。
fn write_request(dir: &Path, rel: &str, value: &Value) -> Result<(), CoreError> {
    let mut bytes = serde_json::to_string(value)
        .map_err(|e| CoreError::new("NF-E-003").with_message(format!("请求序列化失败: {e}")).with_exit(2))?
        .into_bytes();
    bytes.push(b'\n');
    write(dir, rel, &bytes)
}

fn write_json(dir: &Path, rel: &str, value: &Value) -> Result<(), CoreError> {
    let mut bytes = canonical_bytes(value)?;
    bytes.push(b'\n');
    write(dir, rel, &bytes)
}

/// 生成 golden 夹具；返回 case 数。
pub fn generate(out: &str) -> Result<u64, CoreError> {
    let root = std::path::absolute(PathBuf::from(out.replace('\\', "/")))
        .map_err(|e| io_err("解析 golden 目录失败", e))?;
    std::fs::create_dir_all(&root).map_err(|e| io_err("建 golden 目录失败", e))?;
    let old_cwd = std::env::current_dir().map_err(|e| io_err("读当前目录失败", e))?;
    std::env::set_current_dir(&root).map_err(|e| io_err("切换 golden 目录失败", e))?;
    let result = generate_in(&root);
    let _ = std::env::set_current_dir(&old_cwd);
    result
}

fn remove_dir_quiet(p: &Path) {
    let _ = std::fs::remove_dir_all(p);
}

fn generate_in(root: &Path) -> Result<u64, CoreError> {
    // 1) 手写最小输入夹具
    write(&root, "fixtures/import/sample.md", fixtures::sample_markdown().as_bytes())?;
    write(&root, "fixtures/import/sample.txt", fixtures::sample_text().as_bytes())?;
    write(&root, "fixtures/import/sample.yaml", fixtures::sample_yaml().as_bytes())?;
    write(&root, "fixtures/import/sample.json", b"{\"a\":1,\"b\":[1,2]}\n")?;
    write(&root, "fixtures/import/sample.html", b"<!DOCTYPE html><html></html>\n")?;
    write_json(&root, "fixtures/spec/demo-spec.json", &fixtures::spec())?;
    write_json(&root, "fixtures/graph/demo-graph.json", &fixtures::graph())?;
    write_json(&root, "fixtures/protocol/demo-protocol.json", &fixtures::protocol_pack())?;
    write_json(&root, "fixtures/project/demo-project.json", &fixtures::project())?;

    let v1 = root.join("fixtures").join("pack-v1");
    let v2 = root.join("fixtures").join("pack-v2");
    let m1 = fixtures::make_pack(&v1, "demo-pack", "1.0.0", &fixtures::pack_v1_files())?;
    fixtures::make_pack(&v2, "demo-pack", "2.0.0", &fixtures::pack_v2_files())?;
    let overlay = fixtures::overlay(m1["hashes"]["tree"].as_str().unwrap(), "demo-pack", "1.0.0");
    write_json(&root, "fixtures/overlay/demo-overlay.json", &overlay)?;

    // 破损 pack（manifest 与内容不符）用于 pack-verify 负例
    let bad = root.join("fixtures").join("pack-v1-tampered");
    fixtures::make_pack(&bad, "demo-pack", "1.0.0", &fixtures::pack_v1_files())?;
    write(&bad, "docs/old.md", "# 被篡改\n".as_bytes())?;

    // 带环图（负例）
    let mut cycle = fixtures::graph();
    cycle["edges"].as_array_mut().unwrap().push(json!({
        "id": "E99", "from": "N05", "to": "N02", "from_port": "o", "to_port": "i", "type": "data"
    }));
    write_json(&root, "fixtures/graph/cycle-graph.json", &cycle)?;

    let spec = fixtures::spec();
    let graph = fixtures::graph();
    let protocol = fixtures::protocol_pack();
    let project = fixtures::project();

    // 2) 逐个 op 跑真实实现，记录请求 + 期望响应
    let import_md = dispatch_ok(root, "import", &json!({
        "file": "fixtures/import/sample.md",
        "source": {"kind": "file", "name": "sample.md"}
    }))?;
    let plan = dispatch_ok(root, "graph-compile", &json!({
        "graph": graph.clone(), "spec": spec.clone()
    }))?;
    let assemble_req = json!({
        "plan": plan.clone(),
        "spec": spec.clone(),
        "inputs": {"SLT-01": "法师", "SLT-02": "塔", "SLT-03": "正文内容。"},
        "out_dir": "out/assemble"
    });
    std::fs::create_dir_all(root.join("out").join("assemble"))
        .map_err(|e| io_err("建 out_dir 失败", e))?;
    let asm = dispatch_ok(root, "assemble", &assemble_req)?;
    remove_dir_quiet(&root.join("out").join("assemble"));
    let markdown = asm["markdown"].clone();
    let update = dispatch_ok(root, "pack-diff", &json!({
        "old_root": "fixtures/pack-v1", "new_root": "fixtures/pack-v2"
    }))?;
    let task = dispatch_ok(root, "ccos-build-task", &json!({
        "project": project.clone(),
        "task_id": "demo-task-0001",
        "created_at": "2026-01-01T00:00:00Z",
        "budget": {"max_tokens": 1000, "max_chars": 4000, "max_seconds": 60},
        "variables": {"tone": "warm"}
    }))?;
    let task_digest = crate::canonical::digest_value(&task)?;
    let ccos_result = json!({
        "schema": "ccos-result/1",
        "task_id": "demo-task-0001",
        "task_digest": task_digest,
        "status": "succeeded",
        "artifacts": [{
            "name": "result.md", "mime": "text/markdown", "path": "result.md",
            "sha256": fixtures::hex64('7'), "bytes": 10
        }],
        "evidence": [{"kind": "log", "ref": "run.log", "digest": fixtures::hex64('8')}],
        "report": {"summary": "ok", "issues": []},
        "provenance": {"engine": "ccos", "started_at": "2026-01-01T00:00:00Z", "finished_at": "2026-01-01T00:01:00Z"},
        "human_review": {"required": true, "state": "approved"}
    });

    let cases: Vec<(&str, &str, Value, bool)> = vec![
        ("canonical", "canonical", json!({"value": {"b": [1, 2, {"z": "中", "a": "é"}], "a": true}}), false),
        ("canonical-float", "canonical", json!({"value": {"a": 0.5}}), false),
        ("pack-hash", "pack-hash", json!({"root": "fixtures/pack-v1"}), false),
        ("pack-verify", "pack-verify", json!({"root": "fixtures/pack-v1"}), false),
        ("pack-verify-tampered", "pack-verify", json!({"root": "fixtures/pack-v1-tampered"}), false),
        ("import-sniff", "import-sniff", json!({"name": "sample.md", "file": "fixtures/import/sample.md"}), false),
        ("import-markdown", "import", json!({"file": "fixtures/import/sample.md", "source": {"kind": "file", "name": "sample.md"}}), false),
        ("import-yaml", "import", json!({"file": "fixtures/import/sample.yaml", "source": {"kind": "file", "name": "sample.yaml"}}), false),
        ("import-unsupported", "import", json!({"file": "fixtures/import/sample.html", "source": {"kind": "file", "name": "sample.html"}}), false),
        ("map-suggest", "map-suggest", json!({"import": import_md.clone(), "spec": spec.clone()}), false),
        ("protocol-validate", "protocol-validate", json!({"pack": protocol.clone()}), false),
        ("protocol-render", "protocol-render", json!({"pack": protocol.clone(), "values": {"F-001": "法师", "F-002": "塔"}}), false),
        ("graph-validate", "graph-validate", json!({"graph": graph.clone()}), false),
        ("graph-validate-cycle", "graph-validate", json!({"graph": cycle}), false),
        ("graph-compile", "graph-compile", json!({"graph": graph.clone(), "spec": spec.clone()}), false),
        ("spec-validate", "spec-validate", json!({"spec": spec.clone()}), false),
        ("assemble", "assemble", assemble_req.clone(), true),
        ("validate-l0", "validate", json!({"markdown": markdown.clone(), "spec": spec.clone(), "plan": plan.clone(), "level": "L0"}), false),
        ("validate-l1", "validate", json!({"markdown": markdown.clone(), "spec": spec.clone(), "plan": plan.clone(), "level": "L1"}), false),
        ("export-md", "export", json!({"markdown": "# 导出\n正文\n", "format": "md", "out_dir": "out/export-md", "manifest": true}), true),
        ("export-zip", "export", json!({"result": {"markdown": "# 导出\n", "meta": {"schema": "nf-assemble-result/1", "markdown_digest": fixtures::hex64('9')}}, "format": "zip", "out_dir": "out/export-zip"}), true),
        ("pack-diff", "pack-diff", json!({"old_root": "fixtures/pack-v1", "new_root": "fixtures/pack-v2"}), false),
        ("pack-merge", "pack-merge", json!({"update": update, "base_root": "fixtures/pack-v1", "new_root": "fixtures/pack-v2", "out_dir": "out/pack-merge"}), true),
        ("overlay-apply", "overlay-apply", json!({"base_root": "fixtures/pack-v1", "overlay": overlay.clone(), "out_dir": "out/overlay-apply"}), true),
        ("ccos-build-task", "ccos-build-task", json!({"project": project.clone(), "task_id": "demo-task-0002", "created_at": "2026-01-01T00:00:00Z", "budget": {"max_tokens": 1000, "max_chars": 4000, "max_seconds": 60}}), false),
        ("ccos-import-result", "ccos-import-result", json!({"task": task, "result": ccos_result}), false),
        ("project-validate", "project-validate", json!({"project": project}), false),
    ];

    let golden_root = root.join("golden");
    remove_dir_quiet(&golden_root);
    let mut n = 0u64;
    for (name, op, req, needs_out) in cases {
        let case_dir = golden_root.join(name);
        std::fs::create_dir_all(&case_dir).map_err(|e| io_err("建 case 目录失败", e))?;
        write_json(&case_dir, "meta.json", &json!({"op": op, "case": name}))?;
        write_request(&case_dir, "request.json", &req)?;
        let out_dir = root.join("out").join(name);
        if needs_out {
            std::fs::create_dir_all(&out_dir).map_err(|e| io_err("建 out_dir 失败", e))?;
        }
        let env = ops::dispatch(op, &req);
        let mut bytes = canonical_bytes(&env.to_value())?;
        bytes.push(b'\n');
        write(&case_dir, "expected.json", &bytes)?;
        if needs_out {
            remove_dir_quiet(&out_dir);
        }
        n += 1;
    }
    remove_dir_quiet(&root.join("out"));
    Ok(n)
}

fn dispatch_ok(root: &Path, op: &str, req: &Value) -> Result<Value, CoreError> {
    let env = ops::dispatch(op, req);
    if !env.ok || env.exit != 0 {
        return Err(CoreError::new("NF-E-003")
            .with_message(format!(
                "golden 生成失败：op {op} exit={} error={:?} (cwd={})",
                env.exit,
                env.error,
                root.display()
            ))
            .with_exit(2));
    }
    Ok(env.result.unwrap_or(Value::Null))
}
