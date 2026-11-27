use super::*;

pub(crate) fn transform_params<'a>(graph: &'a Value, output_node: &str) -> Option<&'a Value> {
    let edge = graph.get("edges").and_then(|v| v.as_array()).and_then(|a| a.iter().find(|e| e.get("to").and_then(|v| v.as_str()) == Some(output_node)))?;
    let from = edge.get("from").and_then(|v| v.as_str())?;
    graph.get("nodes").and_then(|v| v.as_array()).and_then(|a| a.iter().find(|n| n.get("id").and_then(|v| v.as_str()) == Some(from))).and_then(|n| n.get("params"))
}

pub fn run(req: &Value) -> OpOutcome {
    let sdir = req_value(req, "sdir")?;
    let report = sdir::validate_sdir_value(sdir);
    if report.has_error() { return Ok((1, report.to_value())); }
    let out_dir = ensure_out_dir(opt_str(req, "out_dir")?.ok_or_else(|| usage("build-run 需要 out_dir"))?)?;
    let graph = match req.get("graph") {
        Some(g @ Value::Object(_)) => {
            let rg = validate_graph(g);
            if rg.has_error() { return Ok((1, rg.to_value())); }
            check_cache(g, sdir)?;
            g.clone()
        }
        Some(_) => return Err(usage("graph 必须是 object")),
        None => { let (_, g) = plan(req)?; g }
    };
    let outputs = graph.get("outputs").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let mut artifacts = Vec::new();
    let mut new_outputs = Vec::new();
    for o in &outputs {
        let path = o.get("path").and_then(|v| v.as_str()).unwrap_or("");
        let format = o.get("format").and_then(|v| v.as_str()).unwrap_or("md");
        let node = o.get("node").and_then(|v| v.as_str()).unwrap_or("");
        let profile = transform_params(&graph, node).and_then(|p| p.get("profile")).and_then(|v| v.as_str()).unwrap_or("default");
        let bytes = render_one(sdir, format, profile)?;
        fsutil::validate_rel_path(path).map_err(|_| CoreError::new("NF-EXP-002").with_message(format!("输出路径越界：{path}")).with_exit(3))?;
        let target = out_dir.join(path.replace('/', std::path::MAIN_SEPARATOR_STR));
        atomic_write(&target, &bytes)?;
        let sha = sha256_hex(&bytes);
        artifacts.push(json!({"path": path, "sha256": sha, "bytes": bytes.len() as u64, "format": format}));
        new_outputs.push(json!({"node": node, "path": path, "sha256": sha, "bytes": bytes.len() as u64, "format": format}));
    }
    let mut graph_out = graph.clone();
    graph_out.as_object_mut().unwrap().insert("outputs".into(), Value::Array(new_outputs));
    let plan_sha = graph_out.get("plan_sha").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let verdict = match req.get("verdict").and_then(|v| v.as_str()) {
        Some("verified") => "verified",
        _ => "unverified",
    };
    let skipped: Vec<String> = req
        .get("skipped")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().filter_map(|v| v.as_str().map(ToString::to_string)).collect())
        .unwrap_or_default();
    let mut journal_nodes = Vec::new();
    for node in graph_out.get("nodes").and_then(|v| v.as_array()).into_iter().flatten() {
        journal_nodes.push(json!({
            "id": node.get("id").and_then(|v| v.as_str()).unwrap_or("node"),
            "kind": node.get("kind").and_then(|v| v.as_str()).unwrap_or("node"),
            "status": "run",
            "key": node.get("cache_key").and_then(|v| v.as_str()).filter(|s| !s.is_empty()).unwrap_or("n/a")
        }));
    }
    let mut journal = json!({
        "schema": "nf-build/1",
        "plan_sha": plan_sha,
        "nodes": journal_nodes,
        "artifacts": artifacts,
        "skipped": skipped,
        "verdict": verdict
    });
    if let Some(project_id) = req.get("project_id").and_then(|v| v.as_str()) {
        journal.as_object_mut().unwrap().insert("project_id".into(), json!(project_id));
    }
    let run_id = digest_value(&json!({
        "plan_sha": journal.get("plan_sha"),
        "nodes": journal.get("nodes"),
        "artifacts": journal.get("artifacts")
    }))?;
    journal.as_object_mut().unwrap().insert("run_id".into(), json!(run_id));
    let issues = validate("nf-build", &journal);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-BLD-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    Ok((0, json!({
        "schema": "nf-build-result/1",
        "graph": graph_out,
        "artifacts": journal.get("artifacts").cloned().unwrap_or_else(|| json!([])),
        "plan_sha": journal.get("plan_sha"),
        "journal": journal
    })))
}

pub(crate) fn transform_key(graph: &Value, output_node: &str) -> String {
    let edge = match graph.get("edges").and_then(|v| v.as_array()).and_then(|a| a.iter().find(|e| e.get("to").and_then(|v| v.as_str()) == Some(output_node))) {
        Some(e) => e,
        None => return String::new(),
    };
    let from = edge.get("from").and_then(|v| v.as_str()).unwrap_or("");
    graph
        .get("nodes")
        .and_then(|v| v.as_array())
        .and_then(|a| a.iter().find(|n| n.get("id").and_then(|v| v.as_str()) == Some(from)))
        .and_then(|n| n.get("cache_key"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string()
}

pub fn incremental(req: &Value) -> OpOutcome {
    let old = req_value(req, "old_graph")?;
    let new = req_value(req, "new_graph")?;
    let out_dir = opt_str(req, "out_dir")?;
    let old_outputs: BTreeMap<String, Value> = old.get("outputs").and_then(|v| v.as_array()).map(|a| a.iter().map(|o| (o.get("path").and_then(|v| v.as_str()).unwrap_or("").to_string(), o.clone())).collect()).unwrap_or_default();
    let new_outputs: BTreeMap<String, Value> = new.get("outputs").and_then(|v| v.as_array()).map(|a| a.iter().map(|o| (o.get("path").and_then(|v| v.as_str()).unwrap_or("").to_string(), o.clone())).collect()).unwrap_or_default();
    let mut rebuild = Vec::new();
    let mut reuse = Vec::new();
    let mut missing = Vec::new();
    for (path, o) in &new_outputs {
        let prev = match old_outputs.get(path) {
            Some(p) => p,
            None => { rebuild.push(path.clone()); continue; }
        };
        let old_key = transform_key(old, prev.get("node").and_then(|v| v.as_str()).unwrap_or(""));
        let new_key = transform_key(new, o.get("node").and_then(|v| v.as_str()).unwrap_or(""));
        if old_key.is_empty() || old_key != new_key {
            rebuild.push(path.clone());
            continue;
        }
        let old_sha = prev.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
        if old_sha == sha256_hex(b"") {
            rebuild.push(path.clone());
            continue;
        }
        if let Some(dir) = out_dir.as_ref() {
            let p = PathBuf::from(dir.replace('\\', "/")).join(path.replace('/', std::path::MAIN_SEPARATOR_STR));
            match std::fs::read(&p) {
                Ok(bytes) if sha256_hex(&bytes) == old_sha => reuse.push(path.clone()),
                Ok(_) => rebuild.push(path.clone()),
                Err(_) => missing.push(path.clone()),
            }
        } else {
            reuse.push(path.clone());
        }
    }
    let stale: Vec<String> = old_outputs.keys().filter(|k| !new_outputs.contains_key(*k)).cloned().collect();
    Ok((0, json!({"schema": "nf-incremental-plan/1", "rebuild": rebuild, "reuse": reuse, "stale": stale, "missing": missing, "summary": {"rebuild": rebuild.len() as u64, "reuse": reuse.len() as u64, "stale": stale.len() as u64}})))
}

pub(crate) fn profile_outputs(profile: &str, formats: &[String]) -> Vec<Value> {
    formats
        .iter()
        .map(|f| {
            let ext = match f.as_str() {
                "html" => "html",
                "epub" => "epub",
                "docx" => "docx",
                "json" => "json",
                _ => "md",
            };
            json!({"path": format!("{profile}/index.{ext}"), "format": f, "profile": profile})
        })
        .collect()
}

pub fn export_profile(req: &Value) -> OpOutcome {
    let profile = opt_str(req, "profile")?.unwrap_or("default");
    if !matches!(profile, "default" | "accessible" | "print" | "mobile" | "large-print") {
        return Err(CoreError::new("NF-PROF-001").with_message(format!("未知 profile：{profile}")).with_exit(1));
    }
    let formats: Vec<String> = req
        .get("formats")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect())
        .unwrap_or_else(|| vec!["html".to_string(), "epub".to_string()]);
    let out_dir = opt_str(req, "out_dir")?.ok_or_else(|| usage("export-profile 需要 out_dir"))?;
    let mut sub = req.clone();
    let obj = sub.as_object_mut().unwrap();
    obj.insert("outputs".into(), Value::Array(profile_outputs(profile, &formats)));
    obj.insert("out_dir".into(), Value::String(out_dir.to_string()));
    let (code, mut result) = run(&sub)?;
    if code != 0 {
        return Ok((code, result));
    }
    result.as_object_mut().unwrap().insert("profile".into(), Value::String(profile.to_string()));
    Ok((0, result))
}

pub fn export_accessible(req: &Value) -> OpOutcome {
    let sdir = req_value(req, "sdir")?;
    let report = sdir::validate_sdir_value(sdir);
    if report.has_error() {
        return Ok((1, report.to_value()));
    }
    let mut errors: Vec<String> = Vec::new();
    let mut warnings: Vec<String> = Vec::new();
    let mut flat: Vec<&Value> = Vec::new();
    fn walk<'a>(v: &'a Value, out: &mut Vec<&'a Value>) {
        out.push(v);
        for c in v.get("children").and_then(|x| x.as_array()).into_iter().flatten() {
            walk(c, out);
        }
    }
    if let Some(root) = sdir.get("blocks").and_then(|b| b.get(0)) {
        walk(root, &mut flat);
    }
    let mut orders = BTreeSet::new();
    for b in &flat {
        let ty = b.get("type").and_then(|v| v.as_str()).unwrap_or("");
        let id = b.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if ty == "figure" && b.get("text").and_then(|v| v.as_str()).unwrap_or("").trim().is_empty() {
            errors.push(format!("图 {id} 缺 alt"));
        }
        if ty == "table" {
            let header = b.get("attrs").and_then(|a| a.get("header")).and_then(|v| v.as_bool()).unwrap_or(false);
            if !header {
                errors.push(format!("表 {id} 缺表头"));
            }
        }
        if let Some(a) = sdir
            .get("accessibility")
            .and_then(|v| v.as_array())
            .and_then(|a| a.iter().find(|x| x.get("block").and_then(|v| v.as_str()) == Some(id)))
        {
            if let Some(o) = a.get("reading_order").and_then(|v| v.as_u64()) {
                if !orders.insert(o) {
                    errors.push(format!("块 {id} reading_order 重复"));
                }
            }
            if let Some(missing) = a.get("missing").and_then(|v| v.as_array()) {
                for m in missing {
                    if let Some(s) = m.as_str() {
                        warnings.push(format!("块 {id} 缺 {s}"));
                    }
                }
            }
        }
    }
    if sdir.get("meta").and_then(|m| m.get("lang")).and_then(|v| v.as_str()).unwrap_or("und") == "und" {
        warnings.push("文档未声明语言（lang=und）".to_string());
    }
    if !errors.is_empty() {
        let mut rep = Report::new("L0", sdir, "accessible-export", "accessible");
        for e in &errors {
            rep.error("NF-PROF-001", "$.blocks", e);
        }
        return Ok((1, rep.to_value()));
    }
    let formats: Vec<String> = req
        .get("formats")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect())
        .unwrap_or_else(|| vec!["html".to_string(), "epub".to_string(), "docx".to_string()]);
    let out_dir = opt_str(req, "out_dir")?.ok_or_else(|| usage("export-accessible 需要 out_dir"))?;
    let mut sub = req.clone();
    let obj = sub.as_object_mut().unwrap();
    obj.insert("outputs".into(), Value::Array(profile_outputs("accessible", &formats)));
    obj.insert("out_dir".into(), Value::String(out_dir.to_string()));
    let (code, mut result) = run(&sub)?;
    if code != 0 {
        return Ok((code, result));
    }
    result.as_object_mut().unwrap().insert("profile".into(), Value::String("accessible".into()));
    result.as_object_mut().unwrap().insert(
        "accessibility".into(),
        json!({"errors": 0, "warnings": warnings, "checks": ["alt", "table_header", "reading_order", "lang", "schema"]}),
    );
    Ok((0, result))
}

pub fn export_profile_op(req: &Value) -> OpOutcome { export_profile(req) }
pub fn export_accessible_op(req: &Value) -> OpOutcome { export_accessible(req) }
