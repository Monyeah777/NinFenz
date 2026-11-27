use super::*;

pub(crate) const MAX_DEPTH: usize = 64;

pub(crate) const MAX_PATTERN_CHARS: usize = 512;

/// 真源 `_SUPPORTED`：**不**进 `unsupported` 的关键字。
pub(crate) const SUPPORTED: [&str; 34] = [
    "$schema",
    "$id",
    "$ref",
    "$defs",
    "definitions",
    "title",
    "description",
    "type",
    "enum",
    "const",
    "properties",
    "patternProperties",
    "required",
    "additionalProperties",
    "items",
    "prefixItems",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "allOf",
    "anyOf",
    "oneOf",
    "not",
    "propertyNames",
    "dependentRequired",
];

/// 真源 `_UNSUPPORTED_WORDS`：**进** `unsupported` 的官方关键字。
pub(crate) const UNSUPPORTED_WORDS: [&str; 13] = [
    "if",
    "then",
    "else",
    "contains",
    "minContains",
    "maxContains",
    "unevaluatedProperties",
    "unevaluatedItems",
    "dependentSchemas",
    "$dynamicRef",
    "$dynamicAnchor",
    "contentEncoding",
    "contentMediaType",
];

/// 真源 `type(instance).__name__` 的对应物。
pub(crate) fn py_type_name(v: &Json) -> &'static str {
    match v {
        Json::Null => "NoneType",
        Json::Bool(_) => "bool",
        Json::Int(_) => "int",
        Json::Float(_) => "float",
        Json::Str(_) => "str",
        Json::Array(_) => "list",
        Json::Object(_) => "dict",
    }
}

/// 真源 `_type_ok`。
pub(crate) fn type_ok(value: &Json, want: &str) -> bool {
    match want {
        // `bool` 不算 number/integer（真源显式排除）
        "number" | "integer" => match value {
            Json::Bool(_) | Json::Null | Json::Str(_) | Json::Array(_) | Json::Object(_) => false,
            Json::Int(_) | Json::Float(_) => want == "number" || matches!(value, Json::Int(_)),
        },
        "object" => matches!(value, Json::Object(_)),
        "array" => matches!(value, Json::Array(_)),
        "string" => matches!(value, Json::Str(_)),
        "boolean" => matches!(value, Json::Bool(_)),
        "null" => matches!(value, Json::Null),
        _ => true, // 未知类型名 → 真源 `py is None` → True
    }
}

pub(crate) fn obj_get<'a>(v: &'a Json, k: &str) -> Option<&'a Json> {
    match v {
        Json::Object(o) => o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv),
        _ => None,
    }
}

pub(crate) fn obj_has(v: &Json, k: &str) -> bool {
    obj_get(v, k).is_some()
}

/// 迭代 JSON 对象的键（插入序）。
pub(crate) fn obj_keys(v: &Json) -> Vec<String> {
    match v {
        Json::Object(o) => o.iter().map(|(k, _)| k.clone()).collect(),
        _ => Vec::new(),
    }
}

/// 真源 `_resolve_ref`：只支持本地引用；远程/悬空 → `None`。
pub(crate) fn resolve_ref(reference: &str, root_schema: &Json) -> Option<Json> {
    if !reference.starts_with("#/") {
        return None;
    }
    let mut node: Json = root_schema.clone();
    for part in reference[2..].split('/') {
        let part = part.replace("~1", "/").replace("~0", "~");
        match obj_get(&node, &part) {
            Some(v) => node = v.clone(),
            None => return None,
        }
    }
    match node {
        Json::Object(_) => Some(node),
        _ => None,
    }
}

/// 真源 `pattern_issue` → 该 pattern 的形态问题（空串 = 可用）。
pub(crate) fn pattern_issue(pat: &Json, path: &str) -> String {
    let text = pyval::plain_str(pat);
    if text.chars().count() > MAX_PATTERN_CHARS {
        return format!(
            "{}: pattern 过长（{} > {} 字符）（修复指引：只写必要的约束）",
            path,
            text.chars().count(),
            MAX_PATTERN_CHARS
        );
    }
    // 嵌套量词（ReDoS 形态）：`(x+)+` / `(x*)*` 一族
    match nested_quant_re() {
        Ok(re) if re.is_match(&text).unwrap_or(false) => {
            format!(
                "{}: pattern 含嵌套量词 {}（可能指数回溯）（修复指引：改写表达式，避免 `(x+)+` / `(x*)*` 这类形态）",
                path,
                pyval::py_repr(&Json::Str(text))
            )
        }
        _ => String::new(),
    }
}

// 嵌套量词模式。模式串含裸花括号，提为常量以免被朴素括号计数误判。
pub(crate) const NESTED_QUANT_PAT: &str = r"\([^()]*[+*][^()]*\)\s*[+*{]";

pub(crate) fn nested_quant_re() -> Result<fancy_regex::Regex, fancy_regex::Error> {
    static RE: std::sync::OnceLock<Result<fancy_regex::Regex, fancy_regex::Error>> =
        std::sync::OnceLock::new();
    RE.get_or_init(|| fancy_regex::Regex::new(NESTED_QUANT_PAT))
        .clone()
}

/// 用真源同款引擎搜（pattern 来自投稿者，Rust `regex` 不支持回溯构造）。
pub(crate) fn re_search(pat: &str, s: &str) -> bool {
    fancy_regex::Regex::new(pat)
        .map(|r| r.is_match(s).unwrap_or(false))
        .unwrap_or(false)
}

pub(crate) fn re_fullmatch(pat: &str, s: &str) -> bool {
    fancy_regex::Regex::new(&format!("^(?:{})$", pat))
        .map(|r| r.is_match(s).unwrap_or(false))
        .unwrap_or(false)
}

/// 真源 `_format_errors`。
pub(crate) fn format_errors(value: &str, fmt: &str, path: &str) -> Vec<String> {
    match fmt {
        "date" => {
            if re_fullmatch(r"\d{4}-\d{2}-\d{2}", value) {
                Vec::new()
            } else {
                vec![format!("{}: 非 ISO 8601 日期", path)]
            }
        }
        "date-time" => {
            if re_fullmatch(r"\d{4}-\d{2}-\d{2}[Tt ].+", value) {
                Vec::new()
            } else {
                vec![format!("{}: 非 ISO 8601 日期时间", path)]
            }
        }
        "uri" => {
            if re_search(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) {
                Vec::new()
            } else {
                vec![format!("{}: 非绝对 URI", path)]
            }
        }
        _ => Vec::new(),
    }
}

/// 真源 `_check`。
#[allow(clippy::too_many_arguments)]
pub(crate) fn check(
    instance: &Json,
    schema: &Json,
    path: &str,
    root_schema: Option<&Json>,
    unsupported: &mut Vec<String>,
    depth: usize,
) -> Vec<String> {
    if depth > MAX_DEPTH {
        return vec![format!(
            "{}: 嵌套超过上限 {} 层（修复指引：schema/实例别做这么深的结构；本仓判据面只处理扁平声明）",
            path, MAX_DEPTH
        )];
    }
    let Json::Object(_) = schema else {
        return vec![format!("{}: schema 节点非对象", path)];
    };
    let root_owned;
    let root: &Json = match root_schema {
        Some(r) => r,
        None => {
            root_owned = schema.clone();
            &root_owned
        }
    };
    let mut errors: Vec<String> = Vec::new();

    check_unsupported(schema, path, unsupported);

    errors.extend(check_ref(instance, schema, path, root, unsupported, depth));

    if let Some(types) = obj_get(schema, "type") {
        if !matches!(types, Json::Null) {
            let cand: Vec<Json> = match types {
                Json::Array(a) => a.clone(),
                other => vec![other.clone()],
            };
            if !cand.iter().any(|t| type_ok(instance, &pyval::plain_str(t))) {
                let names: Vec<String> = cand.iter().map(|x| pyval::py_str(Some(x))).collect();
                errors.push(format!(
                    "{}: 类型应为 {}，实为 {}",
                    path,
                    names.join("/"),
                    py_type_name(instance)
                ));
            }
        }
    }
    if let Some(c) = obj_get(schema, "const") {
        if !pyval::py_eq(instance, c) {
            errors.push(format!("{}: 应为常量 {}", path, pyval::py_repr(c)));
        }
    }
    if let Some(Json::Array(en)) = obj_get(schema, "enum") {
        if !en.iter().any(|e| pyval::py_eq(instance, e)) {
            errors.push(format!(
                "{}: 取值 {} 不在枚举内",
                path,
                pyval::py_repr(instance)
            ));
        }
    }

    errors.extend(check_string(instance, schema, path));

    errors.extend(check_number(instance, schema, path));

    errors.extend(check_array(instance, schema, path, root, unsupported, depth));

    if let Json::Object(_) = instance {
        errors.extend(check_object_required(instance, schema, path));
        errors.extend(check_object_props(instance, schema, path, root, unsupported, depth));
    }

    errors.extend(check_compound(instance, schema, path, root, unsupported, depth));

    errors.extend(check_not(instance, schema, path, root, unsupported, depth));
    errors
}

/// 不支持的官方关键字（排序后遍历，去重）。
pub(crate) fn check_unsupported(schema: &Json, path: &str, unsupported: &mut Vec<String>) {
    // 不支持的官方关键字（排序后遍历，去重）
    let mut keys: Vec<String> = obj_keys(schema);
    keys.sort();
    keys.dedup();
    for kw in keys {
        if SUPPORTED.contains(&kw.as_str()) {
            continue;
        }
        if UNSUPPORTED_WORDS.contains(&kw.as_str()) || kw.starts_with('$') {
            let tag = format!("{}@{}", kw, path);
            if !unsupported.contains(&tag) {
                unsupported.push(tag);
            }
        }
    }
}
