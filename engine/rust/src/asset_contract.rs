//! 数字资产契约层（数据 / 代码 / 脚本三面 · 声明即契约）—— 与真源
//! `desktop/src/core/asset_contract.py` 的 `scan` 对账。
//!
//! **不移植**：`freeze()`（重冻 sha256）与 `run_tests()` / `_run_test_file()`（执行被声明脚本）
//! ——前者是写面、后者是执行层，按目标纪律都不碰。
//!
//! 三面口径见真源模块文档。本文件按面拆成三段：数据面 / 代码面 / 脚本面。
//!
//! ## 已知偏差（两处，都是**外来输入的报错文本**）
//!
//! 1. **JSON 解析失败的文本**：真源给 CPython `json` 的报错，本线给 `serde_json` 的。
//! 2. **读件失败的文本**：真源给 `OSError` / `UnicodeDecodeError` 的 repr，本线给 `std::io` 的。
//!
//! 二者都只在**坏输入**时出现在消息里；真语料上这两支都不触发。分支判据里做**归一**后比较，
//! 不假装文本相同（同 `code_metrics` 的语法支处理）。

use crate::json_schema;
use crate::pyjson::Json;
use crate::pyval;
use std::path::Path;

pub const DECL_REL: &str = "protocol/asset_contracts.json";
pub const SCHEMA: &str = "nf-asset-contracts/1";
/// 真源 `SCHEMA_REL`：可移植 schema（⑤ 声明自检用）。
pub const SCHEMA_REL: &str = "protocol/schema/asset_contracts.schema.json";
/// 真源 `EXPORT_REL`：Frictionless Data Package 导出件（④ 漂移判据用）。
pub const EXPORT_REL: &str = "protocol/generated/asset_contract.frictionless.json";
pub const FACES: [&str; 4] = ["data", "code", "script", "index"];
pub const LANGS: [&str; 3] = ["python", "bash", "vba"];
/// 真源 `FORMATS`（D3 写通道契约化后扩到 9 个：yaml/toml/jsonl/graphml/mmd 逐条对应
/// `asset_contracts.json` 里新增的数据件声明）。顺序须与真源元组**逐字同序**——
/// 报错文案里 `"/".join(FORMATS)` 会进判据。
pub const FORMATS: [&str; 9] =
    ["json", "csv", "markdown", "text", "yaml", "toml", "jsonl", "graphml", "mmd"];
/// 真源 `_MMD_KINDS`：Mermaid 首关键词词表（结构判据：只认「这是一张什么图」）。
pub const MMD_KINDS: [&str; 17] = [
    "graph",
    "flowchart",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "erDiagram",
    "gantt",
    "pie",
    "mindmap",
    "timeline",
    "journey",
    "gitGraph",
    "quadrantChart",
    "xychart-beta",
    "requirementDiagram",
    "C4Context",
    "block-beta",
];

// ---------------------------------------------------------------- 基础

fn obj_get<'a>(v: &'a Json, k: &str) -> Option<&'a Json> {
    match v {
        Json::Object(o) => o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv),
        _ => None,
    }
}

/// 真源 `spec.get(k)`：缺键 → `Null`（Python 的 `None`）。
fn sg(spec: &Json, k: &str) -> Json {
    obj_get(spec, k).cloned().unwrap_or(Json::Null)
}

/// 真源 `str(spec.get(k) or "")` 的常用形态。
fn sg_str(spec: &Json, k: &str) -> String {
    match obj_get(spec, k) {
        None | Some(Json::Null) => String::new(),
        Some(v) => pyval::plain_str(v),
    }
}

/// 真源 `spec.get(k) or []` → 字符串列表。
fn sg_strs(spec: &Json, k: &str) -> Vec<String> {
    match obj_get(spec, k) {
        Some(Json::Array(a)) => a.iter().map(pyval::plain_str).collect(),
        _ => Vec::new(),
    }
}

/// 真源 `digest_of`：文件内容 sha256 十六进制。
pub fn digest_of(p: &Path) -> String {
    match std::fs::read(p) {
        Ok(b) => crate::merkle::hex(&crate::merkle::sha256(&b)),
        Err(_) => String::new(),
    }
}

/// 真源 `_read(root, rel)` → `(text, issue)`。
pub fn sread(root: &Path, rel: &str) -> (Option<String>, Option<String>) {
    let p = root.join(rel);
    match std::fs::read(&p) {
        Err(e) => (
            None,
            Some(format!("读不到 {}：{}（修复指引：核对声明里的路径在场）", rel, e)),
        ),
        Ok(b) => match String::from_utf8(b) {
            Ok(s) => (Some(s), None),
            Err(e) => (
                None,
                Some(format!("{} 不是 UTF-8：{}（修复指引：转成 UTF-8 再入库）", rel, e)),
            ),
        },
    }
}

/// 真源 `resolve`：`path` 单件 / `glob` 多件（稳定排序）。
pub fn resolve(root: &Path, spec: &Json) -> Vec<String> {
    if let Some(p) = obj_get(spec, "path") {
        if pyval::py_truthy(p) {
            let rel = pyval::plain_str(p).replace('\\', "/");
            return if root.join(&rel).is_file() { vec![rel] } else { vec![] };
        }
    }
    let pat = sg_str(spec, "glob");
    if pat.is_empty() {
        return Vec::new();
    }
    let mut v = crate::glob::expand(root, &pat);
    v.sort();
    v
}

/// 真源 `_dig`：按点号路径取值；取不到 → `None`（哨兵）。
pub fn dig(obj: &Json, path: &str) -> Option<Json> {
    let mut cur = obj.clone();
    for part in path.split('.') {
        match &cur {
            Json::Object(o) => match o.iter().find(|(k, _)| k == part) {
                Some((_, v)) => cur = v.clone(),
                None => return None,
            },
            Json::Array(a) => {
                let idx: Option<usize> = part.parse().ok();
                match idx {
                    Some(i) if i < a.len() => cur = a[i].clone(),
                    _ => return None,
                }
            }
            _ => return None,
        }
    }
    Some(cur)
}

// ---------------------------------------------------------------- CSV（Python csv.reader 默认方言）

/// Python `csv.reader` 默认方言：分隔 `,`、引号 `"`、`""` 转义、**不**跳过空白。
///
/// 不是"按逗号 split"——带引号字段里的逗号/换行不切分，这是真源 `_csv_rows` 的口径。
pub fn csv_rows(text: &str) -> Vec<Vec<String>> {
    let mut rows: Vec<Vec<String>> = Vec::new();
    let mut row: Vec<String> = Vec::new();
    let mut field = String::new();
    let mut in_quotes = false;
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        if in_quotes {
            if c == '"' {
                if chars.peek() == Some(&'"') {
                    field.push('"');
                    chars.next();
                } else {
                    in_quotes = false;
                }
            } else {
                field.push(c);
            }
            continue;
        }
        match c {
            '"' if field.is_empty() => in_quotes = true,
            ',' => {
                row.push(std::mem::take(&mut field));
            }
            '\r' => {
                if chars.peek() == Some(&'\n') {
                    chars.next();
                }
                row.push(std::mem::take(&mut field));
                rows.push(std::mem::take(&mut row));
            }
            '\n' => {
                row.push(std::mem::take(&mut field));
                rows.push(std::mem::take(&mut row));
            }
            _ => field.push(c),
        }
    }
    // 末尾无换行 ⇒ 还有一行（Python 同）
    if !field.is_empty() || !row.is_empty() {
        row.push(field);
        rows.push(row);
    }
    rows
}

// ---------------------------------------------------------------- 数据面

/// `Path(rel).stem`：末段去掉最后一个 `.` 之后的部分。
fn path_stem(rel: &str) -> String {
    let base = rel.rsplit('/').next().unwrap_or(rel);
    match base.rsplit_once('.') {
        Some((s, _)) => s.to_string(),
        None => base.to_string(),
    }
}

/// `Path(rel).parent`：去掉末段（`.` → 空串，与 `Path("x").parent == "."` 的拼接效果等价）。
fn path_parent(rel: &str) -> String {
    rel.rsplit_once('/').map(|(d, _)| d.to_string()).unwrap_or_default()
}

/// 真源 `_schema_of`：显式 `schema` 优先，其次 `schema_siblings` 里**第一个在场**的兄弟候选。
fn schema_of(root: &Path, rel: &str, spec: &Json) -> String {
    let sch = sg_str(spec, "schema");
    if !sch.is_empty() {
        return sch;
    }
    let stem = path_stem(rel);
    let parent = path_parent(rel);
    for tmpl in sg_strs(spec, "schema_siblings") {
        let cand_raw = tmpl.replace("{stem}", &stem);
        let cand = if parent.is_empty() {
            cand_raw
        } else {
            format!("{}/{}", parent, cand_raw)
        };
        if root.join(&cand).is_file() {
            return cand;
        }
    }
    String::new()
}

/// 真源 `_schema_issues`：按 schema 校验已解析对象（JSON / YAML / TOML 解析后同一数据模型）。
fn schema_issues(root: &Path, rel: &str, obj: &Json, sch_rel: &str) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    let (sch_text, err) = sread(root, sch_rel);
    match err {
        Some(e) => issues.push(format!("数据件 {} 的 schema 读不到：{}", rel, e)),
        None => {
            let errs = match strict_json(&sch_text.unwrap_or_default()) {
                Ok(s) => json_schema::json_schema_check(obj, &s),
                Err(e) => vec![format!("schema 本身不是合法 JSON：{}", e)],
            };
            for e in errs.iter().take(5) {
                issues.push(format!("数据件 {} 不符 schema {}：{}", rel, sch_rel, e));
            }
        }
    }
    issues
}

/// 真源 `_fields_issues`。
fn fields_issues(rel: &str, obj: &Json, spec: &Json) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    if let Some(Json::Array(req)) = obj_get(spec, "required_fields") {
        for field in req {
            let f = pyval::plain_str(field);
            if dig(obj, &f).is_none() {
                issues.push(format!(
                    "数据件 {} 缺必填字段 {}（修复指引：补字段或从声明里删掉——声明即契约）",
                    rel, f
                ));
            }
        }
    }
    issues
}

fn required_fields_len(spec: &Json) -> i64 {
    match obj_get(spec, "required_fields") {
        Some(Json::Array(a)) => a.len() as i64,
        _ => 0,
    }
}

/// 真源 `_data_json`（含 D2 的 `schema_siblings` 兄弟候选与 `no_schema` 缺口计数）。
fn data_json(root: &Path, rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let obj = match strict_json(text) {
        Ok(v) => v,
        Err(e) => {
            return (
                vec![format!("数据件 {} 不是合法 JSON：{}（修复指引：修好语法或换 format）", rel, e)],
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
fn data_csv(rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let rows = csv_rows(text);
    if rows.is_empty() {
        return (
            vec![format!("数据件 {} 是空 CSV（修复指引：至少要有表头行）", rel)],
            Json::Object(vec![("rows".to_string(), Json::Int(0))]),
        );
    }
    let header: Vec<String> = rows[0].iter().map(|c| c.trim().to_string()).collect();
    if header.iter().any(|c| c.is_empty()) {
        issues.push(format!("数据件 {} 表头有空列名（修复指引：每列都要有名字）", rel));
    }
    let width = header.len();
    let data: Vec<&Vec<String>> =
        rows[1..].iter().filter(|r| !(r.len() == 1 && r[0].is_empty())).collect();
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
fn data_markdown(rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    if pyval::py_truthy(&sg(spec, "frontmatter")) && !text.starts_with("---") {
        issues.push(format!("数据件 {} 缺 frontmatter（修复指引：件首补 --- 块）", rel));
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
        let ragged: Vec<&&Vec<String>> =
            body.iter().filter(|r| r.len() != header.len()).collect();
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
    (issues, Json::Object(vec![("tables".to_string(), Json::Int(n))]))
}

/// 真源 `_data_link`。
fn data_link(root: &Path, rel: &str, spec: &Json, obj: &Json) -> Vec<String> {
    let link = sg(spec, "link");
    let mut issues: Vec<String> = Vec::new();
    let path_field = sg_str(&link, "path_field");
    let target = match dig(obj, &path_field) {
        Some(Json::Str(s)) if !s.is_empty() => s,
        _ => {
            return vec![format!(
                "数据件 {} 的 link.path_field={} 取不到字符串路径（修复指引：核对字段名）",
                rel,
                pyval::py_str(Some(&sg(&link, "path_field")))
            )]
        }
    };
    let rel_dir = rel.rsplit_once('/').map(|(d, _)| d.to_string()).unwrap_or_default();
    let base = sg_str(&link, "base");
    let bases: Vec<String> = if !base.is_empty() {
        vec![base]
    } else {
        let parent = rel_dir.rsplit_once('/').map(|(d, _)| d.to_string()).unwrap_or_default();
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
        let want = dig(obj, &rows_field).unwrap_or(Json::Null);
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
fn data_yaml(root: &Path, rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let obj = match crate::miniyaml::parse(text) {
        Ok(v) => v,
        Err(e) => {
            return (
                vec![format!("数据件 {} 不是合法 YAML：{}（修复指引：修好缩进/语法）", rel, e)],
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
        Json::Object(vec![("fields".to_string(), Json::Int(required_fields_len(spec)))]),
    )
}

/// 真源 `tomllib.loads` 的结果 → 本线 `Json`（TOML 的日期时间退化成字符串，足够判 schema/必填）。
fn toml_to_json(v: &toml::Value) -> Json {
    match v {
        toml::Value::String(s) => Json::Str(s.clone()),
        toml::Value::Integer(i) => Json::Int(*i),
        toml::Value::Float(f) => Json::Float(*f),
        toml::Value::Boolean(b) => Json::Bool(*b),
        toml::Value::Datetime(d) => Json::Str(d.to_string()),
        toml::Value::Array(a) => Json::Array(a.iter().map(toml_to_json).collect()),
        toml::Value::Table(t) => Json::Object(
            t.iter().map(|(k, v)| (k.clone(), toml_to_json(v))).collect(),
        ),
    }
}

/// 真源 `_data_toml`：stdlib `tomllib`（本线走 `toml` crate），解析后与 JSON 同判据。
fn data_toml(root: &Path, rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let obj = match text.parse::<toml::Value>() {
        Ok(v) => toml_to_json(&v),
        Err(e) => {
            return (
                vec![format!("数据件 {} 不是合法 TOML：{}（修复指引：修好语法或换 format）", rel, e)],
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
        Json::Object(vec![("fields".to_string(), Json::Int(required_fields_len(spec)))]),
    )
}

/// 真源 `_data_jsonl`：**逐行**严格 JSON（空行跳过）；必填字段对每一行判。
fn data_jsonl(rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let mut rows = 0i64;
    for (i, line) in text.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        rows += 1;
        let obj = match strict_json(line) {
            Ok(v) => v,
            Err(e) => {
                issues.push(format!(
                    "数据件 {} 第 {} 行不是合法 JSON：{}（修复指引：一行一条）",
                    rel,
                    i + 1,
                    e
                ));
                continue;
            }
        };
        for f in sg_strs(spec, "required_fields") {
            if dig(&obj, &f).is_none() {
                issues.push(format!(
                    "数据件 {} 第 {} 行缺必填字段 {}（修复指引：补字段）",
                    rel,
                    i + 1,
                    f
                ));
            }
        }
    }
    let min_rows = pyval::py_int_or(obj_get(spec, "min_rows"), 0);
    if min_rows > 0 && rows < min_rows {
        issues.push(format!(
            "数据件 {} 行数 {} < min_rows {}（修复指引：补样例或下调声明）",
            rel, rows, min_rows
        ));
    }
    (issues, Json::Object(vec![("rows".to_string(), Json::Int(rows))]))
}

/// 真源 `_data_graphml`：XML 良构 + 节点/边计数（入口先拒 DTD/实体声明）。
fn data_graphml(rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    if text.contains("<!DOCTYPE") || text.contains("<!ENTITY") {
        return (
            vec![format!(
                "数据件 {} 含 DTD/实体声明，拒绝解析（修复指引：去掉 DOCTYPE/ENTITY——导出工具重跑）",
                rel
            )],
            Json::Object(vec![]),
        );
    }
    let root_el = match crate::xmlmini::parse(text) {
        Ok(n) => n,
        Err(e) => {
            return (
                vec![format!("数据件 {} 不是良构 XML：{}（修复指引：修好 XML）", rel, e)],
                Json::Object(vec![]),
            )
        }
    };
    // 真源先试 graphml 命名空间版 `.//g:node`，再退 `.//node`；两者在真语料上同值
    // （本线解析器只取局部名，与 `{*}` 通配同效）。
    let nodes = root_el.descendants("node").len() as i64;
    let edges = root_el.descendants("edge").len() as i64;
    let mut issues: Vec<String> = Vec::new();
    let min_nodes = pyval::py_int_or(obj_get(spec, "min_nodes"), 0);
    if min_nodes > 0 && nodes < min_nodes {
        issues.push(format!(
            "数据件 {} 节点数 {} < min_nodes {}（修复指引：补结构或下调声明）",
            rel, nodes, min_nodes
        ));
    }
    (
        issues,
        Json::Object(vec![
            ("nodes".to_string(), Json::Int(nodes)),
            ("edges".to_string(), Json::Int(edges)),
        ]),
    )
}

/// 真源 `_data_mmd`：首关键词须是合法 Mermaid 图型（结构判据，不解析图内容）。
fn data_mmd(rel: &str, text: &str) -> (Vec<String>, Json) {
    let mut first = String::new();
    for line in text.lines() {
        let s = line.trim();
        if !s.is_empty() && !s.starts_with("%%") {
            first = s.split_whitespace().next().unwrap_or("").to_string();
            break;
        }
    }
    if first.is_empty() {
        return (
            vec![format!("数据件 {} 是空 Mermaid 图（修复指引：补图声明）", rel)],
            Json::Object(vec![]),
        );
    }
    let base: &str = if first.starts_with("xychart") || first.starts_with("block") {
        first.split('-').next().unwrap_or("")
    } else {
        &first
    };
    if !MMD_KINDS.contains(&first.as_str()) && !MMD_KINDS.contains(&base) {
        return (
            vec![format!(
                "数据件 {} 首关键词 {} 不是合法 Mermaid 图型（修复指引：用 graph/flowchart/sequenceDiagram 等）",
                rel,
                pyval::py_repr(&Json::Str(first))
            )],
            Json::Object(vec![]),
        );
    }
    (Vec::new(), Json::Object(vec![("kind".to_string(), Json::Str(first))]))
}

/// 真源 `_check_data`。
pub fn check_data(root: &Path, spec: &Json) -> (Vec<String>, Json) {
    let sid = {
        let s = sg_str(spec, "id");
        if !s.is_empty() {
            s
        } else {
            let p = sg_str(spec, "path");
            if !p.is_empty() {
                p
            } else {
                let g = sg_str(spec, "glob");
                if !g.is_empty() {
                    g
                } else {
                    "?".to_string()
                }
            }
        }
    };
    let rels = resolve(root, spec);
    if rels.is_empty() {
        return (
            vec![format!(
                "数据契约 {} 未命中任何文件（修复指引：修正 path/glob —— 空气不是契约）",
                sid
            )],
            Json::Object(vec![("files".to_string(), Json::Int(0))]),
        );
    }
    let fmt = sg_str(spec, "format").to_lowercase();
    if !FORMATS.contains(&fmt.as_str()) {
        return (
            vec![format!(
                "数据契约 {} 的 format={} 不在词表 {}（修复指引：改用词表内格式）",
                sid,
                pyval::py_repr(&Json::Str(fmt)),
                FORMATS.join("/")
            )],
            Json::Object(vec![("files".to_string(), Json::Int(rels.len() as i64))]),
        );
    }
    let has_sha = pyval::py_truthy(&sg(spec, "sha256"));
    if has_sha && rels.len() != 1 {
        return (
            vec![format!(
                "数据契约 {} 声明了 sha256 却命中 {} 件（修复指引：sha256 只用于 path 单件）",
                sid,
                rels.len()
            )],
            Json::Object(vec![("files".to_string(), Json::Int(rels.len() as i64))]),
        );
    }
    let mut issues: Vec<String> = Vec::new();
    let mut stats: Vec<(String, Json)> = vec![
        ("files".to_string(), Json::Int(rels.len() as i64)),
        ("format".to_string(), Json::Str(fmt.clone())),
    ];
    for rel in &rels {
        let (text, err) = sread(root, rel);
        if let Some(e) = err {
            issues.push(e);
            continue;
        }
        let text = text.unwrap_or_default();
        let mut obj: Option<Json> = None;
        let (sub, s) = match fmt.as_str() {
            "json" => {
                let r = data_json(root, rel, &text, spec);
                obj = strict_json(&text).ok();
                r
            }
            "csv" => data_csv(rel, &text, spec),
            "markdown" => data_markdown(rel, &text, spec),
            "yaml" => data_yaml(root, rel, &text, spec),
            "toml" => data_toml(root, rel, &text, spec),
            "jsonl" => data_jsonl(rel, &text, spec),
            "graphml" => data_graphml(rel, &text, spec),
            "mmd" => data_mmd(rel, &text),
            _ => (
                Vec::new(),
                Json::Object(vec![(
                    "lines".to_string(),
                    Json::Int(pyval::splitlines_count(&text) as i64),
                )]),
            ),
        };
        issues.extend(sub);
        if let Json::Object(kv) = s {
            // 真源对 `no_schema` / `yaml_unavailable` 两个键**累加**到顶层，其余键 `update` 覆盖。
            for (k, v) in kv {
                if k == "no_schema" || k == "yaml_unavailable" {
                    let add = pyval::py_int_or(Some(&v), 0);
                    match stats.iter_mut().find(|(kk, _)| *kk == k) {
                        Some(e) => {
                            let base = pyval::py_int_or(Some(&e.1), 0);
                            e.1 = Json::Int(base + add);
                        }
                        None => stats.push((k, Json::Int(add))),
                    }
                    continue;
                }
                match stats.iter_mut().find(|(kk, _)| *kk == k) {
                    Some(e) => e.1 = v,
                    None => stats.push((k, v)),
                }
            }
        }
        if has_sha {
            let got = digest_of(&root.join(rel));
            let want = sg_str(spec, "sha256");
            if got != want {
                issues.push(format!(
                    "数据件 {} 摘要不符（记录 {} / 实测 {}）（修复指引：核对改动，确认后用 nf asset contract --freeze 重冻）",
                    rel,
                    head_chars(&want, 12),
                    head_chars(&got, 12)
                ));
            }
        }
        if pyval::py_truthy(&sg(spec, "link")) {
            if let Some(o) = &obj {
                issues.extend(data_link(root, rel, spec, o));
            }
        }
    }
    (issues, Json::Object(stats))
}

fn head_chars(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

/// 真源 `_strict_json`：**严格如 RFC 8259**——`NaN` / `Infinity` 出现即报错。
pub fn strict_json(text: &str) -> Result<Json, String> {
    match serde_json::from_str::<serde_json::Value>(text) {
        Ok(v) => crate::jsonread::convert(&v),
        Err(e) => Err(e.to_string()),
    }
}

// ---------------------------------------------------------------- 代码面

/// 真源 `_check_tests`。
fn check_tests(root: &Path, rel: &str, spec: &Json) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    let stem = rel.rsplit_once('.').map(|(s, _)| s).unwrap_or(rel);
    let stem = stem.rsplit_once('/').map(|(_, s)| s).unwrap_or(stem);
    if !pyval::py_truthy(&sg(spec, "tests")) {
        issues.push(format!(
            "代码件 {} 未声明测试件（修复指引：补 tests 列表——没有用例的代码资产不算通过测试）",
            rel
        ));
    }
    for t in sg_strs(spec, "tests") {
        let trel = t.replace('\\', "/");
        let p = root.join(&trel);
        if !p.is_file() {
            issues.push(format!(
                "代码件 {} 声明的测试件不在场：{}（修复指引：先写测试再登记）",
                rel, trel
            ));
            continue;
        }
        let text = std::fs::read(&p)
            .map(|b| String::from_utf8_lossy(&b).into_owned())
            .unwrap_or_default();
        if crate::pyast::parse_module(&text).is_none() {
            // 真源在这里给 CPython 的 SyntaxError 文本 ⇒ **已知偏差**（见模块头）
            issues.push(format!("测试件 {} 语法坏：<TEXT>（修复指引：先修语法）", trel));
            continue;
        }
        if !text.contains(stem) {
            issues.push(format!(
                "测试件 {} 未点名被测模块 {}（修复指引：在测试里 import 或引用该模块）",
                trel, stem
            ));
        }
    }
    issues
}

/// spec 里某键的数组条目（非数组 → 空）。
fn sg_array(spec: &Json, k: &str) -> Vec<Json> {
    match obj_get(spec, k) {
        Some(Json::Array(a)) => a.clone(),
        _ => Vec::new(),
    }
}

/// 真源 `_code_structural`（E2 第二实现线结构契约）：不做完整 AST，只判**可证的正则面**——
/// 禁用式（必须 0 处）与计数上限（棘轮只减不增）。真源明说这是「范围与只减不增的计数」，
/// 比「装作 AST 判过」诚实；本线用 `regex` crate 承担同一条语义（模式均来自真源声明）。
fn check_code_structural(root: &Path, spec: &Json) -> (Vec<String>, Json) {
    let sid = {
        let s = sg_str(spec, "id");
        if s.is_empty() {
            "?".to_string()
        } else {
            s
        }
    };
    let rels = resolve(root, spec);
    if rels.is_empty() {
        return (
            vec![format!("代码契约 {} 未命中任何文件（修复指引：修正 path/glob）", sid)],
            Json::Object(vec![("files".to_string(), Json::Int(0))]),
        );
    }
    let mut texts: Vec<(String, String)> = Vec::new();
    for rel in &rels {
        let (text, err) = sread(root, rel);
        if let Some(e) = err {
            return (
                vec![e],
                Json::Object(vec![("files".to_string(), Json::Int(rels.len() as i64))]),
            );
        }
        texts.push((rel.clone(), text.unwrap_or_default()));
    }
    let mut issues: Vec<String> = Vec::new();
    let mut stats: Vec<(String, Json)> =
        vec![("files".to_string(), Json::Int(rels.len() as i64))];
    for rule in sg_array(spec, "forbid_regex") {
        let name = sg_str(&rule, "name");
        let pat = sg_str(&rule, "pattern");
        let Ok(rx) = regex::Regex::new(&pat) else { continue };
        let mut hits: Vec<String> = Vec::new();
        for (rel, text) in &texts {
            for m in rx.find_iter(text) {
                let line = text[..m.start()].matches('\n').count() + 1;
                hits.push(format!("{}:{}", rel, line));
            }
        }
        stats.push((format!("forbid:{}", name), Json::Int(hits.len() as i64)));
        if !hits.is_empty() {
            let why = {
                let w = sg_str(&rule, "why");
                if w.is_empty() {
                    "换成不越界的等价实现".to_string()
                } else {
                    w
                }
            };
            let sample: Vec<String> = hits.iter().take(3).cloned().collect();
            issues.push(format!(
                "代码契约 {} 命中禁用式 {}（{} 处，例 {}）（修复指引：{}）",
                sid,
                name,
                hits.len(),
                sample.join("、"),
                why
            ));
        }
    }
    for rule in sg_array(spec, "regex_limits") {
        let name = sg_str(&rule, "name");
        let pat = sg_str(&rule, "pattern");
        let Ok(rx) = regex::Regex::new(&pat) else { continue };
        let n: i64 = texts.iter().map(|(_, t)| rx.find_iter(t).count() as i64).sum();
        let cap = pyval::py_int_or(obj_get(&rule, "max"), 0);
        stats.push((format!("limit:{}", name), Json::Int(n)));
        if n > cap {
            issues.push(format!(
                "代码契约 {} 的 {} 计数 {} > 上限 {}（棘轮只减不增）（修复指引：先降后改声明）",
                sid, name, n, cap
            ));
        }
    }
    (issues, Json::Object(stats))
}

/// 真源 `_check_code`。
pub fn check_code(root: &Path, spec: &Json) -> (Vec<String>, Json) {
    if !sg_array(spec, "forbid_regex").is_empty() || !sg_array(spec, "regex_limits").is_empty() {
        return check_code_structural(root, spec);
    }
    let rel = sg_str(spec, "path");
    let lang = {
        let l = sg_str(spec, "lang");
        if l.is_empty() {
            "python".to_string()
        } else {
            l
        }
    };
    if lang != "python" {
        return (
            vec![format!(
                "代码契约 {} 的 lang={} 不在支持面（仅 python 走 AST；Bash/VBA 走脚本面声明式契约）",
                pyval::py_str(obj_get(spec, "id")),
                pyval::py_str(obj_get(spec, "lang"))
            )],
            Json::Object(vec![]),
        );
    }
    let rels = resolve(root, spec);
    if rels.is_empty() {
        return (
            vec![format!(
                "代码契约 {} 未命中任何文件（修复指引：修正 path/glob）",
                pyval::py_str(obj_get(spec, "id"))
            )],
            Json::Object(vec![("files".to_string(), Json::Int(0))]),
        );
    }
    let mut issues: Vec<String> = Vec::new();
    let stats = Json::Object(vec![("files".to_string(), Json::Int(rels.len() as i64))]);
    let deny: std::collections::BTreeSet<String> =
        sg_strs(spec, "deny_calls").into_iter().collect();
    for one in &rels {
        let (text, err) = sread(root, one);
        if let Some(e) = err {
            issues.push(e);
            continue;
        }
        let text = text.unwrap_or_default();
        let Some(tree) = crate::pyast::parse_module(&text) else {
            issues.push(format!(
                "代码件 {} 语法坏：<TEXT>（修复指引：先修语法，AST 判据需要可解析的树）",
                one
            ));
            continue;
        };
        let ls = crate::pyast::LineStarts::new(&text);
        issues.extend(crate::asset_code::denied_calls(&tree, one, &deny, &ls));
        issues.extend(crate::asset_code::none_deref(&tree, one, &ls));
    }
    if !rel.is_empty() {
        issues.extend(check_tests(root, &rel, spec));
    }
    (issues, stats)
}

// ---------------------------------------------------------------- 脚本面

fn io_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"(?m)(?:#|')[ \t]*nf-io:[ \t]*(.+?)[ \t]*$").expect("固定合法")
    })
}

/// 真源 `parse_io_header` → `(inputs, outputs)`；无头 → `None`。
pub fn parse_io_header(text: &str) -> Option<(Vec<String>, Vec<String>)> {
    let m = io_re().captures(text)?;
    let mut ins: Vec<String> = Vec::new();
    let mut outs: Vec<String> = Vec::new();
    for token in m[1].split_whitespace() {
        let Some((key, val)) = token.split_once('=') else { continue };
        let key = key.trim().to_lowercase();
        let v = val.trim();
        let list: Vec<String> = if v == "-" || v.is_empty() {
            Vec::new()
        } else {
            v.split(',').map(|x| x.trim().to_string()).filter(|x| !x.is_empty()).collect()
        };
        match key.as_str() {
            "inputs" => ins = list,
            "outputs" => outs = list,
            _ => {}
        }
    }
    Some((ins, outs))
}

/// 真源 `observed_paths`：脚本里**字面量**形式的文件路径。
pub fn observed_paths(text: &str, lang: &str) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    match lang {
        "python" => {
            let Some(tree) = crate::pyast::parse_module(text) else { return out };
            let ls = crate::pyast::LineStarts::new(text);
            for (_, _, _, name, args) in crate::asset_code::calls_with_args(&tree, &ls) {
                if name != "open" && name != "Path" && name != "pathlib.Path" {
                    continue;
                }
                for a in args {
                    if let Some(s) = a {
                        out.push(s);
                    }
                }
            }
        }
        "bash" => {
            let re = regex::Regex::new(r">>?[ \t]*([^\s;|&()]+)|<[ \t]*([^\s;|&()]+)").unwrap();
            for c in re.captures_iter(text) {
                out.push(
                    c.get(1).or_else(|| c.get(2)).map(|m| m.as_str().to_string()).unwrap_or_default(),
                );
            }
        }
        "vba" => {
            let re = regex::Regex::new(r#"(?i)\bOpen\s+"([^"]+)""#).unwrap();
            for c in re.captures_iter(text) {
                out.push(c[1].to_string());
            }
        }
        _ => {}
    }
    let skip = ["/dev/null", "/dev/stdin", "/dev/stdout", "-"];
    out.into_iter()
        .filter(|p| !p.is_empty() && !skip.contains(&p.as_str()) && !p.starts_with('$'))
        .collect()
}

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
            vec![format!("脚本契约 {} 的件不在场：{}（修复指引：修正 path）", sid, rel)],
            Json::Object(vec![("files".to_string(), Json::Int(0))]),
        );
    }
    let (text, err) = sread(root, &rel);
    if let Some(e) = err {
        return (vec![e], Json::Object(vec![("files".to_string(), Json::Int(1))]));
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
    for (key, declared, embedded) in
        [("inputs", sg_strs(spec, "inputs"), emb_in), ("outputs", sg_strs(spec, "outputs"), emb_out)]
    {
        if declared != embedded {
            issues.push(format!(
                "脚本 {} 的 {} 双源不一致：声明={} / 头={}（修复指引：让两边逐字一致）",
                rel,
                key,
                pyval::py_repr_list(&declared.iter().map(|s| Json::Str(s.clone())).collect::<Vec<_>>()),
                pyval::py_repr_list(&embedded.iter().map(|s| Json::Str(s.clone())).collect::<Vec<_>>())
            ));
        }
    }
    let declared_all: std::collections::BTreeSet<String> =
        sg_strs(spec, "inputs").into_iter().chain(sg_strs(spec, "outputs")).collect();
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
            ("inputs".to_string(), Json::Int(sg_strs(spec, "inputs").len() as i64)),
            ("outputs".to_string(), Json::Int(sg_strs(spec, "outputs").len() as i64)),
        ]),
    )
}

/// 真源 `_check_chain`。
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
    let norm = |v: Vec<String>| -> Vec<String> { v.into_iter().map(|x| x.replace('\\', "/")).collect() };
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
    (issues, Json::Object(vec![("matched".to_string(), Json::Int(matched))]))
}

// ---------------------------------------------------------------- 包清单面（S1）

/// 递归收集 `dir` 下的全部文件（相对 `base` 的 POSIX 路径）。真源 `rglob("*") if is_file()`。
fn walk_files(dir: &Path, base: &Path, out: &mut Vec<String>) {
    let Ok(rd) = std::fs::read_dir(dir) else { return };
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
    let sid = {
        let s = sg_str(spec, "id");
        if s.is_empty() {
            "?".to_string()
        } else {
            s
        }
    };
    let rels = resolve(root, spec);
    if rels.is_empty() {
        return (
            vec![format!("包清单契约 {} 未命中任何清单（修复指引：修正 glob）", sid)],
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
        let doc = match strict_json(&text.unwrap_or_default()) {
            Ok(v) => v,
            Err(e) => {
                issues.push(format!(
                    "包清单 {} 不是合法 JSON：{}（修复指引：重跑 nf domain build）",
                    rel, e
                ));
                continue;
            }
        };
        let base = path_parent(&path_parent(rel)); // <包>/outputs/INDEX.json → <包>
        let outs: Vec<Json> = match obj_get(&doc, "outputs") {
            Some(Json::Array(a)) if !a.is_empty() => a.clone(),
            _ => {
                issues.push(format!(
                    "包清单 {} 的 outputs 为空（修复指引：重跑 nf domain build）",
                    rel
                ));
                continue;
            }
        };
        let mut declared: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
        for item in &outs {
            if !matches!(item, Json::Object(_)) {
                continue;
            }
            let pth = sg_str(item, "path");
            if pth.is_empty() {
                issues.push(format!("包清单 {} 有一条无 path 的声明（修复指引：补 path）", rel));
                continue;
            }
            declared.insert(pth.clone());
            declared_total += 1;
            if !root.join(&base).join(&pth).is_file() {
                issues.push(format!(
                    "包清单 {} 声明的 {} 不在场（修复指引：补件或重跑 nf domain build）",
                    rel, pth
                ));
            }
            let sch = sg_str(item, "schema");
            if !sch.is_empty() && !root.join(&base).join(&sch).is_file() {
                issues.push(format!("包清单 {} 声明的 schema {} 不在场（修复指引：补件）", rel, sch));
            }
            // 真源 `item.get("inputs") or ((item.get("recompute") or {}).get("inputs") or [])`
            let mut ins: Vec<String> = sg_strs(item, "inputs");
            if ins.is_empty() {
                let rec = sg(item, "recompute");
                if matches!(rec, Json::Object(_)) {
                    ins = sg_strs(&rec, "inputs");
                }
            }
            for inp in &ins {
                if !root.join(&base).join(inp).is_file() {
                    issues.push(format!(
                        "包清单 {} 声明的输入 {} 不在场（修复指引：补件或改声明）",
                        rel, inp
                    ));
                }
            }
        }
        let mut on_disk: Vec<String> = Vec::new();
        walk_files(&root.join(&base).join("outputs"), &root.join(&base), &mut on_disk);
        // 真源 `self_rel = Path(rel).relative_to(base).as_posix()`：清单自身不是产出面（它是清单）。
        let self_rel: String = if let Some(rest) = rel.strip_prefix(&base) {
            rest.trim_start_matches('/').to_string()
        } else {
            rel.clone()
        };
        let mut missing: Vec<String> = on_disk
            .into_iter()
            .filter(|x| {
                !declared.contains(x)
                    && *x != self_rel
                    && !x.starts_with("outputs/samples/")
            })
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
    (
        issues,
        Json::Object(vec![
            ("files".to_string(), Json::Int(rels.len() as i64)),
            ("declared".to_string(), Json::Int(declared_total)),
        ]),
    )
}

// ---------------------------------------------------------------- 登记册面（D1）

/// 真源 `_registry_issues`：本册声明为数据的 `protocol/` 件必须已在
/// `protocol/data_contracts.json` 登记。
///
/// 为什么：仓库里已有「数据契约登记册」（ODCS 式：谁判 / 谁管 / 坏了怎么重建）。资产册再造一份
/// 「谁管」就是第二套词表——同型病。判据只问一句：**同一 artifact 不许只在资产册出现**。
pub fn registry_issues(root: &Path, doc: &Json) -> Vec<String> {
    // `targets` 为空 ⇒ 本册没有 protocol 真源件 ⇒ 登记册判据不适用（临时场景常见）。
    if protocol_data_targets(root, doc).is_empty() {
        return Vec::new();
    }
    let p = root.join("protocol/data_contracts.json");
    if !p.is_file() {
        return vec!["缺 protocol/data_contracts.json\
                     （修复指引：补登记册——本册有 protocol 真源件须登记）"
            .to_string()];
    }
    let reg = match std::fs::read_to_string(&p) {
        Err(e) => {
            return vec![format!(
                "protocol/data_contracts.json 不可读：{}（修复指引：修好 JSON）",
                e
            )]
        }
        Ok(t) => match strict_json(&t) {
            Err(e) => {
                return vec![format!(
                    "protocol/data_contracts.json 不可读：{}（修复指引：修好 JSON）",
                    e
                )]
            }
            Ok(v) => v,
        },
    };
    let mut arts: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    if let Some(Json::Array(cs)) = obj_get(&reg, "contracts") {
        for c in cs {
            if matches!(c, Json::Object(_)) {
                arts.insert(sg_str(c, "artifact"));
            }
        }
    }
    let mut issues: Vec<String> = Vec::new();
    if let Some(Json::Array(specs)) = obj_get(doc, "data") {
        for spec in specs {
            for rel in resolve(root, spec) {
                if rel.starts_with("protocol/") && rel.ends_with(".json") && !arts.contains(&rel) {
                    issues.push(format!(
                        "资产 {} 未在 protocol/data_contracts.json 登记\
                         （修复指引：补一条契约——同一 artifact 不许只在资产册出现）",
                        rel
                    ));
                    break;
                }
            }
        }
    }
    issues
}

/// 真源 `_registry_issues` 里 `targets` 的那一步：本册数据面命中的 `protocol/**/*.json`。
fn protocol_data_targets(root: &Path, doc: &Json) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    if let Some(Json::Array(specs)) = obj_get(doc, "data") {
        for spec in specs {
            for rel in resolve(root, spec) {
                if rel.starts_with("protocol/") && rel.ends_with(".json") {
                    out.push(rel);
                }
            }
        }
    }
    out
}

// ---------------------------------------------------------------- 导出面（S3）

/// 真源 `_FRIENDLY`：JSON Schema 类型名 → Frictionless Table Schema 类型名。
fn friendly_type(t: &str) -> &'static str {
    match t {
        "string" => "string",
        "integer" => "integer",
        "number" => "number",
        "boolean" => "boolean",
        "array" => "array",
        "object" => "object",
        "null" => "any",
        _ => "any",
    }
}

/// 真源 `frictionless_export`：把已声明的数据资产映射成 **Frictionless Data Package**。
///
/// 诚实边界：`fields` 是 JSON Schema `properties` 的**尽力映射**（类型名对齐 Frictionless
/// Table Schema），原始 JSON Schema 仍在 `x-nf-json-schema` 里逐字段保留——映射丢信息就是
/// 装饰，故不丢。只导出**资产面**（包产物/库索引），协议层真源不外发。
pub fn frictionless_export(root: &Path) -> (Json, Vec<String>) {
    let (doc, issues) = load(root);
    if !issues.is_empty() {
        return (Json::Object(vec![]), issues);
    }
    let mut res: Vec<Json> = Vec::new();
    if let Some(Json::Array(specs)) = obj_get(&doc, "data") {
        for spec in specs {
            if !matches!(spec, Json::Object(_)) {
                continue;
            }
            for rel in resolve(root, spec) {
                if rel.starts_with("protocol/") {
                    continue;
                }
                let mut item: Vec<(String, Json)> = vec![
                    ("name".to_string(), Json::Str(rel.replace('/', "--"))),
                    ("path".to_string(), Json::Str(rel.clone())),
                ];
                let fmt = sg_str(spec, "format");
                if !fmt.is_empty() {
                    item.push(("format".to_string(), Json::Str(fmt)));
                }
                let sch_rel = schema_of(root, &rel, spec);
                if !sch_rel.is_empty() {
                    let (stext, err) = sread(root, &sch_rel);
                    if err.is_none() {
                        let sch = strict_json(&stext.unwrap_or_default())
                            .unwrap_or_else(|_| Json::Object(vec![]));
                        let keep = ["type", "required", "properties", "$schema", "title", "description"];
                        let mut sub: Vec<(String, Json)> = Vec::new();
                        if let Json::Object(kv) = &sch {
                            for k in keep.iter() {
                                if let Some((kk, vv)) = kv.iter().find(|(kk, _)| kk == k) {
                                    sub.push((kk.clone(), vv.clone()));
                                }
                            }
                        }
                        let sch_nonempty = matches!(&sch, Json::Object(kv) if !kv.is_empty());
                        if sch_nonempty {
                            item.push(("x-nf-json-schema".to_string(), Json::Object(sub)));
                            item.push((
                                "x-nf-schema-source".to_string(),
                                Json::Str(sch_rel.clone()),
                            ));
                        }
                        let mut props: Vec<(String, Json)> = match obj_get(&sch, "properties") {
                            Some(Json::Object(o)) => o.clone(),
                            _ => Vec::new(),
                        };
                        props.sort_by(|a, b| a.0.cmp(&b.0));
                        let mut fields: Vec<Json> = Vec::new();
                        for (k, v) in props {
                            if !matches!(v, Json::Object(_)) {
                                continue;
                            }
                            let t = sg_str(&v, "type");
                            fields.push(Json::Object(vec![
                                ("name".to_string(), Json::Str(k)),
                                ("type".to_string(), Json::Str(friendly_type(&t).to_string())),
                            ]));
                        }
                        if !fields.is_empty() {
                            item.push((
                                "schema".to_string(),
                                Json::Object(vec![(
                                    "fields".to_string(),
                                    Json::Array(fields),
                                )]),
                            ));
                        }
                    }
                }
                res.push(Json::Object(item));
            }
        }
    }
    let pkg = Json::Object(vec![
        ("profile".to_string(), Json::Str("data-package".to_string())),
        ("name".to_string(), Json::Str("ninfenz-asset-contracts".to_string())),
        (
            "title".to_string(),
            Json::Str("NinFenz 数字资产契约（Frictionless Data Package 导出）".to_string()),
        ),
        (
            "x-nf-generated-by".to_string(),
            Json::Str("nf asset contract --export".to_string()),
        ),
        (
            "x-nf-note".to_string(),
            Json::Str(
                "由已声明契约面确定性导出；领域包产物按同名 schema 约定带 fields 映射".to_string(),
            ),
        ),
        ("resources".to_string(), Json::Array(res)),
    ]);
    (pkg, Vec::new())
}

/// 真源 `_export_drift`（④）：导出件 == 实时导出（缺件/漂移都 FAIL：导出面不许只在人手里新鲜）。
pub fn export_drift(root: &Path) -> Vec<String> {
    let (live, errs) = frictionless_export(root);
    if !errs.is_empty() {
        return errs;
    }
    let p = root.join(EXPORT_REL);
    if !p.is_file() {
        return vec![format!(
            "④ 缺契约导出 {}（修复指引：nf asset contract --export）",
            EXPORT_REL
        )];
    }
    let disk = match std::fs::read_to_string(&p) {
        Err(e) => {
            return vec![format!(
                "④ {} 不可读：{}（修复指引：nf asset contract --export）",
                EXPORT_REL, e
            )]
        }
        Ok(t) => match strict_json(&t) {
            Err(e) => {
                return vec![format!(
                    "④ {} 不可读：{}（修复指引：nf asset contract --export）",
                    EXPORT_REL, e
                )]
            }
            Ok(v) => v,
        },
    };
    if crate::jsonread::json_eq(&disk, &live) {
        Vec::new()
    } else {
        vec![format!(
            "④ {} 与实时导出不一致（修复指引：nf asset contract --export）",
            EXPORT_REL
        )]
    }
}

// ---------------------------------------------------------------- 声明自检面（S2）

/// 真源 `_schema_self_check`（⑤）：声明必须过**可移植 schema**（规范要可执行，不做文档摆设）。
pub fn schema_self_check(root: &Path) -> Vec<String> {
    let sp = root.join(SCHEMA_REL);
    if !sp.is_file() {
        return vec![format!(
            "⑤ 缺可移植 schema {}（修复指引：补该件——对外可移植契约靠它定型）",
            SCHEMA_REL
        )];
    }
    let read = |p: &Path| -> Result<Json, String> {
        match std::fs::read_to_string(p) {
            Err(e) => Err(e.to_string()),
            Ok(t) => strict_json(&t),
        }
    };
    let doc = match read(&root.join(DECL_REL)) {
        Ok(v) => v,
        Err(e) => {
            return vec![format!(
                "⑤ 声明或 schema 不可读：{}（修复指引：修好 JSON）",
                e
            )]
        }
    };
    let sch = match read(&sp) {
        Ok(v) => v,
        Err(e) => {
            return vec![format!(
                "⑤ 声明或 schema 不可读：{}（修复指引：修好 JSON）",
                e
            )]
        }
    };
    json_schema::json_schema_check(&doc, &sch)
        .iter()
        .take(5)
        .map(|e| {
            format!(
                "⑤ 声明不符可移植 schema {}：{}（修复指引：改声明或改 schema——两者只能有一个对）",
                SCHEMA_REL, e
            )
        })
        .collect()
}

// ---------------------------------------------------------------- 聚合 / 入口

/// 真源 `load`。
pub fn load(root: &Path) -> (Json, Vec<String>) {
    let p = root.join(DECL_REL);
    if !p.is_file() {
        return (
            Json::Object(vec![]),
            vec![format!(
                "缺数字资产契约声明 {}（修复指引：新建并写入 schema={} 与 data/code/script 三面）",
                DECL_REL, SCHEMA
            )],
        );
    }
    let text = match std::fs::read_to_string(&p) {
        Ok(s) => s,
        Err(e) => {
            return (
                Json::Object(vec![]),
                vec![format!("{} 不可读或不是合法 JSON：{}（修复指引：修好语法）", DECL_REL, e)],
            )
        }
    };
    let doc = match strict_json(&text) {
        Ok(v) => v,
        Err(e) => {
            return (
                Json::Object(vec![]),
                vec![format!("{} 不可读或不是合法 JSON：{}（修复指引：修好语法）", DECL_REL, e)],
            )
        }
    };
    if !matches!(doc, Json::Object(_)) || sg_str(&doc, "schema") != SCHEMA {
        return (
            Json::Object(vec![]),
            vec![format!(
                "{} schema 不匹配（期望 {}）（修复指引：改为声明件当前形态）",
                DECL_REL, SCHEMA
            )],
        );
    }
    (doc, Vec::new())
}

/// 真源 `scan(root, faces=())` → `(issues, warns, stats)`。
pub fn scan(root: &Path) -> (Vec<String>, Vec<String>, Json) {
    let (doc, mut issues) = load(root);
    let warns: Vec<String> = Vec::new();
    let mut counts: Vec<(String, i64)> =
        FACES.iter().map(|f| ((*f).to_string(), 0i64)).collect();
    let mut files = 0i64;
    let mut chains = 0i64;
    let mut no_schema = 0i64;
    if !issues.is_empty() {
        let mut kv: Vec<(String, Json)> =
            counts.iter().map(|(k, v)| (k.clone(), Json::Int(*v))).collect();
        kv.push(("files".to_string(), Json::Int(0)));
        kv.push(("chains".to_string(), Json::Int(0)));
        return (issues, warns, Json::Object(kv));
    }
    // 真源同序：load → 登记册（D1，四面都判）→ 导出漂移（④）/ 声明自检（⑤，声明面整体判据）。
    issues.extend(registry_issues(root, &doc));
    issues.extend(export_drift(root));
    issues.extend(schema_self_check(root));
    for face in FACES {
        let specs = match obj_get(&doc, face) {
            Some(Json::Array(a)) => a.clone(),
            _ => Vec::new(),
        };
        for spec in specs {
            if !matches!(spec, Json::Object(_)) {
                issues.push(format!("契约 {} 面有非对象条目（修复指引：每条须是对象）", face));
                continue;
            }
            let (sub, s) = match face {
                "data" => check_data(root, &spec),
                "code" => check_code(root, &spec),
                "index" => check_index(root, &spec),
                _ => check_script(root, &spec),
            };
            issues.extend(sub);
            if let Some(e) = counts.iter_mut().find(|(k, _)| k == face) {
                e.1 += 1;
            }
            files += pyval::py_int_or(obj_get(&s, "files"), 0);
            // 真源：`stats["no_schema"] = int(stats.get("no_schema") or 0) + int(s.get(...) or 0)`
            no_schema += pyval::py_int_or(obj_get(&s, "no_schema"), 0);
        }
    }
    let specs: Vec<(String, Json)> = match obj_get(&doc, "script") {
        Some(Json::Array(a)) => a
            .iter()
            .map(|s| (sg_str(s, "id"), s.clone()))
            .collect(),
        _ => Vec::new(),
    };
    if let Some(Json::Array(cs)) = obj_get(&doc, "chains") {
        for c in cs {
            let empty = Json::Object(vec![]);
            let chain = if matches!(c, Json::Object(_)) { c } else { &empty };
            let (sub, _) = check_chain(&specs, chain);
            issues.extend(sub);
            chains += 1;
        }
    }
    let mut kv: Vec<(String, Json)> =
        counts.iter().map(|(k, v)| (k.clone(), Json::Int(*v))).collect();
    kv.push(("files".to_string(), Json::Int(files)));
    kv.push(("chains".to_string(), Json::Int(chains)));
    kv.push(("no_schema".to_string(), Json::Int(no_schema)));
    (issues, warns, Json::Object(kv))
}

#[cfg(test)]
mod tests {
    use super::*;
    // >>> GENERATED HELPER by tools/gen_asset_data_cases.py（勿手改；重跑生成器覆盖本段）
    /// 合成夹具的内容（与 `tools/gen_asset_data_cases.py` 里 Python 侧那份**逐字同源**）。
    const AC_FIX_FILES: [(&str, &str); 18] = [
        (r#"bad.json"#, r#"{"a": "x"}
"#),
        (r#"badschema.json"#, r#"{"type": }
"#),
        (r#"blankhdr.csv"#, r#"a,,c
1,2,3
"#),
        (r#"empty.csv"#, r#""#),
        (r#"link.csv"#, r#"h
1
2
3
"#),
        (r#"link.json"#, r#"{"p": "link.csv", "n": 3}
"#),
        (r#"linkbad.json"#, r#"{"p": "link.csv", "n": 9}
"#),
        (r#"linkmiss.json"#, r#"{"p": "nope.csv", "n": 1}
"#),
        (r#"nofm.md"#, r#"| a |
| --- |
| 1 |
"#),
        (r#"nonan.json"#, r#"{"a": NaN}
"#),
        (r#"ok.csv"#, r#"a,b
1,2
3,4
"#),
        (r#"ok.json"#, r#"{"a": 1, "n": 3}
"#),
        (r#"ok.md"#, r#"---
x: 1
---

| a | b |
| --- | --- |
| 1 | 2 |
"#),
        (r#"plain.txt"#, r#"l1
l2
"#),
        (r#"quoted.csv"#, r#"a,b
"x,1",2
"#),
        (r#"ragged.csv"#, r#"a,b
1,2,3
4,5
"#),
        (r#"ragged.md"#, r#"---

| a | b |
| --- | --- |
| 1 |
"#),
        (r#"sch.json"#, r#"{"type": "object", "required": ["a"]}
"#),    ];

    fn write_asset_data_fixture(root: &std::path::Path) {
        for (rel, body) in AC_FIX_FILES {
            let p = root.join(rel);
            std::fs::create_dir_all(p.parent().unwrap()).unwrap();
            std::fs::write(p, body).unwrap();
        }
    }
    // <<< GENERATED HELPER
    // >>> GENERATED by tools/gen_asset_data_cases.py（勿手改；重跑生成器覆盖本段）
    /// ===== 数据面用例级判据（期望值由 `tools/gen_asset_data_cases.py` 从真源生成）=====
    ///
    /// ① **真实声明的四条**在**真仓库根**上跑：JSON(schema+required+link) / CSV(required_columns+
    /// min_rows) / markdown / sha256 的通过路径。
    /// ② **合成夹具**覆盖错误分支：缺件 / format 非法 / sha256 多件 / 必填缺 / CSV 空·空列名·
    /// 列数不齐·缺列·行数不足·带引号字段 / markdown 缺 frontmatter·表列数不齐 / link 三类。
    ///
    /// `strict_json` 与 `_read` 的**报错文本**两处已知偏差（serde_json / std::io vs CPython），
    /// 故断言前对这两类消息做**归一**——不假装文本相同。
    fn ac_repo_root() -> std::path::PathBuf {
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
    }

    /// 归一：解析/读件失败的文本两侧不可比，只留稳定前缀。
    fn ac_norm(issues: &[String]) -> Vec<String> {
        issues
            .iter()
            .map(|x| {
                for pat in ["不是合法 JSON：", "schema 本身不是合法 JSON：", "读不到 ",
                            " 不是 UTF-8："] {
                    if let Some(i) = x.find(pat) {
                        return format!("{}<TEXT>", &x[..i + pat.len()]);
                    }
                }
                x.clone()
            })
            .collect()
    }

    #[test]
    fn asset_data_real_declarations_match_truth_source() {
        let root = ac_repo_root();
        let cases: &[(&str, &[&str], &str)] = &[
        (
            r#"{"format": "json", "glob": "community/*/outputs/*.json", "id": "pack-outputs-vs-schemas", "note": "包产物 ↔ 同名 schema 约定（D2 自动发现）：实测 216 对全绿；无 schema 的件计入 no_schema 缺口，不判死", "schema_siblings": ["schemas/{stem}.schema.json"]}"#,
            &[],
            r#"{"fields": 0, "files": 422, "format": "json", "no_schema": 206}"#
        ),
        (
            r#"{"format": "json", "glob": "community/*/outputs/REPORT.json", "id": "pack-reports-io", "link": {"path_field": "sample", "rows_field": "sample_rows"}, "note": "输入输出一致性：REPORT.sample 指向的 CSV 行数必须等于 sample_rows（base 缺省按产物目录与其父目录两候选解析）", "schema_siblings": ["schemas/{stem}.schema.json", "schemas/DOMAIN_REPORT.schema.json"]}"#,
            &[],
            r#"{"fields": 0, "files": 100, "format": "json"}"#
        ),
        (
            r#"{"format": "csv", "glob": "community/*/outputs/samples/CASES.csv", "id": "pack-cases-csv", "min_rows": 1, "note": "样例集表头**族**各不相同（实测 11 种），故只判「至少含族内一个 id 列」", "required_any_columns": ["case_id", "task_id", "query_id", "bucket"]}"#,
            &[],
            r#"{"columns": 4, "files": 100, "format": "csv", "rows": 20}"#
        ),
        (
            r#"{"format": "markdown", "id": "library-index", "path": "library/INDEX.md"}"#,
            &[],
            r#"{"files": 1, "format": "markdown", "tables": 2}"#
        ),
        (
            r#"{"format": "json", "id": "ladder-truth", "path": "protocol/LAYERS.json", "required_fields": ["schema", "rules", "tiers"], "sha256": "0285b8b1fdf20b9ca9cd0857118cd7f3c09946256d33a6d42028a5c41aad0023"}"#,
            &[],
            r#"{"fields": 3, "files": 1, "format": "json"}"#
        ),
        (
            r#"{"format": "yaml", "glob": "community/*/protocol.yaml", "id": "pack-protocol-yaml", "note": "包协议声明：YAML 解析后过 check28 用的同一份 protocol.schema.json（不另造方言）", "schema": "protocol/schema/protocol.schema.json"}"#,
            &[],
            r#"{"fields": 0, "files": 111, "format": "yaml"}"#
        ),
        (
            r#"{"format": "mmd", "glob": "community/*/outputs/charts/*.mmd", "id": "pack-charts-mermaid", "note": "图表资产：只判「首关键词是合法 Mermaid 图型」，不解析图内容"}"#,
            &[],
            r#"{"files": 106, "format": "mmd", "kind": "flowchart"}"#
        ),
        (
            r#"{"format": "graphml", "glob": "community/*/outputs/**/*.graphml", "id": "pack-charts-graphml", "min_nodes": 1, "note": "图结构资产：XML 良构 + 节点/边计数"}"#,
            &[],
            r#"{"edges": 49, "files": 105, "format": "graphml", "nodes": 24}"#
        ),
        (
            r#"{"format": "json", "id": "asset-contracts-self", "note": "本册自检（自指但可证）：声明件自身必须含 schema 与三面键——check40 因此成为它自己的判据", "path": "protocol/asset_contracts.json", "required_fields": ["schema", "data", "code", "script"]}"#,
            &[],
            r#"{"fields": 4, "files": 1, "format": "json"}"#
        ),
        (
            r#"{"format": "json", "id": "role-coordinates", "note": "职能坐标冻结投影（ADR-0006）：核内逐件 + 计数 + 摘要；漂移由 role_model 另判", "path": "protocol/role_coordinates.json", "required_fields": ["schema", "counts", "kernel", "root_digest"]}"#,
            &[],
            r#"{"fields": 4, "files": 1, "format": "json"}"#
        ),
        ];
        for (spec_s, want_issues, want_stats) in cases {
            let spec: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(spec_s).unwrap(),
            )
            .unwrap();
            let (issues, stats) = check_data(&root, &spec);
            assert_eq!(ac_norm(&issues), ac_norm(&want_issues.iter().map(|s| s.to_string()).collect::<Vec<_>>()),
                       "真实声明 issues 不一致");
            let want: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(want_stats).unwrap(),
            )
            .unwrap();
            assert!(crate::jsonread::json_eq(&stats, &want),
                    "真实声明 stats 不一致\n  实得 {}\n  期望 {}", stats.dumps(), want.dumps());
        }
    }

    #[test]
    fn asset_data_synthetic_branches_match_truth_source() {
        let root = crate::testutil::fixture("asset-data-cases-src");
        write_asset_data_fixture(&root);
        let cases: &[(&str, &str, &[&str], &str)] = &[
        (
            r#"ok-json-schema"#,
            r#"{"format": "json", "id": "s1", "path": "ok.json", "schema": "sch.json"}"#,
            &[],
            r#"{"fields": 0, "files": 1, "format": "json"}"#
        ),
        (
            r#"bad-json-schema"#,
            r#"{"format": "json", "id": "s2", "path": "bad.json", "schema": "sch.json"}"#,
            &[],
            r#"{"fields": 0, "files": 1, "format": "json"}"#
        ),
        (
            r#"non-rfc8259"#,
            r#"{"format": "json", "id": "s3", "path": "nonan.json"}"#,
            &[r#"数据件 nonan.json 不是合法 JSON：资产契约文本 不是合法 JSON：按 RFC 8259 不接受 NaN（修复指引：改用 null 或有限数字）（修复指引：核对该件是否被写坏 / 含注释 / 截断）（修复指引：修好语法或换 format）"#],
            r#"{"files": 1, "format": "json"}"#
        ),
        (
            r#"bad-schema-json"#,
            r#"{"format": "json", "id": "s4", "path": "ok.json", "schema": "badschema.json"}"#,
            &[r#"数据件 ok.json 不符 schema badschema.json：schema 本身不是合法 JSON：资产契约文本 不是合法 JSON：Expecting value: line 1 column 10 (char 9)（修复指引：核对该件是否被写坏 / 含注释 / 截断）"#],
            r#"{"fields": 0, "files": 1, "format": "json"}"#
        ),
        (
            r#"schema-missing"#,
            r#"{"format": "json", "id": "s5", "path": "ok.json", "schema": "nope.json"}"#,
            &[r#"数据件 ok.json 的 schema 读不到：读不到 nope.json：[Errno 2] No such file or directory: 'C:\\Users\\mon_7\\Downloads\\nf-wt-rustrf\\engine\\rust\\target\\test-fixtures\\asset-data-cases\\nope.json'（修复指引：核对声明里的路径在场）"#],
            r#"{"fields": 0, "files": 1, "format": "json"}"#
        ),
        (
            r#"required-missing"#,
            r#"{"format": "json", "id": "s6", "path": "bad.json", "required_fields": ["zz"]}"#,
            &[r#"数据件 bad.json 缺必填字段 zz（修复指引：补字段或从声明里删掉——声明即契约）"#],
            r#"{"fields": 1, "files": 1, "format": "json"}"#
        ),
        (
            r#"format-invalid"#,
            r#"{"format": "xml", "id": "s7", "path": "ok.json"}"#,
            &[r#"数据契约 s7 的 format='xml' 不在词表 json/csv/markdown/text/yaml/toml/jsonl/graphml/mmd（修复指引：改用词表内格式）"#],
            r#"{"files": 1}"#
        ),
        (
            r#"path-missing"#,
            r#"{"format": "json", "id": "s8", "path": "nope.json"}"#,
            &[r#"数据契约 s8 未命中任何文件（修复指引：修正 path/glob —— 空气不是契约）"#],
            r#"{"files": 0}"#
        ),
        (
            r#"glob-empty"#,
            r#"{"format": "json", "glob": "*.nope", "id": "s9"}"#,
            &[r#"数据契约 s9 未命中任何文件（修复指引：修正 path/glob —— 空气不是契约）"#],
            r#"{"files": 0}"#
        ),
        (
            r#"sha-multi"#,
            r#"{"format": "csv", "glob": "*.csv", "id": "s10", "sha256": "00"}"#,
            &[r#"数据契约 s10 声明了 sha256 却命中 6 件（修复指引：sha256 只用于 path 单件）"#],
            r#"{"files": 6}"#
        ),
        (
            r#"sha-mismatch"#,
            r#"{"format": "csv", "id": "s11", "path": "ok.csv", "sha256": "00"}"#,
            &[r#"数据件 ok.csv 摘要不符（记录 00 / 实测 b94851485464）（修复指引：核对改动，确认后用 nf asset contract --freeze 重冻）"#],
            r#"{"columns": 2, "files": 1, "format": "csv", "rows": 2}"#
        ),
        (
            r#"csv-ok"#,
            r#"{"format": "csv", "id": "s12", "path": "ok.csv", "required_columns": ["a"]}"#,
            &[],
            r#"{"columns": 2, "files": 1, "format": "csv", "rows": 2}"#
        ),
        (
            r#"csv-empty"#,
            r#"{"format": "csv", "id": "s13", "path": "empty.csv"}"#,
            &[r#"数据件 empty.csv 是空 CSV（修复指引：至少要有表头行）"#],
            r#"{"files": 1, "format": "csv", "rows": 0}"#
        ),
        (
            r#"csv-blank-header"#,
            r#"{"format": "csv", "id": "s14", "path": "blankhdr.csv"}"#,
            &[r#"数据件 blankhdr.csv 表头有空列名（修复指引：每列都要有名字）"#],
            r#"{"columns": 3, "files": 1, "format": "csv", "rows": 1}"#
        ),
        (
            r#"csv-ragged"#,
            r#"{"format": "csv", "id": "s15", "path": "ragged.csv"}"#,
            &[r#"数据件 ragged.csv 第 2 行列数 != 表头 2（修复指引：补齐/删除多余的分隔符）"#],
            r#"{"columns": 2, "files": 1, "format": "csv", "rows": 2}"#
        ),
        (
            r#"csv-missing-col"#,
            r#"{"format": "csv", "id": "s16", "path": "ok.csv", "required_columns": ["zz"]}"#,
            &[r#"数据件 ok.csv 缺必需列 zz（修复指引：加列或改声明）"#],
            r#"{"columns": 2, "files": 1, "format": "csv", "rows": 2}"#
        ),
        (
            r#"csv-min-rows"#,
            r#"{"format": "csv", "id": "s17", "min_rows": 99, "path": "ok.csv"}"#,
            &[r#"数据件 ok.csv 数据行 2 < min_rows 99（修复指引：补样例或下调声明）"#],
            r#"{"columns": 2, "files": 1, "format": "csv", "rows": 2}"#
        ),
        (
            r#"csv-quoted"#,
            r#"{"format": "csv", "id": "s18", "path": "quoted.csv", "required_columns": ["a", "b"]}"#,
            &[],
            r#"{"columns": 2, "files": 1, "format": "csv", "rows": 1}"#
        ),
        (
            r#"md-ok"#,
            r#"{"format": "markdown", "frontmatter": true, "id": "s19", "path": "ok.md"}"#,
            &[],
            r#"{"files": 1, "format": "markdown", "tables": 1}"#
        ),
        (
            r#"md-ragged"#,
            r#"{"format": "markdown", "frontmatter": true, "id": "s20", "path": "ragged.md"}"#,
            &[r#"数据件 ragged.md 有一张表列数不齐：表头 2 列 vs 数据 1 列（修复指引：对齐竖线）"#],
            r#"{"files": 1, "format": "markdown", "tables": 1}"#
        ),
        (
            r#"md-no-frontmatter"#,
            r#"{"format": "markdown", "frontmatter": true, "id": "s21", "path": "nofm.md"}"#,
            &[r#"数据件 nofm.md 缺 frontmatter（修复指引：件首补 --- 块）"#],
            r#"{"files": 1, "format": "markdown", "tables": 1}"#
        ),
        (
            r#"text-lines"#,
            r#"{"format": "text", "id": "s22", "path": "plain.txt"}"#,
            &[],
            r#"{"files": 1, "format": "text", "lines": 2}"#
        ),
        (
            r#"link-ok"#,
            r#"{"format": "json", "id": "s23", "link": {"path_field": "p", "rows_field": "n"}, "path": "link.json"}"#,
            &[],
            r#"{"fields": 0, "files": 1, "format": "json"}"#
        ),
        (
            r#"link-mismatch"#,
            r#"{"format": "json", "id": "s24", "link": {"path_field": "p", "rows_field": "n"}, "path": "linkbad.json"}"#,
            &[r#"数据件 linkbad.json 的 n=9 与 link.csv 数据行 3 不一致（修复指引：重算或改声明）"#],
            r#"{"fields": 0, "files": 1, "format": "json"}"#
        ),
        (
            r#"link-missing"#,
            r#"{"format": "json", "id": "s25", "link": {"path_field": "p"}, "path": "linkmiss.json"}"#,
            &[r#"数据件 linkmiss.json 指向的 nope.csv 不在场（修复指引：补件或修正 link.base）"#],
            r#"{"fields": 0, "files": 1, "format": "json"}"#
        ),
        (
            r#"link-no-path-field"#,
            r#"{"format": "json", "id": "s26", "link": {"path_field": "nope"}, "path": "link.json"}"#,
            &[r#"数据件 link.json 的 link.path_field=nope 取不到字符串路径（修复指引：核对字段名）"#],
            r#"{"fields": 0, "files": 1, "format": "json"}"#
        ),
        ];
        for (name, spec_s, want_issues, want_stats) in cases {
            let spec: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(spec_s).unwrap(),
            )
            .unwrap();
            let (issues, stats) = check_data(&root, &spec);
            assert_eq!(ac_norm(&issues),
                       ac_norm(&want_issues.iter().map(|s| s.to_string()).collect::<Vec<_>>()),
                       "合成用例 {} 的 issues 不一致", name);
            let want: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(want_stats).unwrap(),
            )
            .unwrap();
            assert!(crate::jsonread::json_eq(&stats, &want),
                    "合成用例 {} 的 stats 不一致\n  实得 {}\n  期望 {}", name,
                    stats.dumps(), want.dumps());
        }
    }
    // <<< GENERATED
    // >>> GENERATED by tools/gen_asset_code_cases.py（勿手改；重跑生成器覆盖本段）
    /// ===== 代码面 / 脚本面 / 链 / 聚合（真实声明，期望值由生成器从真源取）=====
    ///
    /// 语法坏那一支的**文本不可比**（真源给 CPython `SyntaxError`，本线给本线解析器的），
    /// 故那类消息在两侧都归一到 `<TEXT>`（同 `code_metrics` 的处理）。
    #[test]
    fn asset_code_real_declarations_match_truth_source() {
        let root = ac_repo_root();
        let cases: &[(&str, &[&str], &str)] = &[
        (
            r#"{"deny_calls": ["eval", "exec", "__import__", "os.system", "pickle.loads", "marshal.loads"], "id": "asset-contract", "lang": "python", "path": "desktop/src/core/asset_contract.py", "tests": ["desktop/tests/test_asset_contract.py"]}"#,
            &[],
            r#"{"files": 1}"#
        ),
        (
            r#"{"deny_calls": ["eval", "exec", "__import__", "os.system"], "id": "json-schema-leaf", "lang": "python", "path": "desktop/src/core/json_schema.py", "tests": ["desktop/tests/test_output_forms.py"]}"#,
            &[],
            r#"{"files": 1}"#
        ),
        (
            r#"{"deny_calls": ["eval", "exec", "__import__", "os.system"], "id": "content-face-leaf", "lang": "python", "path": "desktop/src/core/content_face.py", "tests": ["desktop/tests/test_content_face.py"]}"#,
            &[],
            r#"{"files": 1}"#
        ),
        (
            r#"{"deny_calls": ["eval", "exec", "__import__", "os.system", "pickle.loads", "marshal.loads"], "id": "role-model", "lang": "python", "path": "desktop/src/core/role_model.py", "tests": ["desktop/tests/test_role_model.py"]}"#,
            &[],
            r#"{"files": 1}"#
        ),
        (
            concat!(r#"{"forbid_regex": [{"name": ""#, "un", "safe", r#"", "pattern": "\\b"#, "un", "safe", r#"\\b", "why": "第二实现线是**只读判据**；"#, "un", "safe", r#" 会把它变成可写面"}], "glob": "engine/rust/src/**/*.rs", "id": "engine-rust-structural", "lang": "rust", "note": "E2 结构契约（非 AST）：只判禁用式与计数棘轮；完整语法树不在本层范围（ADR-0005 划范围）", "regex_limits": [{"max": 1, "name": "extern-c", "pattern": "extern\\s+\"C\"", "why": "FFI 面只许只减不增（实测 1 处）"}]}"#),
            &[],
            concat!(r#"{"files": 84, "forbid:"#, "un", "safe", r#"": 0, "limit:extern-c": 1}"#)
        ),
        (
            concat!(r#"{"forbid_regex": [{"name": ""#, "un", "safe", r#"", "pattern": "\\b"#, "un", "safe", r#"\\b", "why": "第二实现线是只读判据"}, {"name": "DllImport", "pattern": "\\bDllImport\\b", "why": "P/Invoke 面须走显式声明与评审"}, {"name": "extern", "pattern": "\\bextern\\b", "why": "外部符号直接绑定会绕过只读边界"}], "glob": "engine/dotnet/**/*.cs", "id": "engine-dotnet-structural", "lang": "cs", "note": "同上（实测三类各 0 处，故按零容忍声明）"}"#),
            &[],
            concat!(r#"{"files": 109, "forbid:DllImport": 0, "forbid:extern": 0, "forbid:"#, "un", "safe", r#"": 0}"#)
        ),
        ];
        for (spec_s, want_issues, want_stats) in cases {
            let spec: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(spec_s).unwrap(),
            )
            .unwrap();
            let (issues, stats) = check_code(&root, &spec);
            assert_eq!(ac_norm(&issues),
                       ac_norm(&want_issues.iter().map(|s| s.to_string()).collect::<Vec<_>>()),
                       "代码面 issues 不一致");
            let want: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(want_stats).unwrap(),
            )
            .unwrap();
            assert!(crate::jsonread::json_eq(&stats, &want), "代码面 stats 不一致");
        }
    }

    #[test]
    fn asset_script_real_declarations_match_truth_source() {
        let root = ac_repo_root();
        let cases: &[(&str, &[&str], &str)] = &[
        (
            r#"{"id": "cards", "inputs": ["verify.sh"], "lang": "python", "outputs": ["docs/verification-cards.md"], "path": "scripts/build_verification_cards.py"}"#,
            &[],
            r#"{"files": 1, "inputs": 1, "outputs": 1}"#
        ),
        (
            r#"{"id": "geo-export", "inputs": ["protocol/standards_catalog.json", "protocol/standards_binding.json"], "lang": "python", "outputs": ["docs/standards/index.md", "docs/standards/answer-cards.md", "protocol/geo_export.json", "docs/standards/layer-data.md", "docs/standards/layer-eng.md", "docs/standards/layer-form.md", "docs/standards/layer-gov.md", "docs/standards/layer-iface.md"], "path": "scripts/geo_export.py"}"#,
            &[],
            r#"{"files": 1, "inputs": 2, "outputs": 8}"#
        ),
        (
            r#"{"id": "external-links", "inputs": ["README.md", "README.en.md", "llms.txt", "docs/agent/AGENT_START.md", "docs/agent/ROUTES.md", "docs/verification-cards.md"], "lang": "python", "outputs": ["results/external-links-report.json"], "path": "scripts/check_external_links.py"}"#,
            &[],
            r#"{"files": 1, "inputs": 6, "outputs": 1}"#
        ),
        (
            r#"{"id": "quality-all", "inputs": ["verify.sh"], "lang": "bash", "outputs": [], "path": "scripts/quality_all.sh"}"#,
            &[],
            r#"{"files": 1, "inputs": 1, "outputs": 0}"#
        ),
        ];
        for (spec_s, want_issues, want_stats) in cases {
            let spec: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(spec_s).unwrap(),
            )
            .unwrap();
            let (issues, stats) = check_script(&root, &spec);
            assert_eq!(issues, want_issues.to_vec(), "脚本面 issues 不一致");
            let want: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(want_stats).unwrap(),
            )
            .unwrap();
            assert!(crate::jsonread::json_eq(&stats, &want), "脚本面 stats 不一致");
        }
    }

    #[test]
    fn asset_chains_match_truth_source() {
        let root = ac_repo_root();
        let specs: Vec<(String, Json)> = {
            let (doc, _) = load(&root);
            match obj_get(&doc, "script") {
                Some(Json::Array(a)) => a.iter().map(|s| (sg_str(s, "id"), s.clone())).collect(),
                _ => Vec::new(),
            }
        };
        let cases: &[(&str, &[&str], &str)] = &[
        (
            r#"{"feeds": [{"input": "docs/verification-cards.md", "output": "docs/verification-cards.md"}], "from": "cards", "id": "cards-to-external-links", "to": "external-links"}"#,
            &[],
            r#"{"matched": 1}"#
        ),
        ];
        for (chain_s, want_issues, want_stats) in cases {
            let chain: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(chain_s).unwrap(),
            )
            .unwrap();
            let (issues, stats) = check_chain(&specs, &chain);
            assert_eq!(issues, want_issues.to_vec(), "链 issues 不一致");
            let want: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(want_stats).unwrap(),
            )
            .unwrap();
            assert!(crate::jsonread::json_eq(&stats, &want), "链 stats 不一致");
        }
    }

    #[test]
    fn asset_contract_scan_matches_truth_source() {
        let root = ac_repo_root();
        let (issues, warns, stats) = scan(&root);
        assert_eq!(ac_norm(&issues), &[] as &[&str], "聚合 issues 不一致");
        assert_eq!(warns, &[] as &[&str], "聚合 warns 不一致");
        let want: Json = crate::jsonread::convert(
            &serde_json::from_str::<serde_json::Value>(r#"{"chains": 1, "code": 6, "data": 10, "files": 1255, "index": 1, "no_schema": 206, "script": 4}"#).unwrap(),
        )
        .unwrap();
        assert!(crate::jsonread::json_eq(&stats, &want),
                "聚合 stats 不一致\n  实得 {}\n  期望 {}", stats.dumps(), want.dumps());
    }
    // <<< GENERATED
    // >>> GENERATED by tools/gen_asset_contract_faces.py（勿手改；重跑生成器覆盖本段）
    /// ===== 三个「声明面整体判据」（D1 / ④ / ⑤）的对拍 + 变异自证 =====
    ///
    /// 真语料上三面都是空集，oracle 只能核到「都对」那一侧——判据有没有接线、文案有没有对齐，
    /// 空集看不出来。故用**同一份夹具**逐面变异：clean（全绿）→ registration_missing /
    /// export_drift / schema_missing（各红一条）→ restored（= clean，改回即回绿）。
    ///
    /// 期望值由 `tools/gen_asset_contract_faces.py` 跑**真源同名函数**现算；同一批文案同时写进
    /// 本段与 `desktop/tests/test_asset_contract_faces.py` ⇒ 两侧断言同一批 issue。
    struct AcFaceFixture {
        name: &'static str,
        files: &'static [(&'static str, &'static str)],
        registry: &'static [&'static str],
        export_drift: &'static [&'static str],
        schema_self: &'static [&'static str],
        scan_issues: &'static [&'static str],
        scan_stats: &'static str,
    }

    const AC_FACE_CASES: &[AcFaceFixture] = &[
        AcFaceFixture {
            name: r#"clean"#,
            files: &[
                (r#"protocol/asset_contracts.json"#, r#"{"chains": [], "code": [], "data": [{"format": "json", "id": "probe", "path": "protocol/probe.json"}], "index": [], "schema": "nf-asset-contracts/1", "script": []}
"#),
                (r#"protocol/data_contracts.json"#, r#"{"contracts": [{"artifact": "protocol/probe.json", "id": "probe"}], "schema": "nf-data-contracts/1"}
"#),
                (r#"protocol/generated/asset_contract.frictionless.json"#, r#"{
  "name": "ninfenz-asset-contracts",
  "profile": "data-package",
  "resources": [],
  "title": "NinFenz 数字资产契约（Frictionless Data Package 导出）",
  "x-nf-generated-by": "nf asset contract --export",
  "x-nf-note": "由已声明契约面确定性导出；领域包产物按同名 schema 约定带 fields 映射"
}
"#),
                (r#"protocol/probe.json"#, r#"{"a": 1}
"#),
                (r#"protocol/schema/asset_contracts.schema.json"#, r#"{"type": "object"}
"#),
            ],
            registry: &[],
            export_drift: &[],
            schema_self: &[],
            scan_issues: &[],
            scan_stats: r#"{"chains": 0, "code": 0, "data": 1, "files": 1, "index": 0, "no_schema": 0, "script": 0}"#,
        },
        AcFaceFixture {
            name: r#"registration_missing"#,
            files: &[
                (r#"protocol/asset_contracts.json"#, r#"{"chains": [], "code": [], "data": [{"format": "json", "id": "probe", "path": "protocol/probe.json"}], "index": [], "schema": "nf-asset-contracts/1", "script": []}
"#),
                (r#"protocol/data_contracts.json"#, r#"{"contracts": [], "schema": "nf-data-contracts/1"}
"#),
                (r#"protocol/generated/asset_contract.frictionless.json"#, r#"{
  "name": "ninfenz-asset-contracts",
  "profile": "data-package",
  "resources": [],
  "title": "NinFenz 数字资产契约（Frictionless Data Package 导出）",
  "x-nf-generated-by": "nf asset contract --export",
  "x-nf-note": "由已声明契约面确定性导出；领域包产物按同名 schema 约定带 fields 映射"
}
"#),
                (r#"protocol/probe.json"#, r#"{"a": 1}
"#),
                (r#"protocol/schema/asset_contracts.schema.json"#, r#"{"type": "object"}
"#),
            ],
            registry: &[r#"资产 protocol/probe.json 未在 protocol/data_contracts.json 登记（修复指引：补一条契约——同一 artifact 不许只在资产册出现）"#],
            export_drift: &[],
            schema_self: &[],
            scan_issues: &[r#"资产 protocol/probe.json 未在 protocol/data_contracts.json 登记（修复指引：补一条契约——同一 artifact 不许只在资产册出现）"#],
            scan_stats: r#"{"chains": 0, "code": 0, "data": 1, "files": 1, "index": 0, "no_schema": 0, "script": 0}"#,
        },
        AcFaceFixture {
            name: r#"export_drift"#,
            files: &[
                (r#"protocol/asset_contracts.json"#, r#"{"chains": [], "code": [], "data": [{"format": "json", "id": "probe", "path": "protocol/probe.json"}], "index": [], "schema": "nf-asset-contracts/1", "script": []}
"#),
                (r#"protocol/data_contracts.json"#, r#"{"contracts": [{"artifact": "protocol/probe.json", "id": "probe"}], "schema": "nf-data-contracts/1"}
"#),
                (r#"protocol/generated/asset_contract.frictionless.json"#, r#"{
  "name": "ninfenz-asset-contracts-drift",
  "profile": "data-package",
  "resources": [],
  "title": "NinFenz 数字资产契约（Frictionless Data Package 导出）",
  "x-nf-generated-by": "nf asset contract --export",
  "x-nf-note": "由已声明契约面确定性导出；领域包产物按同名 schema 约定带 fields 映射"
}
"#),
                (r#"protocol/probe.json"#, r#"{"a": 1}
"#),
                (r#"protocol/schema/asset_contracts.schema.json"#, r#"{"type": "object"}
"#),
            ],
            registry: &[],
            export_drift: &[r#"④ protocol/generated/asset_contract.frictionless.json 与实时导出不一致（修复指引：nf asset contract --export）"#],
            schema_self: &[],
            scan_issues: &[r#"④ protocol/generated/asset_contract.frictionless.json 与实时导出不一致（修复指引：nf asset contract --export）"#],
            scan_stats: r#"{"chains": 0, "code": 0, "data": 1, "files": 1, "index": 0, "no_schema": 0, "script": 0}"#,
        },
        AcFaceFixture {
            name: r#"schema_missing"#,
            files: &[
                (r#"protocol/asset_contracts.json"#, r#"{"chains": [], "code": [], "data": [{"format": "json", "id": "probe", "path": "protocol/probe.json"}], "index": [], "schema": "nf-asset-contracts/1", "script": []}
"#),
                (r#"protocol/data_contracts.json"#, r#"{"contracts": [{"artifact": "protocol/probe.json", "id": "probe"}], "schema": "nf-data-contracts/1"}
"#),
                (r#"protocol/generated/asset_contract.frictionless.json"#, r#"{
  "name": "ninfenz-asset-contracts",
  "profile": "data-package",
  "resources": [],
  "title": "NinFenz 数字资产契约（Frictionless Data Package 导出）",
  "x-nf-generated-by": "nf asset contract --export",
  "x-nf-note": "由已声明契约面确定性导出；领域包产物按同名 schema 约定带 fields 映射"
}
"#),
                (r#"protocol/probe.json"#, r#"{"a": 1}
"#),
            ],
            registry: &[],
            export_drift: &[],
            schema_self: &[r#"⑤ 缺可移植 schema protocol/schema/asset_contracts.schema.json（修复指引：补该件——对外可移植契约靠它定型）"#],
            scan_issues: &[r#"⑤ 缺可移植 schema protocol/schema/asset_contracts.schema.json（修复指引：补该件——对外可移植契约靠它定型）"#],
            scan_stats: r#"{"chains": 0, "code": 0, "data": 1, "files": 1, "index": 0, "no_schema": 0, "script": 0}"#,
        },
        AcFaceFixture {
            name: r#"schema_violation"#,
            files: &[
                (r#"protocol/asset_contracts.json"#, r#"{"chains": [], "code": [], "data": [{"format": "json", "id": "probe", "path": "protocol/probe.json"}], "index": [], "schema": "nf-asset-contracts/1", "script": []}
"#),
                (r#"protocol/data_contracts.json"#, r#"{"contracts": [{"artifact": "protocol/probe.json", "id": "probe"}], "schema": "nf-data-contracts/1"}
"#),
                (r#"protocol/generated/asset_contract.frictionless.json"#, r#"{
  "name": "ninfenz-asset-contracts",
  "profile": "data-package",
  "resources": [],
  "title": "NinFenz 数字资产契约（Frictionless Data Package 导出）",
  "x-nf-generated-by": "nf asset contract --export",
  "x-nf-note": "由已声明契约面确定性导出；领域包产物按同名 schema 约定带 fields 映射"
}
"#),
                (r#"protocol/probe.json"#, r#"{"a": 1}
"#),
                (r#"protocol/schema/asset_contracts.schema.json"#, r#"{"required": ["schema", "no_such_key"], "type": "object"}
"#),
            ],
            registry: &[],
            export_drift: &[],
            schema_self: &[r#"⑤ 声明不符可移植 schema protocol/schema/asset_contracts.schema.json：$: 缺必填字段 no_such_key（修复指引：改声明或改 schema——两者只能有一个对）"#],
            scan_issues: &[r#"⑤ 声明不符可移植 schema protocol/schema/asset_contracts.schema.json：$: 缺必填字段 no_such_key（修复指引：改声明或改 schema——两者只能有一个对）"#],
            scan_stats: r#"{"chains": 0, "code": 0, "data": 1, "files": 1, "index": 0, "no_schema": 0, "script": 0}"#,
        },
        AcFaceFixture {
            name: r#"restored"#,
            files: &[
                (r#"protocol/asset_contracts.json"#, r#"{"chains": [], "code": [], "data": [{"format": "json", "id": "probe", "path": "protocol/probe.json"}], "index": [], "schema": "nf-asset-contracts/1", "script": []}
"#),
                (r#"protocol/data_contracts.json"#, r#"{"contracts": [{"artifact": "protocol/probe.json", "id": "probe"}], "schema": "nf-data-contracts/1"}
"#),
                (r#"protocol/generated/asset_contract.frictionless.json"#, r#"{
  "name": "ninfenz-asset-contracts",
  "profile": "data-package",
  "resources": [],
  "title": "NinFenz 数字资产契约（Frictionless Data Package 导出）",
  "x-nf-generated-by": "nf asset contract --export",
  "x-nf-note": "由已声明契约面确定性导出；领域包产物按同名 schema 约定带 fields 映射"
}
"#),
                (r#"protocol/probe.json"#, r#"{"a": 1}
"#),
                (r#"protocol/schema/asset_contracts.schema.json"#, r#"{"type": "object"}
"#),
            ],
            registry: &[],
            export_drift: &[],
            schema_self: &[],
            scan_issues: &[],
            scan_stats: r#"{"chains": 0, "code": 0, "data": 1, "files": 1, "index": 0, "no_schema": 0, "script": 0}"#,
        },
    ];

    fn write_ac_face_fixture(root: &std::path::Path, files: &[(&str, &str)]) {
        for (rel, body) in files {
            let p = root.join(rel);
            if let Some(parent) = p.parent() {
                std::fs::create_dir_all(parent).expect("夹具父目录可建");
            }
            std::fs::write(&p, body).expect("夹具件可写");
        }
    }

    /// 三个声明面（D1 / ④ / ⑤）的 issues —— 与真源 `scan` 里的调用序一致。
    fn ac_face_issues(root: &std::path::Path) -> (Vec<String>, Vec<String>, Vec<String>) {
        let (doc, _load_issues) = load(root);
        (registry_issues(root, &doc), export_drift(root), schema_self_check(root))
    }

    #[test]
    fn asset_contract_integral_faces_mutation_parity() {
        for case in AC_FACE_CASES {
            let root = crate::testutil::fixture(&format!("asset-contract-faces-{}", case.name));
            write_ac_face_fixture(&root, case.files);
            let (reg, exp, sch) = ac_face_issues(&root);
            assert_eq!(reg, case.registry, "{} 的 D1 登记册 issues 不一致", case.name);
            assert_eq!(exp, case.export_drift, "{} 的 ④ 导出漂移 issues 不一致", case.name);
            assert_eq!(sch, case.schema_self, "{} 的 ⑤ 声明自检 issues 不一致", case.name);
            let (issues, _warns, stats) = scan(&root);
            assert_eq!(issues, case.scan_issues, "{} 的 scan issues 不一致", case.name);
            let want: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(case.scan_stats).unwrap(),
            )
            .unwrap();
            assert!(
                crate::jsonread::json_eq(&stats, &want),
                "{} 的 scan stats 不一致\n  实得 {}\n  期望 {}",
                case.name,
                stats.dumps(),
                want.dumps()
            );
        }
    }

    /// 真语料上三面必须**各自为空**（真源同语料实测见生成器输出）。
    ///
    /// 分开断言是为了**归因**：`asset_contract_scan_matches_truth_source` 只断言聚合 issues
    /// 为空，某面静默不接线时也能绿（这正是本次补齐前的既有缺口）。
    #[test]
    fn asset_contract_integral_faces_clean_on_real_corpus() {
        let root = ac_repo_root();
        let (doc, load_issues) = load(&root);
        assert!(load_issues.is_empty(), "真语料声明件须可读：{:?}", load_issues);
        assert_eq!(
            registry_issues(&root, &doc),
            Vec::<String>::new(),
            "真语料 D1 登记册面须空"
        );
        assert_eq!(export_drift(&root), Vec::<String>::new(), "真语料 ④ 导出漂移面须空");
        assert_eq!(
            schema_self_check(&root),
            Vec::<String>::new(),
            "真语料 ⑤ 声明自检面须空"
        );
    }
    // <<< GENERATED
}
