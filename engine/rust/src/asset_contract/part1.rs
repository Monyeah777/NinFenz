//! 基础工具：Json 取值快捷函数 / 严格 JSON / 摘要 / 读件 / resolve / CSV 解析 / 路径工具。

use super::*;

// ---------------------------------------------------------------- 基础

pub(crate) fn obj_get<'a>(v: &'a Json, k: &str) -> Option<&'a Json> {
    match v {
        Json::Object(o) => o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv),
        _ => None,
    }
}

/// 真源 `spec.get(k)`：缺键 → `Null`（Python 的 `None`）。
pub(crate) fn sg(spec: &Json, k: &str) -> Json {
    obj_get(spec, k).cloned().unwrap_or(Json::Null)
}

/// 真源 `str(spec.get(k) or "")` 的常用形态。
pub(crate) fn sg_str(spec: &Json, k: &str) -> String {
    match obj_get(spec, k) {
        None | Some(Json::Null) => String::new(),
        Some(v) => pyval::plain_str(v),
    }
}

/// 真源 `spec.get(k) or []` → 字符串列表。
pub(crate) fn sg_strs(spec: &Json, k: &str) -> Vec<String> {
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
            Some(format!(
                "读不到 {}：{}（修复指引：核对声明里的路径在场）",
                rel, e
            )),
        ),
        Ok(b) => match String::from_utf8(b) {
            Ok(s) => (Some(s), None),
            Err(e) => (
                None,
                Some(format!(
                    "{} 不是 UTF-8：{}（修复指引：转成 UTF-8 再入库）",
                    rel, e
                )),
            ),
        },
    }
}

/// 真源 `resolve`：`path` 单件 / `glob` 多件（稳定排序）。
pub fn resolve(root: &Path, spec: &Json) -> Vec<String> {
    if let Some(p) = obj_get(spec, "path") {
        if pyval::py_truthy(p) {
            let rel = pyval::plain_str(p).replace('\\', "/");
            return if root.join(&rel).is_file() {
                vec![rel]
            } else {
                vec![]
            };
        }
    }
    let pat = sg_str(spec, "glob");
    if pat.is_empty() {
        return Vec::new();
    }
    let mut v = crate::glob::expand(root, &pat);
    // 真源 `resolve` 的收窄：`.gitignore` 覆盖面 + 工具缓存目录不算契约面（构建产物不得漂 files）。
    if let Some(vis) = crate::repo_paths::visible(root) {
        v.retain(|rel| vis.contains(rel));
    }
    v.sort();
    v
}

/// 真源 `_dig`：按点号路径取值；取不到 → `None`（哨兵）。
pub fn dig_ref<'a>(obj: &'a Json, path: &str) -> Option<&'a Json> {
    let mut cur = obj;
    for part in path.split('.') {
        match cur {
            Json::Object(o) => match o.iter().find(|(k, _)| k == part) {
                Some((_, v)) => cur = v,
                None => return None,
            },
            Json::Array(a) => {
                let idx: Option<usize> = part.parse().ok();
                match idx {
                    Some(i) if i < a.len() => cur = &a[i],
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
pub(crate) fn path_stem(rel: &str) -> String {
    let base = rel.rsplit('/').next().unwrap_or(rel);
    match base.rsplit_once('.') {
        Some((s, _)) => s.to_string(),
        None => base.to_string(),
    }
}

/// `Path(rel).parent`：去掉末段（`.` → 空串，与 `Path("x").parent == "."` 的拼接效果等价）。
pub(crate) fn path_parent(rel: &str) -> String {
    rel.rsplit_once('/')
        .map(|(d, _)| d.to_string())
        .unwrap_or_default()
}

/// 真源 `_schema_of`：显式 `schema` 优先，其次 `schema_siblings` 里**第一个在场**的兄弟候选。
pub(crate) fn schema_of(root: &Path, rel: &str, spec: &Json) -> String {
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
pub(crate) fn schema_issues(root: &Path, rel: &str, obj: &Json, sch_rel: &str) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    let (sch_text, err) = sread(root, sch_rel);
    if let Some(e) = err {
        issues.push(format!("数据件 {} 的 schema 读不到：{}", rel, e));
        return issues;
    }
    // 真源把「读不到」与「schema 非法 JSON」归到同一句报错；Rust 侧此前把它包成
    // 「不符 schema …：schema 本身不是合法 JSON」，与真源文案不一致（A1 对账抓到）。
    let s = match strict_json(&sch_text.unwrap_or_default()) {
        Ok(s) => s,
        Err(e) => {
            issues.push(format!(
                "数据件 {} 的 schema 读不到：{} 不是合法 JSON：{}",
                rel, sch_rel, e
            ));
            return issues;
        }
    };
    for e in json_schema::json_schema_check(obj, &s).iter().take(5) {
        issues.push(format!("数据件 {} 不符 schema {}：{}", rel, sch_rel, e));
    }
    issues
}

/// 真源 `_fields_issues`。
pub(crate) fn fields_issues(rel: &str, obj: &Json, spec: &Json) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    if let Some(Json::Array(req)) = obj_get(spec, "required_fields") {
        for field in req {
            let f = pyval::plain_str(field);
            if dig_ref(obj, &f).is_none() {
                issues.push(format!(
                    "数据件 {} 缺必填字段 {}（修复指引：补字段或从声明里删掉——声明即契约）",
                    rel, f
                ));
            }
        }
    }
    issues
}

pub(crate) fn required_fields_len(spec: &Json) -> i64 {
    match obj_get(spec, "required_fields") {
        Some(Json::Array(a)) => a.len() as i64,
        _ => 0,
    }
}
