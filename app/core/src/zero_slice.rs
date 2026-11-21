//! zero_slice 导入映射的 Rust 参考实现（对照 app/prototypes/zero_slice）。
//!
//! 只覆盖结构解析/映射/例外，不替代 Android ImportSession；用于先锁语义再进 op/FFI。

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
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Spec {
    pub id: String,
    pub slots: Vec<SlotSpec>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Mapping {
    pub from_index: usize,
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

fn kind_of(text: &str) -> &'static str {
    let first = text.lines().next().unwrap_or("").trim();
    if first.starts_with("\u{60}\u{60}\u{60}") { "code" }
    else if first.starts_with('#') { "heading" }
    else if first.starts_with('|') { "table" }
    else if first.starts_with('>') { "quote" }
    else if first.starts_with("- ") || first.starts_with("* ") || first.chars().next().is_some_and(|c| c.is_ascii_digit()) { "list" }
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

fn tokens(text: &str) -> Vec<String> {
    text.to_lowercase().split(|c: char| !c.is_alphanumeric()).filter(|s| !s.is_empty()).map(|s| s.to_string()).collect()
}

fn title_score(a: &str, b: &str) -> f64 {
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
            mappings: vec![Mapping { from_index: 0, from_title: doc.title.clone(), to_id: "freeform".into(), to_name: "自由稿".into(), confidence: 1.0, rationale: "无 spec，全文映射".into() }],
            exceptions: if text.is_empty() { vec![Exception { text: "".into(), target: None, reason: "空文档".into() }] } else { vec![] },
            coverage: if text.is_empty() { 0.0 } else { 1.0 },
        };
    }
    let mut used = vec![false; spec.slots.len()];
    for (index, section) in doc.sections.iter().enumerate() {
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
    for (index, slot) in spec.slots.iter().enumerate() {
        if !used[index] && slot.required {
            exceptions.push(Exception { text: "".into(), target: Some(slot.id.clone()), reason: "必填槽位无匹配".into() });
        }
    }
    let mapped: usize = mappings.iter().filter_map(|m| doc.sections.get(m.from_index)).map(|s| s.text().chars().count()).sum();
    let coverage = if total == 0 { 0.0 } else { (mapped as f64 / total as f64 * 10000.0).round() / 10000.0 };
    Report { mappings, exceptions, coverage }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Stage {
    Empty,
    Source,
    Preview,
    Mapping,
    Draft,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResetScope {
    Current,
    All,
}

#[derive(Debug, Clone, PartialEq)]
struct Snapshot {
    stage: Stage,
    document: Option<Document>,
    report: Option<Report>,
}

/// 最小导入会话：reset 后不自动恢复；undo 只回退内存快照。
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Session {
    stage: Stage,
    document: Option<Document>,
    report: Option<Report>,
    undo: Vec<Snapshot>,
}

impl Default for Stage {
    fn default() -> Self {
        Stage::Empty
    }
}

impl Session {
    pub fn new() -> Self {
        Self { stage: Stage::Empty, document: None, report: None, undo: Vec::new() }
    }

    pub fn stage(&self) -> Stage {
        self.stage
    }

    pub fn document(&self) -> Option<&Document> {
        self.document.as_ref()
    }

    pub fn report(&self) -> Option<&Report> {
        self.report.as_ref()
    }

    fn snapshot(&mut self) {
        self.undo.push(Snapshot {
            stage: self.stage,
            document: self.document.clone(),
            report: self.report.clone(),
        });
        if self.undo.len() > 10 {
            self.undo.remove(0);
        }
    }

    pub fn start(&mut self, document: Document) -> Result<(), String> {
        if document.blocks.is_empty() {
            return Err("空内容不能开始导入".into());
        }
        self.snapshot();
        self.document = Some(document);
        self.report = None;
        self.stage = Stage::Source;
        self.stage = Stage::Preview;
        Ok(())
    }

    pub fn infer(&mut self, spec: &Spec) -> Option<&Report> {
        let doc = self.document.clone()?;
        self.snapshot();
        let report = infer(spec, &doc);
        self.report = Some(report);
        self.stage = Stage::Mapping;
        self.report.as_ref()
    }

    pub fn accept_draft(&mut self) -> Result<(), String> {
        if self.report.is_none() {
            return Err("尚无映射结果".into());
        }
        self.snapshot();
        self.stage = Stage::Draft;
        Ok(())
    }

    pub fn reset(&mut self, _scope: ResetScope) {
        self.undo.clear();
        self.stage = Stage::Empty;
        self.document = None;
        self.report = None;
    }

    pub fn undo(&mut self) -> bool {
        let Some(previous) = self.undo.pop() else { return false; };
        self.stage = previous.stage;
        self.document = previous.document;
        self.report = previous.report;
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn spec() -> Spec {
        Spec { id: "demo".into(), slots: vec![
            SlotSpec { id: "SLT-01".into(), name: "背景".into(), required: true },
            SlotSpec { id: "SLT-02".into(), name: "目标".into(), required: true },
        ]}
    }

    #[test]
    fn headings_become_sections() {
        let doc = parse_markdown("# 简报\n\n## 背景\n\n正文\n\n## 目标\n\n- 一点\n");
        assert_eq!(doc.title, "简报");
        assert_eq!(doc.sections.iter().map(|s| s.title.as_str()).collect::<Vec<_>>(), vec!["背景", "目标"]);
    }

    #[test]
    fn tables_and_code_are_blocks() {
        let doc = parse_markdown("|a|b|\n|-|-|\n|1|2|\n\n\u{60}\u{60}\u{60}\nx\n\u{60}\u{60}\u{60}\n");
        assert!(doc.blocks.iter().any(|b| b.kind == "table"));
        assert!(doc.blocks.iter().any(|b| b.kind == "code"));
    }

    #[test]
    fn exact_titles_map() {
        let doc = parse_markdown("# 简\n\n## 背景\n\n甲\n\n## 目标\n\n乙\n");
        let report = infer(&spec(), &doc);
        assert_eq!(report.mappings.len(), 2);
        assert_eq!(report.coverage, 1.0);
        assert!(report.exceptions.is_empty());
    }

    #[test]
    fn low_confidence_kept_as_exception() {
        let doc = parse_markdown("# 简\n\n## 天气\n\n甲\n");
        let report = infer(&spec(), &doc);
        assert!(report.mappings.is_empty());
        assert_eq!(report.exceptions.len(), 3);
        assert_eq!(report.coverage, 0.0);
    }

    #[test]
    fn session_transitions_and_reset() {
        let mut session = Session::new();
        let doc = parse_markdown("# 简\n\n## 背景\n\n甲\n");
        session.start(doc).unwrap();
        assert_eq!(session.stage(), Stage::Preview);
        session.infer(&spec()).unwrap();
        assert_eq!(session.stage(), Stage::Mapping);
        session.accept_draft().unwrap();
        assert_eq!(session.stage(), Stage::Draft);
        session.reset(ResetScope::All);
        assert_eq!(session.stage(), Stage::Empty);
        assert!(session.document().is_none());
        assert!(!session.undo());
    }

    #[test]
    fn session_undo_restores_previous_stage() {
        let mut session = Session::new();
        session.start(parse_markdown("# 简\n\n## 背景\n\n甲\n")).unwrap();
        session.infer(&spec()).unwrap();
        assert!(session.undo());
        assert_eq!(session.stage(), Stage::Preview);
        assert!(session.report().is_none());
    }

    #[test]
    fn empty_session_start_rejected() {
        let mut session = Session::new();
        assert!(session.start(Document { title: "空".into(), sections: vec![], blocks: vec![] }).is_err());
    }

    #[test]
    fn freeform_without_spec() {
        let doc = parse_markdown("标题\n\n正文");
        let report = infer(&Spec { id: "free".into(), slots: vec![] }, &doc);
        assert_eq!(report.mappings[0].to_id, "freeform");
        assert_eq!(report.coverage, 1.0);
    }
}
