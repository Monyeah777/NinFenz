use super::*;

pub(crate) fn node_ids(graph: &Value) -> BTreeSet<String> {
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

pub(crate) fn nodes_array(graph: &Value) -> Vec<Value> {
    graph
        .get("nodes")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
}

pub(crate) fn edges_array(graph: &Value) -> Vec<Value> {
    graph
        .get("edges")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
}

pub(crate) fn find_node<'a>(nodes: &'a [Value], id: &str) -> Option<&'a Value> {
    nodes
        .iter()
        .find(|n| n.get("id").and_then(|v| v.as_str()) == Some(id))
}

pub(crate) fn kind_of(nodes: &[Value], id: &str) -> Option<String> {
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
