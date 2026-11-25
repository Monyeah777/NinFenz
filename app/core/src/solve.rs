//! 约束求解/规划：从槽位需求 + 模块候选 + 预算/冲突求合法计划，并给 unsat core。
//! 有界 DFS；确定性排序；不依赖外部 SAT 求解器。

use crate::error::OpOutcome;
use crate::ops::{req_value, usage};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone)]
struct Module {
    id: String,
    provides: BTreeSet<String>,
    requires: Vec<String>,
    cost: u64,
    conflicts: BTreeSet<String>,
}

fn parse_modules(req: &Value) -> Result<Vec<Module>, crate::error::CoreError> {
    let arr = req
        .get("modules")
        .and_then(|v| v.as_array())
        .ok_or_else(|| usage("plan-solve 需要 modules:[{id,provides,requires?,cost?,conflicts?}]"))?;
    let mut out = Vec::new();
    let mut ids = BTreeSet::new();
    for (i, m) in arr.iter().enumerate() {
        let id = m
            .get("id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .ok_or_else(|| usage(format!("modules[{i}].id 缺失")))?;
        if !ids.insert(id.to_string()) {
            return Err(usage(format!("modules[{i}].id 重复：{id}")));
        }
        let provides = m
            .get("provides")
            .and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect())
            .unwrap_or_default();
        let requires = m
            .get("requires")
            .and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect())
            .unwrap_or_default();
        let conflicts = m
            .get("conflicts")
            .and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect())
            .unwrap_or_default();
        out.push(Module {
            id: id.to_string(),
            provides,
            requires,
            cost: m.get("cost").and_then(|v| v.as_u64()).unwrap_or(1),
            conflicts,
        });
    }
    out.sort_by(|a, b| a.id.cmp(&b.id));
    Ok(out)
}

fn parse_slots(req: &Value) -> Result<Vec<String>, crate::error::CoreError> {
    let arr = req
        .get("slots")
        .and_then(|v| v.as_array())
        .ok_or_else(|| usage("plan-solve 需要 slots:[id|{id,required?}]"))?;
    let mut out = Vec::new();
    for (i, s) in arr.iter().enumerate() {
        if let Some(id) = s.as_str() {
            out.push(id.to_string());
        } else if let Some(id) = s.get("id").and_then(|v| v.as_str()) {
            if s.get("required").and_then(|v| v.as_bool()).unwrap_or(true) {
                out.push(id.to_string());
            }
        } else {
            return Err(usage(format!("slots[{i}] 非法")));
        }
    }
    out.sort();
    out.dedup();
    Ok(out)
}

struct Search<'a> {
    modules: &'a [Module],
    slots: &'a [String],
    budget: u64,
    assets: BTreeSet<String>,
    best: Option<(u64, Vec<String>, BTreeMap<String, String>)>,
    nodes: u64,
    limit: u64,
    timed_out: bool,
}

impl<'a> Search<'a> {
    fn feasible(&self, selected: &[usize]) -> Option<(u64, BTreeMap<String, String>)> {
        let set: BTreeSet<&str> = selected.iter().map(|i| self.modules[*i].id.as_str()).collect();
        let mut fills: BTreeMap<String, String> = BTreeMap::new();
        let mut cost = 0u64;
        for i in selected {
            let m = &self.modules[*i];
            cost += m.cost;
            for r in &m.requires {
                if let Some(tag) = r.strip_prefix("asset:") {
                    if !self.assets.contains(tag) {
                        return None;
                    }
                } else if !set.contains(r.as_str()) {
                    return None;
                }
            }
            for s in &m.provides {
                if self.slots.contains(s) {
                    fills.entry(s.clone()).or_insert_with(|| m.id.clone());
                }
            }
            for c in &m.conflicts {
                if set.contains(c.as_str()) {
                    return None;
                }
            }
        }
        if self.slots.iter().any(|s| !fills.contains_key(s)) {
            return None;
        }
        if cost > self.budget {
            return None;
        }
        Some((cost, fills))
    }

    fn dfs(&mut self, idx: usize, selected: &mut Vec<usize>) {
        if self.nodes >= self.limit {
            self.timed_out = true;
            return;
        }
        self.nodes += 1;
        if idx == self.modules.len() {
            if let Some((cost, fills)) = self.feasible(selected) {
                let ids: Vec<String> = selected.iter().map(|i| self.modules[*i].id.clone()).collect();
                let better = match &self.best {
                    None => true,
                    Some((bc, bi, _)) => cost < *bc || (cost == *bc && ids < *bi),
                };
                if better {
                    self.best = Some((cost, ids, fills));
                }
            }
            return;
        }
        // 剪枝：当前成本已超预算
        let current: u64 = selected.iter().map(|i| self.modules[*i].cost).sum();
        if current <= self.budget {
            selected.push(idx);
            self.dfs(idx + 1, selected);
            selected.pop();
        }
        self.dfs(idx + 1, selected);
    }
}

fn solve_value(req: &Value) -> Result<Value, crate::error::CoreError> {
    let modules = parse_modules(req)?;
    let slots = parse_slots(req)?;
    let budget = req.get("budget").and_then(|v| v.as_u64()).unwrap_or(u64::MAX);
    let assets: BTreeSet<String> = req
        .get("assets")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().map(|x| x.as_str().unwrap_or("").to_string()).collect())
        .unwrap_or_default();
    let mut s = Search {
        modules: &modules,
        slots: &slots,
        budget,
        assets: assets.clone(),
        best: None,
        nodes: 0,
        limit: req.get("max_nodes").and_then(|v| v.as_u64()).unwrap_or(200_000),
        timed_out: false,
    };
    s.dfs(0, &mut Vec::new());
    if let Some((cost, ids, fills)) = s.best {
        Ok(json!({
            "schema": "nf-plan-result/1",
            "satisfiable": true,
            "selected": ids,
            "fills": fills,
            "cost": cost,
            "nodes": s.nodes,
            "unsat_core": []
        }))
    } else {
        // unsat core：逐个移除必需槽位，若变为可满足则该槽位在核里。
        let mut core: Vec<String> = Vec::new();
        let mut reasons: Vec<String> = Vec::new();
        for slot in &slots {
            let rest: Vec<String> = slots.iter().filter(|s| *s != slot).cloned().collect();
            let mut s2 = Search {
                modules: &modules,
                slots: &rest,
                budget,
                assets: assets.clone(),
                best: None,
                nodes: 0,
                limit: 50_000,
                timed_out: false,
            };
            s2.dfs(0, &mut Vec::new());
            if s2.best.is_some() {
                core.push(slot.clone());
            }
            if !modules.iter().any(|m| m.provides.contains(slot)) {
                reasons.push(format!("槽位 {slot} 无任何模块提供"));
            }
        }
        if core.is_empty() {
            reasons.push("预算/冲突/依赖使计划不可满足".to_string());
        }
        Ok(json!({
            "schema": "nf-plan-result/1",
            "satisfiable": false,
            "selected": [],
            "fills": {},
            "cost": 0,
            "nodes": s.nodes,
            "unsat_core": core,
            "reasons": reasons
        }))
    }
}

pub fn solve(req: &Value) -> OpOutcome {
    Ok((0, solve_value(req)?))
}

pub fn explain(req: &Value) -> OpOutcome {
    let result = if req.get("result").is_some() {
        req_value(req, "result")?.clone()
    } else {
        solve_value(req)?
    };
    let mut lines: Vec<String> = Vec::new();
    if result.get("satisfiable").and_then(|v| v.as_bool()).unwrap_or(false) {
        lines.push(format!("选中 {} 个模块，成本 {}", result["selected"].as_array().map(|a| a.len()).unwrap_or(0), result["cost"]));
        if let Some(fills) = result.get("fills").and_then(|v| v.as_object()) {
            for (slot, m) in fills {
                lines.push(format!("槽位 {slot} ← {m}"));
            }
        }
    } else {
        lines.push("不可满足（unsat）".to_string());
        for s in result.get("unsat_core").and_then(|v| v.as_array()).into_iter().flatten() {
            lines.push(format!("核心槽位：{}", s.as_str().unwrap_or("")));
        }
        for r in result.get("reasons").and_then(|v| v.as_array()).into_iter().flatten() {
            lines.push(format!("原因：{}", r.as_str().unwrap_or("")));
        }
    }
    Ok((0, json!({"schema": "nf-plan-explain/1", "result": result, "explanation": lines})))
}

pub fn plan_solve_op(req: &Value) -> OpOutcome { solve(req) }
pub fn plan_explain_op(req: &Value) -> OpOutcome { explain(req) }
