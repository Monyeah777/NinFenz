use super::*;

pub(crate) fn norm_title(s: &str) -> String {
    s.trim().trim_start_matches('#').trim().to_ascii_lowercase()
}

pub fn map_suggest(req: &Value) -> OpOutcome {
    let mut doc = req_value(req, "import")?.clone();
    if !doc.is_object() {
        return Err(usage("请求字段 import 必须是 object"));
    }
    let import_ref = doc
        .get("source")
        .and_then(|s| s.get("name"))
        .and_then(|v| v.as_str())
        .unwrap_or("$")
        .to_string();
    if let Some(report) = schema_report(
        "nf-import",
        &doc,
        "NF-VAL-001",
        "L0",
        "import",
        &import_ref,
    ) {
        return Ok((1, report));
    }
    let spec = match req.get("spec") {
        None | Some(Value::Null) => None,
        Some(v @ Value::Object(_)) => {
            if let Some(report) =
                schema_report("nf-md-spec", v, "NF-SPC-001", "L0", "md-spec", &ref_id_spec(v))
            {
                return Ok((1, report));
            }
            Some(v.clone())
        }
        Some(_) => return Err(usage("请求字段 spec 必须是 object")),
    };

    let headings = doc["structure"]["headings"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    let paragraphs = doc["structure"]["paragraphs"].as_u64().unwrap_or(0);
    let code_blocks = doc["structure"]["code_blocks"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    let tables = doc["structure"]["tables"]
        .as_array()
        .cloned()
        .unwrap_or_default();

    let spec_sections: Vec<Value> = spec
        .as_ref()
        .and_then(|s| s.get("sections"))
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let spec_slots: Vec<Value> = spec
        .as_ref()
        .and_then(|s| s.get("slots"))
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    let mut mappings: Vec<Value> = Vec::new();
    let mut unmapped: Vec<String> = Vec::new();

    for (i, h) in headings.iter().enumerate() {
        let title = h.get("text").and_then(|v| v.as_str()).unwrap_or("");
        if spec.is_some() {
            let nt = norm_title(title);
            if let Some(sec) = spec_sections
                .iter()
                .find(|s| norm_title(s.get("title").and_then(|v| v.as_str()).unwrap_or("")) == nt)
            {
                mappings.push(json!({
                    "from_kind": "heading",
                    "from_index": i,
                    "to_kind": "section",
                    "to_id": sec.get("id").and_then(|v| v.as_str()).unwrap_or(""),
                    "confidence": 90,
                    "rationale": "标题与 spec 章节标题精确匹配",
                }));
                continue;
            }
            if let Some(sec) = spec_sections.get(i) {
                mappings.push(json!({
                    "from_kind": "heading",
                    "from_index": i,
                    "to_kind": "section",
                    "to_id": sec.get("id").and_then(|v| v.as_str()).unwrap_or(""),
                    "confidence": 60,
                    "rationale": "无标题匹配，按出现顺序对应 spec 章节",
                }));
                continue;
            }
            unmapped.push(format!("heading[{i}]:{title}"));
        } else if i < 99 {
            mappings.push(json!({
                "from_kind": "heading",
                "from_index": i,
                "to_kind": "section",
                "to_id": format!("SEC-{:02}", i + 1),
                "confidence": 50,
                "rationale": "无 spec 快照：按标题序号生成草稿章节 id",
            }));
        } else {
            unmapped.push(format!("heading[{i}]:{title}"));
        }
    }

    for i in 0..paragraphs {
        let idx = i as usize;
        if let Some(slot) = spec_slots.get(idx) {
            mappings.push(json!({
                "from_kind": "paragraph",
                "from_index": idx,
                "to_kind": "slot",
                "to_id": slot.get("id").and_then(|v| v.as_str()).unwrap_or(""),
                "confidence": 55,
                "rationale": "无语言模型的首版规则：按段落序对应槽位序（需用户复核）",
            }));
        } else if idx < 99 {
            mappings.push(json!({
                "from_kind": "paragraph",
                "from_index": idx,
                "to_kind": "slot",
                "to_id": format!("SLT-{:02}", idx + 1),
                "confidence": 40,
                "rationale": "无 spec 快照：按段落序号生成草稿槽位 id",
            }));
        } else {
            unmapped.push(format!("paragraph[{idx}]"));
        }
    }

    for (i, cb) in code_blocks.iter().enumerate() {
        let lang = cb.get("lang").and_then(|v| v.as_str()).unwrap_or("");
        if i < 99 {
            mappings.push(json!({
                "from_kind": "code_block",
                "from_index": i,
                "to_kind": "example",
                "to_id": format!("EX-{:02}", i + 1),
                "confidence": 70,
                "rationale": format!("代码块（lang={lang}）作为示例候选"),
            }));
        } else {
            unmapped.push(format!("code_block[{i}]"));
        }
    }
    for (i, tb) in tables.iter().enumerate() {
        let cols = tb.get("columns").and_then(|v| v.as_u64()).unwrap_or(0);
        if i < 99 {
            mappings.push(json!({
                "from_kind": "table",
                "from_index": i,
                "to_kind": "structured",
                "to_id": format!("TBL-{:02}", i + 1),
                "confidence": 65,
                "rationale": format!("表格（{cols} 列）作为结构化数据候选"),
            }));
        } else {
            unmapped.push(format!("table[{i}]"));
        }
    }

    let suggested = json!({
        "mappings": mappings,
        "unmapped": unmapped,
    });
    let empty = mappings.is_empty();
    doc["suggested"] = suggested;
    if empty {
        let warnings = doc["warnings"].as_array_mut().expect("warnings 数组");
        warnings.push(json!({
            "code": "NF-MAP-001",
            "message": "无映射候选（已归入素材/未分类），需在映射向导里手动指定",
        }));
    }
    if let Some(report) = schema_report(
        "nf-import",
        &doc,
        "NF-VAL-001",
        "L0",
        "import",
        &import_ref,
    ) {
        return Ok((1, report));
    }
    let _ = float_issue(&mut Report::new("L0", &doc, "import", &import_ref), &doc, "NF-VAL-001");
    Ok((0, doc))
}

pub(crate) fn ref_id_spec(v: &Value) -> String {
    v.get("id").and_then(|x| x.as_str()).unwrap_or("$").to_string()
}


/// zero-slice：结构化解析 + spec 映射 + 例外；置信度/覆盖率为 0–100 整数。
pub fn zero_slice(req: &Value) -> OpOutcome {
    let text = req_str(req, "text")?;
    let doc = crate::zero_slice::parse_markdown(text);
    let mut slots = Vec::new();
    let mut sections = Vec::new();
    if let Some(spec) = req.get("spec").and_then(|v| v.as_object()) {
        if let Some(list) = spec.get("slots").and_then(|v| v.as_array()) {
            for item in list {
                let Some(obj) = item.as_object() else { continue };
                let id = obj.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let name = obj.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string();
                if id.is_empty() || name.is_empty() {
                    return Err(usage("spec.slots[] 必须带 id/name"));
                }
                slots.push(crate::zero_slice::SlotSpec {
                    id,
                    name,
                    required: obj.get("required").and_then(|v| v.as_bool()).unwrap_or(false),
                    max_chars: obj.get("budget").and_then(|b| b.get("max_chars")).and_then(|v| v.as_u64()).map(|v| v as usize),
                });
            }
        }
        if let Some(list) = spec.get("sections").and_then(|v| v.as_array()) {
            for item in list {
                let Some(obj) = item.as_object() else { continue };
                let id = obj.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let title = obj.get("title").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let slot_ids = obj.get("slots").and_then(|v| v.as_array())
                    .map(|a| a.iter().filter_map(|v| v.as_str().map(|s| s.to_string())).collect())
                    .unwrap_or_default();
                if !id.is_empty() && !title.is_empty() {
                    sections.push(crate::zero_slice::SectionSpec { id, title, slots: slot_ids });
                }
            }
        }
    }
    let spec = crate::zero_slice::Spec {
        id: req.get("spec").and_then(|v| v.get("id")).and_then(|v| v.as_str()).unwrap_or("freeform").to_string(),
        slots,
        sections,
    };
    let report = crate::zero_slice::infer(&spec, &doc);
    let sections: Vec<Value> = doc.sections.iter().map(|s| json!({
        "title": s.title,
        "chars": s.text().chars().count(),
    })).collect();
    let mappings: Vec<Value> = report.mappings.iter().map(|m| json!({
        "from_index": m.from_index,
        "from_title": m.from_title,
        "to_id": m.to_id,
        "to_name": m.to_name,
        "confidence": (m.confidence * 100.0).round() as u32,
        "rationale": m.rationale,
    })).collect();
    let exceptions: Vec<Value> = report.exceptions.iter().map(|e| json!({
        "text": e.text,
        "target": e.target,
        "reason": e.reason,
    })).collect();
    Ok((0, json!({
        "title": doc.title,
        "sections": sections,
        "mappings": mappings,
        "exceptions": exceptions,
        "coverage": (report.coverage * 100.0).round() as u32,
        "project": crate::zero_slice::to_project(&doc, &report, None),
    })))
}
