use super::*;

/// initial 面：未声明变量 / 缺初始值 / 值类型不符。
pub(crate) fn check_initial(
    label: &str,
    initial: Option<&Json>,
    valid_vars: &[Json],
    issues: &mut Vec<String>,
) {
    if let Some(init @ Json::Object(_)) = initial {
        let declared: Vec<String> = valid_vars
            .iter()
            .filter_map(|v| match get(v, "name") {
                Some(Json::Str(s)) => Some(s),
                _ => None,
            })
            .collect();
        let mut keys: Vec<String> = match init {
            Json::Object(o) => o.iter().map(|(k, _)| k.clone()).collect(),
            _ => Vec::new(),
        };
        keys.sort();
        for key in keys {
            if !declared.contains(&key) {
                issues.push(format!(
                    "{}.abstract_state.initial: 未声明变量 {}",
                    label,
                    pyval::py_repr(&Json::Str(key))
                ));
            }
        }
        for var in valid_vars {
            let name = match get(var, "name") {
                Some(Json::Str(s)) => s,
                _ => continue,
            };
            if !has(init, &name) {
                issues.push(format!(
                    "{}.abstract_state.initial: 缺变量 {} 的初始值",
                    label,
                    pyval::py_repr(&Json::Str(name))
                ));
                continue;
            }
            let kind = match get(var, "kind") {
                Some(Json::Str(s)) => s,
                _ => String::new(),
            };
            let item_kind = match get(var, "item_kind") {
                Some(Json::Str(s)) => Some(s),
                _ => None,
            };
            let value = obj_get(init, &name).cloned().unwrap_or(Json::Null);
            if KINDS.contains(&kind.as_str()) && !matches(&value, &kind, item_kind.as_deref()) {
                issues.push(format!(
                    "{}.abstract_state.initial.{}: 值 {} 不匹配 kind={}",
                    label,
                    name,
                    pyval::py_repr(&value),
                    pyval::py_repr(&Json::Str(kind))
                ));
            }
        }
    }
}

/// transition 骨架解析（initial_phase / phases）。
pub(crate) fn parse_transition(
    wm: &Json,
    label: &str,
    issues: &mut Vec<String>,
) -> (Option<String>, Vec<Json>) {
    let transition_v = get(wm, "transition");
    let mut initial_phase: Option<String> = None;
    let mut phases: Vec<Json> = Vec::new();
    match &transition_v {
        Some(t @ Json::Object(_)) => {
            let ip = get(t, "initial_phase");
            match &ip {
                Some(Json::Str(s)) if !s.trim().is_empty() => initial_phase = Some(s.clone()),
                _ => {
                    issues.push(format!("{}.transition.initial_phase: 非空字符串", label));
                }
            }
            match get(t, "phases") {
                Some(Json::Array(p)) if !p.is_empty() => phases = p,
                _ => issues.push(format!("{}.transition.phases: 非空数组", label)),
            }
        }
        _ => {
            issues.push(format!("{}.transition: 缺失或非对象", label));
        }
    }
    (initial_phase, phases)
}

/// 相位面的 phase / next / guard / writes 核对与边表构建。
pub(crate) fn check_phases(
    label: &str,
    phases: &[Json],
    issues: &mut Vec<String>,
) -> (Vec<String>, Vec<(String, String)>) {
    let mut phase_names: Vec<String> = Vec::new();
    let mut edges: Vec<(String, String)> = Vec::new();
    for (idx, phase) in phases.iter().enumerate() {
        let at = format!("{}.transition.phases[{}]", label, idx);
        if !matches!(phase, Json::Object(_)) {
            issues.push(format!("{}: 非对象", at));
            continue;
        }
        let pname_v = get(phase, "phase");
        let nxt_v = get(phase, "next");
        let guard_v = get(phase, "guard");
        let writes_v = get(phase, "writes");
        let pname = match &pname_v {
            Some(Json::Str(s)) if !s.trim().is_empty() => s.clone(),
            _ => {
                issues.push(format!("{}.phase: 非空字符串", at));
                continue;
            }
        };
        if phase_names.contains(&pname) {
            issues.push(format!(
                "{}.phase: 相位重名 {}",
                at,
                pyval::py_repr(&Json::Str(pname.clone()))
            ));
        }
        phase_names.push(pname.clone());
        let nxt_ok = matches!(&nxt_v, Some(Json::Str(s)) if !s.trim().is_empty());
        if !nxt_ok {
            issues.push(format!("{}.next: 非空字符串", at));
        }
        let guard_ok = matches!(&guard_v, Some(Json::Str(s)) if !s.trim().is_empty());
        if !guard_ok {
            issues.push(format!("{}.guard: 非空守卫说明", at));
        }
        let writes_ok = match &writes_v {
            Some(Json::Array(w)) => w
                .iter()
                .all(|x| matches!(x, Json::Str(s) if !s.trim().is_empty())),
            _ => false,
        };
        if !writes_ok {
            issues.push(format!("{}.writes: 字符串数组（可为空）", at));
        }
        if let (Json::Str(p), Json::Str(n)) = (
            &pname_v.clone().unwrap_or(Json::Null),
            &nxt_v.clone().unwrap_or(Json::Null),
        ) {
            // ⚠️ 真源 `edges` 是 **dict**（`edges[pname] = nxt`）⇒ **后者覆盖前者**，且**保留首次
            // 插入的位置**。用 Vec 追加会同时改变两处结论：①「next 无对应相位」会报出已被覆盖
            // 的旧值；② `all(n in phase_set ...)` 会因旧值悬空而**整段跳过**，漏报不可达相位。
            // 实测（2026-10-04，合成夹具 M92）：`begin→ghost` 被 `begin→begin` 覆盖，两处结论相反。
            match edges.iter_mut().find(|(k, _)| *k == *p) {
                Some(slot) => slot.1 = n.clone(),
                None => edges.push((p.clone(), n.clone())),
            }
        }
    }
    (phase_names, edges)
}

/// initial_phase 在位 + next 指向存在 + 从初始相位可达性。
pub(crate) fn check_reachability(
    label: &str,
    initial_phase: Option<&str>,
    phase_names: &[String],
    edges: &[(String, String)],
    issues: &mut Vec<String>,
) {
    if let Some(ip) = initial_phase {
        if !phase_names.iter().any(|p| p == ip) {
            issues.push(format!(
                "{}.transition.initial_phase: {} 不在 phases 内",
                label,
                pyval::py_repr(&Json::Str(ip.to_string()))
            ));
        }
    }
    for (pname, nxt) in edges {
        if !phase_names.contains(nxt) {
            issues.push(format!(
                "{}.transition.phases[{}].next: {} 无对应相位",
                label,
                pyval::py_repr(&Json::Str(pname.clone())),
                pyval::py_repr(&Json::Str(nxt.clone()))
            ));
        }
    }

    let all_next_ok = edges.iter().all(|(_, n)| phase_names.contains(n));
    if let Some(ip0) = initial_phase {
        if phase_names.iter().any(|p| p == ip0) && all_next_ok {
            let mut seen: Vec<String> = vec![ip0.to_string()];
            let mut frontier: Vec<String> = vec![ip0.to_string()];
            while !frontier.is_empty() {
                let current = frontier.remove(0);
                if let Some((_, nxt)) = edges.iter().find(|(p, _)| *p == current) {
                    if !seen.contains(nxt) {
                        seen.push(nxt.clone());
                        frontier.push(nxt.clone());
                    }
                }
            }
            let mut unreachable: Vec<String> = phase_names
                .iter()
                .filter(|n| !seen.contains(n))
                .cloned()
                .collect();
            unreachable.sort();
            unreachable.dedup();
            if !unreachable.is_empty() {
                issues.push(format!(
                    "{}.transition: 从 initial_phase 不可达的相位 {}",
                    label,
                    pyval::py_repr_list(
                        &unreachable
                            .iter()
                            .map(|s| Json::Str(s.clone()))
                            .collect::<Vec<_>>()
                    )
                ));
            }
        }
    }
}

/// invariants 面：非空字符串数组。
pub(crate) fn check_invariants(wm: &Json, label: &str, issues: &mut Vec<String>) {
    let invariants_v = get(wm, "invariants");
    match &invariants_v {
        Some(Json::Array(inv)) if !inv.is_empty() => {
            for (idx, i) in inv.iter().enumerate() {
                if !matches!(i, Json::Str(s) if !s.trim().is_empty()) {
                    issues.push(format!("{}.invariants[{}]: 非空字符串", label, idx));
                }
            }
        }
        _ => issues.push(format!("{}.invariants: 非空数组", label)),
    }
}

/// 已声明变量名与 (名, kind) 表，供 checks 面引用。
pub(crate) fn declared_names_kinds(valid_vars: &[Json]) -> (Vec<String>, Vec<(String, String)>) {
    let declared_names: Vec<String> = valid_vars
        .iter()
        .filter_map(|v| match get(v, "name") {
            Some(Json::Str(s)) => Some(s),
            _ => None,
        })
        .collect();
    let declared_kinds: Vec<(String, String)> = valid_vars
        .iter()
        .filter_map(|v| match (get(v, "name"), get(v, "kind")) {
            (Some(Json::Str(n)), Some(Json::Str(k))) => Some((n, k)),
            _ => None,
        })
        .collect();
    (declared_names, declared_kinds)
}
