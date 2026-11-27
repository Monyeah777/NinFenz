use super::*;

pub(crate) const SCHEMA_DIR: &str = "protocol/schema";

pub(crate) const DIALECT: &str = "https://json-schema.org/draft/2020-12/schema";

pub(crate) const PLACEHOLDER: &str = "\u{0}NFDOC\u{0}";

/// 校验器已实现的关键字白名单（子集边界显式化）。
pub(crate) const SUBSET_ALLOWED_KEYS: [&str; 16] = [
    "$schema",
    "$id",
    "title",
    "description",
    "type",
    "required",
    "properties",
    "propertyNames",
    "additionalProperties",
    "items",
    "enum",
    "pattern",
    "minLength",
    "minimum",
    "minItems",
    "maxItems",
];

/// 真源 `type(instance).__name__` —— 进错误消息，必须逐字一致。
pub(crate) fn py_type_name(j: &Json) -> &'static str {
    match j {
        Json::Object(_) => "dict",
        Json::Array(_) => "list",
        Json::Str(_) => "str",
        Json::Int(_) => "int",
        Json::Float(_) => "float",
        Json::Bool(_) => "bool",
        Json::Null => "NoneType",
    }
}

/// 真源 `subset_key_violations`：递归扫描未实现的关键字。
pub(crate) fn subset_key_violations(schema: &Json, path: &str) -> Vec<String> {
    let Json::Object(pairs) = schema else {
        return Vec::new();
    };
    let mut out: Vec<String> = pairs
        .iter()
        .filter(|(k, _)| !SUBSET_ALLOWED_KEYS.contains(&k.as_str()))
        .map(|(k, _)| {
            format!(
                "{}: 使用了校验器未实现的关键字 {}（JSON-schema 子集越界——check28 无法兑现该语义；须扩展校验器或删除该关键字）",
                path, k
            )
        })
        .collect();
    if let Some(Json::Object(props)) = get(schema, "properties") {
        for (pname, sub) in props {
            out.extend(subset_key_violations(
                sub,
                &format!("{}/properties/{}", path, pname),
            ));
        }
    }
    if let Some(items) = get(schema, "items") {
        if matches!(items, Json::Object(_)) {
            out.extend(subset_key_violations(items, &format!("{}/items", path)));
        }
    }
    if let Some(Json::Object(extra)) = get(schema, "additionalProperties") {
        let extra = Json::Object(extra.clone());
        out.extend(subset_key_violations(
            &extra,
            &format!("{}/additionalProperties", path),
        ));
    }
    if let Some(pn) = get(schema, "propertyNames") {
        if matches!(pn, Json::Object(_)) {
            out.extend(subset_key_violations(
                pn,
                &format!("{}/propertyNames", path),
            ));
        }
    }
    out
}

/// 已编译正则的缓存 —— **性能关键**。
///
/// 实测教训：`pattern` 分支起初每次校验都 `Regex::new(pat)`，而 Python 的 `re` 自带编译缓存
/// （512 条）⇒ 同一批 schema 在 248 份件上反复校验时，Rust 侧把编译成本乘了几千倍，
/// 整条 `schema-lint` 慢到 Python 的 **3 倍**（606 ms vs 200 ms）。修好后才回到应有水平。
pub(crate) fn cached_regex(pat: &str) -> Option<regex::Regex> {
    thread_local! {
        static CACHE: std::cell::RefCell<std::collections::HashMap<String, Option<regex::Regex>>> =
            std::cell::RefCell::new(std::collections::HashMap::new());
    }
    CACHE.with(|c| {
        let mut m = c.borrow_mut();
        m.entry(pat.to_string())
            .or_insert_with(|| regex::Regex::new(pat).ok())
            .clone()
    })
}

/// 真源 `json_schema.json_equal`：JSON 值相等（**严格**，布尔与数字不互相冒充）。
///
/// 唯一实现在 [`crate::pyval::json_equal`]（`json_schema` 的 const/enum 与这里的 enum 共用）；
/// 2026-10-10 全仓审计 Y4（P1）：Python 的 == 把 False == 0 / True == 1 当同一件，故不能直接用。
pub(crate) use crate::pyval::json_equal;

/// 真源 `subset_validate`：JSON-schema 子集校验（空 = 通过）。
pub(crate) fn subset_validate(instance: &Json, schema: &Json, path: &str) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    if matches!(schema, Json::Null) {
        return out;
    }
    let Json::Object(_) = schema else {
        return vec![format!("{}: schema 段非对象", path)];
    };
    // enum 是**类型无关**的约束：先判一次，后面各类型分支的 return 都会带上它
    // （2026-10-10 审计 Y4：真源此前只在 string 分支里判 ⇒ boolean/number 的 enum 静默放行）。
    enum_issue(instance, schema, path, &mut out);
    let stype = get(schema, "type");
    match stype {
        None => return out,
        Some(Json::Null) => return out,
        _ => {}
    }
    let name = plain_str(stype.unwrap());
    match name.as_str() {
        "object" => validate_object(instance, schema, path, out),
        "array" => validate_array(instance, schema, path, out),
        "string" => validate_string(instance, schema, path, out),
        "integer" => validate_integer(instance, schema, path, out),
        "number" => validate_number(instance, schema, path, out),
        "boolean" => validate_boolean(instance, path, out),
        _ => vec![format!(
            "{}: 校验器不支持的 type {}",
            path,
            py_repr(stype.unwrap())
        )],
    }
}

/// enum 约束（类型无关，先判一次）。
fn enum_issue(instance: &Json, schema: &Json, path: &str, out: &mut Vec<String>) {
    if let Some(Json::Array(en)) = get(schema, "enum") {
        if !en.iter().any(|e| json_equal(e, instance)) {
            out.push(format!(
                "{}: 值 {} 不在枚举 {}",
                path,
                py_repr(instance),
                py_repr(&Json::Array(en.clone()))
            ));
        }
    }
}

/// integer 分支：类型 + minimum 下界。
fn validate_integer(instance: &Json, schema: &Json, path: &str, out: Vec<String>) -> Vec<String> {
    let mut out = out;
    let ok = matches!(instance, Json::Int(_));
    if !ok {
        return vec![format!(
            "{}: 应为 integer，实为 {}",
            path,
            py_type_name(instance)
        )];
    }
    if let Some(m) = get(schema, "minimum") {
        if let (Some(v), Some(n)) = (as_f64(instance), as_f64(m)) {
            if v < n {
                out.push(format!(
                    "{}: 值 {} < minimum {}",
                    path,
                    plain_str(instance),
                    plain_str(m)
                ));
            }
        }
    }
    out
}

/// boolean 分支：类型判别。
fn validate_boolean(instance: &Json, path: &str, out: Vec<String>) -> Vec<String> {
    let out = out;
    if !matches!(instance, Json::Bool(_)) {
        return vec![format!(
            "{}: 应为 boolean，实为 {}",
            path,
            py_type_name(instance)
        )];
    }
    out
}

/// subset_validate 的 number 分支（枚举消息由调用方以 out 传入）。
pub(crate) fn validate_number(
    instance: &Json,
    schema: &Json,
    path: &str,
    mut out: Vec<String>,
) -> Vec<String> {
    let ok = matches!(instance, Json::Int(_) | Json::Float(_));
    if !ok {
        return vec![format!(
            "{}: 应为 number，实为 {}",
            path,
            py_type_name(instance)
        )];
    }
    if let Some(m) = get(schema, "minimum") {
        if let (Some(v), Some(n)) = (as_f64(instance), as_f64(m)) {
            if v < n {
                out.push(format!(
                    "{}: 值 {} < minimum {}",
                    path,
                    plain_str(instance),
                    plain_str(m)
                ));
            }
        }
    }
    out
}

/// subset_validate 的 object 分支（枚举消息由调用方以 out 传入）。
pub(crate) fn validate_object(
    instance: &Json,
    schema: &Json,
    path: &str,
    mut out: Vec<String>,
) -> Vec<String> {
    let Json::Object(inst) = instance else {
        return vec![format!(
            "{}: 应为 object，实为 {}",
            path,
            py_type_name(instance)
        )];
    };
    let props: Vec<(String, Json)> = match get(schema, "properties") {
        Some(Json::Object(p)) => p.clone(),
        _ => Vec::new(),
    };
    required_field_issues(inst, schema, path, &mut out);
    property_names_issues(inst, schema, path, &mut out);
    property_issues(inst, &props, path, &mut out);
    extra_property_issues(inst, &props, schema, path, &mut out);
    out
}

/// properties 面：逐键递归。
fn property_issues(
    inst: &[(String, Json)],
    props: &[(String, Json)],
    path: &str,
    out: &mut Vec<String>,
) {
    for (key, sub) in props {
        if let Some((_, v)) = inst.iter().find(|(k, _)| k == key) {
            out.extend(subset_validate(v, sub, &format!("{}/{}", path, key)));
        }
    }
}

/// additionalProperties 面：禁止 / 带 schema 递归 / 放行。
fn extra_property_issues(
    inst: &[(String, Json)],
    props: &[(String, Json)],
    schema: &Json,
    path: &str,
    out: &mut Vec<String>,
) {
    let extra = get(schema, "additionalProperties");
    for (key, v) in inst {
        if props.iter().any(|(k, _)| k == key) {
            continue;
        }
        match extra {
            Some(Json::Bool(false)) => out.push(format!(
                "{}: 未知字段 {}（不在该 schema 词表内）",
                path, key
            )),
            Some(e) if matches!(e, Json::Object(_)) => {
                out.extend(subset_validate(v, e, &format!("{}/{}", path, key)));
            }
            _ => {}
        }
    }
}

/// subset_validate 的 array 分支（枚举消息由调用方以 out 传入）。
pub(crate) fn validate_array(
    instance: &Json,
    schema: &Json,
    path: &str,
    mut out: Vec<String>,
) -> Vec<String> {
    let Json::Array(items) = instance else {
        return vec![format!(
            "{}: 应为 array，实为 {}",
            path,
            py_type_name(instance)
        )];
    };
    if let Some(m) = get(schema, "minItems") {
        if let Some(n) = as_int(m) {
            if (items.len() as i64) < n {
                out.push(format!(
                    "{}: 数组长度 {} < minItems {}",
                    path,
                    items.len(),
                    n
                ));
            }
        }
    }
    if let Some(m) = get(schema, "maxItems") {
        if let Some(n) = as_int(m) {
            if (items.len() as i64) > n {
                out.push(format!(
                    "{}: 数组长度 {} > maxItems {}",
                    path,
                    items.len(),
                    n
                ));
            }
        }
    }
    let sub = get(schema, "items");
    for (i, item) in items.iter().enumerate() {
        if let Some(s) = sub {
            out.extend(subset_validate(item, s, &format!("{}[{}]", path, i)));
        } else {
            out.extend(subset_validate(
                item,
                &Json::Null,
                &format!("{}[{}]", path, i),
            ));
        }
    }
    out
}

/// subset_validate 的 string 分支（枚举消息由调用方以 out 传入）。
pub(crate) fn validate_string(
    instance: &Json,
    schema: &Json,
    path: &str,
    mut out: Vec<String>,
) -> Vec<String> {
    let Json::Str(s) = instance else {
        return vec![format!(
            "{}: 应为 string，实为 {}",
            path,
            py_type_name(instance)
        )];
    };
    if let Some(m) = get(schema, "minLength") {
        if let Some(n) = as_int(m) {
            let len = s.chars().count() as i64;
            if len < n {
                out.push(format!("{}: 字符串过短 {} < minLength {}", path, len, n));
            }
        }
    }
    if let Some(Json::Str(pat)) = get(schema, "pattern") {
        match cached_regex(pat) {
            Some(re) => {
                if !re.is_match(s) {
                    out.push(format!(
                        "{}: 值 {} 不匹配 pattern {}",
                        path,
                        py_repr(instance),
                        pat
                    ));
                }
            }
            None => out.push(format!(
                "{}: 值 {} 不匹配 pattern {}",
                path,
                py_repr(instance),
                pat
            )),
        }
    }
    out
}
