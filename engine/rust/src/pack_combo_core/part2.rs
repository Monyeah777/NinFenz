use super::*;

/// 不动点一轮：依赖 inputs 递归拉入；返回是否新增。
pub(crate) fn pull_dependencies(
    ctx: &Ctx,
    core: &BTreeSet<String>,
    mods: &mut Vec<(String, Json)>,
    borrowed: &mut Vec<Json>,
) -> bool {
let mut grew = false;
    let snapshot: Vec<(String, Json)> = mods.clone();
    for (m, r) in &snapshot {
        for dep in str_list(obj_get(r, "inputs")) {
            let tail = dep.rsplit(':').next().unwrap_or(&dep).to_string();
            if core.contains(&dep)
                || core.contains(&tail)
                || mods.iter().any(|(k, _)| *k == dep)
            {
                continue;
            }
            if let Some(rec) = find_rec(&ctx.by_id, &dep) {
                let id = s_of(obj_get(&rec, "id"));
                if !mods.iter().any(|(k, _)| *k == id) {
                    // 真源 `_add(rec, why, by)`：`from = rec["pack"]`，`by = by or "<组件级>"`
                    // ⚠️ 必须在 `mods.push` **之前**取 pack —— push 会把 rec 移走。
                    let from_pack = s_of(obj_get(&rec, "pack"));
                    mods.push((id.clone(), rec));
                    let by = if m.is_empty() {
                        "<组件级>".to_string()
                    } else {
                        m.clone()
                    };
                    borrowed.push(Json::Object(vec![
                        ("module".to_string(), Json::Str(id)),
                        ("from".to_string(), Json::Str(from_pack)),
                        ("by".to_string(), Json::Str(by)),
                        ("mode".to_string(), Json::Str("closure_pull".to_string())),
                        (
                            "why".to_string(),
                            Json::Str(format!("依赖 {} 的 inputs 需要 {}", m, dep)),
                        ),
                    ]));
                    grew = true;
                }
            }
        }
    }
grew
}

/// 不动点一轮：事件订阅无发布方时递归拉入发布方；返回是否新增。
pub(crate) fn pull_event_publishers(
    ctx: &Ctx,
    mods: &mut Vec<(String, Json)>,
    borrowed: &mut Vec<Json>,
) -> bool {
let mut grew = false;
    let mut published_now: BTreeSet<String> = ctx.core_pub.clone();
    for (_, x) in mods.iter() {
        for e in str_list(obj_get(x, "publish")) {
            published_now.insert(e);
        }
    }
    let snapshot2: Vec<(String, Json)> = mods.clone();
    for (m, r) in &snapshot2 {
        for ev in str_list(obj_get(r, "subscribe")) {
            if published_now.contains(&ev) {
                continue;
            }
            let Some(recs) = ctx
                .pub_index
                .iter()
                .find(|(k, _)| *k == ev)
                .map(|(_, v)| v.clone())
            else {
                continue;
            };
            for rec in recs {
                let id = s_of(obj_get(&rec, "id"));
                if !mods.iter().any(|(k, _)| *k == id) {
                    let from_pack = s_of(obj_get(&rec, "pack"));
                    mods.push((id.clone(), rec));
                    let by = if m.is_empty() {
                        "<组件级>".to_string()
                    } else {
                        m.clone()
                    };
                    borrowed.push(Json::Object(vec![
                        ("module".to_string(), Json::Str(id)),
                        ("from".to_string(), Json::Str(from_pack)),
                        ("by".to_string(), Json::Str(by)),
                        ("mode".to_string(), Json::Str("closure_pull".to_string())),
                        (
                            "why".to_string(),
                            Json::Str(format!("事件 {} 需要发布方（{} 订阅）", ev, m)),
                        ),
                    ]));
                    grew = true;
                }
            }
        }
    }
grew
}

/// 缺契约模块表 + 悬空 inputs。
pub(crate) fn collect_dangling(mods: &[(String, Json)]) -> (Vec<String>, Vec<Json>) {
    let core = pc::core_ids();
    let mut missing_contracts: Vec<String> = mods
        .iter()
        .filter(|(_, r)| s_of(obj_get(r, "path")).is_empty())
        .map(|(k, _)| k.clone())
        .collect();
    missing_contracts.sort();
    let mut sorted_mods = mods.to_vec();
    sorted_mods.sort_by(|a, b| a.0.cmp(&b.0));
    let mut dangling: Vec<Json> = Vec::new();
    for (m, r) in &sorted_mods {
        for dep in str_list(obj_get(r, "inputs")) {
            let tail = dep.rsplit(':').next().unwrap_or(&dep).to_string();
            if core.contains(&dep) || core.contains(&tail) || mods.iter().any(|(k, _)| *k == dep) {
                continue;
            }
            dangling.push(Json::Object(vec![
                ("module".to_string(), Json::Str(m.clone())),
                ("needs".to_string(), Json::Str(dep)),
            ]));
        }
    }
    (missing_contracts, dangling)
}

/// 事件面：已发布集 / 未桥接 / 无发布方。
pub(crate) fn collect_event_closure(
    ctx: &Ctx,
    mods: &[(String, Json)],
) -> (BTreeSet<String>, Vec<String>, Vec<String>) {
    let mut published: BTreeSet<String> = BTreeSet::new();
    for (_, r) in mods {
        for e in str_list(obj_get(r, "publish")) {
            published.insert(e);
        }
    }
    for e in &ctx.core_pub {
        published.insert(e.clone());
    }
    let mut unbridged: Vec<String> = BTreeSet::from_iter(
        mods.iter()
            .flat_map(|(_, r)| str_list(obj_get(r, "subscribe")))
            .filter(|e| !published.contains(e)),
    )
    .into_iter()
    .collect();
    unbridged.sort();
    let mut unpublished: Vec<String> = BTreeSet::from_iter(
        mods.iter()
            .flat_map(|(_, r)| str_list(obj_get(r, "subscribe")))
            .filter(|e| !published.contains(e) && !ctx.pub_index.iter().any(|(k, _)| k == e)),
    )
    .into_iter()
    .collect();
    unpublished.sort();
    (published, unbridged, unpublished)
}

/// 层栈：按包序与模块层位归并去重。
pub(crate) fn collect_stacks(
    packs: &[String],
    chosen: &[Json],
    mods: &[(String, Json)],
) -> (Vec<String>, Vec<Json>) {
    let mut sorted_mods = mods.to_vec();
    sorted_mods.sort_by(|a, b| a.0.cmp(&b.0));
    let mut canon_packs: Vec<String> = packs.to_vec();
    canon_packs.sort();
    canon_packs.dedup();
    let order: BTreeMap<String, usize> = canon_packs
        .iter()
        .enumerate()
        .map(|(i, p)| (p.clone(), i))
        .collect();
    let mut stacks: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for pr in chosen {
        if let Some(Json::Object(ls)) = obj_get(pr, "layers") {
            for (lay, ms) in ls {
                let entry = stacks.entry(lay.clone()).or_default();
                for m in arr_of(Some(ms)).iter().map(pyval::plain_str) {
                    if !entry.contains(&m) {
                        entry.push(m);
                    }
                }
            }
        }
    }
    for (m, r) in &sorted_mods {
        let lay = s_of(obj_get(r, "layer"));
        if !lay.is_empty() {
            let entry = stacks.entry(lay).or_default();
            if !entry.contains(m) {
                entry.push(m.clone());
            }
        }
    }
    let mut stacks2: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for (k, v) in &stacks {
        let mut uniq: Vec<String> = v.clone();
        uniq.sort();
        uniq.dedup();
        uniq.sort_by_key(|x| {
            let pack = mods
                .iter()
                .find(|(kk, _)| kk == x)
                .map(|(_, r)| s_of(obj_get(r, "pack")))
                .unwrap_or_default();
            (order.get(&pack).copied().unwrap_or(99), x.clone())
        });
        stacks2.insert(k.clone(), uniq);
    }
    let stack_list: Vec<Json> = stacks2
        .iter()
        .map(|(k, v)| {
            Json::Object(vec![
                ("layer".to_string(), Json::Str(k.clone())),
                (
                    "modules".to_string(),
                    Json::Array(v.iter().map(|s| Json::Str(s.clone())).collect()),
                ),
            ])
        })
        .collect();
    (canon_packs, stack_list)
}

/// 资产借阅面：按包内资产与额外资产声明归集。
pub(crate) fn collect_assets(
    ctx: &Ctx,
    chosen: &[Json],
    mods: &[(String, Json)],
    extra_assets: &[String],
) -> (Vec<Json>, Vec<String>) {
    // 资产：借阅面
    let mut asset_index: Vec<((String, String), Json)> = Vec::new();
    for (pn, pr) in &ctx.prof {
        for a in arr_of(obj_get(pr, "assets")) {
            asset_index.push(((pn.clone(), s_of(obj_get(&a, "key"))), a.clone()));
        }
    }
    let mut borrow: Vec<Json> = Vec::new();
    let mut unresolved: Vec<String> = Vec::new();
    for pr in chosen {
        for a in arr_of(obj_get(pr, "assets")) {
            let m = s_of(obj_get(&a, "module"));
            if !m.is_empty() && !mods.iter().any(|(k, _)| *k == m) {
                borrow.push(Json::Object(vec![
                    ("key".to_string(), Json::Str(s_of(obj_get(&a, "key")))),
                    ("from".to_string(), Json::Str(s_of(obj_get(pr, "package")))),
                    ("for_module".to_string(), Json::Str(m)),
                    ("mode".to_string(), Json::Str("asset_readonly".to_string())),
                ]));
            }
        }
    }
    for spec in extra_assets {
        let (pkg, key) = match spec.split_once(':') {
            Some((a, b)) => (a.to_string(), b.to_string()),
            None => (spec.clone(), String::new()),
        };
        if asset_index.iter().any(|((p, k), _)| *p == pkg && *k == key) {
            borrow.push(Json::Object(vec![
                ("key".to_string(), Json::Str(key)),
                ("from".to_string(), Json::Str(pkg)),
                ("for_module".to_string(), Json::Str(String::new())),
                ("mode".to_string(), Json::Str("asset_readonly".to_string())),
            ]));
        } else {
            unresolved.push(spec.clone());
        }
    }
    (borrow, unresolved)
}

/// 各输出列表的排序与派生（借阅表 / 引用 / 未知包 / 依赖与模块 id）。
#[allow(clippy::type_complexity)]
pub(crate) fn prepare_lists(
    borrow: &[Json],
    borrowed: &[Json],
    unresolved_refs: &[Json],
    unknown: &[String],
    mods: &[(String, Json)],
    core: &BTreeSet<String>,
    extra_modules: &[String],
) -> (
    Vec<Json>,
    Vec<Json>,
    Vec<Json>,
    Vec<String>,
    Vec<String>,
    Vec<String>,
    Vec<String>,
    Vec<String>,
) {
    let mut borrow_sorted = borrow.to_vec();
    borrow_sorted.sort_by_key(|x| (s_of(obj_get(x, "from")), s_of(obj_get(x, "key"))));
    let mut borrowed_sorted = borrowed.to_vec();
    borrowed_sorted.sort_by_key(|x| (s_of(obj_get(x, "by")), s_of(obj_get(x, "module"))));
    let mut refs_sorted = unresolved_refs.to_vec();
    refs_sorted.sort_by_key(|x| (s_of(obj_get(x, "by")), s_of(obj_get(x, "module_id"))));
    let mut unknown_sorted = unknown.to_vec();
    unknown_sorted.sort();

    let explicit: Vec<String> = BTreeSet::from_iter(
        mods.iter()
            .flat_map(|(_, r)| str_list(obj_get(r, "inputs")))
            .filter(|d| mods.iter().any(|(k, _)| k == d)),
    )
    .into_iter()
    .collect();
    let mut core_list: Vec<String> = core.iter().cloned().collect();
    core_list.sort();
    let mut extra_sorted: Vec<String> = extra_modules.to_vec();
    extra_sorted.sort();
    extra_sorted.dedup();
    let mut mod_ids: Vec<String> = mods.iter().map(|(k, _)| k.clone()).collect();
    mod_ids.sort();
    (
        borrow_sorted,
        borrowed_sorted,
        refs_sorted,
        unknown_sorted,
        explicit,
        core_list,
        extra_sorted,
        mod_ids,
    )
}
