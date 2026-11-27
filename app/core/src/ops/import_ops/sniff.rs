use super::*;

pub const LOW_CONFIDENCE: u32 = 60;

#[derive(Clone, Debug)]
pub struct Sniff {
    pub format: String,
    pub confidence: u32,
    pub candidates: Vec<(String, u32)>,
}

pub(crate) const UNSUPPORTED: &[&str] = &["html", "docx", "pdf", "ocr", "epub", "xlsx", "pptx"];

pub(crate) fn add_signal(cands: &mut BTreeMap<String, u32>, format: &str, confidence: u32) {
    let e = cands.entry(format.to_string()).or_insert(0);
    if confidence > *e {
        *e = confidence;
    }
}

pub(crate) fn ext_of(name: &str) -> String {
    let base = name.rsplit('/').next().unwrap_or(name);
    match base.rsplit_once('.') {
        Some((_, ext)) => ext.to_ascii_lowercase(),
        None => String::new(),
    }
}

pub(crate) fn ext_format(ext: &str) -> Option<&'static str> {
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

pub(crate) fn mime_format(mime: &str) -> Option<&'static str> {
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

pub(crate) fn decode_utf16(bytes: &[u8], little_endian: bool) -> Option<String> {
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

pub(crate) fn normalize_text(bytes: &[u8]) -> Result<String, CoreError> {
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

pub(crate) fn content_signals(text: &str, cands: &mut BTreeMap<String, u32>) {
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

pub(crate) fn unsupported_error(format: &str) -> CoreError {
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
