use super::*;

/// 真源 `_dual_source_check`：数据面 vs 散文面（键集必须互为子集）。
pub(crate) fn dual_source_check(root: &Path, pkg: &str, path: &str, ds: &Json) -> Vec<String> {
    let md_rel = s_of(obj_get(ds, "markdown"));
    let key_text = {
        let v = s_of(obj_get(ds, "key_pattern"));
        if v.is_empty() {
            r"`([A-Z][A-Z0-9_]{2,})`".to_string()
        } else {
            v
        }
    };
    let why =
        crate::json_schema::pattern_issue(&Json::Str(key_text.clone()), "dual_source.key_pattern");
    if !why.is_empty() {
        return vec![format!("双源 key_pattern 不合形态：{}", why)];
    }
    let re = match fancy_regex::Regex::new(&key_text) {
        Ok(r) => r,
        Err(e) => {
            return vec![format!("双源 key_pattern 不合形态：编译失败 {}", e)];
        }
    };
    let md_full = match of::declared_out_rel(root, pkg, &Json::Str(md_rel.clone())) {
        Ok(v) => v,
        Err(e) => return vec![e],
    };
    let md_path = root.join(&md_full);
    if !md_path.is_file() {
        return vec![format!("双源对照件不存在：{}", md_rel)];
    }
    let text = std::fs::read(&md_path)
        .map(|b| String::from_utf8_lossy(&b).into_owned())
        .unwrap_or_default();
    let mut md_keys: Vec<String> = findall(&re, &text);
    for drop in arr_of(obj_get(ds, "exclude")) {
        let d = pyval::plain_str(&drop);
        md_keys.retain(|x| *x != d);
    }
    let (data, err) = oc::read_json(root, path);
    if !err.is_empty() {
        return vec![err];
    }
    let field = {
        let f = s_of(obj_get(ds, "field"));
        if f.is_empty() {
            "id".to_string()
        } else {
            f
        }
    };
    let data_keys = collect_data_keys(&data, &field);
    let mut only_md: Vec<String> = md_keys
        .iter()
        .filter(|k| !data_keys.contains(k))
        .cloned()
        .collect();
    only_md.sort();
    let mut only_data: Vec<String> = data_keys
        .iter()
        .filter(|k| !md_keys.contains(k))
        .cloned()
        .collect();
    only_data.sort();
    let mut out = Vec::new();
    if !only_md.is_empty() {
        out.push(format!(
            "双源不一致：散文面独有键 {}",
            pyval::py_repr_list(
                &only_md
                    .iter()
                    .take(6)
                    .map(|s| Json::Str(s.clone()))
                    .collect::<Vec<_>>()
            )
        ));
    }
    if !only_data.is_empty() {
        out.push(format!(
            "双源不一致：数据面独有键 {}",
            pyval::py_repr_list(
                &only_data
                    .iter()
                    .take(6)
                    .map(|s| Json::Str(s.clone()))
                    .collect::<Vec<_>>()
            )
        ));
    }
    out
}

/// 数据面键集（每条 output 的 field 值，去重保序）。
pub(crate) fn collect_data_keys(data: &Json, field: &str) -> Vec<String> {
    let mut data_keys: Vec<String> = Vec::new();
    if let Json::Object(o) = data {
        for (_, value) in o {
            let Json::Array(items) = value else { continue };
            for item in items {
                let v = obj_get(item, &field).cloned().unwrap_or(Json::Null);
                if pyval::py_truthy(&v) {
                    let s = pyval::plain_str(&v);
                    if !data_keys.contains(&s) {
                        data_keys.push(s);
                    }
                }
            }
        }
    }
    data_keys
}

/// 近似 Python `re.findall`：无组 → 整个匹配；**恰好一组** → 该组内容；多组 → 元组 repr。
///
/// 本仓 `dual_source.key_pattern` 实测全是**恰好一组**（101 条，如 `(D14-[0-9]{2})`），
/// 无组与多组按 Python 语义实现，不留分支缺口。
pub(crate) fn findall(re: &fancy_regex::Regex, text: &str) -> Vec<String> {
    let groups = re.captures_len().saturating_sub(1);
    let mut out: Vec<String> = Vec::new();
    for cap in re.captures_iter(text).flatten() {
        if groups == 0 {
            out.push(
                cap.get(0)
                    .map(|m| m.as_str().to_string())
                    .unwrap_or_default(),
            );
        } else if groups == 1 {
            out.push(
                cap.get(1)
                    .map(|m| m.as_str().to_string())
                    .unwrap_or_default(),
            );
        } else {
            let parts: Vec<String> = (1..=groups)
                .map(|i| {
                    let v = cap.get(i).map(|m| m.as_str().to_string());
                    format!("'{}'", v.unwrap_or_else(|| "None".to_string()))
                })
                .collect();
            out.push(if parts.len() == 1 {
                parts[0].clone()
            } else {
                format!("({})", parts.join(", "))
            });
        }
    }
    out
}

/// 真源 `_verify_pack` → `(issues, rows)`。
pub(crate) fn verify_pack(root: &Path, pkg: &str) -> (Vec<String>, Vec<Json>) {
    let mut issues: Vec<String> = Vec::new();
    let mut rows: Vec<Json> = Vec::new();
    let rel = format!("community/{}/{}", pkg, of::INDEX_REL);
    let (idx, err) = oc::read_json(root, &rel);
    if !err.is_empty() {
        issues.push(format!("{}: {}", rel, err));
        return (issues, rows);
    }
    if s_of(obj_get(&idx, "schema")) != "nf-output-index/1" {
        issues.push(format!("{}: schema 应为 nf-output-index/1", rel));
    }
    if s_of(obj_get(&idx, "package")) != pkg {
        issues.push(format!(
            "{}: package 字段 {} ≠ 包目录名 {}",
            rel,
            pyval::py_repr(&obj_get(&idx, "package").cloned().unwrap_or(Json::Null)),
            pyval::py_repr(&Json::Str(pkg.to_string()))
        ));
    }
    for entry in arr_of(obj_get(&idx, "outputs")) {
        let Some(f) = entry_facts(root, pkg, &rel, &entry, &mut issues) else {
            continue;
        };
        verify_entry_schema(root, pkg, &f, &entry, &mut issues);
        if let Some(ds) = obj_get(&entry, "dual_source") {
            if matches!(ds, Json::Object(_)) {
                for m in dual_source_check(root, pkg, &f.out_rel, ds) {
                    issues.push(format!("{}: {} {}", rel, f.path, m));
                }
            }
        }
        if let Some(rc) = obj_get(&entry, "recompute") {
            if matches!(rc, Json::Object(_)) {
                let mut e2 = entry.clone();
                if let Json::Object(o) = &mut e2 {
                    o.push(("_pkg".to_string(), Json::Str(pkg.to_string())));
                }
                let (sub, _st) = recompute_entry(root, &e2);
                for s in sub {
                    issues.push(format!("{}: {}", rel, s));
                }
            }
        } else if f.tier == "T4" {
            issues.push(format!(
                "{}: {} 声明 T4（可复算）却无 recompute 声明",
                rel, f.path
            ));
        }
        push_output_row(pkg, &f, &entry, &mut rows);
    }
    (issues, rows)
}

/// outputs 条目的前置核对结论（schema / recompute / 行记录复用）。
pub(crate) struct EntryFacts {
    pub(crate) rel: String,
    pub(crate) path: String,
    pub(crate) form: String,
    pub(crate) tier: String,
    pub(crate) out_rel: String,
    pub(crate) got_form: String,
}

/// outputs 条目前置核对：path / tier / 产出面在场性 / 形态 / 档位。
pub(crate) fn entry_facts(
    root: &Path,
    pkg: &str,
    rel: &str,
    entry: &Json,
    issues: &mut Vec<String>,
) -> Option<EntryFacts> {
    let path = s_of(obj_get(&entry, "path"));
    let form = s_of(obj_get(&entry, "form"));
    let tier = s_of(obj_get(&entry, "tier"));
    if path.is_empty() {
        issues.push(format!("{}: outputs 条目缺 path", rel));
        return None;
    }
    if !of::TIERS.contains(&tier.as_str()) {
        issues.push(format!(
            "{}: {} 档位非法 {}",
            rel,
            path,
            pyval::py_repr(&Json::Str(tier.clone()))
        ));
        return None;
    }
    let out_rel = match of::declared_out_rel(root, pkg, &Json::Str(path.clone())) {
        Ok(v) => v,
        Err(e) => {
            issues.push(format!("{}: {}", rel, e));
            return None;
        }
    };
    if !root.join(&out_rel).is_file() {
        issues.push(format!("{}: 声明产出面不存在 {}", rel, path));
        return None;
    }
    let (got_form, got_tier) = of::detect(root, &out_rel);
    if !form.is_empty() && form != got_form {
        issues.push(format!(
            "{}: {} 声明形态 {}，实测 {}",
            rel, path, form, got_form
        ));
    }
    let ti = of::TIERS.iter().position(|t| *t == tier).unwrap_or(0);
    let gi = of::TIERS.iter().position(|t| *t == got_tier).unwrap_or(0);
    if ti > gi {
        issues.push(format!(
            "{}: {} 声明档位 {} 超出本仓可判上限 {}",
            rel, path, tier, got_tier
        ));
    }
    let form_key = if form.is_empty() {
        got_form.clone()
    } else {
        form.clone()
    };
    if let Some(sub) = oc::form_check(&form_key, root, &out_rel) {
        for s in sub {
            issues.push(format!("{}: {} {}", rel, path, s));
        }
    }
    Some(EntryFacts {
        rel: rel.to_string(),
        path,
        form,
        tier,
        out_rel,
        got_form,
    })
}
