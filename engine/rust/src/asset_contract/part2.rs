//! 数据面：JSON / CSV / Markdown / link 字段。

use super::*;

/// 真源 `_data_json`（含 D2 的 `schema_siblings` 兄弟候选与 `no_schema` 缺口计数）。
pub(crate) fn data_json(root: &Path, rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let obj = match strict_json(text) {
        Ok(v) => v,
        Err(e) => {
            return (
                vec![format!(
                    "数据件 {} 不是合法 JSON：{}（修复指引：修好语法或换 format）",
                    rel, e
                )],
                Json::Object(vec![]),
            )
        }
    };
    let sch_rel = schema_of(root, rel, spec);
    let mut issues: Vec<String> = Vec::new();
    if !sch_rel.is_empty() {
        issues.extend(schema_issues(root, rel, &obj, &sch_rel));
    }
    issues.extend(fields_issues(rel, &obj, spec));
    let mut stats: Vec<(String, Json)> = vec![];
    if sg_strs(spec, "schema_siblings").len() > 0 && sch_rel.is_empty() {
        // 可见缺口：有 schema 兄弟约定但该件没有 schema（**只**跳过 schema 面，必填字段仍判）
        stats.push(("no_schema".to_string(), Json::Int(1)));
    }
    stats.push(("fields".to_string(), Json::Int(required_fields_len(spec))));
    (issues, Json::Object(stats))
}

/// 真源 `_data_csv`。
pub(crate) fn data_csv(rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let rows = csv_rows(text);
    if rows.is_empty() {
        return (
            vec![format!(
                "数据件 {} 是空 CSV（修复指引：至少要有表头行）",
                rel
            )],
            Json::Object(vec![("rows".to_string(), Json::Int(0))]),
        );
    }
    let header: Vec<String> = rows[0].iter().map(|c| c.trim().to_string()).collect();
    if header.iter().any(|c| c.is_empty()) {
        issues.push(format!(
            "数据件 {} 表头有空列名（修复指引：每列都要有名字）",
            rel
        ));
    }
    let width = header.len();
    let data: Vec<&Vec<String>> = rows[1..]
        .iter()
        .filter(|r| !(r.len() == 1 && r[0].is_empty()))
        .collect();
    let bad: Vec<usize> = data
        .iter()
        .enumerate()
        .filter(|(_, r)| r.len() != width)
        .map(|(i, _)| i + 2)
        .collect();
    if !bad.is_empty() {
        let bs: Vec<String> = bad.iter().take(3).map(|b| b.to_string()).collect();
        issues.push(format!(
            "数据件 {} 第 {} 行列数 != 表头 {}（修复指引：补齐/删除多余的分隔符）",
            rel,
            bs.join(","),
            width
        ));
    }
    let missing: Vec<String> = sg_strs(spec, "required_columns")
        .into_iter()
        .filter(|c| !header.contains(c))
        .collect();
    if !missing.is_empty() {
        issues.push(format!(
            "数据件 {} 缺必需列 {}（修复指引：加列或改声明）",
            rel,
            missing.join(",")
        ));
    }
    // 真源 `required_any_columns`：样例集表头**族**各不相同（实测 11 种），故只判「至少含一个」。
    let any_cols: Vec<String> = sg_strs(spec, "required_any_columns");
    if !any_cols.is_empty() && !any_cols.iter().any(|c| header.contains(c)) {
        let shown: Vec<String> = header.iter().take(6).cloned().collect();
        issues.push(format!(
            "数据件 {} 表头不含任一必需列 {}（实为 {}）（修复指引：改用族内表头或改声明）",
            rel,
            any_cols.join("|"),
            shown.join(",")
        ));
    }
    let low = pyval::py_int_or(obj_get(spec, "min_rows"), 0);
    if (data.len() as i64) < low {
        issues.push(format!(
            "数据件 {} 数据行 {} < min_rows {}（修复指引：补样例或下调声明）",
            rel,
            data.len(),
            low
        ));
    }
    (
        issues,
        Json::Object(vec![
            ("rows".to_string(), Json::Int(data.len() as i64)),
            ("columns".to_string(), Json::Int(width as i64)),
        ]),
    )
}

/// 真源 `_md_tables`：按连续竖线行切表。
pub fn md_tables(text: &str) -> Vec<Vec<Vec<String>>> {
    let mut tables: Vec<Vec<Vec<String>>> = Vec::new();
    let mut cur: Vec<Vec<String>> = Vec::new();
    for line in text.lines() {
        let s = line.trim();
        if s.starts_with('|') && s.matches('|').count() >= 2 {
            let inner = s.trim_matches('|');
            cur.push(inner.split('|').map(|c| c.trim().to_string()).collect());
        } else if !cur.is_empty() {
            tables.push(std::mem::take(&mut cur));
        }
    }
    if !cur.is_empty() {
        tables.push(cur);
    }
    tables
}

/// 真源 `_data_markdown`。
pub(crate) fn data_markdown(rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    if pyval::py_truthy(&sg(spec, "frontmatter")) && !text.starts_with("---") {
        issues.push(format!(
            "数据件 {} 缺 frontmatter（修复指引：件首补 --- 块）",
            rel
        ));
    }
    let mut n = 0i64;
    for table in md_tables(text) {
        if table.len() < 2 {
            continue;
        }
        let header = &table[0];
        // 分隔行：每格只由 `-` 与 `:` 组成
        let body: Vec<&Vec<String>> = table[1..]
            .iter()
            .filter(|r| !r.iter().all(|c| c.chars().all(|ch| ch == '-' || ch == ':')))
            .collect();
        let ragged: Vec<&&Vec<String>> = body.iter().filter(|r| r.len() != header.len()).collect();
        if let Some(first) = ragged.first() {
            issues.push(format!(
                "数据件 {} 有一张表列数不齐：表头 {} 列 vs 数据 {} 列（修复指引：对齐竖线）",
                rel,
                header.len(),
                first.len()
            ));
        }
        n += 1;
    }
    (
        issues,
        Json::Object(vec![("tables".to_string(), Json::Int(n))]),
    )
}

/// 真源 `_data_link`。
pub(crate) fn data_link(root: &Path, rel: &str, spec: &Json, obj: &Json) -> Vec<String> {
    let link = sg(spec, "link");
    let mut issues: Vec<String> = Vec::new();
    let path_field = sg_str(&link, "path_field");
    let target = match dig_ref(obj, &path_field) {
        Some(Json::Str(s)) if !s.is_empty() => s.clone(),
        _ => {
            return vec![format!(
                "数据件 {} 的 link.path_field={} 取不到字符串路径（修复指引：核对字段名）",
                rel,
                pyval::py_str(Some(&sg(&link, "path_field")))
            )]
        }
    };
    let rel_dir = rel
        .rsplit_once('/')
        .map(|(d, _)| d.to_string())
        .unwrap_or_default();
    let base = sg_str(&link, "base");
    let bases: Vec<String> = if !base.is_empty() {
        vec![base]
    } else {
        let parent = rel_dir
            .rsplit_once('/')
            .map(|(d, _)| d.to_string())
            .unwrap_or_default();
        vec![rel_dir.clone(), parent]
    };
    let mut found: Option<std::path::PathBuf> = None;
    for b in &bases {
        let cand = root.join(b).join(&target);
        if cand.is_file() {
            found = Some(cand);
            break;
        }
    }
    let Some(fpath) = found else {
        return vec![format!(
            "数据件 {} 指向的 {} 不在场（修复指引：补件或修正 link.base）",
            rel, target
        )];
    };
    let rows_field = sg_str(&link, "rows_field");
    if !rows_field.is_empty() {
        let want = dig_ref(obj, &rows_field).cloned().unwrap_or(Json::Null);
        let got = std::fs::read_to_string(&fpath)
            .map(|t| csv_rows(&t).len().saturating_sub(1))
            .unwrap_or(0);
        if !pyval::py_eq(&want, &Json::Int(got as i64)) {
            issues.push(format!(
                "数据件 {} 的 {}={} 与 {} 数据行 {} 不一致（修复指引：重算或改声明）",
                rel,
                rows_field,
                pyval::py_str(Some(&want)),
                target,
                got
            ));
        }
    }
    issues
}

// ------------------------------------------------ 数据面（D3：yaml/toml/jsonl/graphml/mmd）

/// 真源 `_data_yaml`：复用 `miniyaml`（真源走 `lazy_yaml`），解析后与 JSON 同判据。
pub(crate) fn data_yaml(root: &Path, rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let obj = match crate::miniyaml::parse(text) {
        Ok(v) => v,
        Err(e) => {
            return (
                vec![format!(
                    "数据件 {} 不是合法 YAML：{}（修复指引：修好缩进/语法）",
                    rel, e
                )],
                Json::Object(vec![]),
            )
        }
    };
    let mut issues: Vec<String> = Vec::new();
    let sch = schema_of(root, rel, spec);
    if !sch.is_empty() {
        issues.extend(schema_issues(root, rel, &obj, &sch));
    }
    issues.extend(fields_issues(rel, &obj, spec));
    (
        issues,
        Json::Object(vec![(
            "fields".to_string(),
            Json::Int(required_fields_len(spec)),
        )]),
    )
}

/// 真源 `tomllib.loads` 的结果 → 本线 `Json`（TOML 的日期时间退化成字符串，足够判 schema/必填）。
pub(crate) fn toml_to_json(v: &toml::Value) -> Json {
    match v {
        toml::Value::String(s) => Json::Str(s.clone()),
        toml::Value::Integer(i) => Json::Int(*i),
        toml::Value::Float(f) => Json::Float(*f),
        toml::Value::Boolean(b) => Json::Bool(*b),
        toml::Value::Datetime(d) => Json::Str(d.to_string()),
        toml::Value::Array(a) => Json::Array(a.iter().map(toml_to_json).collect()),
        toml::Value::Table(t) => Json::Object(
            t.iter()
                .map(|(k, v)| (k.clone(), toml_to_json(v)))
                .collect(),
        ),
    }
}

/// 真源 `_data_toml`：stdlib `tomllib`（本线走 `toml` crate），解析后与 JSON 同判据。
pub(crate) fn data_toml(root: &Path, rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let obj = match text.parse::<toml::Value>() {
        Ok(v) => toml_to_json(&v),
        Err(e) => {
            return (
                vec![format!(
                    "数据件 {} 不是合法 TOML：{}（修复指引：修好语法或换 format）",
                    rel, e
                )],
                Json::Object(vec![]),
            )
        }
    };
    let mut issues: Vec<String> = Vec::new();
    let sch = schema_of(root, rel, spec);
    if !sch.is_empty() {
        issues.extend(schema_issues(root, rel, &obj, &sch));
    }
    issues.extend(fields_issues(rel, &obj, spec));
    (
        issues,
        Json::Object(vec![(
            "fields".to_string(),
            Json::Int(required_fields_len(spec)),
        )]),
    )
}
