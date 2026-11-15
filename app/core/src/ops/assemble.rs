//! 装配与校验：assemble（确定性 Markdown 渲染 + nf-assemble-result/1）/ validate（L0/L1/L2）。

use crate::canonical::{digest_value, digest_with_excludes, parse_json_bytes, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::ops::{opt_str, report_level, req_str, req_value, resolve_path, usage};
use crate::report::Report;
use crate::schema::validate as schema_validate;
use crate::ops::spec::{eval_constraint, validate_spec};
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::io::Write;

fn plan_report(plan: &Value, code: &str, path: &str, message: &str) -> Value {
    let refid = plan
        .get("pipeline")
        .and_then(|p| p.get("id"))
        .and_then(|v| v.as_str())
        .unwrap_or("$")
        .to_string();
    let mut report = Report::new("L0", plan, "assembly-plan", &refid);
    report.error(code, path, message);
    report.to_value()
}

fn check_plan(plan: &Value) -> Option<Value> {
    let issues = schema_validate("nf-assembly-plan", plan);
    if !issues.is_empty() {
        let refid = plan
            .get("pipeline")
            .and_then(|p| p.get("id"))
            .and_then(|v| v.as_str())
            .unwrap_or("$")
            .to_string();
        let mut report = Report::new("L0", plan, "assembly-plan", &refid);
        report.extend_schema_issues("NF-ASM-003", &issues);
        return Some(report.to_value());
    }
    let declared = plan.get("digest").and_then(|v| v.as_str()).unwrap_or("");
    match digest_with_excludes(plan, &["digest".to_string()]) {
        Ok(actual) if actual != declared => Some(plan_report(
            plan,
            "NF-ASM-001",
            "$.digest",
            &format!("plan digest 不符：声明 {declared}，实际 {actual}"),
        )),
        Err(e) => Some(plan_report(
            plan,
            "NF-ASM-001",
            "$.digest",
            &format!("plan digest 无法复算：{}", e.message),
        )),
        _ => None,
    }
}

fn normalize_input(value: &str) -> String {
    value.replace("\r\n", "\n").replace('\r', "\n")
}

pub fn render_slot(slot: &Value, raw: &str) -> Result<String, String> {
    let kind = slot.get("kind").and_then(|v| v.as_str()).unwrap_or("text");
    let value = normalize_input(raw);
    match kind {
        "text" => Ok(value),
        "list" => {
            let mut out = String::new();
            for line in value.split('\n') {
                let t = line.trim();
                if t.is_empty() {
                    continue;
                }
                out.push_str("- ");
                out.push_str(t.trim_start_matches("- ").trim());
                out.push('\n');
            }
            Ok(out.trim_end_matches('\n').to_string())
        }
        "table" => Ok(render_table(&value)),
        "code" => {
            let lang = slot.get("lang").and_then(|v| v.as_str()).unwrap_or("text");
            let mut max_run = 0usize;
            let mut run = 0usize;
            for ch in value.chars() {
                if ch == '\u{60}' {
                    run += 1;
                    max_run = max_run.max(run);
                } else {
                    run = 0;
                }
            }
            let fence = "\u{60}".repeat((max_run + 1).max(3));
            Ok(format!("{fence}{lang}\n{value}\n{fence}"))
        }
        "json" => {
            let parsed = parse_json_bytes(value.as_bytes())
                .map_err(|e| format!("json 槽位内容不是合法 JSON: {}", e.message))?;
            let canonical = crate::canonical::canonical_string(&parsed)
                .map_err(|e| format!("json 槽位内容含非法值: {}", e.message))?;
            let fence = "\u{60}".repeat(3);
            Ok(format!("{fence}json\n{canonical}\n{fence}"))
        }
        other => Err(format!("未知槽位 kind {other}")),
    }
}

fn render_table(value: &str) -> String {
    if value.trim().is_empty() {
        return String::new();
    }
    let lines: Vec<&str> = value.split('\n').filter(|l| !l.trim().is_empty()).collect();
    if lines.is_empty() {
        return String::new();
    }
    let sep = if lines.iter().any(|l| l.contains('\t')) {
        '\t'
    } else {
        ','
    };
    let rows: Vec<Vec<String>> = lines
        .iter()
        .map(|l| l.split(sep).map(|c| c.trim().replace('|', "\\|")).collect())
        .collect();
    let cols = rows.iter().map(|r| r.len()).max().unwrap_or(0);
    if cols == 0 {
        return String::new();
    }
    let mut out = String::new();
    let header = &rows[0];
    out.push('|');
    for c in 0..cols {
        out.push(' ');
        out.push_str(header.get(c).map(|s| s.as_str()).unwrap_or(""));
        out.push_str(" |");
    }
    out.push('\n');
    out.push('|');
    for _ in 0..cols {
        out.push_str("---|");
    }
    for r in rows.iter().skip(1) {
        out.push('\n');
        out.push('|');
        for c in 0..cols {
            out.push(' ');
            out.push_str(r.get(c).map(|s| s.as_str()).unwrap_or(""));
            out.push_str(" |");
        }
    }
    out
}

fn slot_by_id(spec: &Value) -> BTreeMap<String, Value> {
    spec.get("slots")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|s| {
                    let id = s.get("id")?.as_str()?.to_string();
                    Some((id, s.clone()))
                })
                .collect()
        })
        .unwrap_or_default()
}

fn selected_slots(_spec: &Value, plan: &Value, stage: Option<&str>) -> Option<BTreeSet<String>> {
    let stage = stage?;
    let mut allowed: BTreeSet<String> = BTreeSet::new();
    let mut any_declared = false;
    if let Some(steps) = plan.get("steps").and_then(|v| v.as_array()) {
        for s in steps {
            if s.get("stage").and_then(|v| v.as_str()) != Some(stage) {
                continue;
            }
            if let Some(list) = s
                .get("params")
                .and_then(|p| p.get("slots"))
                .and_then(|v| v.as_array())
            {
                any_declared = true;
                for id in list {
                    if let Some(id) = id.as_str() {
                        allowed.insert(id.to_string());
                    }
                }
            }
        }
    }
    if any_declared {
        Some(allowed)
    } else {
        None
    }
}

struct RenderedSection {
    heading: String,
    body: String,
    slots: Vec<Value>,
    missing: Vec<String>,
}

fn section_slot_ids(sec: &Value) -> Vec<String> {
    sec.get("slots")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .filter_map(|s| s.as_str().map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default()
}

fn render_section(
    sec: &Value,
    slot_map: &BTreeMap<String, Value>,
    inputs: &Map<String, Value>,
    heading_level: usize,
    plan: &Value,
) -> Result<RenderedSection, Value> {
    let sid = sec.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let title = sec.get("title").and_then(|v| v.as_str()).unwrap_or("");
    let heading = format!("{} {}", "#".repeat(heading_level), title);
    let mut parts: Vec<String> = Vec::new();
    let mut slots: Vec<Value> = Vec::new();
    let mut missing: Vec<String> = Vec::new();
    for slot_id in section_slot_ids(sec) {
        let slot = match slot_map.get(&slot_id) {
            Some(s) => s,
            None => continue,
        };
        let raw = inputs.get(&slot_id).and_then(|v| v.as_str());
        match raw {
            Some(v) => match render_slot(slot, v) {
                Ok(text) => {
                    slots.push(json!({
                        "id": slot_id,
                        "section": sid,
                        "chars": text.chars().count() as u64,
                    }));
                    parts.push(text);
                }
                Err(msg) => {
                    return Err(plan_report(
                        plan,
                        "NF-ASM-003",
                        &format!("$.spec.slots[{slot_id}]"),
                        &format!("槽位 {slot_id} 渲染失败：{msg}"),
                    ))
                }
            },
            None => {
                slots.push(json!({"id": slot_id, "section": sid, "chars": 0}));
                let required = slot
                    .get("required")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                if required {
                    return Err(plan_report(
                        plan,
                        "NF-ASM-002",
                        &format!("$.inputs.{slot_id}"),
                        &format!("必填槽位 {slot_id} 缺失（section {sid}）"),
                    ));
                }
                missing.push(slot_id);
            }
        }
    }
    Ok(RenderedSection {
        heading,
        body: parts.join("\n\n"),
        slots,
        missing,
    })
}

/// fence-aware 标题行扫描：返回 (line_idx, level)。
fn heading_lines(markdown: &str) -> Vec<(usize, usize)> {
    let mut out = Vec::new();
    let mut in_fence = false;
    let mut fence_ch = '\0';
    let mut fence_n = 0usize;
    for (i, line) in markdown.split('\n').enumerate() {
        let t = line.trim();
        if in_fence {
            let count = t.chars().take_while(|c| *c == fence_ch).count();
            if count >= fence_n && count > 0 && t.chars().skip(count).all(|c| c == fence_ch) {
                in_fence = false;
            }
            continue;
        }
        if t.starts_with('\u{60}') || t.starts_with('~') {
            let ch = t.chars().next().unwrap();
            let n = t.chars().take_while(|c| *c == ch).count();
            if n >= 3 {
                in_fence = true;
                fence_ch = ch;
                fence_n = n;
                continue;
            }
        }
        let level = t.chars().take_while(|c| *c == '#').count();
        if (1..=6).contains(&level) && (t.len() == level || t.chars().nth(level) == Some(' ')) {
            out.push((i, level));
        }
    }
    out
}

/// 在 base_markdown 中定位某节标题行及其结束行（下一个同级/更高级标题前）。
fn section_span(base: &str, heading: &str, level: usize) -> Option<(usize, usize)> {
    let lines: Vec<&str> = base.split('\n').collect();
    let heads = heading_lines(base);
    let start = heads
        .iter()
        .find(|(idx, lvl)| *lvl == level && lines.get(*idx).map(|l| l.trim_end()) == Some(heading.trim_end()))
        .map(|(idx, _)| *idx)?;
    let end = heads
        .iter()
        .find(|(idx, lvl)| *idx > start && *lvl <= level)
        .map(|(idx, _)| *idx)
        .unwrap_or(lines.len());
    Some((start, end))
}

fn merged_slot_meta(spec: &Value, rendered: &BTreeMap<String, RenderedSection>) -> Vec<Value> {
    let mut chars_by_id: BTreeMap<String, u64> = BTreeMap::new();
    for r in rendered.values() {
        for s in &r.slots {
            let id = s.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
            let chars = s.get("chars").and_then(|v| v.as_u64()).unwrap_or(0);
            chars_by_id.insert(id, chars);
        }
    }
    spec.get("slots")
        .and_then(|v| v.as_array())
        .map(|slots| {
            slots
                .iter()
                .map(|s| {
                    let id = s.get("id").and_then(|v| v.as_str()).unwrap_or("");
                    let section = s.get("section").and_then(|v| v.as_str()).unwrap_or("");
                    json!({
                        "id": id,
                        "section": section,
                        "chars": chars_by_id.get(id).copied().unwrap_or(0),
                    })
                })
                .collect()
        })
        .unwrap_or_default()
}

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

fn build_meta(
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


/// 提取各 section 在 markdown 中的正文（L1 契约求值用）。
fn section_chunks(markdown: &str, spec: &Value) -> BTreeMap<String, String> {
    let level = spec
        .get("heading_level")
        .and_then(|v| v.as_u64())
        .unwrap_or(2) as usize;
    let sections: Vec<(String, String)> = spec
        .get("sections")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|s| {
                    Some((
                        s.get("id")?.as_str()?.to_string(),
                        format!("{} {}", "#".repeat(level), s.get("title")?.as_str()?),
                    ))
                })
                .collect()
        })
        .unwrap_or_default();
    let lines: Vec<&str> = markdown.split('\n').collect();
    let mut headings_at: Vec<(usize, usize)> = Vec::new(); // (line_idx, level)
    let mut in_fence = false;
    let mut fence_ch = '\0';
    let mut fence_n = 0usize;
    for (i, line) in lines.iter().enumerate() {
        let t = line.trim();
        if in_fence {
            let count = t.chars().take_while(|c| *c == fence_ch).count();
            if count >= fence_n && t.chars().skip(count).all(|c| c == fence_ch) {
                in_fence = false;
            }
            continue;
        }
        if t.starts_with('\u{60}') || t.starts_with('~') {
            let ch = t.chars().next().unwrap();
            let n = t.chars().take_while(|c| *c == ch).count();
            if n >= 3 {
                in_fence = true;
                fence_ch = ch;
                fence_n = n;
                continue;
            }
        }
        let h = t.chars().take_while(|c| *c == '#').count();
        if (1..=6).contains(&h) && (t.len() == h || t.chars().nth(h) == Some(' ')) {
            headings_at.push((i, h));
        }
    }
    let mut out = BTreeMap::new();
    for (sid, heading) in &sections {
        let start = lines
            .iter()
            .position(|l| l.trim_end() == heading.trim_end());
        if let Some(start) = start {
            let end = headings_at
                .iter()
                .find(|(idx, lvl)| *idx > start && *lvl <= level)
                .map(|(idx, _)| *idx)
                .unwrap_or(lines.len());
            let text = lines[start + 1..end].join("\n");
            out.insert(sid.clone(), text.trim().to_string());
        } else {
            out.insert(sid.clone(), String::new());
        }
    }
    out
}

fn l2_validate(markdown: &str, spec: &Value, plan: &Value) -> Result<Vec<Value>, CoreError> {
    let cmd = std::env::var("NF_APP_L2_CMD").unwrap_or_default();
    if cmd.is_empty() {
        return Err(CoreError::new("NF-VAL-005")
            .with_message("L2（仓库协议层）校验不可用：未配置 NF_APP_L2_CMD")
            .with_fix("安装 nf CLI 并设置 NF_APP_L2_CMD，或降级为 L1 并记录")
            .with_exit(4));
    }
    let req = json!({"op": "validate", "level": "L2", "markdown": markdown, "spec": spec, "plan": plan});
    let bytes = crate::canonical::canonical_bytes(&req)?;
    let mut child = std::process::Command::new(&cmd)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| {
            CoreError::new("NF-VAL-005")
                .with_message(format!("L2 命令启动失败：{e}"))
                .with_exit(4)
        })?;
    if let Some(stdin) = child.stdin.as_mut() {
        stdin.write_all(&bytes).map_err(|e| {
            CoreError::new("NF-VAL-005")
                .with_message(format!("L2 命令写入失败：{e}"))
                .with_exit(4)
        })?;
    }
    let output = child.wait_with_output().map_err(|e| {
        CoreError::new("NF-VAL-005")
            .with_message(format!("L2 命令执行失败：{e}"))
            .with_exit(4)
    })?;
    if !output.status.success() {
        return Err(CoreError::new("NF-VAL-005")
            .with_message("L2 命令非零退出")
            .with_exit(4));
    }
    let value = crate::canonical::parse_json_bytes(&output.stdout).map_err(|e| {
        CoreError::new("NF-VAL-005")
            .with_message(format!("L2 输出不是合法 JSON：{}", e.message))
            .with_exit(4)
    })?;
    let issues = value
        .get("issues")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    Ok(issues)
}

pub fn validate(req: &Value) -> OpOutcome {
    let markdown = req_str(req, "markdown")?;
    let spec = req_value(req, "spec")?;
    let plan = req_value(req, "plan")?;
    let level = report_level(req_str(req, "level")?);
    let spec_report = validate_spec(spec);
    if spec_report.has_error() {
        return Ok((1, spec_report.to_value()));
    }
    if let Some(report) = check_plan(plan) {
        return Ok((1, report));
    }
    let refid = plan
        .get("pipeline")
        .and_then(|p| p.get("id"))
        .and_then(|v| v.as_str())
        .unwrap_or("$")
        .to_string();
    let digest = sha256_hex(markdown.as_bytes());
    let mut report = Report::raw(&level, "assembly", &refid, &digest);

    // L0：结构（spec/plan 已在上面校验）
    let sections = spec
        .get("sections")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let chunks = section_chunks(markdown, spec);
    let level_n = spec
        .get("heading_level")
        .and_then(|v| v.as_u64())
        .unwrap_or(2) as usize;
    for (i, sec) in sections.iter().enumerate() {
        let title = sec.get("title").and_then(|v| v.as_str()).unwrap_or("");
        let expected = format!("{} {}", "#".repeat(level_n), title);
        if markdown
            .lines()
            .any(|l| l.trim_end() == expected.trim_end())
        {
            continue;
        }
        report.error(
            "NF-VAL-001",
            &format!("$.result.sections[{i}]"),
            &format!("缺少章节标题：{expected}"),
        );
    }

    if level == "L1" || level == "L2" {
        let slot_map = slot_by_id(spec);
        let acc_desc: BTreeMap<String, String> = spec
            .get("acceptance")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|a| {
                        Some((
                            a.get("id")?.as_str()?.to_string(),
                            a.get("description")?.as_str()?.to_string(),
                        ))
                    })
                    .collect()
            })
            .unwrap_or_default();
        for (i, sec) in sections.iter().enumerate() {
            let sid = sec.get("id").and_then(|v| v.as_str()).unwrap_or("");
            let chunk = chunks.get(sid).cloned().unwrap_or_default();
            let sec_slots: Vec<String> = sec
                .get("slots")
                .and_then(|v| v.as_array())
                .map(|a| {
                    a.iter()
                        .filter_map(|s| s.as_str().map(|s| s.to_string()))
                        .collect()
                })
                .unwrap_or_default();
            for (j, slot_id) in sec_slots.iter().enumerate() {
                let slot = match slot_map.get(slot_id) {
                    Some(s) => s,
                    None => continue,
                };
                if let Some(cs) = slot.get("constraints").and_then(|v| v.as_array()) {
                    for c in cs {
                        if let Err(msg) = eval_constraint(c, &chunk) {
                            report.error(
                                "NF-VAL-002",
                                &format!("result.sections[{i}].slots[{j}]"),
                                &format!("槽位 {slot_id} 约束失败：{msg}"),
                            );
                        }
                    }
                }
                if let Some(acc) = slot.get("acceptance").and_then(|v| v.as_array()) {
                    for a in acc {
                        let id = a.as_str().unwrap_or("");
                        match acc_desc.get(id) {
                            Some(desc) => report.info(
                                "NF-VAL-002",
                                &format!("result.sections[{i}].slots[{j}]"),
                                &format!("acceptance {id} 需人工复核：{desc}"),
                            ),
                            None => report.error(
                                "NF-VAL-002",
                                &format!("result.sections[{i}].slots[{j}]"),
                                &format!("引用了不存在的 acceptance {id}"),
                            ),
                        }
                    }
                }
            }
        }
    }

    if level == "L2" {
        let issues = l2_validate(markdown, spec, plan)?;
        for issue in issues {
            let code = issue.get("code").and_then(|v| v.as_str()).unwrap_or("NF-VAL-002");
            let severity = issue
                .get("severity")
                .and_then(|v| v.as_str())
                .unwrap_or("error");
            let path = issue
                .get("path")
                .and_then(|v| v.as_str())
                .unwrap_or("result");
            let message = issue
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("L2 校验失败");
            report.push(code, severity, path, message);
        }
    }
    Ok((0, report.to_value()))
}
