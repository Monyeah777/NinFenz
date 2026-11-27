use super::*;

pub(crate) const CORE_DATE: &str = "1980-01-01T00:00:00Z";

pub(crate) fn esc(s: &str) -> String {
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

pub(crate) fn run(text: &str, bold: bool, italic: bool, code: bool) -> String {
    let mut rpr = String::new();
    if bold {
        rpr.push_str("<w:b/>");
    }
    if italic {
        rpr.push_str("<w:i/>");
    }
    if code {
        rpr.push_str("<w:rFonts w:ascii=\"Consolas\" w:hAnsi=\"Consolas\" w:eastAsia=\"Consolas\"/>");
    }
    let rpr = if rpr.is_empty() { rpr } else { format!("<w:rPr>{rpr}</w:rPr>") };
    format!(
        "<w:r>{rpr}<w:t xml:space=\"preserve\">{}</w:t></w:r>",
        esc(text)
    )
}

pub(crate) fn runs_xml(text: &str) -> String {
    runs_xml_with(text, false, false)
}

pub(crate) fn runs_xml_with(text: &str, force_bold: bool, force_italic: bool) -> String {
    let mut out = String::new();
    let mut plain = String::new();
    let mut i = 0usize;
    while i < text.len() {
        let rest = &text[i..];
        let (open, close, bold, italic, code): (&str, &str, bool, bool, bool) = if rest.starts_with("**") {
            ("**", "**", true, false, false)
        } else if rest.starts_with("__") {
            ("__", "__", true, false, false)
        } else if rest.starts_with('\u{0060}') {
            ("\u{0060}", "\u{0060}", false, false, true)
        } else if rest.starts_with('*') {
            ("*", "*", false, true, false)
        } else if rest.starts_with('_') {
            ("_", "_", false, true, false)
        } else {
            ("", "", false, false, false)
        };
        if open.is_empty() {
            let ch = rest.chars().next().unwrap();
            plain.push(ch);
            i += ch.len_utf8();
            continue;
        }
        let close_at = if rest.ends_with("***") {
            rest.rfind(close)
        } else {
            rest[open.len()..].find(close).map(|p| p + open.len())
        };
        if let Some(pos) = close_at {
            let inner = &rest[open.len()..pos];
            if !inner.is_empty() {
                if !plain.is_empty() {
                    out.push_str(&run(&plain, force_bold, force_italic, false));
                    plain.clear();
                }
                if code {
                    out.push_str(&run(inner, force_bold || bold, force_italic || italic, true));
                } else {
                    out.push_str(&runs_xml_with(inner, force_bold || bold, force_italic || italic));
                }
                i += pos + close.len();
                continue;
            }
        }
        let ch = rest.chars().next().unwrap();
        plain.push(ch);
        i += ch.len_utf8();
    }
    if !plain.is_empty() {
        out.push_str(&run(&plain, force_bold, force_italic, false));
    }
    out
}

pub(crate) fn paragraph(text: &str, style: Option<&str>, numbered: bool, num_id: &str) -> String {
    paragraph_with(text, style, numbered, num_id, false)
}

pub(crate) fn paragraph_code(text: &str, style: Option<&str>, numbered: bool, num_id: &str) -> String {
    paragraph_with(text, style, numbered, num_id, true)
}

pub(crate) fn paragraph_with(text: &str, style: Option<&str>, numbered: bool, num_id: &str, plain_run: bool) -> String {
    let mut ppr = String::new();
    if let Some(st) = style {
        ppr.push_str(&format!("<w:pStyle w:val=\"{}\"/>", st));
    }
    if numbered && style.is_none() {
        ppr.push_str(&format!("<w:numPr><w:ilvl w:val=\"0\"/><w:numId w:val=\"{num_id}\"/></w:numPr>"));
    }
    if plain_run {
        ppr.push_str("<w:shd w:val=\"clear\" w:color=\"auto\" w:fill=\"F5F5F5\"/>");
    }
    let ppr = if ppr.is_empty() { ppr } else { format!("<w:pPr>{ppr}</w:pPr>") };
    let runs = if plain_run { run(text, false, false, true) } else { runs_xml(text) };
    format!("<w:p>{ppr}{runs}</w:p>")
}

pub(crate) fn heading_style(level: usize) -> &'static str {
    match level {
        1 => "Heading1",
        2 => "Heading2",
        3 => "Heading3",
        4 => "Heading4",
        5 => "Heading5",
        _ => "Heading6",
    }
}

pub(crate) fn is_table_row(trimmed: &str) -> bool {
    trimmed.starts_with('|') && trimmed.ends_with('|') && trimmed.len() > 2
}

pub(crate) fn table_cells(trimmed: &str) -> Vec<String> {
    trimmed.trim_matches('|').split('|').map(|c| c.trim().to_string()).collect()
}

pub(crate) fn is_table_separator(cells: &[String]) -> bool {
    !cells.is_empty() && cells.iter().all(|c| {
        let t = c.trim_matches(':');
        t.len() >= 3 && t.chars().all(|ch| ch == '-')
    })
}

pub(crate) fn cell_paragraph(text: &str, bold: bool) -> String {
    format!("<w:p>{}</w:p>", runs_xml_with(text, bold, false))
}

pub(crate) fn table_xml(rows: &[Vec<String>]) -> String {
    if rows.is_empty() {
        return String::new();
    }
    let cols = rows.iter().map(|r| r.len()).max().unwrap_or(1).max(1);
    let mut weights = vec![1usize; cols];
    for row in rows {
        for (i, cell) in row.iter().enumerate() {
            weights[i] = weights[i].max(cell.chars().count().min(40));
        }
    }
    let total: usize = weights.iter().sum::<usize>().max(1);
    let widths: Vec<usize> = weights
        .iter()
        .map(|w| (9360 * w / total).max(600))
        .collect();
    let mut out = String::from(
        "<w:tbl><w:tblPr><w:tblW w:w=\"9360\" w:type=\"dxa\"/><w:tblBorders>\
         <w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         <w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         <w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         <w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         <w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         <w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>\
         </w:tblBorders></w:tblPr>",
    );
    out.push_str("<w:tblGrid>");
    for w in &widths {
        out.push_str(&format!("<w:gridCol w:w=\"{w}\"/>"));
    }
    out.push_str("</w:tblGrid>");
    for (ri, row) in rows.iter().enumerate() {
        out.push_str("<w:tr>");
        if ri == 0 {
            out.push_str("<w:trPr><w:tblHeader/></w:trPr>");
        }
        for c in 0..cols {
            let cell = row.get(c).map(|s| s.as_str()).unwrap_or("");
            out.push_str(&format!(
                "<w:tc><w:tcPr><w:tcW w:w=\"{}\" w:type=\"dxa\"/></w:tcPr>",
                widths.get(c).copied().unwrap_or(600)
            ));
            out.push_str(&cell_paragraph(cell, ri == 0));
            out.push_str("</w:tc>");
        }
        out.push_str("</w:tr>");
    }
    out.push_str("</w:tbl>");
    out
}
