//! 数据化断言表（assertions）判据。
//!
//! 自 `contracts.rs` 按族拆出：判据实现逐字搬运，逻辑与文案未改；由父模块 glob 引入分派面。

use crate::jsonread;
use crate::pyjson::Json;
use crate::pyval::{arr_items, get, obj_is_empty, plain_str, plain_str_opt, py_eq, py_int_or, py_str, py_truthy, str_list};
use std::path::Path;

// ---------------------------------------------------------------- assertions

pub(super) const ASSERTIONS_REL: &str = "protocol/assertions.json";
pub(super) const ASSERTIONS_SCHEMA: &str = "nf-assertions/1";
pub(super) const SEVERITIES: [&str; 2] = ["fail", "warn"];
pub(super) const REQUIRED: [&str; 6] = ["id", "severity", "kind", "params", "message", "fix"];
/// `kind` 封闭集。真源是 **dict 字面量**（Python 3.7+ 保序，非 set）——
/// 故 `tuple(KINDS)` 的顺序是确定的，可与 `kind_vocabulary` 逐项比序（已实测六种 hash 种子下同序）。
pub(super) const KINDS: [&str; 4] = [
    "regex_absent",
    "regex_present",
    "count_at_least",
    "json_value",
];

/// 真源 `_c_assertions`：跑一遍断言表，fail 级不通过即 FAIL。
pub(super) fn assertions(root: &Path) -> (bool, String) {
    let run = assertions_run(root);
    let ok = run.issues.is_empty();
    let detail = if ok {
        format!(
            "断言 {} 条（通过 {}）· kind 封闭集 {} 种",
            run.results,
            run.passed,
            KINDS.len()
        )
    } else {
        run.issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}

pub(super) struct AssertionsRun {
    results: usize,
    passed: usize,
    issues: Vec<String>,
}

/// 真源 `assertions.run`。
pub(super) fn assertions_run(root: &Path) -> AssertionsRun {
    let (decl_issues, _count) = assertions_scan(root);
    let mut issues = decl_issues;
    let mut results = 0usize;
    let mut passed = 0usize;

    let Some(doc) = jsonread::read_file(root, ASSERTIONS_REL) else {
        return AssertionsRun {
            results,
            passed,
            issues,
        };
    };
    for a in arr_items(get(&doc, "assertions")) {
        let kind = plain_str_opt(get(a, "kind"));
        let params = get(a, "params")
            .cloned()
            .unwrap_or(Json::Object(Vec::new()));
        let outcome = match kind.as_str() {
            "regex_absent" => k_regex_absent(root, &params),
            "regex_present" => k_regex_present(root, &params),
            "count_at_least" => k_count_at_least(root, &params),
            "json_value" => k_json_value(root, &params),
            _ => {
                issues.push(format!(
                    "断言 {} 的 kind 不在封闭集：{}",
                    plain_str_opt(get(a, "id")),
                    kind
                ));
                continue;
            }
        };
        let (ok, detail) = outcome;
        results += 1;
        if ok {
            passed += 1;
        }
        if !ok && plain_str_opt(get(a, "severity")) == "fail" {
            issues.push(format!(
                "{} 不通过：{}（修复指引：{}）",
                plain_str_opt(get(a, "id")),
                detail,
                plain_str_opt(get(a, "fix"))
            ));
        }
    }
    AssertionsRun {
        results,
        passed,
        issues,
    }
}

/// 真源 `assertions.scan`（断言表自身的合法性）。
pub(super) fn assertions_scan(root: &Path) -> (Vec<String>, usize) {
    let mut issues: Vec<String> = Vec::new();
    if !root.join(ASSERTIONS_REL).is_file() {
        return (vec![format!("缺断言表 {}", ASSERTIONS_REL)], 0);
    }
    let Some(doc) = jsonread::read_file(root, ASSERTIONS_REL) else {
        return (vec![format!("缺断言表 {}", ASSERTIONS_REL)], 0);
    };
    if obj_is_empty(&doc) {
        return (vec![format!("缺断言表 {}", ASSERTIONS_REL)], 0);
    }
    if py_str(get(&doc, "schema")) != ASSERTIONS_SCHEMA {
        issues.push(format!(
            "断言表 schema 不匹配（期望 {}）",
            ASSERTIONS_SCHEMA
        ));
    }
    if str_list(get(&doc, "severity_vocabulary")) != SEVERITIES {
        issues.push(format!(
            "severity 词表与判据不一致（期望 {}）",
            SEVERITIES.join("/")
        ));
    }
    if str_list(get(&doc, "kind_vocabulary")) != KINDS {
        issues.push(format!(
            "kind 词表必须与 runner 封闭集逐项一致（{}）",
            KINDS.join("/")
        ));
    }
    let items = arr_items(get(&doc, "assertions"));
    let mut seen: Vec<String> = Vec::new();
    for a in &items {
        assertion_item_issues(a, &mut seen, &mut issues);
    }
    (issues, items.len())
}

/// 单条断言：必填字段 / id 唯一 / severity / kind / fix。
fn assertion_item_issues(a: &Json, seen: &mut Vec<String>, issues: &mut Vec<String>) {
    let aid = py_str(get(a, "id"));
    for k in REQUIRED {
        let v = get(a, k);
        // 真源 if not a.get(k) and a.get(k) != {} —— 空对象不算缺
        let falsy = !v.map(py_truthy).unwrap_or(false);
        let empty_obj = matches!(v, Some(Json::Object(p)) if p.is_empty());
        if falsy && !empty_obj {
            let tag = if aid.is_empty() {
                "(无名)"
            } else {
                aid.as_str()
            };
            issues.push(format!("断言 {} 缺必填字段：{}", tag, k));
        }
    }
    if seen.contains(&aid) {
        issues.push(format!("断言 id 重复：{}", aid));
    }
    seen.push(aid.clone());
    let sev = plain_str_opt(get(a, "severity"));
    if !SEVERITIES.contains(&sev.as_str()) {
        issues.push(format!("断言 {} severity 越词表：{}", aid, sev));
    }
    let kind = plain_str_opt(get(a, "kind"));
    if !KINDS.contains(&kind.as_str()) {
        issues.push(format!("断言 {} kind 不在封闭集：{}", aid, kind));
    }
    if py_str(get(a, "fix")).trim().is_empty() {
        issues.push(format!("断言 {} 缺 fix（无修复指引不许入表）", aid));
    }
}

/// 真源 `assertions._glob`：结果形如 `str(Path(root)/p)`（含 root 前缀、平台分隔符）。
pub(super) fn a_glob(root: &Path, pattern: &str) -> Vec<String> {
    if crate::glob::has_wildcard(pattern) {
        crate::glob::expand(root, pattern)
            .iter()
            .map(|rel| crate::glob::py_path_str(root, rel))
            .collect()
    } else if root.join(pattern).is_file() {
        vec![crate::glob::py_path_str(root, pattern)]
    } else {
        Vec::new()
    }
}

/// `regex_absent`：数据驱动模式——用 fancy-regex（支持后顾）。编译失败按真源「异常」口径。
pub(super) fn k_regex_absent(root: &Path, params: &Json) -> (bool, String) {
    let pat = py_str(get(params, "pattern"));
    let Ok(re) = fancy_regex::Regex::new(&pat) else {
        // 真源此处由 run() 的 except 兜住；**错误措辞不做逐字节承诺**
        return (false, "断言执行异常：模式不可编译".to_string());
    };
    let mut hits: Vec<String> = Vec::new();
    for g in arr_items(get(params, "globs")) {
        for f in a_glob(root, &plain_str(g)) {
            let text = std::fs::read_to_string(&f).unwrap_or_default();
            if re.is_match(&text).unwrap_or(false) {
                hits.push(f);
            }
        }
    }
    if hits.is_empty() {
        (true, "零命中".to_string())
    } else {
        let head: Vec<&str> = hits.iter().take(2).map(|s| s.as_str()).collect();
        (false, format!("命中：{}", head.join(", ")))
    }
}

/// `regex_present`：目标件必须含全部锚点（纯子串判定，不涉及正则）。
pub(super) fn k_regex_present(root: &Path, params: &Json) -> (bool, String) {
    let rel = plain_str_opt(get(params, "path"));
    if !root.join(&rel).is_file() {
        return (false, format!("目标件不存在：{}", rel));
    }
    let text = std::fs::read_to_string(root.join(&rel)).unwrap_or_default();
    let patterns = arr_items(get(params, "patterns"));
    let miss: Vec<String> = patterns
        .iter()
        .map(|p| plain_str(p))
        .filter(|p| !text.contains(p))
        .collect();
    if miss.is_empty() {
        (true, format!("{} 锚点齐", patterns.len()))
    } else {
        let head: Vec<&str> = miss.iter().take(3).map(|s| s.as_str()).collect();
        (false, format!("缺：{}", head.join(", ")))
    }
}

/// `count_at_least`：glob 命中数 ≥ min。
pub(super) fn k_count_at_least(root: &Path, params: &Json) -> (bool, String) {
    let n = a_glob(root, &plain_str_opt(get(params, "glob"))).len();
    let want = py_int_or(get(params, "min"), 0);
    (n as i64 >= want, format!("{} ≥ {}", n, want))
}

/// `json_value`：按键路径取值后做封闭集算子判定。
pub(super) fn k_json_value(root: &Path, params: &Json) -> (bool, String) {
    let rel = plain_str_opt(get(params, "path"));
    if !root.join(&rel).is_file() {
        return (false, format!("目标件不存在：{}", rel));
    }
    let text = std::fs::read_to_string(root.join(&rel)).unwrap_or_default();
    let Ok(raw) = serde_json::from_str::<serde_json::Value>(&text) else {
        // 真源把 json.JSONDecodeError 的文本拼进消息——**该措辞不做逐字节承诺**
        return (false, "JSON 不可解析：<解析失败>".to_string());
    };
    let Ok(mut cur) = jsonread::convert(&raw) else {
        return (false, "JSON 不可解析：<含不支持的值>".to_string());
    };
    let key = py_str(get(params, "key"));
    for part in key.split('.') {
        let Json::Object(pairs) = &cur else {
            return (
                false,
                format!("缺键：{}", plain_str_opt(get(params, "key"))),
            );
        };
        match pairs.iter().find(|(k, _)| k == part) {
            Some((_, v)) => cur = v.clone(),
            None => {
                return (
                    false,
                    format!("缺键：{}", plain_str_opt(get(params, "key"))),
                )
            }
        }
    }
    let op = py_str(get(params, "op"));
    let val = get(params, "value").cloned();
    match op.as_str() {
        "exists" => (true, "键在场".to_string()),
        "nonempty" => {
            let ok = py_truthy(&cur);
            (ok, if ok { "非空" } else { "空值" }.to_string())
        }
        "equals" => {
            let v = val.unwrap_or(Json::Null);
            (py_eq(&cur, &v), format!("= {}", plain_str(&v)))
        }
        "in_vocab" => {
            let ok = arr_items(val.as_ref()).iter().any(|v| py_eq(&cur, v));
            (
                ok,
                if ok {
                    format!("{} ∈ 词表", plain_str(&cur))
                } else {
                    format!("{} 越词表", plain_str(&cur))
                },
            )
        }
        "contains_keys" => {
            let want: Vec<String> = arr_items(val.as_ref())
                .iter()
                .map(|v| plain_str(v))
                .collect();
            let miss: Vec<String> = want
                .iter()
                .filter(|k| match &cur {
                    Json::Object(pairs) => !pairs.iter().any(|(n, _)| n == *k),
                    Json::Array(items) => !items.iter().any(|v| plain_str(v) == **k),
                    _ => true,
                })
                .cloned()
                .collect();
            if miss.is_empty() {
                (true, "键齐".to_string())
            } else {
                (false, format!("缺：{}", miss.join(", ")))
            }
        }
        _ => (
            false,
            format!(
                "未知 op：{}（封闭集：exists/nonempty/equals/in_vocab/contains_keys）",
                op
            ),
        ),
    }
}

// ---------------------------------------------------------------- assertions
//
// 已抽到 `crate::pyval`（`contracts` 与 `layers` 共用唯一实现，避免两处 Python 语义漂移）。
