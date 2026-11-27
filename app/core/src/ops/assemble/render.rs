use super::*;

pub(crate) fn plan_report(plan: &Value, code: &str, path: &str, message: &str) -> Value {
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

pub(crate) fn check_plan(plan: &Value) -> Option<Value> {
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

pub(crate) fn normalize_input(value: &str) -> String {
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

pub(crate) fn render_table(value: &str) -> String {
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

pub(crate) fn slot_by_id(spec: &Value) -> BTreeMap<String, Value> {
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

pub(crate) fn selected_slots(_spec: &Value, plan: &Value, stage: Option<&str>) -> Option<BTreeSet<String>> {
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

pub(crate) struct RenderedSection {
    pub(crate) heading: String,
    pub(crate) body: String,
    pub(crate) slots: Vec<Value>,
    pub(crate) missing: Vec<String>,
}

pub(crate) fn section_slot_ids(sec: &Value) -> Vec<String> {
    sec.get("slots")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .filter_map(|s| s.as_str().map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default()
}

pub(crate) fn slot_visible(slot: &Value, inputs: &Map<String, Value>) -> bool {
    let Some(cond) = slot.get("visible_if") else { return true };
    let field = cond.get("slot").and_then(|v| v.as_str()).unwrap_or("");
    let equals = cond.get("equals").and_then(|v| v.as_str()).unwrap_or("");
    if field.is_empty() { return true }
    inputs.get(field).and_then(|v| v.as_str()) == Some(equals)
}

pub(crate) fn render_section(
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
        if !slot_visible(slot, inputs) {
            slots.push(json!({"id": slot_id, "section": sid, "chars": 0}));
            continue;
        }
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
pub(crate) fn heading_lines(markdown: &str) -> Vec<(usize, usize)> {
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
pub(crate) fn section_span(base: &str, heading: &str, level: usize) -> Option<(usize, usize)> {
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

pub(crate) fn merged_slot_meta(spec: &Value, rendered: &BTreeMap<String, RenderedSection>) -> Vec<Value> {
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
