use super::*;

/// $ref 解析（远程/悬空记 unsupported；可解析则递归）。
pub(crate) fn check_ref(
    instance: &Json,
    schema: &Json,
    path: &str,
    root: &Json,
    unsupported: &mut Vec<String>,
    depth: usize,
) -> Vec<String> {
    let mut errors: Vec<String> = Vec::new();
    if let Some(r) = obj_get(schema, "$ref") {
        let refstr = pyval::plain_str(r);
        match resolve_ref(&refstr, root) {
            None => unsupported.push(format!("远程/悬空 $ref {}@{}", refstr, path)),
            Some(target) => errors.extend(check(
                instance,
                &target,
                path,
                Some(root),
                unsupported,
                depth + 1,
            )),
        }
    }
    errors
}

/// 数组面：minItems / maxItems / uniqueItems / prefixItems / items 递归。
pub(crate) fn check_array(
    instance: &Json,
    schema: &Json,
    path: &str,
    root: &Json,
    unsupported: &mut Vec<String>,
    depth: usize,
) -> Vec<String> {
    let mut errors: Vec<String> = Vec::new();
    if let Json::Array(items) = instance {
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
        let prefix = obj_get(schema, "prefixItems");
        if let Some(Json::Array(prefix)) = prefix {
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
        if let Some(items_schema) = obj_get(schema, "items") {
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
    }
    errors
}

/// 对象面属性：properties / patternProperties / additionalProperties / propertyNames。
pub(crate) fn check_object_props(
    instance: &Json,
    schema: &Json,
    path: &str,
    root: &Json,
    unsupported: &mut Vec<String>,
    depth: usize,
) -> Vec<String> {
    let mut errors: Vec<String> = Vec::new();
    let props = obj_get(schema, "properties")
        .cloned()
        .unwrap_or(Json::Object(vec![]));
    let pats = obj_get(schema, "patternProperties")
        .cloned()
        .unwrap_or(Json::Object(vec![]));
    if let Json::Object(map) = instance {
        for (key, value) in map {
            let mut matched = false;
            if let Some(sub) = obj_get(&props, key) {
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
            if let Json::Object(pats) = &pats {
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
            if !matched {
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
        }
        if let Some(pn) = obj_get(schema, "propertyNames") {
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
    }
    errors
}

/// allOf / anyOf / oneOf 组合子式。
pub(crate) fn check_compound(
    instance: &Json,
    schema: &Json,
    path: &str,
    root: &Json,
    unsupported: &mut Vec<String>,
    depth: usize,
) -> Vec<String> {
    let mut errors: Vec<String> = Vec::new();
    for (kw, mode) in [("allOf", "all"), ("anyOf", "any"), ("oneOf", "one")] {
        let Some(Json::Array(subs)) = obj_get(schema, kw) else {
            continue;
        };
        let results: Vec<Vec<String>> = subs
            .iter()
            .map(|s| check(instance, s, path, Some(root), unsupported, depth + 1))
            .collect();
        let ok = results.iter().filter(|r| r.is_empty()).count();
        if mode == "all" && ok != subs.len() {
            errors.push(format!(
                "{}: allOf 有 {}/{} 子式不成立",
                path,
                subs.len() - ok,
                subs.len()
            ));
        }
        if mode == "any" && ok == 0 {
            errors.push(format!("{}: anyOf 全不成立", path));
        }
        if mode == "one" && ok != 1 {
            errors.push(format!("{}: oneOf 命中 {} 个（须恰 1）", path, ok));
        }
    }
    errors
}

/// not 子式（被满足即报错）。
pub(crate) fn check_not(
    instance: &Json,
    schema: &Json,
    path: &str,
    root: &Json,
    unsupported: &mut Vec<String>,
    depth: usize,
) -> Vec<String> {
    let mut errors: Vec<String> = Vec::new();
    if let Some(not) = obj_get(schema, "not") {
        if matches!(not, Json::Object(_))
            && check(instance, not, path, Some(root), unsupported, depth + 1).is_empty()
        {
            errors.push(format!("{}: not 子式被满足", path));
        }
    }
    errors
}

/// 字符串面：minLength / maxLength / pattern / format。
pub(crate) fn check_string(instance: &Json, schema: &Json, path: &str) -> Vec<String> {
    let mut errors: Vec<String> = Vec::new();
    if let Json::Str(s) = instance {
        let len = s.chars().count() as i64;
        if let Some(v) = obj_get(schema, "minLength") {
            if len < pyval::py_int_or(Some(v), 0) {
                errors.push(format!("{}: 长度 < {}", path, pyval::plain_str(v)));
            }
        }
        if let Some(v) = obj_get(schema, "maxLength") {
            if len > pyval::py_int_or(Some(v), 0) {
                errors.push(format!("{}: 长度 > {}", path, pyval::plain_str(v)));
            }
        }
        if let Some(p) = obj_get(schema, "pattern") {
            let why = pattern_issue(p, path);
            if !why.is_empty() {
                errors.push(why);
            } else if !re_search(&pyval::plain_str(p), s) {
                errors.push(format!("{}: 不匹配 pattern {}", path, pyval::plain_str(p)));
            }
        }
        if let Some(f) = obj_get(schema, "format") {
            let fmt = pyval::plain_str(f);
            if !fmt.is_empty() {
                errors.extend(format_errors(s, &fmt, path));
            }
        }
    }
    errors
}

/// 数值面：minimum / maximum / 排他边界 / multipleOf。
pub(crate) fn check_number(instance: &Json, schema: &Json, path: &str) -> Vec<String> {
    let mut errors: Vec<String> = Vec::new();
    if matches!(instance, Json::Int(_) | Json::Float(_)) {
        let iv = num_of(instance);
        for (kw, op, cmp) in [
            ("minimum", ">=", 0),
            ("maximum", "<=", 1),
            ("exclusiveMinimum", ">", 2),
            ("exclusiveMaximum", "<", 3),
        ] {
            if let Some(b) = obj_get(schema, kw) {
                let bv = num_of(b);
                let ok = match cmp {
                    0 => iv >= bv,
                    1 => iv <= bv,
                    2 => iv > bv,
                    _ => iv < bv,
                };
                if !ok {
                    errors.push(format!(
                        "{}: {} {} {} 不成立",
                        path,
                        pyval::plain_str(instance),
                        op,
                        pyval::plain_str(b)
                    ));
                }
            }
        }
        if let Some(m) = obj_get(schema, "multipleOf") {
            let mv = num_of(m);
            if mv != 0.0 {
                let q = iv / mv;
                if (q - round_half_even(q)).abs() > 1e-9 {
                    errors.push(format!("{}: 非 {} 的整数倍", path, pyval::plain_str(m)));
                }
            }
        }
    }
    errors
}

/// 对象面必填：required / dependentRequired。
pub(crate) fn check_object_required(instance: &Json, schema: &Json, path: &str) -> Vec<String> {
    let mut errors: Vec<String> = Vec::new();
        if let Some(Json::Array(req)) = obj_get(schema, "required") {
            for key in req {
                let k = pyval::plain_str(key);
                if !obj_has(instance, &k) {
                    errors.push(format!("{}: 缺必填字段 {}", path, k));
                }
            }
        }
        if let Some(Json::Object(deps)) = obj_get(schema, "dependentRequired") {
            for (dep, need) in deps {
                if obj_has(instance, dep) {
                    if let Json::Array(ns) = need {
                        for n in ns {
                            let nk = pyval::plain_str(n);
                            if !obj_has(instance, &nk) {
                                errors.push(format!("{}: 出现 {} 时必填 {}", path, dep, nk));
                            }
                        }
                    }
                }
            }
        }
    errors
}

pub(crate) fn num_of(v: &Json) -> f64 {
    match v {
        Json::Int(i) => *i as f64,
        Json::Float(f) => *f,
        Json::Bool(b) => {
            if *b {
                1.0
            } else {
                0.0
            }
        }
        _ => 0.0,
    }
}

/// Python 的 `round()`（**银行家舍入**）。
pub(crate) fn round_half_even(x: f64) -> f64 {
    let r = x.round();
    if (x - x.trunc()).abs() == 0.5 && r % 2.0 != 0.0 {
        r - x.signum()
    } else {
        r
    }
}

/// 真源公开入口 `json_schema_check(instance, schema, path="$", ...)`。
/// 真源 `json_schema_check(..., unsupported=out)` 的对应物：同时给出**不支持关键字**清单。
pub(crate) fn json_schema_check_unsup(instance: &Json, schema: &Json) -> (Vec<String>, Vec<String>) {
    let mut unsupported: Vec<String> = Vec::new();
    let errs = check(instance, schema, "$", None, &mut unsupported, 0);
    (errs, unsupported)
}

pub(crate) fn json_schema_check(instance: &Json, schema: &Json) -> Vec<String> {
    let mut unsupported: Vec<String> = Vec::new();
    check(instance, schema, "$", None, &mut unsupported, 0)
}
