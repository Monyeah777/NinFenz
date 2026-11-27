use super::*;

pub(crate) const BLOCK_MARKER: &str = "concept_graph";

pub(crate) const LAYERS: [&str; 9] = [
    "P00", "P10", "P20", "P30", "P40", "P50", "P60", "P70", "P80",
];

/// 真源 `SHELF_GLOBS`（资产货架，单层）。
pub(crate) const SHELF_GLOBS: [&str; 2] = ["community/*/assets/*.md", "05_资产库/用户自定义/*.md"];

pub(crate) const PROVENANCE_STRENGTHS: [&str; 4] = ["external", "mixed", "domain-logic", "inferred"];

pub(crate) const NON_SOURCE_KEYS: [&str; 2] = ["inferred", "domain-logic"];

pub(crate) fn obj_get<'a>(v: &'a Json, k: &str) -> Option<&'a Json> {
    match v {
        Json::Object(o) => o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv),
        _ => None,
    }
}

pub(crate) fn arr_of(v: Option<&Json>) -> Vec<Json> {
    match v {
        Some(Json::Array(a)) => a.clone(),
        _ => Vec::new(),
    }
}

pub(crate) fn s(v: &Json) -> String {
    pyval::plain_str(v)
}

/// 真源 `fenced_block`：取含 marker 的 ```yaml 围栏**正文**（无则空串）。
pub(crate) fn fenced_block(text: &str, marker: &str) -> String {
    // `(?ms)^```yaml\s*\n(.*?)^```` 的等价物
    let mut idx = 0usize;
    let lines: Vec<&str> = text.split('\n').collect();
    while idx < lines.len() {
        if lines[idx].trim_end() == "```yaml" {
            let start = idx + 1;
            let mut end = start;
            while end < lines.len() && lines[end].trim_end() != "```" {
                end += 1;
            }
            if end <= lines.len() {
                let body = lines[start..end].join("\n");
                if has_marker(&body, marker) {
                    return body;
                }
                idx = end + 1;
                continue;
            }
        }
        idx += 1;
    }
    String::new()
}

/// 真源 `re.search(r"(?m)^%s\s*:" % escape(marker), body)`。
pub(crate) fn has_marker(body: &str, marker: &str) -> bool {
    body.split('\n').any(|l| {
        l.strip_prefix(marker)
            .map(|rest| rest.trim_start().starts_with(':'))
            .unwrap_or(false)
    })
}

/// 真源 `load_graph`：读资产 → `concept_graph` 字典；失败即 `Err(原因)`（对应 `ClosureError`）。
pub(crate) fn load_graph(root: &Path, rel: &str) -> Result<Json, String> {
    let path = root.join(rel);
    if !path.is_file() {
        return Err(format!(
            "概念图资产不存在：{}（修复指引：给出域包内 assets/CONCEPT_GRAPH.md 路径）",
            path.display()
        ));
    }
    let text = std::fs::read(&path)
        .map(|b| String::from_utf8_lossy(&b).into_owned())
        .unwrap_or_default();
    let body = fenced_block(&text, BLOCK_MARKER);
    if body.is_empty() {
        return Err(format!(
            "资产缺 `{}:` 机器可读块：{}（修复指引：补 ```yaml 围栏块，块内首键为 {}）",
            BLOCK_MARKER,
            path.display(),
            BLOCK_MARKER
        ));
    }
    let data = crate::miniyaml::parse(&body)?;
    match obj_get(&data, BLOCK_MARKER) {
        Some(g @ Json::Object(_)) => Ok(g.clone()),
        _ => Err(format!(
            "机读块结构非法：{}（修复指引：顶层键须为 {}）",
            path.display(),
            BLOCK_MARKER
        )),
    }
}

/// 真源 `graph_assets`：仓库内带概念图机读块的资产（相对路径，排序）。
pub(crate) fn graph_assets(root: &Path) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for pat in SHELF_GLOBS {
        let mut hits = crate::glob::expand(root, pat);
        hits.sort();
        for f in hits {
            let text = std::fs::read(root.join(&f))
                .map(|b| String::from_utf8_lossy(&b).into_owned())
                .unwrap_or_default();
            if !fenced_block(&text, BLOCK_MARKER).is_empty() {
                out.push(f);
            }
        }
    }
    out
}

/// 真源 `prereqs_of`：`{概念 id: 直接前置 id 列表}`（保持声明序，去重）。
pub(crate) fn prereqs_of(graph: &Json) -> Vec<(String, Vec<String>)> {
    let mut out: Vec<(String, Vec<String>)> = Vec::new();
    for node in arr_of(obj_get(graph, "nodes")) {
        let Json::Object(_) = &node else { continue };
        let id = match obj_get(&node, "id") {
            Some(v) if pyval::py_truthy(v) => s(v),
            _ => continue,
        };
        let mut seen: Vec<String> = Vec::new();
        for p in arr_of(obj_get(&node, "prereqs")) {
            let ps = s(&p);
            if !seen.contains(&ps) {
                seen.push(ps);
            }
        }
        out.push((id, seen));
    }
    out
}

/// 真源 `branch_map`：`{分支 id: [概念 id]}`（保持声明序）。
pub(crate) fn branch_map(graph: &Json) -> Vec<(String, Vec<String>)> {
    let mut out: Vec<(String, Vec<String>)> = Vec::new();
    for br in arr_of(obj_get(graph, "branches")) {
        let Json::Object(_) = &br else { continue };
        if let Some(id) = obj_get(&br, "id") {
            if pyval::py_truthy(id) {
                out.push((s(id), arr_of(obj_get(&br, "nodes")).iter().map(s).collect()));
            }
        }
    }
    out
}

/// 真源 `node_branch`：`{概念 id: 分支 id}`（首次出现者胜）。
pub(crate) fn node_branch(graph: &Json) -> Vec<(String, String)> {
    let mut out: Vec<(String, String)> = Vec::new();
    for (bid, nodes) in branch_map(graph) {
        for nid in nodes {
            if !out.iter().any(|(k, _)| *k == nid) {
                out.push((nid, bid.clone()));
            }
        }
    }
    out
}

/// 真源 `alias_map`：`{别名(casefold): 概念 id}`；重复即 `Err`。
pub(crate) fn alias_map(graph: &Json) -> Result<Vec<(String, String)>, String> {
    let mut out: Vec<(String, String)> = Vec::new();
    for node in arr_of(obj_get(graph, "nodes")) {
        let Json::Object(_) = &node else { continue };
        let id = match obj_get(&node, "id") {
            Some(v) if pyval::py_truthy(v) => s(v),
            _ => continue,
        };
        for raw in arr_of(obj_get(&node, "aliases")) {
            let key = s(&raw).trim().to_lowercase();
            if key.is_empty() {
                continue;
            }
            if let Some((_, prev)) = out.iter().find(|(k, _)| *k == key) {
                if *prev != id {
                    return Err(format!(
                        "别名重复：{} 同时指向 {} 与 {}（修复指引：别名在图内须唯一——与 01 §1.1 词法纪律同源）",
                        pyval::py_repr(&Json::Str(s(&raw))),
                        prev,
                        id
                    ));
                }
            }
            match out.iter_mut().find(|(k, _)| *k == key) {
                Some(e) => e.1 = id.clone(),
                None => out.push((key, id.clone())),
            }
        }
    }
    Ok(out)
}

/// 真源 `external_coverage` → (有外部来源锚的节点数, 包内节点总数)。
pub(crate) fn external_coverage(graph: &Json) -> (i64, i64) {
    let (mut total, mut covered) = (0i64, 0i64);
    for node in arr_of(obj_get(graph, "nodes")) {
        let Json::Object(_) = &node else { continue };
        match obj_get(&node, "id") {
            Some(v) if pyval::py_truthy(v) => {}
            _ => continue,
        }
        total += 1;
        let prov: Vec<String> = arr_of(obj_get(&node, "provenance")).iter().map(s).collect();
        if prov.iter().any(|p| !NON_SOURCE_KEYS.contains(&p.as_str())) {
            covered += 1;
        }
    }
    (covered, total)
}

/// 真源 `provenance_strength`。
pub(crate) fn provenance_strength(graph: &Json) -> String {
    match obj_get(graph, "provenance_strength") {
        Some(Json::Null) | None => String::new(),
        Some(v) => s(v).trim().to_string(),
    }
}

/// 真源 `toposort`（Kahn；并列按 id 升序）。有环 → `Err`。
pub(crate) fn toposort(graph: &Json) -> Result<Vec<String>, String> {
    let prereqs = prereqs_of(graph);
    let mut ids: Vec<String> = prereqs.iter().map(|(k, _)| k.clone()).collect();
    ids.sort();
    let mut indeg: Vec<(String, i64)> = ids.iter().map(|i| (i.clone(), 0)).collect();
    let mut children: Vec<(String, Vec<String>)> =
        ids.iter().map(|i| (i.clone(), Vec::new())).collect();
    for (i, ps) in &prereqs {
        for p in ps {
            if indeg.iter().any(|(k, _)| k == p) {
                if let Some(e) = indeg.iter_mut().find(|(k, _)| k == i) {
                    e.1 += 1;
                }
                if let Some(e) = children.iter_mut().find(|(k, _)| k == p) {
                    let _ = &e.0;
                    e.1.push(i.clone());
                }
            }
        }
    }
    let mut ready: Vec<String> = indeg
        .iter()
        .filter(|(_, d)| *d == 0)
        .map(|(k, _)| k.clone())
        .collect();
    ready.sort();
    let mut out: Vec<String> = Vec::new();
    while !ready.is_empty() {
        let cur = ready.remove(0);
        out.push(cur.clone());
        let mut nxts: Vec<String> = children
            .iter()
            .find(|(k, _)| *k == cur)
            .map(|(_, v)| v.clone())
            .unwrap_or_default();
        nxts.sort();
        for nxt in nxts {
            if let Some(e) = indeg.iter_mut().find(|(k, _)| *k == nxt) {
                e.1 -= 1;
                if e.1 == 0 {
                    ready.push(nxt);
                }
            }
        }
        ready.sort();
    }
    if out.len() != ids.len() {
        return Err(
            "概念图存在环，无法给出装载序（修复指引：按资产 §4 conflict_rules 归并并列节点）"
                .to_string(),
        );
    }
    Ok(out)
}
