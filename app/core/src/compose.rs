//! 组合编排：多个独立构建任务隔离执行；单任务失败不污染其他任务。
//! 每个 job 有独立目录；失败时只清理该 job 的目录，成功任务保留。

use crate::build;
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::ops::{ensure_out_dir, opt_str, usage};
use serde_json::{json, Value};

pub fn compose(req: &Value) -> OpOutcome {
    let jobs = req
        .get("jobs")
        .and_then(|v| v.as_array())
        .ok_or_else(|| usage("compose-run 需要 jobs:[{id,sdir,outputs}]"))?;
    let base = ensure_out_dir(opt_str(req, "out_dir")?.ok_or_else(|| usage("compose-run 需要 out_dir"))?)?;
    let mut seen = std::collections::BTreeSet::new();
    let mut results = Vec::new();
    let mut ok_count = 0u64;
    let mut failed = 0u64;
    for (i, job) in jobs.iter().enumerate() {
        let id = job.get("id").and_then(|v| v.as_str()).filter(|s| !s.is_empty()).ok_or_else(|| usage(format!("jobs[{i}].id 缺失")))?;
        if !seen.insert(id.to_string()) {
            return Err(usage(format!("jobs[{i}].id 重复：{id}")));
        }
        fsutil::validate_rel_path(id).map_err(|_| usage(format!("jobs[{i}].id 不安全：{id}")))?;
        let sdir = job.get("sdir").ok_or_else(|| usage(format!("jobs[{i}].sdir 缺失")))?;
        let outputs = job.get("outputs").ok_or_else(|| usage(format!("jobs[{i}].outputs 缺失")))?;
        let dir = base.join(id.replace('/', std::path::MAIN_SEPARATOR_STR));
        if dir.exists() {
            std::fs::remove_dir_all(&dir).map_err(|e| fsutil::io_error("清理旧 job 目录失败", &dir, e))?;
        }
        std::fs::create_dir_all(&dir).map_err(|e| fsutil::io_error("创建 job 目录失败", &dir, e))?;
        let sub = json!({
            "sdir": sdir,
            "outputs": outputs,
            "out_dir": dir.to_string_lossy().replace('\\', "/"),
            "locale": job.get("locale").cloned().unwrap_or_else(|| json!("und"))
        });
        let outcome = build::run(&sub);
        let record = match outcome {
            Ok((0, result)) => {
                ok_count += 1;
                json!({"id": id, "ok": true, "dir": id, "artifacts": result.get("artifacts").cloned().unwrap_or_else(|| json!([]))})
            }
            Ok((exit, result)) => {
                failed += 1;
                let _ = std::fs::remove_dir_all(&dir);
                json!({"id": id, "ok": false, "exit": exit, "error": result, "recovered": true})
            }
            Err(e) => {
                failed += 1;
                let _ = std::fs::remove_dir_all(&dir);
                json!({"id": id, "ok": false, "exit": e.exit, "error": e.to_value(), "recovered": true})
            }
        };
        results.push(record);
    }
    // 隔离检查：每个成功 job 的输出必须在其目录内
    let mut isolated = true;
    for r in &results {
        if r.get("ok").and_then(|v| v.as_bool()) == Some(true) {
            if let Some(arts) = r.get("artifacts").and_then(|v| v.as_array()) {
                for a in arts {
                    let p = a.get("path").and_then(|v| v.as_str()).unwrap_or("");
                    if fsutil::validate_rel_path(p).is_err() {
                        isolated = false;
                    }
                }
            }
        }
    }
    if !isolated {
        return Err(CoreError::new("NF-BLD-001").with_message("组合编排检测到跨目录输出").with_exit(1));
    }
    Ok((0, json!({
        "schema": "nf-compose-result/1",
        "jobs": results,
        "summary": {"ok": ok_count, "failed": failed, "total": jobs.len() as u64, "isolated": true}
    })))
}

pub fn compose_op(req: &Value) -> OpOutcome { compose(req) }
