//! DOCX 导出（OOXML / WordprocessingML，最小但可被 Word/LibreOffice 打开）。
//!
//! 目的：EXP-01 的 md/zip/docx 出口。全部字节由本模块确定性生成：
//! - 固定 zip 时间戳/权限（见 zipsec::fixed_options）
//! - docProps 的 created/modified 固定为 1980-01-01T00:00:00Z（不写运行时间）
//! - 段落顺序 = Markdown 行序；样式用内置 Heading1–6 / Code / Normal

use crate::error::CoreError;
use crate::zipsec;
use regex::Regex;

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

fn paragraph(text: &str, style: Option<&str>, numbered: bool, num_id: &str) -> String {
    let mut ppr = String::new();
    if let Some(st) = style {
        ppr.push_str(&format!("<w:pStyle w:val=\"{}\"/>", st));
    }
    if numbered && style.is_none() {
        ppr.push_str(&format!("<w:numPr><w:ilvl w:val=\"0\"/><w:numId w:val=\"{num_id}\"/></w:numPr>"));
    }
    let ppr = if ppr.is_empty() { ppr } else { format!("<w:pPr>{ppr}</w:pPr>") };
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

fn is_table_row(trimmed: &str) -> bool {
    trimmed.starts_with('|') && trimmed.ends_with('|') && trimmed.len() > 2
}

fn table_cells(trimmed: &str) -> Vec<String> {
    trimmed.trim_matches('|').split('|').map(|c| c.trim().to_string()).collect()
}

fn is_table_separator(cells: &[String]) -> bool {
    !cells.is_empty() && cells.iter().all(|c| {
        let t = c.trim_matches(':');
        t.len() >= 3 && t.chars().all(|ch| ch == '-')
    })
}

fn cell_paragraph(text: &str, bold: bool) -> String {
    let rpr = if bold { "<w:rPr><w:b/></w:rPr>" } else { "" };
    format!(
        "<w:p><w:r>{rpr}<w:t xml:space=\"preserve\">{}</w:t></w:r></w:p>",
        esc(text)
    )
}

fn table_xml(rows: &[Vec<String>]) -> String {
    if rows.is_empty() {
        return String::new();
    }
    let cols = rows.iter().map(|r| r.len()).max().unwrap_or(1).max(1);
    let mut out = String::from(
        "<w:tbl><w:tblPr><w:tblW w:w=\"0\" w:type=\"auto\"/><w:tblBorders>\
         <w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         <w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         <w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         <w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         <w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         <w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         </w:tblBorders></w:tblPr>",
    );
    for (ri, row) in rows.iter().enumerate() {
        out.push_str("<w:tr>");
        for c in 0..cols {
            let cell = row.get(c).map(|s| s.as_str()).unwrap_or("");
            out.push_str("<w:tc><w:tcPr><w:tcW w:w=\"0\" w:type=\"auto\"/></w:tcPr>");
            out.push_str(&cell_paragraph(&inline_plain(cell), ri == 0));
            out.push_str("</w:tc>");
        }
        out.push_str("</w:tr>");
    }
    out.push_str("</w:tbl>");
    out
}

/// Markdown → document.xml 的 body 段落序列（确定性）。
fn document_body(markdown: &str, numbered: bool, num_id: &str) -> String {
    let mut parts: Vec<String> = Vec::new();
    let mut in_code = false;
    let lines: Vec<&str> = markdown.lines().collect();
    let mut i = 0usize;
    while i < lines.len() {
        let raw = lines[i];
        i += 1;
        let line = raw.trim_end_matches('\r');
        let trimmed = line.trim();
        if trimmed.starts_with("~~~") {
            in_code = !in_code;
            continue;
        }
        if in_code {
            parts.push(paragraph(if line.is_empty() { " " } else { line }, Some("Code"), false, num_id));
            continue;
        }
        if trimmed.is_empty() {
            continue;
        }
        if is_table_row(trimmed) {
            let mut rows: Vec<Vec<String>> = Vec::new();
            let mut j = i - 1;
            while j < lines.len() {
                let t = lines[j].trim();
                if !is_table_row(t) {
                    break;
                }
                let cells = table_cells(t);
                if !is_table_separator(&cells) {
                    rows.push(cells);
                }
                j += 1;
            }
            i = j;
            parts.push(table_xml(&rows));
            continue;
        }
        if trimmed.starts_with('>') {
            parts.push(paragraph(&inline_plain(trimmed.trim_start_matches('>').trim()), Some("Quote"), false, num_id));
            continue;
        }
        if trimmed.len() >= 3
            && (trimmed.chars().all(|c| c == '-')
                || trimmed.chars().all(|c| c == '*')
                || trimmed.chars().all(|c| c == '_'))
        {
            parts.push(
                "<w:p><w:pPr><w:pBdr><w:bottom w:val=\"single\" w:sz=\"6\" w:space=\"1\" w:color=\"auto\"/></w:pBdr></w:pPr><w:r><w:t> </w:t></w:r></w:p>"
                    .to_string(),
            );
            continue;
        }
        let hashes = trimmed.chars().take_while(|c| *c == '#').count();
        if (1..=6).contains(&hashes) {
            let rest = trimmed[hashes..].trim();
            if !rest.is_empty() {
                parts.push(paragraph(&inline_plain(rest), Some(heading_style(hashes)), false, num_id));
                continue;
            }
        }
        if let Some(rest) = trimmed
            .strip_prefix("- ")
            .or_else(|| trimmed.strip_prefix("* "))
            .or_else(|| trimmed.strip_prefix("+ "))
        {
            let bullet_text = if numbered { inline_plain(rest) } else { format!("• {}", inline_plain(rest)) };
            parts.push(paragraph(&bullet_text, None, numbered, num_id));
            continue;
        }
        parts.push(paragraph(&inline_plain(trimmed), None, false, num_id));
    }
    if parts.is_empty() {
        parts.push(paragraph(" ", None, false, num_id));
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
<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:ind w:left="360"/><w:pBdr><w:left w:val="single" w:sz="6" w:space="4" w:color="auto"/></w:pBdr></w:pPr><w:rPr><w:i/></w:rPr></w:style>
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

fn document_xml(markdown: &str, sect_pr: &str, numbered: bool, num_id: &str) -> String {
    format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>{}{}</w:body></w:document>\n",
        document_body(markdown, numbered, num_id),
        sect_pr
    )
}

/// 生成 .docx 字节（确定性；同 input 同 bytes）。
pub fn build_docx(markdown: &str, title: &str) -> Result<Vec<u8>, CoreError> {
    build_docx_with_styles(markdown, title, None, None, None, None, None, None)
}

/// 参考样式：用调用方提供的 word/styles.xml 替换内置样式（reference-doc 继承）。
pub fn build_docx_with_styles(
    markdown: &str,
    title: &str,
    styles: Option<&str>,
    sect_pr: Option<&str>,
    theme: Option<&str>,
    numbering: Option<&str>,
    header: Option<&str>,
    footer: Option<&str>,
) -> Result<Vec<u8>, CoreError> {
    let styles_xml = styles.unwrap_or(STYLES);
    let sect_xml_raw = sect_pr.unwrap_or(DEFAULT_SECT_PR);
    // 当前只继承页面设置，不继承页眉页脚；移除悬空引用，避免 Word 打开失败。
    let mut sect_xml = Regex::new(r"<w:(header|footer)Reference[^>]*/>")
        .expect("sectPr 清理正则")
        .replace_all(sect_xml_raw, "")
        .to_string();
    if header.is_some() {
        sect_xml = sect_xml.replace("</w:sectPr>", "<w:headerReference w:type=\"default\" r:id=\"rId100\"/></w:sectPr>");
    }
    if footer.is_some() {
        sect_xml = sect_xml.replace("</w:sectPr>", "<w:footerReference w:type=\"default\" r:id=\"rId101\"/></w:sectPr>");
    }
    let sect_xml = sect_xml.as_str();
    if let Some(t) = theme {
        if t.len() > 1024 * 1024 || !t.contains("<a:theme") {
            return Err(CoreError::new("NF-EXP-002")
                .with_message("docx 参考主题非法（需 a:theme）")
                .with_exit(3));
        }
    }
    if let Some(n) = numbering {
        if n.len() > 1024 * 1024 || !n.contains("<w:numbering") {
            return Err(CoreError::new("NF-EXP-002")
                .with_message("docx 参考编号非法（需 w:numbering）")
                .with_exit(3));
        }
    }
    if let Some(h) = header {
        if h.len() > 1024 * 1024 || !h.contains("<w:hdr") {
            return Err(CoreError::new("NF-EXP-002")
                .with_message("docx 参考页眉非法（需 w:hdr）")
                .with_exit(3));
        }
    }
    if let Some(f) = footer {
        if f.len() > 1024 * 1024 || !f.contains("<w:ftr") {
            return Err(CoreError::new("NF-EXP-002")
                .with_message("docx 参考页脚非法（需 w:ftr）")
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
    let num_id = numbering
        .and_then(|n| {
            Regex::new(r#"w:num[^>]*w:numId="([0-9]+)""#)
                .ok()
                .and_then(|re| re.captures(n))
                .and_then(|c| c.get(1))
                .map(|m| m.as_str().to_string())
        })
        .unwrap_or_else(|| "1".to_string());
    let mut content_types = CONTENT_TYPES.to_string();
    let mut document_rels = DOCUMENT_RELS.to_string();
    if numbering.is_some() {
        content_types = content_types.replace(
            "</Types>",
            "<Override PartName=\"/word/numbering.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml\"/></Types>",
        );
        document_rels = document_rels.replace(
            "</Relationships>",
            "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering\" Target=\"numbering.xml\"/></Relationships>",
        );
    }
    if header.is_some() {
        content_types = content_types.replace(
            "</Types>",
            "<Override PartName=\"/word/header1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml\"/></Types>",
        );
        document_rels = document_rels.replace(
            "</Relationships>",
            "<Relationship Id=\"rId100\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/header\" Target=\"header1.xml\"/></Relationships>",
        );
    }
    if footer.is_some() {
        content_types = content_types.replace(
            "</Types>",
            "<Override PartName=\"/word/footer1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml\"/></Types>",
        );
        document_rels = document_rels.replace(
            "</Relationships>",
            "<Relationship Id=\"rId101\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer\" Target=\"footer1.xml\"/></Relationships>",
        );
    }
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
            document_xml(markdown, sect_xml, numbering.is_some(), &num_id).into_bytes(),
        ),
        ("word/styles.xml".to_string(), styles_xml.as_bytes().to_vec()),
    ];
    if let Some(n) = numbering {
        entries.push(("word/numbering.xml".to_string(), n.as_bytes().to_vec()));
    }
    if let Some(h) = header {
        entries.push(("word/header1.xml".to_string(), h.as_bytes().to_vec()));
    }
    if let Some(f) = footer {
        entries.push(("word/footer1.xml".to_string(), f.as_bytes().to_vec()));
    }
    if let Some(t) = theme {
        entries.push(("word/theme/theme1.xml".to_string(), t.as_bytes().to_vec()));
    }
    zipsec::zip_bytes(&entries)
}
