use super::*;

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
pub(crate) struct Snapshot {
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

/// 极简草稿落盘：同源覆盖（同一 source_id 同一 id），异源新建；不做回收站。
#[derive(Debug, Clone)]
pub struct DraftStore {
    root: std::path::PathBuf,
}

impl DraftStore {
    pub fn new(root: impl Into<std::path::PathBuf>) -> Self {
        Self { root: root.into() }
    }

    fn id_for(source_id: &str) -> String {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(source_id.as_bytes());
        hasher.finalize().iter().take(8).map(|b| format!("{b:02x}")).collect()
    }

    pub fn save(&self, source_id: &str, doc: &Document, report: &Report) -> Result<String, crate::error::CoreError> {
        let id = Self::id_for(source_id);
        std::fs::create_dir_all(&self.root)
            .map_err(|e| crate::fsutil::io_error("draft dir", &self.root, e))?;
        let path = self.root.join(format!("{id}.json"));
        let value = serde_json::json!({
            "schema": "nf-zero-slice-draft/1",
            "source_id": source_id,
            "document": document_json(doc),
            "report": report_json(report),
        });
        crate::fsutil::write_json_canonical(&path, &value)?;
        Ok(id)
    }

    pub fn load(&self, id: &str) -> Option<serde_json::Value> {
        let path = self.root.join(format!("{id}.json"));
        crate::fsutil::load_json_file(&path).ok()
    }

    pub fn delete(&self, id: &str) -> bool {
        std::fs::remove_file(self.root.join(format!("{id}.json"))).is_ok()
    }

    pub fn list(&self) -> Vec<String> {
        let mut ids: Vec<String> = std::fs::read_dir(&self.root).ok().into_iter().flatten().flatten()
            .filter_map(|e| e.file_name().to_string_lossy().strip_suffix(".json").map(|s| s.to_string()))
            .collect();
        ids.sort();
        ids
    }
}

pub fn document_json(doc: &Document) -> serde_json::Value {
    serde_json::json!({
        "title": doc.title,
        "sections": doc.sections.iter().map(|s| serde_json::json!({
            "title": s.title,
            "blocks": s.blocks.iter().map(|b| serde_json::json!({"kind": b.kind, "text": b.text})).collect::<Vec<_>>(),
        })).collect::<Vec<_>>(),
    })
}

pub fn report_json(report: &Report) -> serde_json::Value {
    serde_json::json!({
        "mappings": report.mappings.iter().map(|m| serde_json::json!({
            "from_index": m.from_index,
            "to_id": m.to_id,
            "to_name": m.to_name,
            "confidence": (m.confidence * 100.0).round() as u32,
        })).collect::<Vec<_>>(),
        "exceptions": report.exceptions.iter().map(|e| serde_json::json!({
            "text": e.text,
            "target": e.target,
            "reason": e.reason,
        })).collect::<Vec<_>>(),
        "coverage": (report.coverage * 100.0).round() as u32,
    })
}
