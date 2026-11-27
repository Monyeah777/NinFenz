use super::*;

pub fn assemble(req: &Value) -> OpOutcome {
    let plan = req_value(req, "plan")?;
    let spec = req_value(req, "spec")?;
    if let Some(report) = check_plan(plan) {
        return Ok((1, report));
    }
    let spec_report = validate_spec(spec);
    if spec_report.has_error() {
        return Ok((1, spec_report.to_value()));
    }
    let inputs: Map<String, Value> = match req.get("inputs") {
        None | Some(Value::Null) => Map::new(),
        Some(Value::Object(m)) => m.clone(),
        Some(_) => return Err(usage("请求字段 inputs 必须是 object")),
    };
    for (k, v) in inputs.iter() {
        if !v.is_string() {
            return Ok((
                1,
                plan_report(
                    plan,
                    "NF-ASM-003",
                    &format!("$.inputs.{k}"),
                    "inputs 的值必须是字符串",
                ),
            ));
        }
    }
    let stage = opt_str(req, "stage")?;
    let block = opt_str(req, "block")?;
    if let Some(st) = stage {
        let exists = plan
            .get("steps")
            .and_then(|v| v.as_array())
            .map(|a| {
                a.iter()
                    .any(|s| s.get("stage").and_then(|v| v.as_str()) == Some(st))
            })
            .unwrap_or(false);
        if !exists {
            return Ok((
                1,
                plan_report(
                    plan,
                    "NF-ASM-003",
                    "$.stage",
                    &format!("plan 中不存在 stage {st}"),
                ),
            ));
        }
    }
    let sections: Vec<Value> = spec
        .get("sections")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let mut ordered = sections;
    ordered.sort_by_key(|s| s.get("order").and_then(|v| v.as_i64()).unwrap_or(0));
    let slot_map = slot_by_id(spec);
    let heading_level = spec
        .get("heading_level")
        .and_then(|v| v.as_u64())
        .unwrap_or(2) as usize;
    let allowed = selected_slots(spec, plan, stage);
    let plan_slots: BTreeSet<String> = plan
        .get("slots")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .filter_map(|s| s.as_str().map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default();

    let markdown;
    let mut rendered_by_id: BTreeMap<String, RenderedSection> = BTreeMap::new();
    let mut missing: Vec<String> = Vec::new();

    if let Some(b) = block {
        let sec = match ordered
            .iter()
            .find(|s| s.get("id").and_then(|v| v.as_str()) == Some(b))
        {
            Some(s) => s.clone(),
            None => {
                return Ok((
                    1,
                    plan_report(
                        plan,
                        "NF-ASM-004",
                        "$.block",
                        &format!("块级编辑目标节不存在：{b}"),
                    ),
                ))
            }
        };
        let base = match opt_str(req, "base_markdown")? {
            Some(s) => s,
            None => {
                return Ok((
                    1,
                    plan_report(
                        plan,
                        "NF-ASM-004",
                        "$.base_markdown",
                        "block 给定时必须提供 base_markdown（只替换该节、其余字节保留）",
                    ),
                ))
            }
        };
        let rendered = match render_section(&sec, &slot_map, &inputs, heading_level, plan) {
            Ok(r) => r,
            Err(report) => return Ok((1, report)),
        };
        let (start_line, end_line) = match section_span(base, &rendered.heading, heading_level) {
            Some(s) => s,
            None => {
                return Ok((
                    1,
                    plan_report(
                        plan,
                        "NF-ASM-004",
                        "$.base_markdown",
                        &format!("base_markdown 中找不到目标节标题：{}", rendered.heading),
                    ),
                ))
            }
        };
        let mut seg: Vec<String> = if rendered.body.is_empty() {
            vec![rendered.heading.clone()]
        } else {
            vec![
                rendered.heading.clone(),
                String::new(),
                rendered.body.clone(),
            ]
        };
        let lines: Vec<String> = base.split('\n').map(|s| s.to_string()).collect();
        if end_line < lines.len() {
            seg.push(String::new());
        }
        let mut new_lines: Vec<String> = Vec::with_capacity(lines.len() + seg.len());
        new_lines.extend_from_slice(&lines[..start_line]);
        new_lines.extend(seg);
        new_lines.extend_from_slice(&lines[end_line..]);
        markdown = new_lines.join("\n");
        missing.extend(rendered.missing.clone());
        rendered_by_id.insert(b.to_string(), rendered);
    } else {
        let mut blocks: Vec<String> = Vec::new();
        for sec in &ordered {
            if let Some(allowed) = &allowed {
                let sec_slot_ids = section_slot_ids(sec);
                let hit = sec_slot_ids.iter().any(|id| allowed.contains(id))
                    || plan_slots.is_empty();
                if !hit {
                    continue;
                }
            }
            let rendered = match render_section(sec, &slot_map, &inputs, heading_level, plan) {
                Ok(r) => r,
                Err(report) => return Ok((1, report)),
            };
            let body = rendered.body.clone();
            let text = if body.is_empty() {
                rendered.heading.clone()
            } else {
                format!("{}\n\n{}", rendered.heading, body)
            };
            blocks.push(text);
            missing.extend(rendered.missing.clone());
            let sid = sec.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
            rendered_by_id.insert(sid, rendered);
        }
        markdown = if blocks.is_empty() {
            String::new()
        } else {
            format!("{}\n", blocks.join("\n\n"))
        };
    }

    let meta = build_meta(
        plan,
        spec,
        &markdown,
        merged_slot_meta(spec, &rendered_by_id),
        missing,
        stage,
        block,
    );
    let meta_issues = schema_validate("nf-assemble-result", &meta);
    if !meta_issues.is_empty() {
        return Err(CoreError::new("NF-E-002")
            .with_message(format!(
                "assemble 元数据未通过 nf-assemble-result schema 自检: {}",
                crate::schema::first_issue_text(&meta_issues)
            ))
            .with_exit(3));
    }
    if let Some(out) = opt_str(req, "out_dir")? {
        let dir = resolve_path(out);
        crate::fsutil::ensure_dir(&dir)?;
        crate::fsutil::write_bytes(&dir.join("result.md"), markdown.as_bytes())?;
        crate::fsutil::write_json_canonical(&dir.join("result.meta.json"), &meta)?;
    }
    Ok((0, json!({"markdown": markdown, "meta": meta})))
}

pub(crate) fn build_meta(
    plan: &Value,
    spec: &Value,
    markdown: &str,
    slots: Vec<Value>,
    missing: Vec<String>,
    stage: Option<&str>,
    block: Option<&str>,
) -> Value {
    let plan_digest = plan
        .get("digest")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let spec_digest = digest_value(spec)
        .unwrap_or_else(|_| crate::canonical::digest_allow_float(spec));
    let mut meta = Map::new();
    meta.insert("schema".into(), Value::String("nf-assemble-result/1".into()));
    meta.insert("plan_digest".into(), Value::String(plan_digest));
    meta.insert("spec_digest".into(), Value::String(spec_digest));
    meta.insert(
        "markdown_digest".into(),
        Value::String(sha256_hex(markdown.as_bytes())),
    );
    meta.insert("slots".into(), Value::Array(slots));
    meta.insert(
        "missing".into(),
        Value::Array(missing.iter().map(|s| Value::String(s.clone())).collect()),
    );
    if let Some(st) = stage {
        meta.insert("stage".into(), Value::String(st.to_string()));
    }
    if let Some(b) = block {
        meta.insert("block".into(), Value::String(b.to_string()));
    }
    Value::Object(meta)
}
