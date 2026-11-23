//! 导入/嗅探/映射（A3）：import-sniff / import / map-suggest。
//! 置信度为整数百分比 0–100（禁浮点，见 nf-import/1 schema 修订）。

use crate::canonical::{parse_json_bytes, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::limits::limits;
use crate::markdown;
use crate::ops::{float_issue, opt_str, req_str, req_value, resolve_path, schema_report, usage};
use crate::report::Report;
use crate::yaml;
use crate::zipsec;
use serde_json::{json, Map, Value};
use std::collections::BTreeMap;
use std::path::Path;

pub const LOW_CONFIDENCE: u32 = 60;

#[derive(Clone, Debug)]
pub struct Sniff {
    pub format: String,
    pub confidence: u32,
    pub candidates: Vec<(String, u32)>,
}

const UNSUPPORTED: &[&str] = &["html", "docx", "pdf", "ocr", "epub", "xlsx", "pptx"];

fn add_signal(cands: &mut BTreeMap<String, u32>, format: &str, confidence: u32) {
    let e = cands.entry(format.to_string()).or_insert(0);
    if confidence > *e {
        *e = confidence;
    }
}

fn ext_of(name: &str) -> String {
    let base = name.rsplit('/').next().unwrap_or(name);
    match base.rsplit_once('.') {
        Some((_, ext)) => ext.to_ascii_lowercase(),
        None => String::new(),
    }
}

fn ext_format(ext: &str) -> Option<&'static str> {
    Some(match ext {
        "md" | "markdown" | "mdown" => "markdown",
        "txt" | "text" | "log" => "text",
        "json" => "json",
        "yaml" | "yml" => "yaml",
        "zip" => "zip",
        "nftpl" => "nftpl",
        "nfpack" => "nfpack",
        "html" | "htm" => "html",
        "docx" => "docx",
        "pdf" => "pdf",
        "epub" => "epub",
        "xlsx" => "xlsx",
        "pptx" => "pptx",
        _ => return None,
    })
}

fn mime_format(mime: &str) -> Option<&'static str> {
    let m = mime.to_ascii_lowercase();
    Some(match m.as_str() {
        "text/markdown" | "text/x-markdown" => "markdown",
        "text/plain" => "text",
        "application/json" | "text/json" => "json",
        "application/yaml" | "text/yaml" | "application/x-yaml" | "text/x-yaml" => "yaml",
        "application/zip" | "application/x-zip-compressed" => "zip",
        "application/pdf" => "pdf",
        "text/html" => "html",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document" => "docx",
        "application/epub+zip" => "epub",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" => "xlsx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation" => "pptx",
        _ => return None,
    })
}

fn decode_utf16(bytes: &[u8], little_endian: bool) -> Option<String> {
    if bytes.len() % 2 != 0 {
        return None;
    }
    let mut units = Vec::with_capacity(bytes.len() / 2);
    for pair in bytes.chunks_exact(2) {
        units.push(if little_endian {
            u16::from_le_bytes([pair[0], pair[1]])
        } else {
            u16::from_be_bytes([pair[0], pair[1]])
        });
    }
    String::from_utf16(&units).ok()
}

fn normalize_text(bytes: &[u8]) -> Result<String, CoreError> {
    let decoded = if bytes.starts_with(&[0xFF, 0xFE]) {
        decode_utf16(&bytes[2..], true)
    } else if bytes.starts_with(&[0xFE, 0xFF]) {
        decode_utf16(&bytes[2..], false)
    } else {
        std::str::from_utf8(bytes)
            .ok()
            .map(|s| s.strip_prefix('\u{feff}').unwrap_or(s).to_string())
    };
    let text = decoded.ok_or_else(|| {
        CoreError::new("NF-IMP-001")
            .with_message("内容不是合法 UTF-8/UTF-16 文本，无法按文本格式导入（GB18030/Big5 请先转码）")
            .with_exit(3)
    })?;
    Ok(text.replace("\r\n", "\n").replace('\r', "\n"))
}

fn content_signals(text: &str, cands: &mut BTreeMap<String, u32>) {
    let trimmed = text.trim_start();
    if (trimmed.starts_with('{') || trimmed.starts_with('['))
        && parse_json_bytes(text.as_bytes()).is_ok()
    {
        add_signal(cands, "json", 90);
    }
    if let Ok(st) = markdown::extract(text) {
        if !st.headings.is_empty() || !st.code_blocks.is_empty() || !st.tables.is_empty() {
            add_signal(cands, "markdown", 82);
        }
    }
    let mut yamlish = false;
    for (i, line) in text.split('\n').enumerate() {
        let t = line.trim();
        if i == 0 && t == "---" {
            yamlish = true;
            break;
        }
        if let Some((k, _)) = t.split_once(':') {
            if !k.is_empty()
                && !k.contains(' ')
                && k.chars()
                    .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.'))
                && t.ends_with(':') || (k.len() < 64 && t.contains(": "))
            {
                yamlish = true;
                break;
            }
        }
    }
    if yamlish {
        add_signal(cands, "yaml", 80);
    }
    if !trimmed.is_empty()
        && trimmed
            .chars()
            .all(|c| c == '\n' || c == '\t' || !c.is_control())
    {
        // 纯文本只能算中等置信（<60）：命中时 import 会给 NF-IMP-002 warn 要求用户确认。
        add_signal(cands, "text", 55);
    }
}

/// 嗅探顺序：魔数 → MIME/扩展 → 内容特征（CONTRACT §5.2）。
pub fn sniff(
    name: &str,
    mime: Option<&str>,
    bytes: Option<&[u8]>,
) -> Result<Option<Sniff>, CoreError> {
    let mut cands: BTreeMap<String, u32> = BTreeMap::new();
    let mut text_for_content: Option<String> = None;

    if let Some(b) = bytes {
        if b.starts_with(b"PK\x03\x04") {
            let entries = zipsec::read_zip_bytes(b)?;
            let has = |needle: &str| entries.iter().any(|e| e.name == needle || e.name.ends_with(needle));
            let epub_mimetype = entries
                .iter()
                .find(|e| e.name == "mimetype")
                .map(|e| String::from_utf8_lossy(&e.data).trim().to_string());
            if has("nf-pack.json") {
                add_signal(&mut cands, "nfpack", 100);
            } else if has("nf-template.json") {
                add_signal(&mut cands, "nftpl", 100);
            } else if epub_mimetype.as_deref() == Some("application/epub+zip")
                || has("META-INF/container.xml")
            {
                add_signal(&mut cands, "epub", 100);
            } else if has("word/document.xml") {
                add_signal(&mut cands, "docx", 100);
            } else if has("xl/workbook.xml") {
                add_signal(&mut cands, "xlsx", 100);
            } else if has("ppt/presentation.xml") {
                add_signal(&mut cands, "pptx", 100);
            } else {
                add_signal(&mut cands, "zip", 95);
            }
        }
        if b.starts_with(b"%PDF-") {
            add_signal(&mut cands, "pdf", 100);
        }
        let head = &b[..b.len().min(1024)];
        let head_lower = String::from_utf8_lossy(head).to_ascii_lowercase();
        if head_lower.contains("<!doctype html") || head_lower.contains("<html") {
            add_signal(&mut cands, "html", 96);
        }
        if !b.starts_with(b"PK\x03\x04") && !b.starts_with(b"%PDF-") {
            if let Ok(text) = normalize_text(b) {
                content_signals(&text, &mut cands);
                text_for_content = Some(text);
            }
        }
    }
    let _ = &text_for_content;

    if let Some(m) = mime {
        if let Some(f) = mime_format(m) {
            add_signal(&mut cands, f, 75);
        }
    }
    if let Some(f) = ext_format(&ext_of(name)) {
        add_signal(&mut cands, f, 85);
    }

    if cands.is_empty() {
        return Ok(None);
    }
    let mut candidates: Vec<(String, u32)> = cands.into_iter().collect();
    candidates.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    let (format, confidence) = candidates[0].clone();
    Ok(Some(Sniff {
        format,
        confidence,
        candidates,
    }))
}

fn unsupported_error(format: &str) -> CoreError {
    CoreError::new("NF-IMP-004")
        .with_message(format!(
            "格式 {format} 的适配器本版本未实现（首版：text/markdown/json/yaml/zip/nftpl/nfpack）"
        ))
        .with_exit(3)
}

pub fn import_sniff(req: &Value) -> OpOutcome {
    let name = req_str(req, "name")?;
    let mime = opt_str(req, "mime")?;
    let file = opt_str(req, "file")?;
    let bytes_path = opt_str(req, "bytes_path")?;
    let bytes = if let Some(p) = file.or(bytes_path) {
        Some(fsutil::read_bytes(
            Path::new(&resolve_path(p)),
            limits().pack_max_file_bytes,
        )?)
    } else {
        None
    };
    let sniffed = sniff(name, mime, bytes.as_deref())?.ok_or_else(|| {
        CoreError::new("NF-IMP-001")
            .with_message("导入格式无法识别（嗅探无任何候选）")
            .with_exit(3)
    })?;
    if UNSUPPORTED.contains(&sniffed.format.as_str()) {
        return Err(unsupported_error(&sniffed.format));
    }
    let candidates: Vec<Value> = sniffed
        .candidates
        .iter()
        .map(|(f, c)| json!({"format": f, "confidence": c}))
        .collect();
    Ok((
        0,
        json!({
            "format": sniffed.format,
            "confidence": sniffed.confidence,
            "candidates": candidates,
        }),
    ))
}

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

fn build_source(req: &Value, file_name: &str, bytes: &[u8]) -> Result<Value, CoreError> {
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

fn norm_title(s: &str) -> String {
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

fn ref_id_spec(v: &Value) -> String {
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
