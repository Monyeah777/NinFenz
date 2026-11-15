//! MD spec：spec-validate（结构/双向一致/约束/预算）与 L1 约束求值。

use crate::error::OpOutcome;
use crate::ops::{float_issue, ref_id, req_value};
use crate::report::Report;
use crate::schema::{regex_matches, validate};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

fn constraint_issue(op: &str, value: Option<&Value>) -> Option<String> {
    match op {
        "min_chars" | "max_chars" | "max_tokens" => match value {
            Some(Value::Number(n)) if n.is_i64() || n.is_u64() => {
                if n.as_i64().unwrap_or(0) <= 0 {
                    Some(format!("{op} 必须是正整数"))
                } else {
                    None
                }
            }
            Some(_) => Some(format!("{op} 的 value 必须是整数")),
            None => Some(format!("{op} 缺 value")),
        },
        "pattern" | "starts_with" | "ends_with" => match value {
            Some(Value::String(_)) => None,
            _ => Some(format!("{op} 的 value 必须是字符串")),
        },
        "non_empty" => None,
        _ => Some(format!("未知 constraint op {op}")),
    }
}

/// 对文本求值单条约束；返回 Err(定位说明)。
pub fn eval_constraint(constraint: &Value, text: &str) -> Result<(), String> {
    let op = constraint.get("op").and_then(|v| v.as_str()).unwrap_or("");
    let value = constraint.get("value");
    if let Some(msg) = constraint_issue(op, value) {
        return Err(msg);
    }
    let chars = text.chars().count() as u64;
    match op {
        "min_chars" => {
            let want = value.and_then(|v| v.as_u64()).unwrap_or(0);
            if chars < want {
                return Err(format!("字符数 {chars} < min_chars {want}"));
            }
        }
        "max_chars" => {
            let want = value.and_then(|v| v.as_u64()).unwrap_or(u64::MAX);
            if chars > want {
                return Err(format!("字符数 {chars} > max_chars {want}"));
            }
        }
        "max_tokens" => {
            let want = value.and_then(|v| v.as_u64()).unwrap_or(u64::MAX);
            let tokens = (chars + 3) / 4;
            if tokens > want {
                return Err(format!("估算 tokens {tokens} > max_tokens {want}"));
            }
        }
        "pattern" => {
            let pat = value.and_then(|v| v.as_str()).unwrap_or("");
            match regex_matches(pat, text) {
                Ok(true) => {}
                Ok(false) => return Err(format!("文本不匹配 pattern {pat:?}")),
                Err(e) => return Err(format!("pattern 无法求值: {e}")),
            }
        }
        "non_empty" => {
            if text.trim().is_empty() {
                return Err("文本为空（non_empty）".into());
            }
        }
        "starts_with" => {
            let p = value.and_then(|v| v.as_str()).unwrap_or("");
            if !text.starts_with(p) {
                return Err(format!("文本未以 {p:?} 开头"));
            }
        }
        "ends_with" => {
            let p = value.and_then(|v| v.as_str()).unwrap_or("");
            if !text.ends_with(p) {
                return Err(format!("文本未以 {p:?} 结尾"));
            }
        }
        _ => return Err(format!("未知 constraint op {op}")),
    }
    Ok(())
}

pub fn validate_spec(spec: &Value) -> Report {
    let mut report = Report::new("L0", spec, "md-spec", &ref_id(spec, "id"));
    let issues = validate("nf-md-spec", spec);
    report.extend_schema_issues("NF-SPC-001", &issues);
    float_issue(&mut report, spec, "NF-SPC-001");

    let sections: Vec<Value> = spec
        .get("sections")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let slots: Vec<Value> = spec
        .get("slots")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    // section/slot id 唯一
    let mut sec_seen = BTreeSet::new();
    let mut sec_ids = BTreeSet::new();
    for (i, sec) in sections.iter().enumerate() {
        if let Some(id) = sec.get("id").and_then(|v| v.as_str()) {
            sec_ids.insert(id.to_string());
            if !sec_seen.insert(id.to_string()) {
                report.error(
                    "NF-SPC-002",
                    &format!("$.sections[{i}].id"),
                    &format!("section id 重复：{id}"),
                );
            }
        }
    }
    let mut slot_seen = BTreeSet::new();
    let mut slot_by_id: BTreeMap<String, Value> = BTreeMap::new();
    for (i, slot) in slots.iter().enumerate() {
        if let Some(id) = slot.get("id").and_then(|v| v.as_str()) {
            slot_by_id.insert(id.to_string(), slot.clone());
            if !slot_seen.insert(id.to_string()) {
                report.error(
                    "NF-SPC-002",
                    &format!("$.slots[{i}].id"),
                    &format!("slot id 重复：{id}"),
                );
            }
        }
    }

    // order 唯一且从 1 连续
    let mut orders: Vec<i64> = Vec::new();
    for sec in &sections {
        if let Some(o) = sec.get("order").and_then(|v| v.as_i64()) {
            orders.push(o);
        }
    }
    let unique: BTreeSet<i64> = orders.iter().copied().collect();
    if unique.len() != orders.len() {
        report.error("NF-SPC-003", "$.sections", "section.order 不唯一");
    }
    let max_order = unique.iter().copied().max().unwrap_or(0);
    if max_order as usize != unique.len() {
        report.error(
            "NF-SPC-003",
            "$.sections",
            "section.order 必须从 1 连续（当前集合不连续）",
        );
    }
    for (want, got) in unique.iter().enumerate() {
        if *got != (want as i64) + 1 {
            report.error(
                "NF-SPC-003",
                "$.sections",
                &format!("section.order 期望 {}，实际 {got}", want + 1),
            );
            break;
        }
    }

    // 双向一致
    for (i, sec) in sections.iter().enumerate() {
        let sid = sec.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if let Some(list) = sec.get("slots").and_then(|v| v.as_array()) {
            for (j, s) in list.iter().enumerate() {
                let id = s.as_str().unwrap_or("");
                match slot_by_id.get(id) {
                    None => report.error(
                        "NF-SPC-002",
                        &format!("$.sections[{i}].slots[{j}]"),
                        &format!("section 引用了不存在的槽位 {id}"),
                    ),
                    Some(slot) => {
                        if slot.get("section").and_then(|v| v.as_str()) != Some(sid) {
                            report.error(
                                "NF-SPC-002",
                                &format!("$.sections[{i}].slots[{j}]"),
                                &format!("槽位 {id} 的 section 不是 {sid}（双向不一致）"),
                            );
                        }
                    }
                }
            }
        }
    }
    for (i, slot) in slots.iter().enumerate() {
        let sid = slot.get("section").and_then(|v| v.as_str()).unwrap_or("");
        if !sid.is_empty() && !sec_ids.contains(sid) {
            report.error(
                "NF-SPC-002",
                &format!("$.slots[{i}].section"),
                &format!("槽位引用了不存在的 section {sid}"),
            );
            continue;
        }
        let declared = sections.iter().any(|sec| {
            sec.get("id").and_then(|v| v.as_str()) == Some(sid)
                && sec
                    .get("slots")
                    .and_then(|v| v.as_array())
                    .map(|a| {
                        a.iter().any(|x| {
                            x.as_str()
                                == slot.get("id").and_then(|v| v.as_str())
                        })
                    })
                    .unwrap_or(false)
        });
        if !declared {
            report.error(
                "NF-SPC-002",
                &format!("$.slots[{i}].id"),
                "槽位未被其 section.slots 声明（双向不一致）",
            );
        }
    }

    // acceptance id 唯一
    let mut acc_ids: BTreeSet<String> = BTreeSet::new();
    if let Some(acc) = spec.get("acceptance").and_then(|v| v.as_array()) {
        for (i, a) in acc.iter().enumerate() {
            if let Some(id) = a.get("id").and_then(|v| v.as_str()) {
                if !acc_ids.insert(id.to_string()) {
                    report.error(
                        "NF-SPC-005",
                        &format!("$.acceptance[{i}].id"),
                        &format!("acceptance id 重复：{id}"),
                    );
                }
            }
        }
    }

    // slots 约束/预算/acceptance 引用
    for (i, slot) in slots.iter().enumerate() {
        if let Some(cs) = slot.get("constraints").and_then(|v| v.as_array()) {
            let mut min_chars: Option<u64> = None;
            let mut max_chars: Option<u64> = None;
            for (j, c) in cs.iter().enumerate() {
                let op = c.get("op").and_then(|v| v.as_str()).unwrap_or("");
                if let Some(msg) = constraint_issue(op, c.get("value")) {
                    report.error(
                        "NF-SPC-003",
                        &format!("$.slots[{i}].constraints[{j}]"),
                        &msg,
                    );
                    continue;
                }
                if op == "pattern" {
                    let pat = c.get("value").and_then(|v| v.as_str()).unwrap_or("");
                    if let Err(e) = regex_matches(pat, "") {
                        report.error(
                            "NF-SPC-003",
                            &format!("$.slots[{i}].constraints[{j}]"),
                            &format!("pattern 非法：{e}"),
                        );
                    }
                }
                if op == "min_chars" {
                    min_chars = c.get("value").and_then(|v| v.as_u64());
                }
                if op == "max_chars" {
                    max_chars = c.get("value").and_then(|v| v.as_u64());
                }
            }
            if let (Some(a), Some(b)) = (min_chars, max_chars) {
                if a > b {
                    report.error(
                        "NF-SPC-003",
                        &format!("$.slots[{i}].constraints"),
                        &format!("min_chars {a} > max_chars {b}"),
                    );
                }
            }
        }
        if let Some(acc) = slot.get("acceptance").and_then(|v| v.as_array()) {
            for (j, a) in acc.iter().enumerate() {
                let id = a.as_str().unwrap_or("");
                if !acc_ids.contains(id) {
                    report.error(
                        "NF-SPC-002",
                        &format!("$.slots[{i}].acceptance[{j}]"),
                        &format!("槽位引用了不存在的 acceptance {id}"),
                    );
                }
            }
        }
    }

    // 顶层预算（可选）：给了才判 Σ slot 预算超出 → NF-SPC-004
    if let Some(budget) = spec.get("budget") {
        let sum_chars: u64 = slots
            .iter()
            .filter_map(|s| s.get("budget").and_then(|b| b.get("max_chars")).and_then(|v| v.as_u64()))
            .sum();
        let sum_tokens: u64 = slots
            .iter()
            .filter_map(|s| s.get("budget").and_then(|b| b.get("max_tokens")).and_then(|v| v.as_u64()))
            .sum();
        if let Some(max) = budget.get("max_total_chars").and_then(|v| v.as_u64()) {
            if sum_chars > max {
                report.error(
                    "NF-SPC-004",
                    "$.budget.max_total_chars",
                    &format!("Σ slot max_chars = {sum_chars} > max_total_chars {max}"),
                );
            }
        }
        if let Some(max) = budget.get("max_total_tokens").and_then(|v| v.as_u64()) {
            if sum_tokens > max {
                report.error(
                    "NF-SPC-004",
                    "$.budget.max_total_tokens",
                    &format!("Σ slot max_tokens = {sum_tokens} > max_total_tokens {max}"),
                );
            }
        }
    }

    // references 去重
    if let Some(refs) = spec.get("references").and_then(|v| v.as_array()) {
        let mut seen = BTreeSet::new();
        for (i, r) in refs.iter().enumerate() {
            let key = format!(
                "{}\u{0}{}",
                r.get("kind").and_then(|v| v.as_str()).unwrap_or(""),
                r.get("ref").and_then(|v| v.as_str()).unwrap_or("")
            );
            if !seen.insert(key) {
                report.error(
                    "NF-SPC-003",
                    &format!("$.references[{i}]"),
                    "重复引用（kind+ref）",
                );
            }
        }
    }
    report
}

pub fn spec_validate(req: &Value) -> OpOutcome {
    let spec = req_value(req, "spec")?;
    Ok((0, validate_spec(spec).to_value()))
}
