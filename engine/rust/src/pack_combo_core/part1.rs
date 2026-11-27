use super::*;

/// 用到的那几个索引（一次构建、全程共用）。
pub(crate) struct Ctx {
    pub prof: Vec<(String, Json)>,
    pub contracts: Vec<(String, Json)>,
    pub by_id: Vec<(String, Json)>,
    pub pub_index: Vec<(String, Vec<Json>)>,
    pub core_pub: BTreeSet<String>,
}

impl Ctx {
    pub fn build(root: &Path, contracts: Vec<(String, Json)>, prof: Vec<(String, Json)>) -> Ctx {
        let (by_id, pub_index, core_pub) = pc::indexes(root, &contracts);
        Ctx {
            prof,
            contracts,
            by_id,
            pub_index,
            core_pub,
        }
    }
}

pub(crate) fn find_rec<'a>(v: &'a [(String, Json)], key: &str) -> Option<Json> {
    if let Some((_, r)) = v.iter().find(|(k, _)| k == key) {
        return Some(r.clone());
    }
    let tail = key.rsplit(':').next().unwrap_or(key);
    v.iter().find(|(k, _)| k == tail).map(|(_, r)| r.clone())
}

/// 真源 `combine`。
pub(crate) fn combine(
    ctx: &Ctx,
    packs: &[String],
    extra_modules: &[String],
    extra_assets: &[String],
) -> Json {
    let (unknown, chosen, mut mods) = collect_selected(ctx, packs, extra_modules);
    let mut borrowed: Vec<Json> = Vec::new();
    let mut unresolved_refs: Vec<Json> = Vec::new();
    collect_references(ctx, &chosen, &mut mods, &mut borrowed, &mut unresolved_refs);

    // 不动点闭包：依赖 inputs ∪ 事件发布方（递归），直到不再新增
    let core = pc::core_ids();
    for _round in 0..12 {
        let mut grew = false;
        grew |= pull_dependencies(ctx, &core, &mut mods, &mut borrowed);
        grew |= pull_event_publishers(ctx, &mut mods, &mut borrowed);
        if !grew {
            break;
        }
    }

    let (missing_contracts, dangling) = collect_dangling(&mods);
    let (published, unbridged, unpublished) = collect_event_closure(ctx, &mods);
    let (canon_packs, stack_list) = collect_stacks(packs, &chosen, &mods);
    let (borrow, mut unresolved) = collect_assets(ctx, &chosen, &mods, extra_assets);
    let (
        borrow_sorted,
        borrowed_sorted,
        refs_sorted,
        unknown_sorted,
        explicit,
        core_list,
        extra_sorted,
        mod_ids,
    ) = prepare_lists(
        &borrow,
        &borrowed,
        &unresolved_refs,
        &unknown,
        &mods,
        &core,
        extra_modules,
    );
    unresolved.sort();

    let mut cert = Json::Object(vec![
        ("schema".to_string(), Json::Str("nf-combo/1".to_string())),
        ("packs".to_string(), str_json(&canon_packs)),
        ("unknown_packs".to_string(), str_json(&unknown_sorted)),
        ("extra_modules".to_string(), str_json(&extra_sorted)),
        ("modules".to_string(), str_json(&mod_ids)),
        ("module_count".to_string(), Json::Int(mods.len() as i64)),
        ("layer_stacks".to_string(), Json::Array(stack_list)),
        (
            "dependency_closure".to_string(),
            Json::Object(vec![
                ("core".to_string(), str_json(&core_list)),
                ("explicit".to_string(), str_json(&explicit)),
                ("dangling".to_string(), Json::Array(dangling.clone())),
            ]),
        ),
        (
            "event_closure".to_string(),
            Json::Object(vec![
                (
                    "published".to_string(),
                    str_json(&published.iter().cloned().collect::<Vec<_>>()),
                ),
                ("unbridged".to_string(), str_json(&unbridged)),
            ]),
        ),
        ("events_unpublished".to_string(), str_json(&unpublished)),
        ("assets_borrowed".to_string(), Json::Array(borrow_sorted)),
        ("modules_borrowed".to_string(), Json::Array(borrowed_sorted)),
        (
            "references_unresolved".to_string(),
            Json::Array(refs_sorted),
        ),
        ("assets_unresolved".to_string(), str_json(&unresolved)),
        (
            "module_missing_contract".to_string(),
            str_json(&missing_contracts),
        ),
    ]);
    finish_cert(
        &mut cert,
        &unknown,
        &dangling,
        &unbridged,
        &missing_contracts,
        &unresolved,
        &unresolved_refs,
    );
    cert
}

/// legal 位与证书摘要的收尾写入。
pub(crate) fn finish_cert(
    cert: &mut Json,
    unknown: &[String],
    dangling: &[Json],
    unbridged: &[String],
    missing_contracts: &[String],
    unresolved: &[String],
    unresolved_refs: &[Json],
) {
    let legal = unknown.is_empty()
        && dangling.is_empty()
        && unbridged.is_empty()
        && missing_contracts.is_empty()
        && unresolved.is_empty()
        && unresolved_refs.is_empty();
    if let Json::Object(o) = &mut *cert {
        o.push(("legal".to_string(), Json::Bool(legal)));
    }
    let dg = pc::digest_of_cert(cert);
    if let Json::Object(o) = &mut *cert {
        o.push(("digest".to_string(), Json::Str(dg)));
    }
}

/// 选择 packs 对应的画像，并用模块记录 / 额外模块建 mods 表。
pub(crate) fn collect_selected(
    ctx: &Ctx,
    packs: &[String],
    extra_modules: &[String],
) -> (Vec<String>, Vec<Json>, Vec<(String, Json)>) {
    let mut unknown: Vec<String> = Vec::new();
    let mut chosen: Vec<Json> = Vec::new();
    for p in packs {
        match ctx.prof.iter().find(|(k, _)| k == p) {
            Some((_, r)) => chosen.push(r.clone()),
            None => unknown.push(p.clone()),
        }
    }
    let mut mods: Vec<(String, Json)> = Vec::new();
    for pr in &chosen {
        for rec in arr_of(obj_get(pr, "module_recs")) {
            let id = s_of(obj_get(&rec, "id"));
            match mods.iter_mut().find(|(k, _)| *k == id) {
                Some(slot) => slot.1 = rec,
                None => mods.push((id, rec)),
            }
        }
    }
    for mid in extra_modules {
        if let Some(rec) = find_rec(&ctx.contracts, mid) {
            let id = s_of(obj_get(&rec, "id"));
            match mods.iter_mut().find(|(k, _)| *k == id) {
                Some(slot) => slot.1 = rec,
                None => mods.push((id, rec)),
            }
        }
    }
    (unknown, chosen, mods)
}

/// 各包 references 的模块借用 / 未解析引用归集。
pub(crate) fn collect_references(
    ctx: &Ctx,
    chosen: &[Json],
    mods: &mut Vec<(String, Json)>,
    borrowed: &mut Vec<Json>,
    unresolved_refs: &mut Vec<Json>,
) {
    for pr in chosen {
        for r in arr_of(obj_get(pr, "references")) {
            let src = s_of(obj_get(&r, "source_package"));
            let mid = s_of(obj_get(&r, "module_id"));
            match find_rec(&ctx.contracts, &mid) {
                Some(rec) => {
                    let id = s_of(obj_get(&rec, "id"));
                    if mods.iter().any(|(k, _)| *k == id) {
                        continue;
                    }
                    let rec_pack = s_of(obj_get(&rec, "pack"));
                    mods.push((id.clone(), rec));
                    if rec_pack == src {
                        borrowed.push(Json::Object(vec![
                            ("module".to_string(), Json::Str(id)),
                            ("from".to_string(), Json::Str(src.clone())),
                            ("by".to_string(), Json::Str(s_of(obj_get(pr, "package")))),
                            ("mode".to_string(), Json::Str("module_borrow".to_string())),
                        ]));
                    } else {
                        borrowed.push(Json::Object(vec![
                            ("module".to_string(), Json::Str(id)),
                            ("from".to_string(), Json::Str(rec_pack)),
                            ("by".to_string(), Json::Str(s_of(obj_get(pr, "package")))),
                            ("mode".to_string(), Json::Str("module_borrow".to_string())),
                        ]));
                    }
                }
                None => unresolved_refs.push(Json::Object(vec![
                    ("by".to_string(), Json::Str(s_of(obj_get(pr, "package")))),
                    ("source_package".to_string(), Json::Str(src)),
                    ("module_id".to_string(), Json::Str(mid)),
                ])),
            }
        }
    }
}
