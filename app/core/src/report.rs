//! nf-validate-report/1 构造器：issue 定位（path + fix），verdict 只由 issues 推出，
//! 禁时间戳；同输入两次报告逐字节一致。

use crate::canonical::{digest_allow_float, digest_with_excludes};
use crate::error::{registry, CoreError};
use crate::schema::SchemaIssue;
use serde_json::{json, Value};

#[derive(Clone, Debug)]
pub struct Issue {
    pub code: String,
    pub severity: String,
    pub path: String,
    pub message: String,
    pub fix: String,
    pub rule: Option<String>,
}

#[derive(Clone, Debug)]
pub struct Report {
    pub level: String,
    pub target_kind: String,
    pub target_ref: String,
    pub target_digest: String,
    pub issues: Vec<Issue>,
}

/// 目标对象的摘要：按 CONTRACT §7 的 digest_exclude 口径剔除人读字段。
pub fn target_digest(target: &Value) -> String {
    let mut excludes: Vec<String> = Vec::new();
    match target.get("schema").and_then(|v| v.as_str()) {
        Some("nf-project/1") => excludes.push("history".to_string()),
        Some("nf-assembly-plan/1") => excludes.push("digest".to_string()),
        Some("nf-pipeline-graph/1") => {
            if let Some(list) = target.get("x-digest-exclude").and_then(|v| v.as_array()) {
                for item in list {
                    if let Some(s) = item.as_str() {
                        excludes.push(s.to_string());
                    }
                }
            }
        }
        _ => {}
    }
    match digest_with_excludes(target, &excludes) {
        Ok(d) => d,
        // 非法 canonical（含 float）也要给报告一个确定性摘要
        Err(_) => digest_allow_float(target),
    }
}

impl Report {
    pub fn new(level: &str, target: &Value, target_kind: &str, target_ref: &str) -> Self {
        Report {
            level: level.to_string(),
            target_kind: target_kind.to_string(),
            target_ref: target_ref.to_string(),
            target_digest: target_digest(target),
            issues: Vec::new(),
        }
    }

    pub fn raw(
        level: &str,
        target_kind: &str,
        target_ref: &str,
        digest: &str,
    ) -> Self {
        Report {
            level: level.to_string(),
            target_kind: target_kind.to_string(),
            target_ref: target_ref.to_string(),
            target_digest: digest.to_string(),
            issues: Vec::new(),
        }
    }

    fn registry_meta(code: &str) -> (String, String, String) {
        match registry().get(code) {
            Some(m) => (m.severity.clone(), m.message.clone(), m.fix.clone()),
            None => ("error".to_string(), code.to_string(), "补登记错误码".to_string()),
        }
    }

    pub fn push(&mut self, code: &str, severity: &str, path: &str, message: &str) {
        let (_, default_msg, fix) = Self::registry_meta(code);
        self.issues.push(Issue {
            code: code.to_string(),
            severity: severity.to_string(),
            path: path.to_string(),
            message: if message.is_empty() {
                default_msg
            } else {
                message.to_string()
            },
            fix,
            rule: None,
        });
    }

    pub fn error(&mut self, code: &str, path: &str, message: &str) {
        self.push(code, "error", path, message);
    }

    pub fn warn(&mut self, code: &str, path: &str, message: &str) {
        self.push(code, "warn", path, message);
    }

    pub fn info(&mut self, code: &str, path: &str, message: &str) {
        self.push(code, "info", path, message);
    }

    /// 用 schema issue 批量记错误（同一 code）。
    pub fn extend_schema_issues(&mut self, code: &str, issues: &[SchemaIssue]) {
        for i in issues {
            self.error(code, &i.path, &i.message);
        }
    }

    pub fn has_error(&self) -> bool {
        self.issues.iter().any(|i| i.severity == "error")
    }

    pub fn has_warn(&self) -> bool {
        self.issues.iter().any(|i| i.severity == "warn")
    }

    pub fn verdict(&self) -> &'static str {
        if self.has_error() {
            "fail"
        } else if self.has_warn() {
            "warn"
        } else {
            "pass"
        }
    }

    pub fn counts(&self) -> (u64, u64, u64) {
        let mut e = 0;
        let mut w = 0;
        let mut i = 0;
        for issue in &self.issues {
            match issue.severity.as_str() {
                "error" => e += 1,
                "warn" => w += 1,
                _ => i += 1,
            }
        }
        (e, w, i)
    }

    /// 报告失败时对外的错误码：优先调用方指定，否则取第一条 error 的 code。
    pub fn failure_error(&self, preferred: Option<&str>) -> CoreError {
        let code = preferred
            .map(|s| s.to_string())
            .or_else(|| {
                self.issues
                    .iter()
                    .find(|i| i.severity == "error")
                    .map(|i| i.code.clone())
            })
            .unwrap_or_else(|| "NF-VAL-001".to_string());
        let first = self.issues.iter().find(|i| i.severity == "error");
        let mut err = CoreError::new(&code);
        if let Some(i) = first {
            err = err
                .with_message(format!("{}: {}", i.path, i.message))
                .at(i.path.clone());
        }
        err.with_exit(1)
    }

    pub fn to_value(&self) -> Value {
        let (e, w, i) = self.counts();
        let issues: Vec<Value> = self
            .issues
            .iter()
            .map(|issue| {
                let mut v = json!({
                    "code": issue.code,
                    "severity": issue.severity,
                    "path": issue.path,
                    "message": issue.message,
                    "fix": issue.fix,
                });
                if let Some(rule) = &issue.rule {
                    v["rule"] = Value::String(rule.clone());
                }
                v
            })
            .collect();
        json!({
            "schema": "nf-validate-report/1",
            "target": {
                "kind": self.target_kind,
                "ref": self.target_ref,
                "digest": self.target_digest,
            },
            "level": self.level,
            "issues": issues,
            "summary": {"error": e, "warn": w, "info": i},
            "verdict": self.verdict(),
        })
    }
}

/// 单元错误 + 单条 issue 的快捷报告（exit 1 用）。
pub fn failure_report(
    level: &str,
    target: &Value,
    kind: &str,
    target_ref: &str,
    code: &str,
    path: &str,
    message: &str,
) -> Value {
    let mut r = Report::new(level, target, kind, target_ref);
    r.error(code, path, message);
    r.to_value()
}
