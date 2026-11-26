//! nf-fragment/1 + nf-composition/1：片段校验、引用/循环检测、条件/重复器/占位符渲染。

use crate::canonical::{digest_value, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::ops::{req_value, usage};
use crate::schema::validate;
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};

fn digest_without_digest(value: &Value) -> Result<String, CoreError> {
    let mut copy = value.clone();
    if let Some(obj) = copy.as_object_mut() {
        obj.remove("digest");
    }
    digest_value(&copy)
}

fn fragment_report(fragment: &Value) -> Result<Value, CoreError> {
    let issues = validate("nf-fragment", fragment);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-CMP-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    let blocks = fragment.get("blocks").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let mut ids = BTreeSet::new();
    for block in &blocks {
        let id = block.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if !ids.insert(id.to_string()) {
            return Err(CoreError::new("NF-CMP-001").with_message(format!("片段 block id 重复：{id}")).with_exit(1));
        }
    }
    Ok(json!({
        "schema": "nf-fragment-report/1",
        "id": fragment.get("id"),
        "blocks": blocks.len() as u64,
        "slots": fragment.get("slots").cloned().unwrap_or_else(|| json!([])),
        "digest": digest_without_digest(fragment)?
    }))
}

fn fragment_map(fragments: &[Value]) -> Result<BTreeMap<String, Value>, CoreError> {
    let mut map = BTreeMap::new();
    for fragment in fragments {
        let id = fragment.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if id.is_empty() {
            return Err(CoreError::new("NF-CMP-001").with_message("片段缺 id").with_exit(1));
        }
        fragment_report(fragment)?;
        if map.insert(id.to_string(), fragment.clone()).is_some() {
            return Err(CoreError::new("NF-CMP-002").with_message(format!("片段 id 重复：{id}")).with_exit(1));
        }
    }
    Ok(map)
}

fn fragment_refs(fragment: &Value) -> Vec<String> {
    let mut refs = Vec::new();
    for block in fragment.get("blocks").and_then(|v| v.as_array()).into_iter().flatten() {
        let text = block.get("text").and_then(|v| v.as_str()).unwrap_or("");
        let mut rest = text;
        while let Some(at) = rest.find("{{>") {
            let after = &rest[at + 3..];
            if let Some(end) = after.find("}}") {
                let id = after[..end].trim();
                if !id.is_empty() {
                    refs.push(id.to_string());
                }
                rest = &after[end + 2..];
            } else {
                break;
            }
        }
    }
    refs
}

fn detect_cycles(map: &BTreeMap<String, Value>) -> Result<(), CoreError> {
    fn visit(
        id: &str,
        map: &BTreeMap<String, Value>,
        visiting: &mut BTreeSet<String>,
        done: &mut BTreeSet<String>,
    ) -> Result<(), CoreError> {
        if done.contains(id) {
            return Ok(());
        }
        if !visiting.insert(id.to_string()) {
            return Err(CoreError::new("NF-CMP-002").with_message(format!("片段循环依赖：{id}")).with_exit(1));
        }
        if let Some(fragment) = map.get(id) {
            for next in fragment_refs(fragment) {
                if !map.contains_key(&next) {
                    return Err(CoreError::new("NF-CMP-002").with_message(format!("片段引用缺失：{next}")).with_exit(1));
                }
                visit(&next, map, visiting, done)?;
            }
        }
        visiting.remove(id);
        done.insert(id.to_string());
        Ok(())
    }
    let mut visiting = BTreeSet::new();
    let mut done = BTreeSet::new();
    for id in map.keys() {
        visit(id, map, &mut visiting, &mut done)?;
    }
    Ok(())
}

fn composition_report(composition: &Value, fragments: &[Value]) -> Result<(Value, BTreeMap<String, Value>), CoreError> {
    let issues = validate("nf-composition", composition);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-CMP-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    let map = fragment_map(fragments)?;
    for reference in composition.get("fragments").and_then(|v| v.as_array()).into_iter().flatten() {
        let id = reference.get("id").and_then(|v| v.as_str()).unwrap_or("");
        let pinned = reference.get("digest").and_then(|v| v.as_str()).unwrap_or("");
        let fragment = map.get(id).ok_or_else(|| CoreError::new("NF-CMP-002").with_message(format!("组合引用缺失：{id}")).with_exit(1))?;
        let actual = digest_without_digest(fragment)?;
        if actual != pinned {
            return Err(CoreError::new("NF-CMP-002").with_message(format!("片段摘要不符：{id}")).with_exit(1));
        }
    }
    for root in composition.get("roots").and_then(|v| v.as_array()).into_iter().flatten() {
        let id = root.as_str().unwrap_or("");
        if !map.contains_key(id) {
            return Err(CoreError::new("NF-CMP-002").with_message(format!("根片段缺失：{id}")).with_exit(1));
        }
    }
    detect_cycles(&map)?;
    Ok((json!({
        "schema": "nf-composition-report/1",
        "id": composition.get("id"),
        "fragments": map.len() as u64,
        "roots": composition.get("roots").cloned().unwrap_or_else(|| json!([]))
    }), map))
}

fn value_str(values: &Map<String, Value>, key: &str) -> Option<String> {
    values.get(key).and_then(|v| v.as_str()).map(ToString::to_string)
}

fn render_template(text: &str, values: &Map<String, Value>, map: &BTreeMap<String, Value>, stack: &mut BTreeSet<String>) -> Result<String, CoreError> {
    let mut out = String::new();
    let mut rest = text;
    while let Some(start) = rest.find("{{#if ") {
        out.push_str(&rest[..start]);
        let head = &rest[start + 6..];
        let head_end = head.find("}}").ok_or_else(|| CoreError::new("NF-CMP-003").with_message("if 未闭合").with_exit(1))?;
        let expr = head[..head_end].trim();
        let body_and_rest = &head[head_end + 2..];
        let close = body_and_rest.find("{{/if}}").ok_or_else(|| CoreError::new("NF-CMP-003").with_message("if 缺 {{/if}}").with_exit(1))?;
        let body = &body_and_rest[..close];
        let (key, expected) = expr.split_once('=').ok_or_else(|| CoreError::new("NF-CMP-003").with_message("if 条件应为 key=value").with_exit(1))?;
        if value_str(values, key.trim()).as_deref() == Some(expected.trim()) {
            out.push_str(&render_template(body, values, map, stack)?);
        }
        rest = &body_and_rest[close + 7..];
    }
    while let Some(start) = rest.find("{{#each ") {
        out.push_str(&rest[..start]);
        let head = &rest[start + 8..];
        let head_end = head.find("}}").ok_or_else(|| CoreError::new("NF-CMP-003").with_message("each 未闭合").with_exit(1))?;
        let key = head[..head_end].trim();
        let body_and_rest = &head[head_end + 2..];
        let close = body_and_rest.find("{{/each}}").ok_or_else(|| CoreError::new("NF-CMP-003").with_message("each 缺 {{/each}}").with_exit(1))?;
        let body = &body_and_rest[..close];
        let rows = values.get(key).and_then(|v| v.as_array()).ok_or_else(|| CoreError::new("NF-CMP-003").with_message(format!("each 需要数组：{key}")).with_exit(1))?;
        for row in rows {
            let mut row_values = values.clone();
            if let Some(obj) = row.as_object() {
                for (k, v) in obj {
                    if let Some(s) = v.as_str() {
                        row_values.insert(k.clone(), Value::String(s.to_string()));
                    }
                }
            }
            out.push_str(&render_template(body, &row_values, map, stack)?);
        }
        rest = &body_and_rest[close + 9..];
    }
    out.push_str(rest);
    let mut text = out;

    while let Some(at) = text.find("{{>") {
        let after = &text[at + 3..];
        let end = after.find("}}").ok_or_else(|| CoreError::new("NF-CMP-003").with_message("片段引用未闭合").with_exit(1))?;
        let id = after[..end].trim();
        if !stack.insert(id.to_string()) {
            return Err(CoreError::new("NF-CMP-002").with_message(format!("片段循环依赖：{id}")).with_exit(1));
        }
        let fragment = map.get(id).ok_or_else(|| CoreError::new("NF-CMP-002").with_message(format!("片段引用缺失：{id}")).with_exit(1))?;
        let rendered = render_fragment(fragment, values, map, stack)?;
        stack.remove(id);
        text.replace_range(at..at + 3 + end + 2, &rendered);
    }

    let mut result = String::new();
    let mut rest = text.as_str();
    while let Some(at) = rest.find("{{") {
        result.push_str(&rest[..at]);
        let after = &rest[at + 2..];
        let end = after.find("}}").ok_or_else(|| CoreError::new("NF-CMP-003").with_message("占位符未闭合").with_exit(1))?;
        let key = after[..end].trim();
        let value = value_str(values, key).ok_or_else(|| CoreError::new("NF-CMP-003").with_message(format!("占位符无值：{key}")).with_exit(1))?;
        result.push_str(&value);
        rest = &after[end + 2..];
    }
    result.push_str(rest);
    Ok(result)
}

fn render_fragment(fragment: &Value, values: &Map<String, Value>, map: &BTreeMap<String, Value>, stack: &mut BTreeSet<String>) -> Result<String, CoreError> {
    let mut parts = Vec::new();
    for block in fragment.get("blocks").and_then(|v| v.as_array()).into_iter().flatten() {
        let text = block.get("text").and_then(|v| v.as_str()).unwrap_or("");
        parts.push(render_template(text, values, map, stack)?);
    }
    Ok(parts.join("\n\n"))
}

pub fn fragment_validate_op(req: &Value) -> OpOutcome {
    let fragment = req_value(req, "fragment")?;
    Ok((0, fragment_report(fragment)?))
}

pub fn composition_validate_op(req: &Value) -> OpOutcome {
    let composition = req_value(req, "composition")?;
    let fragments = req.get("fragments").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let (report, _) = composition_report(composition, &fragments)?;
    Ok((0, report))
}

pub fn compose_render_op(req: &Value) -> OpOutcome {
    let composition = req_value(req, "composition")?;
    let fragments = req.get("fragments").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let (_, map) = composition_report(composition, &fragments)?;
    let values = req.get("values").and_then(|v| v.as_object()).cloned().unwrap_or_default();
    let mut parts = Vec::new();
    let mut stack = BTreeSet::new();
    for root in composition.get("roots").and_then(|v| v.as_array()).into_iter().flatten() {
        let id = root.as_str().unwrap_or("");
        if !stack.insert(id.to_string()) {
            return Err(CoreError::new("NF-CMP-002").with_message(format!("片段循环依赖：{id}")).with_exit(1));
        }
        let fragment = map.get(id).ok_or_else(|| CoreError::new("NF-CMP-002").with_message(format!("根片段缺失：{id}")).with_exit(1))?;
        parts.push(render_fragment(fragment, &values, &map, &mut stack)?);
        stack.remove(id);
    }
    let markdown = parts.join("\n\n") + "\n";
    Ok((0, json!({
        "schema": "nf-compose-result/1",
        "markdown": markdown,
        "sha256": sha256_hex(markdown.as_bytes()),
        "fragments": map.len() as u64
    })))
}

pub fn _usage() -> CoreError { usage("unused") }
