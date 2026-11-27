use super::*;

pub struct Extracted {
    pub text: Option<String>,
    pub text_digest: String,
    pub structure: markdown::MarkdownStructure,
    pub assets: Vec<Value>,
}

/// 按格式抽取（import 与 Adapter 扩展口共用）。
pub fn extract_format(format: &str, bytes: &[u8]) -> Result<Extracted, CoreError> {
    let l = limits();
    let mut out = Extracted {
        text: None,
        text_digest: sha256_hex(bytes),
        structure: markdown::MarkdownStructure::default(),
        assets: Vec::new(),
    };
    match format {
        "markdown" | "text" | "json" | "yaml" => {
            let text = normalize_text(bytes)?;
            if text.chars().count() as u64 > l.text_max_chars {
                return Err(CoreError::new("NF-IMP-003")
                    .with_message(format!(
                        "文本字符数超过上限 {}",
                        l.text_max_chars
                    ))
                    .with_exit(3));
            }
            out.structure = match format {
                "markdown" => markdown::extract(&text)?,
                "text" => markdown::plain_structure(&text),
                "json" => {
                    parse_json_bytes(text.as_bytes())?;
                    markdown::MarkdownStructure {
                        headings: vec![],
                        paragraphs: 1,
                        code_blocks: vec![],
                        tables: vec![],
                    }
                }
                "yaml" => {
                    let v = yaml::parse(&text)?;
                    markdown::MarkdownStructure {
                        headings: vec![],
                        paragraphs: yaml::top_entries(&v),
                        code_blocks: vec![],
                        tables: vec![],
                    }
                }
                _ => unreachable!(),
            };
            out.text_digest = sha256_hex(text.as_bytes());
            out.text = Some(text);
        }
        "zip" | "nftpl" | "nfpack" => {
            let entries = zipsec::read_zip_bytes(bytes)?;
            let mut assets: Vec<Value> = entries
                .iter()
                .map(|e| {
                    json!({
                        "path": e.name,
                        "sha256": sha256_hex(&e.data),
                        "size": e.data.len(),
                    })
                })
                .collect();
            assets.sort_by(|a, b| a["path"].as_str().cmp(&b["path"].as_str()));
            out.assets = assets;
        }
        other => return Err(unsupported_error(other)),
    }
    Ok(out)
}

pub(crate) fn build_source(req: &Value, file_name: &str, bytes: &[u8]) -> Result<Value, CoreError> {
    let mut source = Map::new();
    match req.get("source") {
        None | Some(Value::Null) => {}
        Some(Value::Object(m)) => {
            for key in ["kind", "name", "mime", "size", "sha256", "uri_kind"] {
                if let Some(v) = m.get(key) {
                    source.insert(key.to_string(), v.clone());
                }
            }
        }
        Some(_) => return Err(usage("请求字段 source 必须是 object")),
    }
    if !source.contains_key("kind") {
        source.insert("kind".into(), Value::String("file".into()));
    }
    if !source.contains_key("name") {
        source.insert("name".into(), Value::String(file_name.to_string()));
    }
    if !source.contains_key("size") {
        source.insert("size".into(), Value::from(bytes.len() as u64));
    }
    if !source.contains_key("sha256") {
        source.insert("sha256".into(), Value::String(sha256_hex(bytes)));
    }
    Ok(Value::Object(source))
}

pub fn import(req: &Value) -> OpOutcome {
    let file = req_str(req, "file")?;
    let file_path = resolve_path(file);
    let bytes = fsutil::read_bytes(&file_path, limits().pack_max_file_bytes)?;
    let file_name = file_path
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| file.to_string());
    let source = build_source(req, &file_name, &bytes)?;
    let mime = source.get("mime").and_then(|v| v.as_str());
    let sniffed = sniff(
        source.get("name").and_then(|v| v.as_str()).unwrap_or(&file_name),
        mime,
        Some(&bytes),
    )?
    .ok_or_else(|| {
        CoreError::new("NF-IMP-001")
            .with_message("导入格式无法识别（嗅探无任何候选）")
            .with_exit(3)
    })?;
    if UNSUPPORTED.contains(&sniffed.format.as_str()) {
        return Err(unsupported_error(&sniffed.format));
    }
    let extracted = extract_format(&sniffed.format, &bytes)?;
    let candidates: Vec<Value> = sniffed
        .candidates
        .iter()
        .map(|(f, c)| json!({"format": f, "confidence": c}))
        .collect();
    let mut warnings: Vec<Value> = Vec::new();
    if sniffed.confidence < LOW_CONFIDENCE {
        warnings.push(json!({
            "code": "NF-IMP-002",
            "message": format!(
                "嗅探置信度 {}% < {}%，需用户确认格式（候选: {}）",
                sniffed.confidence,
                LOW_CONFIDENCE,
                sniffed
                    .candidates
                    .iter()
                    .map(|(f, c)| format!("{f}:{c}%"))
                    .collect::<Vec<_>>()
                    .join(", ")
            ),
        }));
    }
    let mut doc = Map::new();
    doc.insert("schema".into(), Value::String("nf-import/1".into()));
    doc.insert("source".into(), source);
    doc.insert(
        "detected".into(),
        json!({
            "format": sniffed.format,
            "confidence": sniffed.confidence,
            "candidates": candidates,
        }),
    );
    if let Some(text) = &extracted.text {
        doc.insert("text".into(), Value::String(text.clone()));
    }
    doc.insert(
        "text_digest".into(),
        Value::String(extracted.text_digest),
    );
    doc.insert(
        "structure".into(),
        json!({
            "headings": extracted.structure.headings,
            "paragraphs": extracted.structure.paragraphs,
            "code_blocks": extracted.structure.code_blocks,
            "tables": extracted.structure.tables,
        }),
    );
    doc.insert("assets".into(), Value::Array(extracted.assets));
    doc.insert(
        "suggested".into(),
        json!({"mappings": [], "unmapped": []}),
    );
    doc.insert("warnings".into(), Value::Array(warnings));
    let doc = Value::Object(doc);
    if let Some(report) = schema_report(
        "nf-import",
        &doc,
        "NF-IMP-001",
        "L0",
        "import",
        &file_name,
    ) {
        return Ok((1, report));
    }
    Ok((0, doc))
}
