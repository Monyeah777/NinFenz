//! 数据面检查（JSON / JSONL / CSV / Markdown / TOML / YAML / Vega-Lite）。

use super::*;

pub(crate) fn obj_get<'a>(v: &'a Json, k: &str) -> Option<&'a Json> {
    match v {
        Json::Object(o) => o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv),
        _ => None,
    }
}

pub(crate) fn as_str(v: Option<&Json>) -> String {
    match v {
        None | Some(Json::Null) => String::new(),
        Some(x) => pyval::plain_str(x),
    }
}

/// 真源 `_read_json` 的**判据面**版本（用 `jsonmini`，与 `json.loads` 同接受面）。
pub fn read_json(root: &Path, rel: &str) -> (Json, String) {
    let p = rel_path(root, rel);
    match std::fs::read(&p) {
        Err(e) => (Json::Null, format!("不可读：{}", e)),
        Ok(b) => {
            let text = String::from_utf8_lossy(&b).into_owned();
            match crate::jsonmini::parse(&text) {
                Ok(parsed) => (parsed.value, String::new()),
                Err(e) => (Json::Null, format!("JSON 解析失败：{}", e)),
            }
        }
    }
}

/// 真源 `_check_json`（含**重复键**判据——`serde_json` 会静默覆盖，故走 `jsonmini`）。
pub fn check_json(root: &Path, rel: &str) -> Vec<String> {
    let p = rel_path(root, rel);
    let raw = std::fs::read(&p)
        .map(|b| String::from_utf8_lossy(&b).into_owned())
        .unwrap_or_default();
    match crate::jsonmini::parse(&raw) {
        Err(e) => vec![format!("JSON 不可解析：{}", e)],
        Ok(parsed) => {
            let mut uniq: Vec<String> = parsed.dups.clone();
            uniq.sort();
            uniq.dedup();
            uniq.into_iter()
                .map(|d| format!("JSON 重复键：{}", d))
                .collect()
        }
    }
}

/// 真源 `_check_jsonl`。
pub fn check_jsonl(root: &Path, rel: &str) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    let text = read_text(root, rel);
    for (i, line) in text.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        if let Err(e) = crate::jsonmini::parse(line) {
            issues.push(format!("第 {} 行非 JSON：{}", i + 1, e));
        }
    }
    issues
}

/// 真源 `_check_csv`。
pub fn check_csv(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    if text.contains('\u{0}') {
        return vec!["含 NUL 字节（非文本 CSV）".to_string()];
    }
    let rows: Vec<Vec<String>> = crate::asset_contract::csv_rows(&text)
        .into_iter()
        .filter(|r| !r.is_empty())
        .collect();
    if rows.is_empty() {
        return vec!["空表".to_string()];
    }
    let width = rows[0].len();
    let mut issues: Vec<String> = if width == 0 {
        vec!["表头为空".to_string()]
    } else {
        Vec::new()
    };
    for (i, r) in rows.iter().enumerate().skip(1) {
        if r.len() != width {
            issues.push(format!(
                "第 {} 行字段数 {} ≠ 表头 {}",
                i + 1,
                r.len(),
                width
            ));
        }
    }
    let mut hdr = rows[0].clone();
    hdr.sort();
    hdr.dedup();
    if hdr.len() != width {
        issues.push("表头有重名列".to_string());
    }
    issues
}

/// 真源 `_check_markdown`。
pub fn check_markdown(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    let mut issues: Vec<String> = Vec::new();
    if text.trim().is_empty() {
        issues.push("空档".to_string());
    }
    if text.matches("```").count() % 2 == 1 {
        issues.push("代码围栏未闭合（``` 奇数个）".to_string());
    }
    issues
}

/// 真源 `_check_toml`（用 `toml` crate，对 `tomllib`）。
pub fn check_toml(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    match toml::from_str::<toml::Value>(&text) {
        Ok(_) => Vec::new(),
        Err(e) => vec![format!("TOML 不可解析：{}", e)],
    }
}

/// 真源 `_check_yaml`（**收窄子集**良构判定：Tab 缩进 + 非映射项）。
pub fn check_yaml(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    let mut issues: Vec<String> = Vec::new();
    for (i, line) in text.lines().enumerate() {
        let indent_len = line.len() - line.trim_start().len();
        if line[..indent_len].contains('\t') {
            issues.push(format!("第 {} 行用 Tab 缩进（YAML 禁 Tab）", i + 1));
        }
        let stripped = line.trim();
        if stripped.starts_with("- ") || stripped.is_empty() || stripped.starts_with('#') {
            continue;
        }
        if !line.contains(':') {
            let head: String = stripped.chars().take(40).collect();
            issues.push(format!(
                "第 {} 行非映射项（收窄子集要求 key: value）：{}",
                i + 1,
                head
            ));
        }
    }
    issues
}

/// 真源 `_check_vega_lite`。
pub fn check_vega_lite(root: &Path, rel: &str) -> Vec<String> {
    let (data, err) = read_json(root, rel);
    if !err.is_empty() {
        return vec![err];
    }
    let mut issues: Vec<String> = Vec::new();
    if !as_str(obj_get(&data, "$schema")).contains("vega-lite") {
        issues.push("缺 $schema（应为 vega-lite v5）".to_string());
    }
    let body_keys = [
        "mark", "layer", "hconcat", "vconcat", "concat", "facet", "spec", "repeat",
    ];
    if !body_keys.iter().any(|k| obj_get(&data, k).is_some()) {
        issues.push("缺 mark/layer 等绘图主体".to_string());
    }
    if obj_get(&data, "data").is_none() {
        issues.push("缺 data（图不能没有数据源）".to_string());
    }
    match obj_get(&data, "encoding") {
        Some(Json::Object(enc)) => {
            for (ch, spec) in enc {
                if !matches!(spec, Json::Object(_)) {
                    issues.push(format!("encoding.{} 非对象", ch));
                    continue;
                }
                let ch_keys = ["field", "aggregate", "value", "datum", "timeUnit", "bin"];
                if !ch_keys.iter().any(|k| obj_get(spec, k).is_some()) {
                    issues.push(format!(
                        "encoding.{} 无 field/aggregate/value（通道未绑定）",
                        ch
                    ));
                }
            }
        }
        Some(Json::Null) | None => {}
        _ => issues.push("encoding 非对象".to_string()),
    }
    issues
}
