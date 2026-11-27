use super::*;

/// 单条 checks 声明核对（kind / field / values / 变量类型适配）。
pub(crate) fn check_one_check(
    label: &str,
    idx: usize,
    check: &Json,
    declared_names: &[String],
    declared_kinds: &[(String, String)],
    valid_vars: &[Json],
    issues: &mut Vec<String>,
) {
    let at = format!("{}.checks[{}]", label, idx);
    if !matches!(check, Json::Object(_)) {
        issues.push(format!("{}: 非对象", at));
        return;
    }
    let kind = match get(check, "kind") {
        Some(Json::Str(s)) => s,
        _ => String::new(),
    };
    let field_v = get(check, "field");
    let values_v = get(check, "values");
    check_kind_declared(&at, check, &kind, issues);
    let field = check_field_declared(&at, &field_v, declared_names, issues);
    check_values_face(&at, &kind, &values_v, issues);
    check_monotonic_face(&at, &kind, &field, declared_kinds, issues);
    check_finite_sequence_face(&at, &kind, &field, declared_kinds, valid_vars, issues);
}

/// kind 词表面。
fn check_kind_declared(at: &str, check: &Json, kind: &str, issues: &mut Vec<String>) {
    if !["finite_phase", "monotonic", "finite_sequence"].contains(&kind) {
        issues.push(format!(
            "{}.kind: 非法检查类型 {}",
            at,
            pyval::py_repr(&get(check, "kind").unwrap_or(Json::Null))
        ));
    }
}

/// field 面：非空字符串且在已声明变量表内；返回取到的字段名（缺省为空串）。
fn check_field_declared(
    at: &str,
    field_v: &Option<Json>,
    declared_names: &[String],
    issues: &mut Vec<String>,
) -> String {
    let field_ok = matches!(field_v, Some(Json::Str(s)) if !s.trim().is_empty());
    if !field_ok {
        issues.push(format!("{}.field: 非空字符串", at));
    } else if let Some(Json::Str(f)) = field_v {
        if !declared_names.contains(f) {
            issues.push(format!(
                "{}.field: 未声明变量 {}",
                at,
                pyval::py_repr(&Json::Str(f.clone()))
            ));
        }
    }
    match field_v {
        Some(Json::Str(s)) => s.clone(),
        _ => String::new(),
    }
}

/// values 面：finite_phase / finite_sequence 需非空字符串数组。
fn check_values_face(at: &str, kind: &str, values_v: &Option<Json>, issues: &mut Vec<String>) {
    if kind == "finite_phase" || kind == "finite_sequence" {
        let ok = match values_v {
            Some(Json::Array(v)) => {
                !v.is_empty()
                    && v.iter()
                        .all(|x| matches!(x, Json::Str(s) if !s.trim().is_empty()))
            }
            _ => false,
        };
        if !ok {
            issues.push(format!("{}.values: {} 需非空字符串数组", at, kind));
        }
    }
}

/// monotonic 面：只能用于 integer / number 变量。
fn check_monotonic_face(
    at: &str,
    kind: &str,
    field: &str,
    declared_kinds: &[(String, String)],
    issues: &mut Vec<String>,
) {
    if kind == "monotonic" {
        let k = declared_kinds
            .iter()
            .find(|(n, _)| *n == field)
            .map(|(_, k)| k.clone())
            .unwrap_or_default();
        if k != "integer" && k != "number" {
            issues.push(format!(
                "{}.field: monotonic 只能用于 integer/number 变量",
                at
            ));
        }
    }
}

/// finite_sequence 面：只能用于 array 变量，且元素类型应为 string。
fn check_finite_sequence_face(
    at: &str,
    kind: &str,
    field: &str,
    declared_kinds: &[(String, String)],
    valid_vars: &[Json],
    issues: &mut Vec<String>,
) {
    if kind == "finite_sequence" {
        let k = declared_kinds
            .iter()
            .find(|(n, _)| *n == field)
            .map(|(_, k)| k.clone())
            .unwrap_or_default();
        if k != "array" {
            issues.push(format!("{}.field: finite_sequence 只能用于 array 变量", at));
        } else {
            let spec = valid_vars
                .iter()
                .find(|v| matches!(get(v, "name"), Some(Json::Str(n)) if n == field));
            let ik = spec.and_then(|s| get(s, "item_kind"));
            if !matches!(ik, None | Some(Json::Null))
                && !matches!(&ik, Some(Json::Str(s)) if s == "string")
            {
                issues.push(format!(
                    "{}.field: finite_sequence 的 array 元素应为 string",
                    at
                ));
            }
        }
    }
}

/// slot 注册面：槽位在册 / kind / item_kind / owner 漂移。
pub(crate) fn check_slots(
    label: &str,
    valid_vars: &[Json],
    slot_registry: &[(String, Json)],
    issues: &mut Vec<String>,
) {
    if slot_registry.is_empty() {
        return;
    }
    for var in valid_vars {
        let slot = match get(var, "slot") {
            Some(Json::Str(s)) if !s.trim().is_empty() => s,
            _ => continue,
        };
        let name = get(var, "name").unwrap_or(Json::Null);
        let source = get(var, "source").unwrap_or(Json::Null);
        let Some(spec) = slot_spec_or_issues(label, &name, slot, slot_registry, issues) else {
            continue;
        };
        slot_type_drift_issues(label, &name, &spec, var, issues);
        slot_owner_drift_issues(label, &name, &spec, &source, issues);
    }
}

/// 取槽位注册记录；未注册 / 非对象即报出并返回 None。
fn slot_spec_or_issues(
    label: &str,
    name: &Json,
    slot: String,
    slot_registry: &[(String, Json)],
    issues: &mut Vec<String>,
) -> Option<Json> {
    let Some(spec) = slot_lookup(slot_registry, &slot) else {
        issues.push(format!(
            "{}.abstract_state.variables[{}].slot: 未在 protocol/world_slots.json 注册 {}",
            label,
            pyval::py_repr(name),
            pyval::py_repr(&Json::Str(slot))
        ));
        return None;
    };
    if !matches!(spec, Json::Object(_)) {
        issues.push(format!(
            "{}.abstract_state.variables[{}].slot: 未在 protocol/world_slots.json 注册 {}",
            label,
            pyval::py_repr(name),
            pyval::py_repr(&Json::Str(slot))
        ));
        return None;
    }
    Some(spec)
}

/// kind / item_kind 与槽位注册的类型漂移。
fn slot_type_drift_issues(
    label: &str,
    name: &Json,
    spec: &Json,
    var: &Json,
    issues: &mut Vec<String>,
) {
    let kind_v = get(var, "kind").unwrap_or(Json::Null);
    let spec_kind = get(spec, "kind").unwrap_or(Json::Null);
    if !pyval::py_eq(&spec_kind, &kind_v) {
        issues.push(format!(
            "{}.abstract_state.variables[{}].slot: 类型漂移 slot={} var={}",
            label,
            pyval::py_repr(name),
            pyval::py_repr(&spec_kind),
            pyval::py_repr(&kind_v)
        ));
    }
    let item_kind_v = get(var, "item_kind").unwrap_or(Json::Null);
    if kind_v == Json::Str("array".to_string()) && pyval::py_truthy(&item_kind_v) {
        let spec_ik = get(spec, "item_kind").unwrap_or(Json::Null);
        if !pyval::py_eq(&spec_ik, &item_kind_v) {
            issues.push(format!(
                "{}.abstract_state.variables[{}].slot: 元素类型漂移 slot={} var={}",
                label,
                pyval::py_repr(name),
                pyval::py_repr(&spec_ik),
                pyval::py_repr(&item_kind_v)
            ));
        }
    }
}

/// owner 漂移（注册了 owner 才核对）。
fn slot_owner_drift_issues(
    label: &str,
    name: &Json,
    spec: &Json,
    source: &Json,
    issues: &mut Vec<String>,
) {
    let spec_owner = get(spec, "owner").unwrap_or(Json::Null);
    if pyval::py_truthy(&spec_owner) && !pyval::py_eq(source, &spec_owner) {
        issues.push(format!(
            "{}.abstract_state.variables[{}].slot: owner 漂移 slot={} var.source={}",
            label,
            pyval::py_repr(name),
            pyval::py_repr(&spec_owner),
            pyval::py_repr(source)
        ));
    }
}

/// 真源 `scan` → `(issues, stats)`。
pub(crate) fn scan(root: &Path) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let slot_registry = load_slots(root);
    if slot_registry.is_empty() {
        issues.push("protocol/world_slots.json 缺失或 slots 为空".to_string());
    }
    let (mut modules, mut variables, mut phases, mut invariants, mut checks, mut slots) =
        (0i64, 0i64, 0i64, 0i64, 0i64, 0i64);
    let mut models: Vec<Json> = Vec::new();

    for rel in crate::depth_small::module_docs(root) {
        if let Some(m) = scan_model(root, &rel, &slot_registry, &mut issues) {
            modules += 1;
            variables += m.variables;
            phases += m.phases;
            invariants += m.invariants;
            checks += m.checks;
            slots += m.slots;
            models.push(m.row);
        }
    }

    (
        issues,
        Json::Object(vec![
            ("modules".to_string(), Json::Int(modules)),
            ("variables".to_string(), Json::Int(variables)),
            ("phases".to_string(), Json::Int(phases)),
            ("invariants".to_string(), Json::Int(invariants)),
            ("checks".to_string(), Json::Int(checks)),
            ("slots".to_string(), Json::Int(slots)),
            (
                "slot_registry".to_string(),
                Json::Int(slot_registry.len() as i64),
            ),
            ("models".to_string(), Json::Array(models)),
        ]),
    )
}

/// 单份模块文档的 world_model 段核对结论（一行模型记录 + 各项计数）。
pub(crate) struct ScannedModel {
    pub(crate) row: Json,
    pub(crate) variables: i64,
    pub(crate) phases: i64,
    pub(crate) invariants: i64,
    pub(crate) checks: i64,
    pub(crate) slots: i64,
}

/// 核对单份模块文档的 world_model 段；解析缺件 / 非对象即 None（贡献空结论）。
pub(crate) fn scan_model(
    root: &Path,
    rel: &str,
    slot_registry: &[(String, Json)],
    issues: &mut Vec<String>,
) -> Option<ScannedModel> {
    let text = std::fs::read(root.join(&rel)).map(|b| String::from_utf8_lossy(&b).into_owned());
    let text = match text {
        Ok(t) => t,
        Err(e) => {
            issues.push(format!("{}: 读取失败 {}", rel, e));
            return None;
        }
    };
    let Some(parsed) = crate::miniyaml::fence_yaml(&text, "machine_contract") else {
        return None;
    };
    let Some(Json::Object(mc)) = obj_get(&parsed, "machine_contract") else {
        return None;
    };
    let mc = Json::Object(mc.clone());
    let Some(wm) = obj_get(&mc, "world_model").cloned() else {
        return None;
    };
    for issue in validate_contract(&wm, &format!("{}.world_model", rel), &slot_registry) {
        issues.push(issue);
    }
    let abstract_v = get(&wm, "abstract_state").unwrap_or(Json::Null);
    let transition_v = get(&wm, "transition").unwrap_or(Json::Null);
    let invs = get(&wm, "invariants").unwrap_or(Json::Null);
    let check_list = get(&wm, "checks").unwrap_or(Json::Null);
    let (model_variables, model_slots) = abstract_metrics(&abstract_v);
    let (model_phases, initial_phase) = transition_metrics(&transition_v);
    let model_invs = array_len_or_zero(&invs);
    let model_checks = array_len_or_zero(&check_list);
    let mid = model_id(&mc, rel);
    Some(ScannedModel {
        row: Json::Object(vec![
            ("module".to_string(), Json::Str(mid)),
            ("source".to_string(), Json::Str(rel.to_string())),
            ("initial_phase".to_string(), initial_phase),
            ("phases".to_string(), Json::Int(model_phases)),
            ("invariants".to_string(), Json::Int(model_invs)),
            ("checks".to_string(), Json::Int(model_checks)),
            ("slots".to_string(), Json::Int(model_slots)),
        ]),
        variables: model_variables,
        phases: model_phases,
        invariants: model_invs,
        checks: model_checks,
        slots: model_slots,
    })
}

/// abstract_state 段 → (变量数, 挂槽位数)。
fn abstract_metrics(abstract_v: &Json) -> (i64, i64) {
    if !matches!(abstract_v, Json::Object(_)) {
        return (0, 0);
    }
    let var_list = arr_of(obj_get(abstract_v, "variables"));
    let variables = var_list.len() as i64;
    let slots = var_list
        .iter()
        .filter(|v| pyval::py_truthy(&get(v, "slot").unwrap_or(Json::Null)))
        .count() as i64;
    (variables, slots)
}

/// transition 段 → (相位声明数, initial_phase)。
fn transition_metrics(transition_v: &Json) -> (i64, Json) {
    if !matches!(transition_v, Json::Object(_)) {
        return (0, Json::Null);
    }
    let ps = arr_of(obj_get(transition_v, "phases"));
    (
        ps.len() as i64,
        get(transition_v, "initial_phase").unwrap_or(Json::Null),
    )
}

/// 数组声明 → 元素数；非数组按 0（真源 isinstance(list) 口径）。
fn array_len_or_zero(v: &Json) -> i64 {
    if matches!(v, Json::Array(_)) {
        arr_of(Some(v)).len() as i64
    } else {
        0
    }
}

/// 模块 id：机读段 id 真值，缺省回落到相对路径。
fn model_id(mc: &Json, rel: &str) -> String {
    match obj_get(mc, "id") {
        Some(v) if pyval::py_truthy(v) => pyval::plain_str(v),
        _ => rel.to_string(),
    }
}
