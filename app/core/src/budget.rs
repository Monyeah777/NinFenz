//! nf-budget/1：性能与资源预算；超限按 policy fail/warn。

use crate::error::{CoreError, OpOutcome};
use crate::ops::{req_value, usage};
use crate::schema::validate;
use serde_json::{json, Value};

const SCHEMA: &str = "nf-budget/1";

fn num(v: &Value, k: &str) -> f64 {
    v.get(k).and_then(|x| x.as_f64()).unwrap_or(0.0)
}

pub fn budget_check(req: &Value) -> OpOutcome {
    let mut budget = req_value(req, "budget")?.clone();
    let limits = budget.get("limits").cloned().ok_or_else(|| usage("budget 缺 limits"))?;
    let observed = budget.get("observed").cloned().ok_or_else(|| usage("budget 缺 observed"))?;
    let mut violations: Vec<String> = Vec::new();
    for (k, label) in [("seconds", "seconds"), ("peak_mb", "peak_mb"), ("pages", "pages"), ("blocks", "blocks")] {
        let l = num(&limits, k);
        let o = num(&observed, k);
        if o > l {
            violations.push(format!("{label}: {o} > {l}"));
        }
    }
    let policy = budget.get("policy").and_then(|v| v.as_str()).unwrap_or("fail").to_string();
    if !matches!(policy.as_str(), "fail" | "warn") {
        return Err(CoreError::new("NF-BUD-001").with_message("policy 必须是 fail|warn").with_exit(1));
    }
    let within = violations.is_empty();
    let obj = budget.as_object_mut().unwrap();
    obj.insert("ok".into(), Value::Bool(within));
    obj.insert("reason".into(), Value::String(if violations.is_empty() { "within budget".into() } else { violations.join("; ") }));
    let issues = validate("nf-budget", &budget);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-BUD-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    Ok((if within || policy == "warn" { 0 } else { 1 }, json!({
        "schema": SCHEMA,
        "budget": budget,
        "ok": within,
        "violations": violations
    })))
}

pub fn budget_check_op(req: &Value) -> OpOutcome { budget_check(req) }
