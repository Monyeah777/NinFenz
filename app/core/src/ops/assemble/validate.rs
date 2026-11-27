use super::*;

/// 提取各 section 在 markdown 中的正文（L1 契约求值用）。
pub(crate) fn section_chunks(markdown: &str, spec: &Value) -> BTreeMap<String, String> {
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

pub(crate) fn l2_validate(markdown: &str, spec: &Value, plan: &Value) -> Result<Vec<Value>, CoreError> {
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
