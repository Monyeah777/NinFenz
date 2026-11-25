//! 管线图：graph-validate（L0+L1）/ graph-compile（→ nf-assembly-plan/1）。

use crate::canonical::digest_with_excludes;
use crate::error::{CoreError, OpOutcome};
use crate::ops::{float_issue, ref_id, req_value};
use crate::report::Report;
use crate::schema::validate;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet, VecDeque};

fn node_ids(graph: &Value) -> BTreeSet<String> {
    graph
        .get("nodes")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|n| n.get("id").and_then(|v| v.as_str()).map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default()
}

fn nodes_array(graph: &Value) -> Vec<Value> {
    graph
        .get("nodes")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
}

fn edges_array(graph: &Value) -> Vec<Value> {
    graph
        .get("edges")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
}

fn find_node<'a>(nodes: &'a [Value], id: &str) -> Option<&'a Value> {
    nodes
        .iter()
        .find(|n| n.get("id").and_then(|v| v.as_str()) == Some(id))
}

fn kind_of(nodes: &[Value], id: &str) -> Option<String> {
    find_node(nodes, id)
        .and_then(|n| n.get("kind"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
}

/// graph-validate 的核心（graph-compile 复用）。
pub fn validate_graph(graph: &Value) -> Report {
    let mut report = Report::new("L0", graph, "pipeline-graph", &ref_id(graph, "id"));
    let schema_issues = validate("nf-pipeline-graph", graph);
    report.extend_schema_issues("NF-GRF-001", &schema_issues);
    float_issue(&mut report, graph, "NF-GRF-001");

    let nodes = nodes_array(graph);
    let edges = edges_array(graph);
    let node_set = node_ids(graph);

    // id 唯一
    for (key, path) in [("nodes", "$.nodes"), ("edges", "$.edges")] {
        let mut seen = BTreeSet::new();
        if let Some(arr) = graph.get(key).and_then(|v| v.as_array()) {
            for (i, item) in arr.iter().enumerate() {
                if let Some(id) = item.get("id").and_then(|v| v.as_str()) {
                    if !seen.insert(id.to_string()) {
                        report.error(
                            "NF-GRF-002",
                            &format!("{path}[{i}].id"),
                            &format!("{key} id 重复：{id}"),
                        );
                    }
                }
            }
        }
    }

    // 端点/端口
    let has_port = |node: &Value, dir: &str, port: &str| -> bool {
        node.get("ports")
            .and_then(|p| p.get(dir))
            .and_then(|v| v.as_array())
            .map(|a| a.iter().any(|x| x.as_str() == Some(port)))
            .unwrap_or(false)
    };
    for (i, e) in edges.iter().enumerate() {
        let from = e.get("from").and_then(|v| v.as_str()).unwrap_or("");
        let to = e.get("to").and_then(|v| v.as_str()).unwrap_or("");
        match (find_node(&nodes, from), find_node(&nodes, to)) {
            (Some(fnode), Some(tnode)) => {
                let fp = e.get("from_port").and_then(|v| v.as_str()).unwrap_or("");
                let tp = e.get("to_port").and_then(|v| v.as_str()).unwrap_or("");
                if !has_port(fnode, "out", fp) {
                    report.error(
                        "NF-GRF-003",
                        &format!("$.edges[{i}].from_port"),
                        &format!("节点 {from} 未声明输出端口 {fp}"),
                    );
                }
                if !has_port(tnode, "in", tp) {
                    report.error(
                        "NF-GRF-003",
                        &format!("$.edges[{i}].to_port"),
                        &format!("节点 {to} 未声明输入端口 {tp}"),
                    );
                }
                if from == to {
                    report.error(
                        "NF-GRF-004",
                        &format!("$.edges[{i}]"),
                        &format!("自环边 {from}->{to} 构成环"),
                    );
                }
            }
            (None, _) => report.error(
                "NF-GRF-003",
                &format!("$.edges[{i}].from"),
                &format!("边引用了不存在的节点 {from}"),
            ),
            (_, None) => report.error(
                "NF-GRF-003",
                &format!("$.edges[{i}].to"),
                &format!("边引用了不存在的节点 {to}"),
            ),
        }
    }

    // kind ↔ 必填字段
    for (i, n) in nodes.iter().enumerate() {
        let kind = n.get("kind").and_then(|v| v.as_str()).unwrap_or("");
        if kind == "module" && n.get("module_ref").is_none() {
            report.error(
                "NF-GRF-001",
                &format!("$.nodes[{i}].module_ref"),
                "module 节点必须有 module_ref",
            );
        }
        if kind == "asset" && n.get("asset_refs").is_none() {
            report.warn(
                "NF-GRF-001",
                &format!("$.nodes[{i}].asset_refs"),
                "asset 节点没有 asset_refs（可为空但建议声明）",
            );
        }
    }

    // 模式限制
    let mode = graph.get("mode").and_then(|v| v.as_str()).unwrap_or("");
    if mode == "simple" {
        for (i, n) in nodes.iter().enumerate() {
            let kind = n.get("kind").and_then(|v| v.as_str()).unwrap_or("");
            if matches!(kind, "branch" | "merge" | "asset") {
                report.error(
                    "NF-GRF-006",
                    &format!("$.nodes[{i}].kind"),
                    &format!("simple 模式禁止 {kind} 节点"),
                );
            }
        }
    }

    // 权重
    if let Some(weights) = graph.get("weights").and_then(|v| v.as_object()) {
        for (id, _) in weights.iter() {
            match kind_of(&nodes, id) {
                Some(k) if k == "stage" || k == "module" => {}
                Some(k) => report.error(
                    "NF-GRF-007",
                    &format!("$.weights.{id}"),
                    &format!("权重只能挂在 stage/module，节点 {id} 是 {k}"),
                ),
                None => report.error(
                    "NF-GRF-007",
                    &format!("$.weights.{id}"),
                    &format!("权重引用了不存在的节点 {id}"),
                ),
            }
        }
    }

    // 结构：≥1 stage / ≥1 module；required_stages
    let stages: Vec<String> = nodes
        .iter()
        .filter(|n| n.get("kind").and_then(|v| v.as_str()) == Some("stage"))
        .filter_map(|n| n.get("id").and_then(|v| v.as_str()).map(|s| s.to_string()))
        .collect();
    let modules: Vec<String> = nodes
        .iter()
        .filter(|n| n.get("kind").and_then(|v| v.as_str()) == Some("module"))
        .filter_map(|n| n.get("id").and_then(|v| v.as_str()).map(|s| s.to_string()))
        .collect();
    if stages.is_empty() {
        report.error("NF-GRF-005", "$.nodes", "图必须至少有 1 个 stage 节点");
    }
    if modules.is_empty() {
        report.error("NF-GRF-005", "$.nodes", "图必须至少有 1 个 module 节点");
    }
    if let Some(req) = graph
        .get("settings")
        .and_then(|s| s.get("required_stages"))
        .and_then(|v| v.as_array())
    {
        for (i, r) in req.iter().enumerate() {
            let id = r.as_str().unwrap_or("");
            match kind_of(&nodes, id) {
                Some(k) if k == "stage" => {}
                Some(_) => report.error(
                    "NF-GRF-005",
                    &format!("$.settings.required_stages[{i}]"),
                    &format!("required_stages 引用的 {id} 不是 stage 节点"),
                ),
                None => report.error(
                    "NF-GRF-005",
                    &format!("$.settings.required_stages[{i}]"),
                    &format!("required_stages 引用了不存在的节点 {id}"),
                ),
            }
        }
    }

    // 分支/合并度数
    let mut indeg: BTreeMap<String, usize> = BTreeMap::new();
    let mut outdeg: BTreeMap<String, usize> = BTreeMap::new();
    for id in &node_set {
        indeg.insert(id.clone(), 0);
        outdeg.insert(id.clone(), 0);
    }
    for e in &edges {
        let f = e.get("from").and_then(|v| v.as_str()).unwrap_or("");
        let t = e.get("to").and_then(|v| v.as_str()).unwrap_or("");
        if node_set.contains(f) && node_set.contains(t) && f != t {
            *outdeg.entry(f.to_string()).or_insert(0) += 1;
            *indeg.entry(t.to_string()).or_insert(0) += 1;
        }
    }
    for (i, n) in nodes.iter().enumerate() {
        let id = n.get("id").and_then(|v| v.as_str()).unwrap_or("");
        match n.get("kind").and_then(|v| v.as_str()) {
            Some("branch") => {
                if outdeg.get(id).copied().unwrap_or(0) < 2 {
                    report.error(
                        "NF-GRF-005",
                        &format!("$.nodes[{i}]"),
                        &format!("branch 节点 {id} 出边必须 ≥2"),
                    );
                }
            }
            Some("merge") => {
                if indeg.get(id).copied().unwrap_or(0) < 2 {
                    report.error(
                        "NF-GRF-005",
                        &format!("$.nodes[{i}]"),
                        &format!("merge 节点 {id} 入边必须 ≥2"),
                    );
                }
            }
            _ => {}
        }
    }

    // 环检测（Kahn）
    let mut topo_indeg = indeg.clone();
    let mut queue: VecDeque<String> = topo_indeg
        .iter()
        .filter(|(_, d)| **d == 0)
        .map(|(k, _)| k.clone())
        .collect();
    let mut adj: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for e in &edges {
        let f = e.get("from").and_then(|v| v.as_str()).unwrap_or("");
        let t = e.get("to").and_then(|v| v.as_str()).unwrap_or("");
        if node_set.contains(f) && node_set.contains(t) {
            adj.entry(f.to_string()).or_default().push(t.to_string());
        }
    }
    let mut visited = 0usize;
    while let Some(n) = queue.pop_front() {
        visited += 1;
        if let Some(nexts) = adj.get(&n) {
            for m in nexts {
                if let Some(d) = topo_indeg.get_mut(m) {
                    *d -= 1;
                    if *d == 0 {
                        queue.push_back(m.clone());
                    }
                }
            }
        }
    }
    if visited < node_set.len() {
        let remaining: Vec<String> = topo_indeg
            .iter()
            .filter(|(_, d)| **d > 0)
            .map(|(k, _)| k.clone())
            .collect();
        report.error(
            "NF-GRF-004",
            "$.edges",
            &format!("管线图含环（非 DAG）；环上/受影响节点: {}", remaining.join(",")),
        );
    }

    // 可达性：入口（无入边的 stage；无 stage 入口时退回全部无入边节点）→ 全部节点；全部节点 → 出口
    let stage_roots: Vec<String> = nodes
        .iter()
        .filter(|n| n.get("kind").and_then(|v| v.as_str()) == Some("stage"))
        .filter_map(|n| n.get("id").and_then(|v| v.as_str()).map(|s| s.to_string()))
        .filter(|id| indeg.get(id).copied().unwrap_or(0) == 0)
        .collect();
    let entries: Vec<String> = if stage_roots.is_empty() {
        node_set
            .iter()
            .filter(|id| indeg.get(*id).copied().unwrap_or(0) == 0)
            .cloned()
            .collect()
    } else {
        stage_roots
    };
    let exits: Vec<String> = node_set
        .iter()
        .filter(|id| outdeg.get(*id).copied().unwrap_or(0) == 0)
        .cloned()
        .collect();
    let mut fwd: BTreeSet<String> = entries.iter().cloned().collect();
    let mut stack: Vec<String> = entries.clone();
    while let Some(n) = stack.pop() {
        if let Some(nexts) = adj.get(&n) {
            for m in nexts {
                if fwd.insert(m.clone()) {
                    stack.push(m.clone());
                }
            }
        }
    }
    let mut radj: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for (f, ts) in &adj {
        for t in ts {
            radj.entry(t.clone()).or_default().push(f.clone());
        }
    }
    let mut bwd: BTreeSet<String> = exits.iter().cloned().collect();
    let mut stack2: Vec<String> = exits.clone();
    while let Some(n) = stack2.pop() {
        if let Some(prev) = radj.get(&n) {
            for m in prev {
                if bwd.insert(m.clone()) {
                    stack2.push(m.clone());
                }
            }
        }
    }
    for (i, n) in nodes.iter().enumerate() {
        let id = n.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if !node_set.contains(id) {
            continue;
        }
        if entries.is_empty() {
            break;
        }
        if !fwd.contains(id) {
            report.error(
                "NF-GRF-005",
                &format!("$.nodes[{i}]"),
                &format!("节点 {id} 从入口不可达"),
            );
        }
        if !bwd.contains(id) {
            report.error(
                "NF-GRF-005",
                &format!("$.nodes[{i}]"),
                &format!("节点 {id} 无法到达出口"),
            );
        }
    }
    report
}

pub fn graph_typecheck(req: &Value) -> OpOutcome {
    let graph = req_value(req, "graph")?;
    let mut report = validate_graph(graph);
    let nodes = graph.get("nodes").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let edges = graph.get("edges").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let mut fanin: BTreeMap<(String, String), usize> = BTreeMap::new();
    for (i, e) in edges.iter().enumerate() {
        let ty = e.get("type").and_then(|v| v.as_str()).unwrap_or("data");
        if ty != "data" {
            continue;
        }
        let from_port = e.get("from_port").and_then(|v| v.as_str()).unwrap_or("");
        let to_port = e.get("to_port").and_then(|v| v.as_str()).unwrap_or("");
        let to = e.get("to").and_then(|v| v.as_str()).unwrap_or("").to_string();
        if from_port != to_port {
            report.error(
                "NF-GRF-008",
                &format!("$.edges[{i}]"),
                &format!("端口类型不匹配：{from_port} -> {to_port}"),
            );
        }
        *fanin.entry((to, to_port.to_string())).or_insert(0) += 1;
    }
    for ((to, port), count) in fanin {
        if count > 1 {
            let kind = nodes
                .iter()
                .find(|n| n.get("id").and_then(|v| v.as_str()) == Some(to.as_str()))
                .and_then(|n| n.get("kind"))
                .and_then(|v| v.as_str())
                .unwrap_or("");
            if kind != "merge" {
                report.error(
                    "NF-GRF-008",
                    &format!("$.nodes[{to}].ports.in"),
                    &format!("输入端口 {port} 有 {count} 条 data 入边，非 merge 节点不允许非法扇入"),
                );
            }
        }
    }
    Ok((0, report.to_value()))
}

pub fn graph_validate(req: &Value) -> OpOutcome {
    let graph = req_value(req, "graph")?;
    let report = validate_graph(graph);
    Ok((0, report.to_value()))
}

fn topo_order(graph: &Value) -> Vec<String> {
    let nodes = node_ids(graph);
    let edges = edges_array(graph);
    let mut indeg: BTreeMap<String, usize> = nodes.iter().map(|n| (n.clone(), 0)).collect();
    let mut adj: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for e in &edges {
        let f = e.get("from").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let t = e.get("to").and_then(|v| v.as_str()).unwrap_or("").to_string();
        if nodes.contains(&f) && nodes.contains(&t) {
            adj.entry(f).or_default().push(t);
        }
    }
    for (_, ts) in adj.iter() {
        for t in ts {
            if let Some(d) = indeg.get_mut(t) {
                *d += 1;
            }
        }
    }
    let mut ready: BTreeSet<String> = indeg
        .iter()
        .filter(|(_, d)| **d == 0)
        .map(|(k, _)| k.clone())
        .collect();
    let mut order = Vec::new();
    while let Some(n) = ready.iter().next().cloned() {
        ready.remove(&n);
        order.push(n.clone());
        if let Some(nexts) = adj.get(&n) {
            for m in nexts {
                if let Some(d) = indeg.get_mut(m) {
                    *d -= 1;
                    if *d == 0 {
                        ready.insert(m.clone());
                    }
                }
            }
        }
    }
    order
}

/// 最近的上游 stage（按反距离 BFS；同层取 id 码点最小）。找不到时返回 None。
fn reachable_stage(graph: &Value, module_node: &str) -> Option<String> {
    let nodes = nodes_array(graph);
    let edges = edges_array(graph);
    let stage_ids: BTreeSet<String> = nodes
        .iter()
        .filter(|n| n.get("kind").and_then(|v| v.as_str()) == Some("stage"))
        .filter_map(|n| n.get("id").and_then(|v| v.as_str()).map(|s| s.to_string()))
        .collect();
    let mut radj: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for e in &edges {
        let f = e.get("from").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let t = e.get("to").and_then(|v| v.as_str()).unwrap_or("").to_string();
        radj.entry(t).or_default().push(f);
    }
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let mut frontier: Vec<String> = vec![module_node.to_string()];
    seen.insert(module_node.to_string());
    while !frontier.is_empty() {
        let mut hits: Vec<String> = frontier
            .iter()
            .filter(|n| stage_ids.contains(*n))
            .cloned()
            .collect();
        if !hits.is_empty() {
            hits.sort();
            return hits.into_iter().next();
        }
        let mut next: Vec<String> = Vec::new();
        for n in &frontier {
            if let Some(prev) = radj.get(n) {
                for m in prev {
                    if seen.insert(m.clone()) {
                        next.push(m.clone());
                    }
                }
            }
        }
        frontier = next;
    }
    None
}

pub fn graph_compile(req: &Value) -> OpOutcome {
    let graph = req_value(req, "graph")?;
    let report = validate_graph(graph);
    if report.has_error() {
        return Ok((1, report.to_value()));
    }
    let spec = match req.get("spec") {
        None | Some(Value::Null) => None,
        Some(v @ Value::Object(_)) => {
            let sr = crate::ops::spec::validate_spec(v);
            if sr.has_error() {
                return Ok((1, sr.to_value()));
            }
            Some(v.clone())
        }
        Some(_) => return Err(crate::ops::usage("请求字段 spec 必须是 object")),
    };
    let nodes = nodes_array(graph);
    let edges = edges_array(graph);
    let node_set = node_ids(graph);
    let order = topo_order(graph);

    // 每个 module 节点的入边 from_port（去重码点升序）
    let mut inputs_map: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for e in &edges {
        let to = e.get("to").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let port = e.get("from_port").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let list = inputs_map.entry(to).or_default();
        if !list.contains(&port) {
            list.push(port);
        }
    }
    for (_, list) in inputs_map.iter_mut() {
        list.sort();
    }

    let weights = graph.get("weights").and_then(|v| v.as_object()).cloned().unwrap_or_default();
    let mut steps: Vec<Value> = Vec::new();
    let mut step_no = 0usize;
    for id in &order {
        if !node_set.contains(id) {
            continue;
        }
        let node = match find_node(&nodes, id) {
            Some(n) => n,
            None => continue,
        };
        if node.get("kind").and_then(|v| v.as_str()) != Some("module") {
            continue;
        }
        step_no += 1;
        if step_no > 99 {
            return Err(CoreError::new("NF-GRF-005")
                .with_message("module 节点数超过 99，S## 编号溢出")
                .with_exit(3));
        }
        let module_id = node
            .get("module_ref")
            .and_then(|m| m.get("id"))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let stage = match reachable_stage(graph, id) {
            Some(s) => s,
            None => {
                let mut report =
                    Report::new("L0", graph, "pipeline-graph", &ref_id(graph, "id"));
                report.error(
                    "NF-GRF-005",
                    &format!("$.nodes[{id}].id"),
                    &format!("module 节点 {id} 没有上游 stage 节点（模块所属阶段不可推导）"),
                );
                return Ok((1, report.to_value()));
            }
        };
        let weight = weights.get(id).and_then(|v| v.as_u64()).unwrap_or(0);
        let outputs: Vec<Value> = node
            .get("ports")
            .and_then(|p| p.get("out"))
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();
        steps.push(json!({
            "id": format!("S{:02}", step_no),
            "node": id,
            "stage": stage,
            "module": module_id,
            "weight": weight,
            "inputs": inputs_map.get(id).cloned().unwrap_or_default(),
            "outputs": outputs,
        }));
    }

    // modules：按 step 首次出现顺序去重
    let mut modules: Vec<Value> = Vec::new();
    let mut seen_modules = BTreeSet::new();
    for id in &order {
        let node = match find_node(&nodes, id) {
            Some(n) => n,
            None => continue,
        };
        if node.get("kind").and_then(|v| v.as_str()) != Some("module") {
            continue;
        }
        if let Some(mr) = node.get("module_ref") {
            let mid = mr.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
            if mid.is_empty() || !seen_modules.insert(mid.clone()) {
                continue;
            }
            let mut m = serde_json::Map::new();
            m.insert("id".into(), Value::String(mid));
            if let Some(v) = mr.get("version") {
                m.insert("version".into(), v.clone());
            }
            if let Some(v) = mr.get("digest") {
                m.insert("digest".into(), v.clone());
            }
            modules.push(Value::Object(m));
        }
    }

    // assets：所有 asset 节点的 asset_refs，按 key 排序
    let mut assets: Vec<Value> = Vec::new();
    let mut seen_assets = BTreeSet::new();
    for node in &nodes {
        if node.get("kind").and_then(|v| v.as_str()) != Some("asset") {
            continue;
        }
        if let Some(refs) = node.get("asset_refs").and_then(|v| v.as_array()) {
            for r in refs {
                let key = r.get("key").and_then(|v| v.as_str()).unwrap_or("");
                let dedupe = format!(
                    "{}\u{0}{}\u{0}{}",
                    key,
                    r.get("version").and_then(|v| v.as_str()).unwrap_or(""),
                    r.get("digest").and_then(|v| v.as_str()).unwrap_or("")
                );
                if !seen_assets.insert(dedupe) {
                    continue;
                }
                let mut m = serde_json::Map::new();
                m.insert("key".into(), Value::String(key.to_string()));
                if let Some(v) = r.get("version") {
                    m.insert("version".into(), v.clone());
                }
                if let Some(v) = r.get("digest") {
                    m.insert("digest".into(), v.clone());
                }
                assets.push(Value::Object(m));
            }
        }
    }
    assets.sort_by(|a, b| {
        a["key"]
            .as_str()
            .unwrap_or("")
            .cmp(b["key"].as_str().unwrap_or(""))
            .then_with(|| {
                a["version"]
                    .as_str()
                    .unwrap_or("")
                    .cmp(b["version"].as_str().unwrap_or(""))
            })
    });

    let slots: Vec<Value> = spec
        .as_ref()
        .and_then(|s| s.get("slots"))
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|s| s.get("id").cloned())
                .collect()
        })
        .unwrap_or_default();

    let seed = graph
        .get("settings")
        .and_then(|s| s.get("seed"))
        .and_then(|v| v.as_i64())
        .unwrap_or(0);
    let graph_digest = match digest_with_excludes(graph, &[]) {
        Ok(d) => d,
        Err(_) => crate::canonical::digest_allow_float(graph),
    };
    let pipeline_id = graph.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let version = graph.get("version").and_then(|v| v.as_str()).unwrap_or("0.0.0");
    let mut plan = json!({
        "schema": "nf-assembly-plan/1",
        "pipeline": {"id": pipeline_id, "version": version, "digest": graph_digest},
        "steps": steps,
        "modules": modules,
        "assets": assets,
        "slots": slots,
        "output": {"form": "md", "path": "result.md"},
        "fallback": {"on_failure": "abort", "max_retries": 0},
        "settings": {"seed": seed},
    });
    let digest = digest_with_excludes(&plan, &["digest".to_string()])?;
    plan["digest"] = Value::String(digest);
    let issues = validate("nf-assembly-plan", &plan);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-E-002")
            .with_message(format!(
                "graph-compile 产物未通过 nf-assembly-plan schema 自检: {}",
                crate::schema::first_issue_text(&issues)
            ))
            .with_exit(3));
    }
    Ok((0, plan))
}