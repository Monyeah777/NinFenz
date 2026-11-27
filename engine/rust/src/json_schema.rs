//! JSON Schema 2020-12 **子集**校验器 —— 与真源 `desktop/src/core/json_schema.py` 对账。
//!
//! 真源是**叶子件**（不 import 任何 core 模块）；本线同形，只依赖 `pyjson` / `pyval`。
//! 调用面：`asset_contract` 的数据面，以及 `output_forms` / `pack_combo`（后者在深度子扫描器里）。
//!
//! 子集边界与真源一致，且**"不支持"绝不等价"通过"**：超出 `_SUPPORTED` 的官方关键字进
//! `unsupported` 清单（调用方若关心可自行取用；`asset_contract` 不取，故不影响其结论）。
//!
//! 三处口径陷阱（都影响逐字节对账）：
//!
//! 1. **`bool` 不是 `number`/`integer`**（Python 里 `isinstance(True, int)` 为真，真源显式排除）。
//! 2. **`const` / `enum` 用 Python 的 `==`**：`True == 1` 成立 ⇒ 本线走 `pyval::py_eq`，
//!    不能用结构相等。
//! 3. **`type(instance).__name__`**：消息里出现的是 `dict` / `list` / `NoneType` 这些
//!    **Python 类型名**，不是 Rust 的。
use crate::pyjson::Json;
use crate::pyval;
mod part1;
mod part2;
pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
#[path = "generated/json_schema_gen.rs"]
mod json_schema_gen;

/// 数组长度面：minItems / maxItems。
pub(crate) fn array_count_errors(items: &[Json], schema: &Json, path: &str, errors: &mut Vec<String>) {
    if let Some(v) = obj_get(schema, "minItems") {
        if (items.len() as i64) < pyval::py_int_or(Some(v), 0) {
            errors.push(format!("{}: 元素数 < {}", path, pyval::plain_str(v)));
        }
    }
    if let Some(v) = obj_get(schema, "maxItems") {
        if (items.len() as i64) > pyval::py_int_or(Some(v), 0) {
            errors.push(format!("{}: 元素数 > {}", path, pyval::plain_str(v)));
        }
    }
}

/// 数组去重面：uniqueItems。
pub(crate) fn array_unique_errors(items: &[Json], schema: &Json, path: &str, errors: &mut Vec<String>) {
    if pyval::py_truthy(
        &obj_get(schema, "uniqueItems")
            .cloned()
            .unwrap_or(Json::Bool(false)),
    ) {
        let seen: Vec<String> = items.iter().map(|x| x.dumps()).collect();
        let mut uniq: Vec<&String> = seen.iter().collect();
        uniq.sort();
        uniq.dedup();
        if uniq.len() != seen.len() {
            errors.push(format!("{}: uniqueItems 被违反", path));
        }
    }
}

/// prefixItems 逐位递归。
#[allow(clippy::too_many_arguments)]
pub(crate) fn array_prefix_errors(
    items: &[Json],
    prefix: Option<&Json>,
    path: &str,
    root: &Json,
    unsupported: &mut Vec<String>,
    depth: usize,
    errors: &mut Vec<String>,
) {
    let Some(Json::Array(prefix)) = prefix else {
        return;
    };
    for (i, sub) in prefix.iter().enumerate() {
        if i < items.len() {
            errors.extend(check(
                &items[i],
                sub,
                &format!("{}[{}]", path, i),
                Some(root),
                unsupported,
                depth + 1,
            ));
        }
    }
}

/// items 子式（prefixItems 之后的元素）递归。
#[allow(clippy::too_many_arguments)]
pub(crate) fn array_items_errors(
    items: &[Json],
    schema: &Json,
    prefix: Option<&Json>,
    path: &str,
    root: &Json,
    unsupported: &mut Vec<String>,
    depth: usize,
    errors: &mut Vec<String>,
) {
    let Some(items_schema) = obj_get(schema, "items") else {
        return;
    };
    if matches!(items_schema, Json::Object(_)) {
        let start = match prefix {
            Some(Json::Array(p)) => p.len(),
            _ => 0,
        };
        for i in start..items.len() {
            errors.extend(check(
                &items[i],
                items_schema,
                &format!("{}[{}]", path, i),
                Some(root),
                unsupported,
                depth + 1,
            ));
        }
    }
}
/// properties / patternProperties 面；返回该键是否已被任一子式覆盖（供 additionalProperties 判据）。
#[allow(clippy::too_many_arguments)]
pub(crate) fn object_prop_errors(
    key: &str,
    value: &Json,
    props: &Json,
    pats: &Json,
    path: &str,
    root: &Json,
    unsupported: &mut Vec<String>,
    depth: usize,
    errors: &mut Vec<String>,
) -> bool {
    let mut matched = false;
    if let Some(sub) = obj_get(props, key) {
        matched = true;
        errors.extend(check(
            value,
            sub,
            &format!("{}.{}", path, key),
            Some(root),
            unsupported,
            depth + 1,
        ));
    }
    if let Json::Object(pats) = pats {
        for (pat, sub) in pats {
            let why = pattern_issue(&Json::Str(pat.clone()), path);
            if !why.is_empty() {
                errors.push(why); // 形态闸门：不拿投稿者的表达式去跑匹配
                continue;
            }
            if re_search(pat, key) {
                matched = true;
                errors.extend(check(
                    value,
                    sub,
                    &format!("{}.{}", path, key),
                    Some(root),
                    unsupported,
                    depth + 1,
                ));
            }
        }
    }
    matched
}

/// additionalProperties 面（仅未被覆盖的键）。
#[allow(clippy::too_many_arguments)]
pub(crate) fn object_additional_errors(
    key: &str,
    value: &Json,
    schema: &Json,
    path: &str,
    root: &Json,
    unsupported: &mut Vec<String>,
    depth: usize,
    errors: &mut Vec<String>,
) {
    let ap = obj_get(schema, "additionalProperties")
        .cloned()
        .unwrap_or(Json::Bool(true));
    match ap {
        Json::Bool(false) => errors.push(format!(
            "{}: 多余字段 {}（additionalProperties=false）",
            path, key
        )),
        Json::Object(_) => errors.extend(check(
            value,
            &ap,
            &format!("{}.{}", path, key),
            Some(root),
            unsupported,
            depth + 1,
        )),
        _ => {}
    }
}

/// propertyNames 面：用键本身当实例再校验一次。
#[allow(clippy::too_many_arguments)]
pub(crate) fn object_property_names_errors(
    map: &[(String, Json)],
    schema: &Json,
    path: &str,
    root: &Json,
    unsupported: &mut Vec<String>,
    depth: usize,
    errors: &mut Vec<String>,
) {
    let Some(pn) = obj_get(schema, "propertyNames") else {
        return;
    };
    if matches!(pn, Json::Object(_)) {
        for (key, _) in map.iter() {
            errors.extend(check(
                &Json::Str(key.clone()),
                pn,
                &format!("{}<键:{}>", path, key),
                Some(root),
                unsupported,
                depth + 1,
            ));
        }
    }
}
