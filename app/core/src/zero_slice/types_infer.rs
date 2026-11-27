use super::*;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Block {
    pub kind: String,
    pub text: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Section {
    pub title: String,
    pub blocks: Vec<Block>,
}

impl Section {
    pub fn text(&self) -> String {
        self.blocks.iter().map(|b| b.text.as_str()).collect::<Vec<_>>().join("\n\n")
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Document {
    pub title: String,
    pub sections: Vec<Section>,
    pub blocks: Vec<Block>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SlotSpec {
    pub id: String,
    pub name: String,
    pub required: bool,
    pub max_chars: Option<usize>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SectionSpec {
    pub id: String,
    pub title: String,
    pub slots: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Spec {
    pub id: String,
    pub slots: Vec<SlotSpec>,
    pub sections: Vec<SectionSpec>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Mapping {
    pub from_index: usize,
    pub from_block: Option<usize>,
    pub from_title: String,
    pub to_id: String,
    pub to_name: String,
    pub confidence: f64,
    pub rationale: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Exception {
    pub text: String,
    pub target: Option<String>,
    pub reason: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Report {
    pub mappings: Vec<Mapping>,
    pub exceptions: Vec<Exception>,
    pub coverage: f64,
}

pub(crate) fn is_ordered_list(first: &str) -> bool {
    let mut chars = first.chars().peekable();
    let mut digits = 0;
    while chars.peek().is_some_and(|c| c.is_ascii_digit()) {
        chars.next();
        digits += 1;
    }
    digits > 0 && matches!(chars.next(), Some('.') | Some(')')) && chars.next().is_some_and(|c| c == ' ' || c == '\t')
}

pub(crate) fn kind_of(text: &str) -> &'static str {
    let first = text.lines().next().unwrap_or("").trim();
    if first.starts_with("\u{60}\u{60}\u{60}") { "code" }
    else if first.starts_with('#') { "heading" }
    else if first.starts_with('|') { "table" }
    else if first.starts_with('>') { "quote" }
    else if first.starts_with("- ") || first.starts_with("* ") || is_ordered_list(first) { "list" }
    else { "paragraph" }
}

pub fn parse_markdown(text: &str) -> Document {
    let normalized = text.replace("\r\n", "\n");
    let mut blocks: Vec<Block> = Vec::new();
    let mut current = String::new();
    let mut in_fence = false;
    let flush = |current: &mut String, blocks: &mut Vec<Block>| {
        let t = current.trim();
        if !t.is_empty() {
            blocks.push(Block { kind: kind_of(t).to_string(), text: t.to_string() });
        }
        current.clear();
    };
    for line in normalized.split('\n') {
        if line.trim_start().starts_with("\u{60}\u{60}\u{60}") {
            if in_fence {
                current.push_str(line);
                current.push('\n');
                flush(&mut current, &mut blocks);
                in_fence = false;
            } else {
                flush(&mut current, &mut blocks);
                current.push_str(line);
                current.push('\n');
                in_fence = true;
            }
        } else if !in_fence && line.trim().is_empty() {
            flush(&mut current, &mut blocks);
        } else {
            current.push_str(line);
            current.push('\n');
        }
    }
    flush(&mut current, &mut blocks);
    let title = blocks.iter()
        .find(|b| b.kind == "heading")
        .map(|b| b.text.trim_start_matches('#').trim().to_string())
        .or_else(|| blocks.first().map(|b| b.text.lines().next().unwrap_or("").trim().to_string()))
        .unwrap_or_default();
    let mut sections: Vec<Section> = Vec::new();
    for block in &blocks {
        if block.kind == "heading" {
            sections.push(Section {
                title: block.text.trim_start_matches('#').trim().to_string(),
                blocks: Vec::new(),
            });
        } else if let Some(last) = sections.last_mut() {
            last.blocks.push(block.clone());
        }
    }
    if sections.first().is_some_and(|s| s.title == title && s.blocks.is_empty()) {
        sections.remove(0);
    }
    if sections.is_empty() {
        sections.push(Section { title: title.clone(), blocks: blocks.clone() });
    }
    Document { title, sections, blocks }
}

pub(crate) fn tokens(text: &str) -> Vec<String> {
    text.to_lowercase().split(|c: char| !c.is_alphanumeric()).filter(|s| !s.is_empty()).map(|s| s.to_string()).collect()
}

pub(crate) fn title_score(a: &str, b: &str) -> f64 {
    let a = a.trim();
    let b = b.trim();
    if a.is_empty() || b.is_empty() { return 0.0; }
    if a == b { return 1.0; }
    if a.contains(b) || b.contains(a) { return 0.85; }
    let ta = tokens(a);
    let tb = tokens(b);
    if ta.is_empty() || tb.is_empty() { return 0.0; }
    let overlap = ta.iter().filter(|t| tb.contains(t)).count() as f64;
    (overlap / ta.len().max(tb.len()) as f64).min(0.8)
}

pub fn infer(spec: &Spec, doc: &Document) -> Report {
    let total: usize = doc.sections.iter().map(|s| s.text().chars().count()).sum();
    let mut mappings = Vec::new();
    let mut exceptions = Vec::new();
    if spec.slots.is_empty() {
        let text = doc.sections.iter().map(|s| s.text()).collect::<Vec<_>>().join("\n\n");
        return Report {
            mappings: vec![Mapping { from_index: 0, from_block: None, from_title: doc.title.clone(), to_id: "freeform".into(), to_name: "自由稿".into(), confidence: 1.0, rationale: "无 spec，全文映射".into() }],
            exceptions: if text.is_empty() { vec![Exception { text: "".into(), target: None, reason: "空文档".into() }] } else { vec![] },
            coverage: if text.is_empty() { 0.0 } else { 1.0 },
        };
    }
    let mut used = vec![false; spec.slots.len()];
    for (index, section) in doc.sections.iter().enumerate() {
        // 先按 spec 章节标题匹配，再把章节块落到其槽位；没有章节命中才回退到槽位名匹配。
        let mut section_best: Option<(usize, f64)> = None;
        for (ssi, sec) in spec.sections.iter().enumerate() {
            let score = title_score(&section.title, &sec.title);
            if section_best.map_or(true, |(_, s)| score > s) { section_best = Some((ssi, score)); }
        }
        if let Some((ssi, score)) = section_best {
            if score >= 0.6 {
                let mut mapped_any = false;
                for (bi, slot_id) in spec.sections[ssi].slots.iter().enumerate() {
                    if section.blocks.get(bi).is_none() { break; }
                    let Some(si) = spec.slots.iter().enumerate()
                        .find(|(i, slot)| &slot.id == slot_id && !used[*i])
                        .map(|(i, _)| i) else { continue };
                    used[si] = true;
                    mapped_any = true;
                    mappings.push(Mapping {
                        from_index: index,
                        from_block: Some(bi),
                        from_title: section.title.clone(),
                        to_id: spec.slots[si].id.clone(),
                        to_name: spec.slots[si].name.clone(),
                        confidence: (score * 100.0).round() / 100.0,
                        rationale: "章节标题匹配".into(),
                    });
                }
                for (_bi, block) in section.blocks.iter().enumerate().skip(spec.sections[ssi].slots.len()) {
                    exceptions.push(Exception {
                        text: block.text.clone(),
                        target: None,
                        reason: "章节槽位已满，保留为附加内容".into(),
                    });
                }
                if mapped_any { continue; }
            }
        }
        let mut best: Option<(usize, f64)> = None;
        for (si, slot) in spec.slots.iter().enumerate() {
            if used[si] { continue; }
            let score = title_score(&section.title, &slot.name);
            if best.map_or(true, |(_, s)| score > s) { best = Some((si, score)); }
        }
        match best {
            Some((si, score)) if score >= 0.6 => {
                used[si] = true;
                mappings.push(Mapping {
                    from_index: index,
                    from_block: None,
                    from_title: section.title.clone(),
                    to_id: spec.slots[si].id.clone(),
                    to_name: spec.slots[si].name.clone(),
                    confidence: (score * 100.0).round() / 100.0,
                    rationale: if score >= 0.99 { "标题精确匹配".into() } else { "标题包含/词重叠".into() },
                });
            }
            _ => exceptions.push(Exception {
                text: section.text(),
                target: None,
                reason: "低于 0.6 或无处可映射，保留为附加内容".into(),
            }),
        }
    }
    // 自由稿兜底：无标题命中且只有一个 section 时，把全文放入第一个必填（或第一个）槽位。
    if mappings.is_empty() && doc.sections.len() == 1 && total > 0 && doc.blocks.iter().filter(|b| b.kind == "heading").count() <= 1 {
        if let Some(si) = spec.slots.iter().position(|s| s.required).or(if spec.slots.is_empty() { None } else { Some(0) }) {
            let section = &doc.sections[0];
            let fits = spec.slots[si].max_chars.map_or(true, |max| total <= max);
            if fits {
                used[si] = true;
                mappings.push(Mapping {
                    from_index: 0,
                    from_block: None,
                    from_title: section.title.clone(),
                    to_id: spec.slots[si].id.clone(),
                    to_name: spec.slots[si].name.clone(),
                    confidence: 0.6,
                    rationale: "自由稿：无标题匹配，放入该槽位，请复核".into(),
                });
                exceptions.clear();
            }
        }
    }
    for (index, slot) in spec.slots.iter().enumerate() {
        if !used[index] && slot.required {
            exceptions.push(Exception { text: "".into(), target: Some(slot.id.clone()), reason: "必填槽位无匹配".into() });
        }
    }
    let mapped: usize = mappings.iter().filter_map(|m| {
        let section = doc.sections.get(m.from_index)?;
        Some(m.from_block.and_then(|bi| section.blocks.get(bi)).map(|b| b.text.chars().count()).unwrap_or_else(|| section.text().chars().count()))
    }).sum();
    let coverage = if total == 0 { 0.0 } else { (mapped as f64 / total as f64 * 10000.0).round() / 10000.0 };
    Report { mappings, exceptions, coverage }
}

/// 参考转换（不是可入库的完整 nf-project/1）：只用于验证 document+slots 形状。
pub fn to_project(doc: &Document, report: &Report, draft_id: Option<&str>) -> serde_json::Value {
    let mut slots = serde_json::Map::new();
    for mapping in &report.mappings {
        if let Some(section) = doc.sections.get(mapping.from_index) {
            let text = mapping.from_block.and_then(|bi| section.blocks.get(bi)).map(|b| b.text.clone()).unwrap_or_else(|| section.text());
            slots.insert(mapping.to_id.clone(), serde_json::Value::String(text));
        }
    }
    serde_json::json!({
        "schema": "nf-project/1",
        "title": doc.title,
        "document": document_json(doc),
        "slots": slots,
        "draft_id": draft_id,
    })
}
