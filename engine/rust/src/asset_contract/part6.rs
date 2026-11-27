//! 脚本面：nf-io 头 / 观测路径 / check_script / 链。

use super::*;

/// 真源 `_check_script`。
pub fn check_script(root: &Path, spec: &Json) -> (Vec<String>, Json) {
    let sid = {
        let s = sg_str(spec, "id");
        if s.is_empty() {
            sg_str(spec, "path")
        } else {
            s
        }
    };
    let lang = sg_str(spec, "lang");
    if !LANGS.contains(&lang.as_str()) {
        return (
            vec![format!(
                "脚本契约 {} 的 lang={} 不在词表 {}（修复指引：改用词表内语言）",
                sid,
                pyval::py_repr(&Json::Str(lang)),
                LANGS.join("/")
            )],
            Json::Object(vec![]),
        );
    }
    let rel = sg_str(spec, "path");
    if !root.join(&rel).is_file() {
        return (
            vec![format!(
                "脚本契约 {} 的件不在场：{}（修复指引：修正 path）",
                sid, rel
            )],
            Json::Object(vec![("files".to_string(), Json::Int(0))]),
        );
    }
    let (text, err) = sread(root, &rel);
    if let Some(e) = err {
        return (
            vec![e],
            Json::Object(vec![("files".to_string(), Json::Int(1))]),
        );
    }
    let text = text.unwrap_or_default();
    let mut issues: Vec<String> = Vec::new();
    let header = parse_io_header(&text);
    let (emb_in, emb_out) = match header {
        Some((a, b)) => (a, b),
        None => {
            issues.push(format!(
                "脚本 {} 未自带 nf-io 头（修复指引：顶部加一行注释 # nf-io: inputs=a,b outputs=c；VBA 用单引号起头——脚本契约必须双源）",
                rel
            ));
            (Vec::new(), Vec::new())
        }
    };
    script_dual_source_issues(&rel, spec, emb_in, emb_out, &mut issues);
    let declared_all: std::collections::BTreeSet<String> = sg_strs(spec, "inputs")
        .into_iter()
        .chain(sg_strs(spec, "outputs"))
        .collect();
    let mut extra: Vec<String> = observed_paths(&text, &lang)
        .into_iter()
        .filter(|x| !declared_all.contains(x))
        .collect();
    extra.sort();
    extra.dedup();
    if !extra.is_empty() {
        issues.push(format!(
            "脚本 {} 出现未声明的字面路径 {}（修复指引：补进 inputs/outputs 或去掉硬编码）",
            rel,
            extra.iter().take(3).cloned().collect::<Vec<_>>().join(",")
        ));
    }
    (
        issues,
        Json::Object(vec![
            ("files".to_string(), Json::Int(1)),
            (
                "inputs".to_string(),
                Json::Int(sg_strs(spec, "inputs").len() as i64),
            ),
            (
                "outputs".to_string(),
                Json::Int(sg_strs(spec, "outputs").len() as i64),
            ),
        ]),
    )
}


/// 脚本契约的 inputs/outputs 双源核对（声明 vs nf-io 头）。
pub(crate) fn script_dual_source_issues(
    rel: &str,
    spec: &Json,
    emb_in: Vec<String>,
    emb_out: Vec<String>,
    issues: &mut Vec<String>,
) {
    for (key, declared, embedded) in [
        ("inputs", sg_strs(spec, "inputs"), emb_in),
        ("outputs", sg_strs(spec, "outputs"), emb_out),
    ] {
        if declared != embedded {
            issues.push(format!(
                "脚本 {} 的 {} 双源不一致：声明={} / 头={}（修复指引：让两边逐字一致）",
                rel,
                key,
                pyval::py_repr_list(
                    &declared
                        .iter()
                        .map(|s| Json::Str(s.clone()))
                        .collect::<Vec<_>>()
                ),
                pyval::py_repr_list(
                    &embedded
                        .iter()
                        .map(|s| Json::Str(s.clone()))
                        .collect::<Vec<_>>()
                )
            ));
        }
    }
}

pub fn check_chain(specs: &[(String, Json)], chain: &Json) -> (Vec<String>, Json) {
    let a_id = sg_str(chain, "from");
    let b_id = sg_str(chain, "to");
    let find = |id: &str| specs.iter().find(|(k, _)| k == id).map(|(_, v)| v);
    let (Some(a), Some(b)) = (find(&a_id), find(&b_id)) else {
        return (
            vec![format!(
                "链 {}→{} 的端点未在脚本面登记（修复指引：先登记两端脚本契约）",
                a_id, b_id
            )],
            Json::Object(vec![]),
        );
    };
    let norm =
        |v: Vec<String>| -> Vec<String> { v.into_iter().map(|x| x.replace('\\', "/")).collect() };
    let ao = norm(sg_strs(a, "outputs"));
    let bi = norm(sg_strs(b, "inputs"));
    let mut issues: Vec<String> = Vec::new();
    let feeds = obj_get(chain, "feeds").cloned().unwrap_or(Json::Null);
    match &feeds {
        Json::Array(fs) if !fs.is_empty() => {
            for f in fs {
                let out_p = sg_str(f, "output").replace('\\', "/");
                let in_p = sg_str(f, "input").replace('\\', "/");
                if !ao.contains(&out_p) {
                    issues.push(format!(
                        "链 {}→{}：上游未声明产物 {}（修复指引：补进上游 outputs）",
                        a_id, b_id, out_p
                    ));
                }
                if !bi.contains(&in_p) {
                    issues.push(format!(
                        "链 {}→{}：下游未声明该输入 {}（修复指引：补进下游 inputs）",
                        a_id, b_id, in_p
                    ));
                }
                if out_p != in_p {
                    issues.push(format!(
                        "链 {}→{}：产物路径不对齐（上游 {} vs 下游 {}）（修复指引：统一路径写法）",
                        a_id, b_id, out_p, in_p
                    ));
                }
            }
        }
        _ => {
            let inter: Vec<String> = ao.iter().filter(|x| bi.contains(x)).cloned().collect();
            if inter.is_empty() {
                issues.push(format!(
                    "链 {}→{}：上游产物与下游输入无交集（上游 {} / 下游 {}）（修复指引：契约未对齐——A 的输出必须匹配 B 的输入）",
                    a_id,
                    b_id,
                    pyval::py_repr_list(&ao.iter().take(3).map(|s| Json::Str(s.clone())).collect::<Vec<_>>()),
                    pyval::py_repr_list(&bi.iter().take(3).map(|s| Json::Str(s.clone())).collect::<Vec<_>>())
                ));
            }
        }
    }
    let matched = ao.iter().filter(|x| bi.contains(x)).count() as i64;
    (
        issues,
        Json::Object(vec![("matched".to_string(), Json::Int(matched))]),
    )
}

// ---------------------------------------------------------------- 包清单面（S1）

/// 递归收集 `dir` 下的全部文件（相对 `base` 的 POSIX 路径）。真源 `rglob("*") if is_file()`。
pub(crate) fn walk_files(dir: &Path, base: &Path, out: &mut Vec<String>) {
    let Ok(rd) = std::fs::read_dir(dir) else {
        return;
    };
    let mut names: Vec<std::path::PathBuf> = rd.filter_map(|e| e.ok()).map(|e| e.path()).collect();
    names.sort();
    for p in names {
        if p.is_dir() {
            walk_files(&p, base, out);
        } else if p.is_file() {
            if let Ok(rel) = p.strip_prefix(base) {
                out.push(rel.to_string_lossy().replace('\\', "/"));
            }
        }
    }
}

/// 真源 `_check_index`：读包自己的 `outputs/INDEX.json`，与**磁盘实况**双向对账。
///
/// 为什么归到「资产契约」：包清单（`nf-output-index/1`）本就是**包自带**的产出面契约，
/// NF 侧再拿 glob 猜一遍就是两套词表；本判据让**声明**与**实况**互相对齐。
pub fn check_index(root: &Path, spec: &Json) -> (Vec<String>, Json) {
    let sid = id_or_question(spec);
    let rels = resolve(root, spec);
    if rels.is_empty() {
        return (
            vec![format!(
                "包清单契约 {} 未命中任何清单（修复指引：修正 glob）",
                sid
            )],
            Json::Object(vec![("files".to_string(), Json::Int(0))]),
        );
    }
    let mut issues: Vec<String> = Vec::new();
    let mut declared_total = 0i64;
    for rel in &rels {
        let (text, err) = sread(root, rel);
        if let Some(e) = err {
            issues.push(e);
            continue;
        }
        let Some(doc) = index_doc_or_issue(rel, &text.unwrap_or_default(), &mut issues) else {
            continue;
        };
        let Some(outs) = index_outputs_or_issue(rel, &doc, &mut issues) else {
            continue;
        };
        let base = path_parent(&path_parent(rel)); // <包>/outputs/INDEX.json → <包>
        let mut declared: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
        for item in &outs {
            declared_total += check_index_item(root, &base, rel, item, &mut declared, &mut issues);
        }
        check_index_disk(root, rel, &base, &declared, &mut issues);
    }
    (
        issues,
        Json::Object(vec![
            ("files".to_string(), Json::Int(rels.len() as i64)),
            ("declared".to_string(), Json::Int(declared_total)),
        ]),
    )
}

/// 读包清单 JSON；坏 JSON 即报一条并返回 None（真源抛错 → 本线记 issue）。
fn index_doc_or_issue(rel: &str, text: &str, issues: &mut Vec<String>) -> Option<Json> {
    match strict_json(text) {
        Ok(v) => Some(v),
        Err(e) => {
            issues.push(format!(
                "包清单 {} 不是合法 JSON：{}（修复指引：重跑 nf domain build）",
                rel, e
            ));
            None
        }
    }
}

/// 清单 outputs 段；为空即报一条并返回 None。
fn index_outputs_or_issue(rel: &str, doc: &Json, issues: &mut Vec<String>) -> Option<Vec<Json>> {
    match obj_get(doc, "outputs") {
        Some(Json::Array(a)) if !a.is_empty() => Some(a.clone()),
        _ => {
            issues.push(format!(
                "包清单 {} 的 outputs 为空（修复指引：重跑 nf domain build）",
                rel
            ));
            None
        }
    }
}

/// 磁盘实况与清单声明的单向核对（实况未声明即报，样例目录与清单自身不算产出面）。
fn check_index_disk(
    root: &Path,
    rel: &str,
    base: &str,
    declared: &std::collections::BTreeSet<String>,
    issues: &mut Vec<String>,
) {
    let mut on_disk: Vec<String> = Vec::new();
    walk_files(
        &root.join(base).join("outputs"),
        &root.join(base),
        &mut on_disk,
    );
    // 真源 self_rel = Path(rel).relative_to(base).as_posix()：清单自身不是产出面（它是清单）。
    let self_rel: String = if let Some(rest) = rel.strip_prefix(base) {
        rest.trim_start_matches('/').to_string()
    } else {
        rel.to_string()
    };
    let mut missing: Vec<String> = on_disk
        .into_iter()
        .filter(|x| !declared.contains(x) && *x != self_rel && !x.starts_with("outputs/samples/"))
        .collect();
    missing.sort();
    if !missing.is_empty() {
        let sample: Vec<String> = missing.iter().take(3).cloned().collect();
        issues.push(format!(
            "包清单 {} 未声明 {} 件实况（例 {}）（修复指引：重跑 nf domain build 让清单与实况同步）",
            rel,
            missing.len(),
            sample.join("、")
        ));
    }
}
