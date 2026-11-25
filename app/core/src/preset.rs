//! nf-preset/1：内置与自定义预设；只声明设置，不执行代码。

use crate::error::{CoreError, OpOutcome};
use crate::ops::{req_value};
use crate::schema::validate;
use serde_json::{json, Map, Value};

fn builtin(id: &str, name: &str, theme: &str, density: &str, profile: &str) -> Value {
    json!({"schema": "nf-preset/1", "id": id, "name": name, "version": 1,
        "settings": {"theme": theme, "language": "SYSTEM", "density": density, "profile": profile, "typeScale": 1.0},
        "extensions": []})
}

fn builtins() -> Vec<Value> {
    vec![
        builtin("default", "Default", "SYSTEM", "standard", "default"),
        builtin("accessible", "Accessible", "SYSTEM", "comfortable", "accessible"),
        builtin("print", "Print", "LIGHT", "compact", "print"),
        builtin("focus", "Focus", "DARK", "comfortable", "mobile"),
    ]
}

pub fn preset_list(req: &Value) -> OpOutcome {
    let mut out = builtins();
    if let Some(list) = req.get("presets").and_then(|v| v.as_array()) {
        for p in list {
            let issues = validate("nf-preset", p);
            if issues.is_empty() { out.push(p.clone()); }
        }
    }
    Ok((0, json!({"schema": "nf-preset-list/1", "presets": out})))
}

pub fn preset_apply(req: &Value) -> OpOutcome {
    let preset = req_value(req, "preset")?;
    let issues = validate("nf-preset", preset);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-PRESET-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    let mut prefs: Map<String, Value> = req.get("prefs").and_then(|v| v.as_object()).cloned().unwrap_or_default();
    if let Some(s) = preset.get("settings").and_then(|v| v.as_object()) {
        for (k, v) in s { prefs.insert(k.clone(), v.clone()); }
    }
    Ok((0, json!({"schema": "nf-preset-apply/1", "preset": preset, "prefs": prefs, "reversible": true})))
}

pub fn preset_list_op(req: &Value) -> OpOutcome { preset_list(req) }
pub fn preset_apply_op(req: &Value) -> OpOutcome { preset_apply(req) }
