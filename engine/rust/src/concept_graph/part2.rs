use super::*;

/// 真源 `problems`：图健康度判据。
pub(crate) fn problems(graph: &Json) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    let prereqs = prereqs_of(graph);
    let ext: Vec<String> = arr_of(obj_get(graph, "external_prereqs"))
        .iter()
        .filter(|x| matches!(x, Json::Object(_)))
        .map(|x| s(&obj_get(x, "id").cloned().unwrap_or(Json::Null)))
        .collect();
    let mut declared: Vec<String> = prereqs.iter().map(|(k, _)| k.clone()).collect();
    declared.extend(ext);
    let legend: Vec<String> = match obj_get(graph, "provenance_legend") {
        Some(Json::Object(o)) => o.iter().map(|(k, _)| k.clone()).collect(),
        _ => Vec::new(),
    };
    let strength = provenance_strength(graph);
    check_provenance_strength(graph, &strength, &mut issues);
    check_nodes(graph, &legend, &mut issues);
    let mut sorted_prereqs = prereqs.clone();
    sorted_prereqs.sort_by(|a, b| a.0.cmp(&b.0));
    issues.extend(prereq_edges_issues(&sorted_prereqs, &declared));
    let bids = node_branch(graph);
    let mut unbranched: Vec<String> = prereqs
        .iter()
        .map(|(k, _)| k.clone())
        .filter(|n| !bids.iter().any(|(k, _)| k == n))
        .collect();
    unbranched.sort();
    for nid in unbranched {
        issues.push(format!(
            "概念 {} 未归入任何分支（修复指引：在图 branches 段登记）",
            nid
        ));
    }
    let mut ghost: Vec<String> = bids
        .iter()
        .map(|(k, _)| k.clone())
        .filter(|n| !prereqs.iter().any(|(k, _)| k == n))
        .collect();
    ghost.sort();
    for nid in ghost {
        issues.push(format!(
            "分支声明了不存在的概念：{}（修复指引：核对 branches.nodes）",
            nid
        ));
    }
    let flat: Vec<String> = branch_map(graph).into_iter().flat_map(|(_, v)| v).collect();
    let mut uniq = flat.clone();
    uniq.sort();
    uniq.dedup();
    if uniq.len() != flat.len() {
        issues.push("概念被多个分支重复声明（修复指引：一概念只入一个分支）".to_string());
    }
    if let Err(e) = alias_map(graph) {
        issues.push(e);
    }
    if let Err(e) = toposort(graph) {
        issues.push(e);
    }
    issues
}

/// 前置边核对：悬空前置 / 自环（按 (nid, 前置) 升序产出，保持真源报错次序）。
fn prereq_edges_issues(prereqs: &[(String, Vec<String>)], declared: &[String]) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    for (nid, ps) in prereqs {
        for p in ps {
            if !declared.contains(p) {
                issues.push(format!(
                    "悬空前置：{} ← {}（前置不在节点表 / 外部前置族中）",
                    nid, p
                ));
            }
            if p == nid {
                issues.push(format!("自环：{} ← {}", nid, p));
            }
        }
    }
    issues
}

/// provenance_strength 声明与外部覆盖率的自洽核对。
pub(crate) fn check_provenance_strength(graph: &Json, strength: &str, issues: &mut Vec<String>) {
    if strength.is_empty() {
        issues.push(format!(
            "图缺 provenance_strength 声明（修复指引：在机读块声明取值 {}——证据强度须显式，不得默认按强证据理解）",
            PROVENANCE_STRENGTHS.join(" / ")
        ));
    } else if !PROVENANCE_STRENGTHS.contains(&strength) {
        issues.push(format!(
            "provenance_strength 越词表：{}（取值 {}）",
            strength,
            PROVENANCE_STRENGTHS.join(" / ")
        ));
    } else {
        coverage_strength_issues(graph, strength, issues);
    }
}

/// 外部覆盖率与声明强度的自洽判据（external / mixed / domain-logic|inferred 三档）。
fn coverage_strength_issues(graph: &Json, strength: &str, issues: &mut Vec<String>) {
    let (covered, total, ratio) = coverage_ratio(graph);
    if strength == "external" && ratio < 1.0 {
        issues.push(format!(
            "provenance_strength=external 但外部覆盖仅 {}/{}（修复指引：补齐每节点的外部来源锚，或按实况降为 mixed / domain-logic）",
            covered, total
        ));
    } else if strength == "mixed" && !(ratio > 0.0 && ratio < 1.0) {
        issues.push(format!(
            "provenance_strength=mixed 但外部覆盖 = {}/{}（修复指引：全覆盖用 external；无外部锚用 domain-logic / inferred）",
            covered, total
        ));
    } else if (strength == "domain-logic" || strength == "inferred") && ratio > 0.0 {
        issues.push(format!(
            "provenance_strength={} 但已有 {}/{} 节点挂外部来源键（修复指引：按实况升为 mixed / external）",
            strength, covered, total
        ));
    }
}

/// 外部覆盖率 → (有外部来源锚的节点数, 包内节点总数, 比值)；总数为 0 时比值取 0.0。
fn coverage_ratio(graph: &Json) -> (i64, i64, f64) {
    let (covered, total) = external_coverage(graph);
    let ratio = if total != 0 {
        covered as f64 / total as f64
    } else {
        0.0
    };
    (covered, total, ratio)
}

/// 节点面的 id / name / provenance / layer 核对。
pub(crate) fn check_nodes(graph: &Json, legend: &[String], issues: &mut Vec<String>) {
    let mut seen_nodes: Vec<String> = Vec::new();
    for node in arr_of(obj_get(graph, "nodes")) {
        let Json::Object(_) = &node else { continue };
        let idv = obj_get(&node, "id").cloned().unwrap_or(Json::Null);
        if !pyval::py_truthy(&idv) {
            issues.push("节点缺 id（修复指引：每个节点须有 Cxx 编号）".to_string());
            continue;
        }
        let nid = s(&idv);
        if seen_nodes.contains(&nid) {
            issues.push(format!("节点 id 重复：{}（编号须唯一）", nid));
        }
        seen_nodes.push(nid.clone());
        let name = obj_get(&node, "name").cloned().unwrap_or(Json::Null);
        if s(&name).trim().is_empty() {
            issues.push(format!(
                "节点 {} 缺 name（修复指引：每个概念须有可读名）",
                nid
            ));
        }
        node_provenance_issues(&nid, &node, legend, issues);
        let layer = match obj_get(&node, "layer") {
            Some(Json::Null) | None => String::new(),
            Some(v) => s(v),
        };
        if !layer.is_empty() && !LAYERS.contains(&layer.as_str()) {
            issues.push(format!(
                "节点 {} 层位越界：{}（取值 {}）",
                nid,
                layer,
                LAYERS.join("/")
            ));
        }
    }
}

/// 单节点 provenance 面：非空 + 每个键都在图例中。
fn node_provenance_issues(nid: &str, node: &Json, legend: &[String], issues: &mut Vec<String>) {
    let prov = arr_of(obj_get(node, "provenance"));
    if prov.is_empty() {
        issues.push(format!("节点 {} 缺 provenance（边无溯源即不可复核）", nid));
    } else {
        for key in &prov {
            if !legend.contains(&s(key)) {
                issues.push(format!(
                    "节点 {} 的 provenance 键 {} 不在 provenance_legend 中（修复指引：补图例键，防图例漂移静默）",
                    nid,
                    pyval::py_repr(key)
                ));
            }
        }
    }
}

/// 真源 `scan` → `(issues, stats)`。
pub(crate) fn scan(root: &Path) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let (mut nodes, mut edges) = (0i64, 0i64);
    let assets = graph_assets(root);
    for rel in &assets {
        let graph = match load_graph(root, rel) {
            Ok(g) => g,
            Err(e) => {
                issues.push(format!("{}: {}", rel, e));
                continue;
            }
        };
        let prereqs = prereqs_of(&graph);
        nodes += prereqs.len() as i64;
        edges += prereqs.iter().map(|(_, v)| v.len() as i64).sum::<i64>();
        for msg in problems(&graph) {
            issues.push(format!("{}: {}", rel, msg));
        }
    }
    (
        issues,
        Json::Object(vec![
            ("graphs".to_string(), Json::Int(assets.len() as i64)),
            ("nodes".to_string(), Json::Int(nodes)),
            ("edges".to_string(), Json::Int(edges)),
        ]),
    )
}

/// 真源 `DEFAULT_ASSET`。
pub(crate) const DEFAULT_ASSET: &str = "community/AI系统域包/assets/CONCEPT_GRAPH.md";

/// 真源 `node_meta`：`{概念 id: 节点元信息}`（含包外前置，标 `external=True`）。
pub(crate) fn node_meta(graph: &Json) -> Vec<(String, Json)> {
    let mut out: Vec<(String, Json)> = Vec::new();
    if let Some(Json::Array(nodes)) = obj_get(graph, "nodes") {
        out.extend(meta_rows(nodes, false));
    }
    if let Some(Json::Array(ext)) = obj_get(graph, "external_prereqs") {
        for row in meta_rows(ext, true) {
            if !out.iter().any(|(k, _)| *k == row.0) {
                out.push(row);
            }
        }
    }
    out
}

/// 一组节点声明 → (概念 id, 记录)；external 标记由调用方给定。
fn meta_rows(nodes: &[Json], external: bool) -> Vec<(String, Json)> {
    let mut out: Vec<(String, Json)> = Vec::new();
    for n in nodes {
        let Json::Object(no) = n else { continue };
        let Some(Json::Str(id)) = no.iter().find(|(k, _)| k == "id").map(|(_, v)| v) else {
            continue;
        };
        let mut rec = no.clone();
        rec.push(("external".to_string(), Json::Bool(external)));
        out.push((id.clone(), Json::Object(rec)));
    }
    out
}

/// 真源 `in_package_ids`：包内概念 id（外部前置族不计入装载序），**有序**。
pub(crate) fn in_package_ids(graph: &Json) -> Vec<String> {
    let mut ids: Vec<String> = prereqs_of(graph).into_iter().map(|(k, _)| k).collect();
    ids.sort();
    ids
}

/// 真源 `resolve`：检索词 → 概念 id（顺序：条目键 → 别名 → 概念名）。
///
/// ⚠️ 别名比对真源用 `str.casefold()`，本线用 `to_lowercase()`（与 `miniyaml` 的别名口径同一
/// 已登记偏差）；本仓语料无 casefold 与 lowercase 分歧的字符。
pub(crate) fn resolve(graph: &Json, token: &str) -> Result<String, String> {
    let t = token.trim().to_string();
    let meta = node_meta(graph);
    if meta.iter().any(|(k, _)| *k == t) {
        return Ok(t);
    }
    let am = alias_map(graph)?;
    if let Some((_, v)) = am.iter().find(|(k, _)| *k == t.to_lowercase()) {
        return Ok(v.clone());
    }
    for (nid, rec) in &meta {
        let name = match rec {
            Json::Object(o) => match o.iter().find(|(k, _)| k == "name").map(|(_, v)| v) {
                Some(Json::Str(s)) => s.trim().to_string(),
                _ => String::new(),
            },
            _ => String::new(),
        };
        if name.to_lowercase() == t.to_lowercase() {
            return Ok(nid.clone());
        }
    }
    Err(format!(
        "检索词不在图中：{}（修复指引：用条目键 Cxx、别名或概念名——`--list` 可枚举全表）",
        token
    ))
}

/// 真源 `closure`：传递闭包 `closure(target) = {target} ∪ ⋃ closure(p)`；返回**排序**列表。
pub(crate) fn closure(graph: &Json, target: &str) -> Result<Vec<String>, String> {
    let tid = resolve(graph, target)?;
    let prereqs = prereqs_of(graph);
    let mut seen: Vec<String> = Vec::new();
    let mut stack: Vec<String> = vec![tid];
    while let Some(cur) = stack.pop() {
        if seen.contains(&cur) {
            continue;
        }
        seen.push(cur.clone());
        if let Some((_, ps)) = prereqs.iter().find(|(k, _)| *k == cur) {
            for p in ps {
                stack.push(p.clone());
            }
        }
    }
    seen.sort();
    Ok(seen)
}
