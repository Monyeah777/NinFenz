//! DOCX 导出（OOXML / WordprocessingML，最小但可被 Word/LibreOffice 打开）。
//!
//! 目的：EXP-01 的 md/zip/docx 出口。全部字节由本模块确定性生成：
//! - 固定 zip 时间戳/权限（见 zipsec::fixed_options）
//! - docProps 的 created/modified 固定为 1980-01-01T00:00:00Z（不写运行时间）
//! - 段落顺序 = Markdown 行序；样式用内置 Heading1–6 / Code / Normal

use crate::error::CoreError;
use crate::zipsec;

const CORE_DATE: &str = "1980-01-01T00:00:00Z";

fn esc(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&apos;"),
            _ => out.push(c),
        }
    }
    out
}

/// 去掉最常见的行内标记（加粗星号与反引号），其余原样保留——不做完整 MD 解析器。
fn inline_plain(line: &str) -> String {
    let mut s = line.replace("**", "");
    s = s.replace(char::from(96), "");
    s
}

fn paragraph(text: &str, style: Option<&str>) -> String {
    let ppr = match style {
        Some(st) => format!("<w:pPr><w:pStyle w:val=\"{}\"/></w:pPr>", st),
        None => String::new(),
    };
    format!(
        "<w:p>{ppr}<w:r><w:t xml:space=\"preserve\">{}</w:t></w:r></w:p>",
        esc(text)
    )
}

fn heading_style(level: usize) -> &'static str {
    match level {
        1 => "Heading1",
        2 => "Heading2",
        3 => "Heading3",
        4 => "Heading4",
        5 => "Heading5",
        _ => "Heading6",
    }
}

/// Markdown → document.xml 的 body 段落序列（确定性）。
fn document_body(markdown: &str) -> String {
    let mut parts: Vec<String> = Vec::new();
    let mut in_code = false;
    for raw in markdown.lines() {
        let line = raw.trim_end_matches('\r');
        let trimmed = line.trim();
        if trimmed.starts_with("~~~") {
            in_code = !in_code;
            continue;
        }
        if in_code {
            parts.push(paragraph(if line.is_empty() { " " } else { line }, Some("Code")));
            continue;
        }
        if trimmed.is_empty() {
            continue;
        }
        let hashes = trimmed.chars().take_while(|c| *c == '#').count();
        if (1..=6).contains(&hashes) {
            let rest = trimmed[hashes..].trim();
            if !rest.is_empty() {
                parts.push(paragraph(&inline_plain(rest), Some(heading_style(hashes))));
                continue;
            }
        }
        if let Some(rest) = trimmed
            .strip_prefix("- ")
            .or_else(|| trimmed.strip_prefix("* "))
            .or_else(|| trimmed.strip_prefix("+ "))
        {
            parts.push(paragraph(&format!("• {}", inline_plain(rest)), None));
            continue;
        }
        parts.push(paragraph(&inline_plain(trimmed), None));
    }
    if parts.is_empty() {
        parts.push(paragraph(" ", None));
    }
    parts.join("")
}

const STYLES: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:outlineLvl w:val="0"/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:outlineLvl w:val="1"/><w:spacing w:before="200" w:after="100"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:outlineLvl w:val="2"/><w:spacing w:before="160" w:after="80"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading4"><w:name w:val="heading 4"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:outlineLvl w:val="3"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading5"><w:name w:val="heading 5"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:outlineLvl w:val="4"/></w:pPr><w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading6"><w:name w:val="heading 6"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:outlineLvl w:val="5"/></w:pPr><w:rPr><w:b/><w:sz w:val="20"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="Consolas"/><w:sz w:val="20"/></w:rPr></w:style>
</w:styles>
"#;

const CONTENT_TYPES: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"#;

const ROOT_RELS: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"#;

const DOCUMENT_RELS: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"#;

const APP_PROPS: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>NF APP</Application><AppVersion>1.0</AppVersion>
</Properties>
"#;

fn core_props(title: &str) -> String {
    format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">\n<dc:title>{title}</dc:title><dc:creator>NF APP</dc:creator><cp:lastModifiedBy>NF APP</cp:lastModifiedBy>\n<dcterms:created xsi:type=\"dcterms:W3CDTF\">{date}</dcterms:created>\n<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{date}</dcterms:modified>\n</cp:coreProperties>\n",
        title = esc(title),
        date = CORE_DATE
    )
}

const DEFAULT_SECT_PR: &str = r#"<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>"#;

fn document_xml(markdown: &str, sect_pr: &str) -> String {
    format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>{}{}</w:body></w:document>\n",
        document_body(markdown),
        sect_pr
    )
}

/// 生成 .docx 字节（确定性；同 input 同 bytes）。
pub fn build_docx(markdown: &str, title: &str) -> Result<Vec<u8>, CoreError> {
    build_docx_with_styles(markdown, title, None, None, None)
}

/// 参考样式：用调用方提供的 word/styles.xml 替换内置样式（reference-doc 继承）。
pub fn build_docx_with_styles(
    markdown: &str,
    title: &str,
    styles: Option<&str>,
    sect_pr: Option<&str>,
    theme: Option<&str>,
) -> Result<Vec<u8>, CoreError> {
    let styles_xml = styles.unwrap_or(STYLES);
    let sect_xml = sect_pr.unwrap_or(DEFAULT_SECT_PR);
    if let Some(t) = theme {
        if t.len() > 1024 * 1024 || !t.contains("<a:theme") {
            return Err(CoreError::new("NF-EXP-002")
                .with_message("docx 参考主题非法（需 a:theme）")
                .with_exit(3));
        }
    }
    if sect_xml.len() > 1024 * 1024 || !sect_xml.contains("<w:sectPr") || !sect_xml.contains("</w:sectPr>") {
        return Err(CoreError::new("NF-EXP-002")
            .with_message("docx 参考页面设置非法（需 w:sectPr）")
            .with_exit(3));
    }
    if styles_xml.len() > 1024 * 1024 {
        return Err(CoreError::new("NF-EXP-002")
            .with_message("docx 参考样式超过 1 MiB")
            .with_exit(3));
    }
    if !styles_xml.contains("<w:styles") {
        return Err(CoreError::new("NF-EXP-002")
            .with_message("docx 参考样式缺 w:styles 根")
            .with_exit(3));
    }
    let mut content_types = CONTENT_TYPES.to_string();
    let mut document_rels = DOCUMENT_RELS.to_string();
    if theme.is_some() {
        content_types = content_types.replace(
            "</Types>",
            "<Override PartName=\"/word/theme/theme1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.theme+xml\"/></Types>",
        );
        document_rels = document_rels.replace(
            "</Relationships>",
            "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme\" Target=\"theme/theme1.xml\"/></Relationships>",
        );
    }
    let mut entries: Vec<(String, Vec<u8>)> = vec![
        (
            "[Content_Types].xml".to_string(),
            content_types.into_bytes(),
        ),
        ("_rels/.rels".to_string(), ROOT_RELS.as_bytes().to_vec()),
        (
            "docProps/app.xml".to_string(),
            APP_PROPS.as_bytes().to_vec(),
        ),
        (
            "docProps/core.xml".to_string(),
            core_props(title).into_bytes(),
        ),
        (
            "word/_rels/document.xml.rels".to_string(),
            document_rels.into_bytes(),
        ),
        (
            "word/document.xml".to_string(),
            document_xml(markdown, sect_xml).into_bytes(),
        ),
        ("word/styles.xml".to_string(), styles_xml.as_bytes().to_vec()),
    ];
    if let Some(t) = theme {
        entries.push(("word/theme/theme1.xml".to_string(), t.as_bytes().to_vec()));
    }
    zipsec::zip_bytes(&entries)
}
