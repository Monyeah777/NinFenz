use super::*;

pub(crate) fn walk_leaf<'a>(b: &'a Value, out: &mut Vec<&'a Value>) {
    let ty = type_of(b);
    if ty == "document" {
        for c in kids(b) { walk_leaf(c, out); }
        return;
    }
    out.push(b);
    if ty == "heading" {
        for c in kids(b) { walk_leaf(c, out); }
    }
}

pub(crate) fn block_md(b: &Value) -> String {
    let mut out = String::new();
    match type_of(b) {
        "heading" => {
            out.push_str(&"#".repeat(heading_level(b).clamp(1, 6)));
            out.push(' ');
            out.push_str(text_of(b));
            out.push_str("\n\n");
        }
        "paragraph" => { out.push_str(text_of(b)); out.push_str("\n\n"); }
        "list" => {
            let ordered = b.get("attrs").and_then(|a| a.get("ordered")).and_then(|v| v.as_bool()).unwrap_or(false);
            for (i, c) in kids(b).iter().enumerate() {
                if ordered { out.push_str(&format!("{}. ", i + 1)); } else { out.push_str("- "); }
                out.push_str(text_of(c)); out.push('\n');
            }
            out.push('\n');
        }
        "table" => {
            let rows: Vec<&Value> = kids(b).iter().collect();
            if let Some(first) = rows.first() {
                let cells: Vec<String> = kids(first).iter().map(|c| text_of(c).replace('|', "\\|")).collect();
                out.push_str(&format!("| {} |\n", cells.join(" | ")));
                out.push_str(&format!("| {} |\n", vec!["---"; cells.len()].join(" | ")));
            }
            for row in rows.iter().skip(1) {
                let cells: Vec<String> = kids(row).iter().map(|c| text_of(c).replace('|', "\\|")).collect();
                out.push_str(&format!("| {} |\n", cells.join(" | ")));
            }
            out.push('\n');
        }
        "code" => {
            let lang = b.get("attrs").and_then(|a| a.get("lang")).and_then(|v| v.as_str()).unwrap_or("");
            out.push_str(FENCE); out.push_str(lang); out.push('\n');
            out.push_str(text_of(b)); out.push('\n'); out.push_str(FENCE); out.push_str("\n\n");
        }
        "quote" => {
            for line in text_of(b).split('\n') { out.push_str("> "); out.push_str(line); out.push('\n'); }
            out.push('\n');
        }
        "figure" => {
            let src = b.get("attrs").and_then(|a| a.get("src")).and_then(|v| v.as_str()).unwrap_or("");
            out.push_str(&format!("![{}]({})\n\n", text_of(b), src));
        }
        "footnote" => {
            let label = b.get("attrs").and_then(|a| a.get("label")).and_then(|v| v.as_str()).unwrap_or("1");
            out.push_str(&format!("[^{}]: {}\n\n", label, text_of(b)));
        }
        _ => { if !text_of(b).is_empty() { out.push_str(text_of(b)); out.push_str("\n\n"); } }
    }
    out
}

pub(crate) fn intrinsic_block(b: &Value) -> String {
    hash_of(&json!({
        "type": b.get("type").cloned().unwrap_or(Value::Null),
        "text": b.get("text").cloned().unwrap_or(Value::Null),
        "attrs": b.get("attrs").cloned().unwrap_or_else(|| json!({}))
    }))
}

pub fn block_plan(req: &Value) -> OpOutcome {
    let sdir = req_value(req, "sdir")?;
    let report = sdir::validate_sdir_value(sdir);
    if report.has_error() { return Ok((1, report.to_value())); }
    let mut flat: Vec<&Value> = Vec::new();
    if let Some(root) = sdir.get("blocks").and_then(|b| b.get(0)) { walk_leaf(root, &mut flat); }
    let mut blocks = Vec::new();
    let mut out = String::new();
    for b in flat {
        let rendered = block_md(b);
        out.push_str(&rendered);
        blocks.push(json!({
            "id": id_of(b),
            "type": type_of(b),
            "hash": intrinsic_block(b),
            "render_sha256": sha256_hex(rendered.as_bytes()),
            "bytes": rendered.len() as u64
        }));
    }
    let normalized = out.trim_end().to_string() + "
";
    Ok((0, json!({
        "schema": "nf-block-plan/1",
        "blocks": blocks,
        "output": normalized,
        "output_sha256": sha256_hex(normalized.as_bytes()),
        "summary": {"blocks": blocks.len() as u64}
    })))
}

pub fn block_incremental(req: &Value) -> OpOutcome {
    let old = req.get("old_blocks").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let (code, mut plan) = block_plan(req)?;
    if code != 0 { return Ok((code, plan)); }
    let new_blocks = plan.get("blocks").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let old_map: BTreeMap<String, String> = old.iter().map(|b| (b.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string(), b.get("hash").and_then(|v| v.as_str()).unwrap_or("").to_string())).collect();
    let mut recompute = Vec::new();
    let mut reuse = Vec::new();
    let mut seen = BTreeSet::new();
    for b in &new_blocks {
        let id = b.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        seen.insert(id.clone());
        if old_map.get(&id).map(|h| h.as_str()) == b.get("hash").and_then(|v| v.as_str()) {
            reuse.push(id);
        } else {
            recompute.push(id);
        }
    }
    let removed: Vec<String> = old_map.keys().filter(|k| !seen.contains(*k)).cloned().collect();
    plan.as_object_mut().unwrap().insert("recompute".into(), Value::Array(recompute.iter().map(|s| Value::String(s.clone())).collect()));
    plan.as_object_mut().unwrap().insert("reuse".into(), Value::Array(reuse.iter().map(|s| Value::String(s.clone())).collect()));
    plan.as_object_mut().unwrap().insert("removed".into(), Value::Array(removed.iter().map(|s| Value::String(s.clone())).collect()));
    plan.as_object_mut().unwrap().insert("stale".into(), Value::Array(vec![]));
    plan.as_object_mut().unwrap().insert("summary".into(), json!({"recompute": recompute.len() as u64, "reuse": reuse.len() as u64, "removed": removed.len() as u64, "stale": 0}));
    Ok((0, plan))
}

pub fn journal_op(req: &Value) -> OpOutcome {
    let journal = req
        .get("journal")
        .or_else(|| req.get("result").and_then(|r| r.get("journal")))
        .cloned()
        .ok_or_else(|| usage("build-journal 需要 journal 或 result.journal"))?;
    let issues = validate("nf-build", &journal);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-BLD-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    Ok((0, journal))
}

pub fn why_op(req: &Value) -> OpOutcome {
    let old = req_value(req, "old_graph")?;
    let new = req_value(req, "new_graph")?;
    let old_report = validate_graph(old);
    if old_report.has_error() {
        return Ok((1, old_report.to_value()));
    }
    let new_report = validate_graph(new);
    if new_report.has_error() {
        return Ok((1, new_report.to_value()));
    }
    let old_outputs: BTreeMap<String, Value> = old
        .get("outputs")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().map(|o| (o.get("path").and_then(|v| v.as_str()).unwrap_or("").to_string(), o.clone())).collect())
        .unwrap_or_default();
    let new_outputs: BTreeMap<String, Value> = new
        .get("outputs")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().map(|o| (o.get("path").and_then(|v| v.as_str()).unwrap_or("").to_string(), o.clone())).collect())
        .unwrap_or_default();
    let mut rebuild = Vec::new();
    let mut reasons = Vec::new();
    for (path, output) in &new_outputs {
        let old_output = match old_outputs.get(path) {
            Some(value) => value,
            None => {
                rebuild.push(path.clone());
                reasons.push(json!({"path": path, "reason": "new-output"}));
                continue;
            }
        };
        let old_key = transform_key(old, old_output.get("node").and_then(|v| v.as_str()).unwrap_or(""));
        let new_key = transform_key(new, output.get("node").and_then(|v| v.as_str()).unwrap_or(""));
        if old_key.is_empty() || old_key != new_key {
            rebuild.push(path.clone());
            reasons.push(json!({"path": path, "reason": "cache-key", "old_key": old_key, "new_key": new_key}));
        } else if old_output.get("sha256") != output.get("sha256") {
            rebuild.push(path.clone());
            reasons.push(json!({"path": path, "reason": "content"}));
        }
    }
    for path in old_outputs.keys().filter(|path| !new_outputs.contains_key(*path)) {
        reasons.push(json!({"path": path, "reason": "removed"}));
    }
    let plan_changed = old.get("plan_sha") != new.get("plan_sha");
    let environment_changed = old.get("environment") != new.get("environment");
    Ok((0, json!({
        "schema": "nf-build-why/1",
        "rebuild": rebuild,
        "reasons": reasons,
        "plan_changed": plan_changed,
        "environment_changed": environment_changed
    })))
}

pub fn block_plan_op(req: &Value) -> OpOutcome { block_plan(req) }
pub fn block_incremental_op(req: &Value) -> OpOutcome { block_incremental(req) }
pub fn build_plan_op(req: &Value) -> OpOutcome { plan(req) }
pub fn build_run_op(req: &Value) -> OpOutcome { run(req) }
pub fn build_incremental_op(req: &Value) -> OpOutcome { incremental(req) }
