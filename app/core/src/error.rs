//! 错误码登记表（单一真源 = app/schema/error_codes.json，编译期内嵌）与响应信封。

use serde_json::{json, Map, Value};
use std::collections::BTreeMap;
use std::sync::OnceLock;

#[derive(Clone, Debug)]
pub struct CodeMeta {
    pub severity: String,
    pub exit: i32,
    pub message: String,
    pub fix: String,
}

pub fn registry() -> &'static BTreeMap<String, CodeMeta> {
    static REG: OnceLock<BTreeMap<String, CodeMeta>> = OnceLock::new();
    REG.get_or_init(|| {
        let raw = include_str!("../../schema/error_codes.json");
        let doc: Value = serde_json::from_str(raw).expect("error_codes.json 必须是合法 JSON");
        let mut map = BTreeMap::new();
        for c in doc["codes"].as_array().expect("codes 必须是数组") {
            let code = c["code"].as_str().expect("code 必须是字符串").to_string();
            map.insert(
                code,
                CodeMeta {
                    severity: c["severity"].as_str().unwrap_or("error").to_string(),
                    exit: c["exit"].as_i64().unwrap_or(3) as i32,
                    message: c["message"].as_str().unwrap_or("").to_string(),
                    fix: c["fix"].as_str().unwrap_or("").to_string(),
                },
            );
        }
        map
    })
}

#[derive(Clone, Debug)]
pub struct CoreError {
    pub code: String,
    pub message: String,
    pub fix: String,
    pub path: Option<String>,
    pub exit: i32,
}

impl CoreError {
    /// 从登记表取 code/message/fix/exit；未登记的码会保留字面量（测试会扫描源码防漏登）。
    pub fn new(code: &str) -> Self {
        match registry().get(code) {
            Some(meta) => CoreError {
                code: code.to_string(),
                message: meta.message.clone(),
                fix: meta.fix.clone(),
                path: None,
                exit: meta.exit,
            },
            None => CoreError {
                code: code.to_string(),
                message: format!("错误码 {code} 未在 error_codes.json 登记"),
                fix: "补登记错误码".to_string(),
                path: None,
                exit: 3,
            },
        }
    }

    pub fn with_message(mut self, message: impl Into<String>) -> Self {
        self.message = message.into();
        self
    }

    pub fn with_fix(mut self, fix: impl Into<String>) -> Self {
        self.fix = fix.into();
        self
    }

    pub fn at(mut self, path: impl Into<String>) -> Self {
        self.path = Some(path.into());
        self
    }

    pub fn with_exit(mut self, exit: i32) -> Self {
        self.exit = exit;
        self
    }

    pub fn to_value(&self) -> Value {
        let mut m = Map::new();
        m.insert("code".into(), Value::String(self.code.clone()));
        m.insert("message".into(), Value::String(self.message.clone()));
        m.insert("fix".into(), Value::String(self.fix.clone()));
        if let Some(p) = &self.path {
            m.insert("path".into(), Value::String(p.clone()));
        }
        Value::Object(m)
    }
}

/// 进程响应信封（CLI.md §2）。
#[derive(Clone, Debug)]
pub struct Envelope {
    pub ok: bool,
    pub exit: i32,
    pub result: Option<Value>,
    pub error: Option<Value>,
}

impl Envelope {
    pub fn success(result: Value) -> Self {
        Envelope {
            ok: true,
            exit: 0,
            result: Some(result),
            error: None,
        }
    }

    /// 成功但带 warn（如 NF-IMP-002 低置信）：exit 0，warning 在 result 内。
    pub fn success_exit(result: Value, exit: i32) -> Self {
        Envelope {
            ok: exit == 0,
            exit,
            result: Some(result),
            error: None,
        }
    }

    /// 失败：exit 1 时必须带 report（CLI.md §2），其余 result=null。
    pub fn failure(err: &CoreError, report: Option<Value>) -> Self {
        debug_assert!(err.exit != 1 || report.is_some(), "exit 1 必须给 nf-validate-report");
        Envelope {
            ok: false,
            exit: err.exit,
            result: report,
            error: Some(err.to_value()),
        }
    }

    pub fn to_value(&self) -> Value {
        json!({
            "ok": self.ok,
            "exit": self.exit,
            "result": self.result.clone().unwrap_or(Value::Null),
            "error": self.error.clone().unwrap_or(Value::Null),
        })
    }
}

/// 所有 op 的实现签名：成功返回 (exit, result)，失败返回错误。
pub type OpOutcome = Result<(i32, Value), CoreError>;
