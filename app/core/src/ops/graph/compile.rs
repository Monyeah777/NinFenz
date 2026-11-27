use super::*;

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

pub(crate) fn topo_order(graph: &Value) -> Vec<String> {
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
pub(crate) fn reachable_stage(graph: &Value, module_node: &str) -> Option<String> {
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
