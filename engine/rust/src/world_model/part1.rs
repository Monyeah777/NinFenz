use super::*;

pub(crate) const KINDS: [&str; 5] = ["string", "integer", "number", "boolean", "array"];

pub(crate) const ITEM_KINDS: [&str; 4] = ["string", "integer", "number", "boolean"];

pub(crate) fn obj_get<'a>(v: &'a Json, k: &str) -> Option<&'a Json> {
    match v {
        Json::Object(o) => o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv),
        _ => None,
    }
}

/// 真源 `v.get(k)`：**区分"缺键"与"显式 null"**（判据里 `checks is not None` 依赖这一点）。
pub(crate) fn get(v: &Json, k: &str) -> Option<Json> {
    obj_get(v, k).cloned()
}

/// 该键是否**在场**（真源 `k in dict`）。
pub(crate) fn has(v: &Json, k: &str) -> bool {
    matches!(v, Json::Object(o) if o.iter().any(|(kk, _)| kk == k))
}

pub(crate) fn arr_of(v: Option<&Json>) -> Vec<Json> {
    match v {
        Some(Json::Array(a)) => a.clone(),
        _ => Vec::new(),
    }
}

/// 真源 `load_slots`：`protocol/world_slots.json` 的 `slots` 段。
pub(crate) fn load_slots(root: &Path) -> Vec<(String, Json)> {
    let rel = "protocol/world_slots.json";
    if !root.join(rel).is_file() {
        return Vec::new();
    }
    let Ok(text) = std::fs::read_to_string(root.join(rel)) else {
        return Vec::new();
    };
    let Ok(data) = crate::asset_contract::strict_json(&text) else {
        return Vec::new();
    };
    match obj_get(&data, "slots") {
        Some(Json::Object(o)) => o.clone(),
        _ => Vec::new(),
    }
}

pub(crate) fn slot_lookup(reg: &[(String, Json)], slot: &str) -> Option<Json> {
    reg.iter().find(|(k, _)| k == slot).map(|(_, v)| v.clone())
}

/// 真源 `_matches`。
pub(crate) fn matches(value: &Json, kind: &str, item_kind: Option<&str>) -> bool {
    match kind {
        "integer" => matches!(value, Json::Int(_)),
        "number" => matches!(value, Json::Int(_) | Json::Float(_)),
        "string" => matches!(value, Json::Str(_)),
        "boolean" => matches!(value, Json::Bool(_)),
        "array" => match value {
            Json::Array(a) => match item_kind {
                None => true,
                Some(ik) => a.iter().all(|v| matches(v, ik, None)),
            },
            _ => false,
        },
        _ => false,
    }
}

/// 真源 `validate_contract`。
pub(crate) fn validate_contract(wm: &Json, label: &str, slot_registry: &[(String, Json)]) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    if !matches!(wm, Json::Object(_)) {
        return vec![format!("{}: 非对象", label)];
    }

    let (variables, initial) = parse_abstract(wm, label, &mut issues);

    let valid_vars = check_variables(label, &variables, &mut issues);

    check_initial(label, initial.as_ref(), &valid_vars, &mut issues);

    let (initial_phase, phases) = parse_transition(wm, label, &mut issues);

    let (phase_names, edges) = check_phases(label, &phases, &mut issues);

    check_reachability(label, initial_phase.as_deref(), &phase_names, &edges, &mut issues);

    check_invariants(wm, label, &mut issues);

    let (declared_names, declared_kinds) = declared_names_kinds(&valid_vars);
    if let Some(checks_v) = get(wm, "checks") {
        if !matches!(checks_v, Json::Null) {
            let checks = match &checks_v {
                Json::Array(c) if !c.is_empty() => c.clone(),
                _ => {
                    issues.push(format!("{}.checks: 非空数组", label));
                    Vec::new()
                }
            };
            for (idx, check) in checks.iter().enumerate() {
                check_one_check(
                    label,
                    idx,
                    check,
                    &declared_names,
                    &declared_kinds,
                    &valid_vars,
                    &mut issues,
                );
            }
        }
    }

    check_slots(label, &valid_vars, slot_registry, &mut issues);
    issues
}

/// abstract_state 骨架解析（变量数组 / 初始值对象）。
pub(crate) fn parse_abstract(wm: &Json, label: &str, issues: &mut Vec<String>) -> (Vec<Json>, Option<Json>) {
    let abstract_v = get(wm, "abstract_state");
    let mut variables: Vec<Json> = Vec::new();
    let mut initial: Option<Json> = None;
    match &abstract_v {
        Some(a @ Json::Object(_)) => {
            let vars = get(a, "variables");
            initial = get(a, "initial");
            match &vars {
                Some(Json::Array(v)) if !v.is_empty() => variables = v.clone(),
                _ => {
                    issues.push(format!("{}.abstract_state.variables: 非空数组", label));
                }
            }
            if !matches!(initial, Some(Json::Object(_))) {
                issues.push(format!("{}.abstract_state.initial: 缺失或非对象", label));
                initial = None;
            }
        }
        _ => {
            issues.push(format!("{}.abstract_state: 缺失或非对象", label));
        }
    }
    (variables, initial)
}

/// 变量面的 name / kind / item_kind / source / slot 核对；返回通过筛的变量。
pub(crate) fn check_variables(label: &str, variables: &[Json], issues: &mut Vec<String>) -> Vec<Json> {
    let mut names: Vec<String> = Vec::new();
    let mut slots: Vec<String> = Vec::new();
    let mut valid_vars: Vec<Json> = Vec::new();
    for (idx, var) in variables.iter().enumerate() {
        let at = format!("{}.abstract_state.variables[{}]", label, idx);
        if !matches!(var, Json::Object(_)) {
            issues.push(format!("{}: 非对象", at));
            continue;
        }
        let name_v = get(var, "name");
        let kind_v = get(var, "kind");
        let source_v = get(var, "source");
        let slot_v = get(var, "slot");
        let item_kind_v = get(var, "item_kind");
        let name = match &name_v {
            Some(Json::Str(s)) if !s.trim().is_empty() => Some(s.clone()),
            _ => {
                issues.push(format!("{}.name: 非空字符串", at));
                None
            }
        };
        if let Some(n) = &name {
            if names.contains(n) {
                issues.push(format!(
                    "{}.name: 变量重名 {}",
                    at,
                    pyval::py_repr(&Json::Str(n.clone()))
                ));
            }
            names.push(n.clone());
        }
        let kind = match &kind_v {
            Some(Json::Str(s)) => s.clone(),
            _ => String::new(),
        };
        if !KINDS.contains(&kind.as_str()) {
            issues.push(format!(
                "{}.kind: 非法类型 {}",
                at,
                pyval::py_repr(&kind_v.clone().unwrap_or(Json::Null))
            ));
        }
        let item_kind_str = match &item_kind_v {
            Some(Json::Str(s)) => Some(s.clone()),
            _ => None,
        };
        if kind == "array" {
            if let Some(ik) = &item_kind_str {
                if !ITEM_KINDS.contains(&ik.as_str()) {
                    issues.push(format!(
                        "{}.item_kind: 非法元素类型 {}",
                        at,
                        pyval::py_repr(&item_kind_v.clone().unwrap_or(Json::Null))
                    ));
                }
            }
        } else if !matches!(item_kind_v, None | Some(Json::Null)) {
            issues.push(format!("{}.item_kind: 仅 kind=array 可用", at));
        }
        let source_ok = matches!(&source_v, Some(Json::Str(s)) if !s.trim().is_empty());
        if !source_ok {
            issues.push(format!("{}.source: 非空字符串", at));
        }
        if !matches!(slot_v, None | Some(Json::Null)) {
            let slot_str = match &slot_v {
                Some(Json::Str(s)) => Some(s.clone()),
                _ => None,
            };
            match slot_str {
                None => issues.push(format!("{}.slot: 非空字符串", at)),
                Some(s) if s.trim().is_empty() => issues.push(format!("{}.slot: 非空字符串", at)),
                Some(s) => {
                    if slots.contains(&s) {
                        issues.push(format!(
                            "{}.slot: 槽位重复 {}",
                            at,
                            pyval::py_repr(&Json::Str(s))
                        ));
                    } else {
                        slots.push(s);
                    }
                }
            }
        }
        valid_vars.push(var.clone());
    }
    valid_vars
}
