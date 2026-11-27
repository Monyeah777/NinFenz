use super::*;

pub(crate) fn str_json(v: &[String]) -> Json {
    Json::Array(v.iter().map(|s| Json::Str(s.clone())).collect())
}

/// 真源 `verify_certificate`。
pub(crate) fn verify_certificate(ctx: &Ctx, cert: &Json) -> (Vec<String>, Json) {
    let fresh = combine(
        ctx,
        &str_list(obj_get(cert, "packs")),
        &str_list(obj_get(cert, "extra_modules")),
        &[],
    );
    let mut issues: Vec<String> = Vec::new();
    for key in [
        "modules",
        "module_count",
        "layer_stacks",
        "dependency_closure",
        "event_closure",
        "assets_borrowed",
        "modules_borrowed",
        "legal",
        "digest",
    ] {
        let a = obj_get(&fresh, key).cloned().unwrap_or(Json::Null);
        let b = obj_get(cert, key).cloned().unwrap_or(Json::Null);
        if !crate::jsonread::json_eq(&a, &b) {
            issues.push(format!(
                "字段不一致：{}（复算 {} ≠ 在盘 {}）",
                key,
                pyval::py_repr(&a),
                pyval::py_repr(&b)
            ));
        }
    }
    (
        issues,
        Json::Object(vec![
            (
                "legal".to_string(),
                obj_get(&fresh, "legal").cloned().unwrap_or(Json::Null),
            ),
            (
                "modules".to_string(),
                obj_get(&fresh, "module_count")
                    .cloned()
                    .unwrap_or(Json::Null),
            ),
        ]),
    )
}

/// 真源 `breadth`（抽样器见 `pyrandom`，已单独判据钉住）。
pub(crate) fn breadth(
    root: &Path,
    ctx: &Ctx,
    triple_sample: usize,
    quad_sample: usize,
    quint_sample: usize,
    sext_sample: usize,
    seed: u64,
) -> Json {
    let verdict = |names: &[String]| -> (bool, Vec<Json>, Vec<Json>) {
        let cert = combine(ctx, names, &[], &[]);
        let legal = matches!(obj_get(&cert, "legal"), Some(Json::Bool(true)));
        let dangling =
            arr_of(obj_get(&cert, "dependency_closure").and_then(|d| obj_get(d, "dangling")))
                .into_iter()
                .take(2)
                .collect();
        let unbridged =
            arr_of(obj_get(&cert, "event_closure").and_then(|d| obj_get(d, "unbridged")))
                .into_iter()
                .take(2)
                .collect();
        (legal, dangling, unbridged)
    };
    let mut names: Vec<String> = ctx.prof.iter().map(|(k, _)| k.clone()).collect();
    names.sort();
    let mut failures: Vec<Json> = Vec::new();
    let (pairs, pairs_legal) = count_pairs(&names, &verdict, &mut failures);
    let _ = root;
    let mut rnd = crate::pyrandom::PyRandom::new(seed);
    let (mut triples, mut triples_legal) = (0i64, 0i64);
    for t in draw_samples(&mut rnd, &names, 3, triple_sample) {
        let (legal, _, _) = verdict(&t);
        triples += 1;
        if legal {
            triples_legal += 1;
        }
    }
    let (mut quads, mut quads_legal) = (0i64, 0i64);
    for q in draw_samples(&mut rnd, &names, 4, quad_sample) {
        let (legal, _, _) = verdict(&q);
        quads += 1;
        if legal {
            quads_legal += 1;
        }
    }
    let (mut quints, mut quints_legal) = (0i64, 0i64);
    for p in draw_samples(&mut rnd, &names, 5, quint_sample) {
        let (legal, _, _) = verdict(&p);
        quints += 1;
        if legal {
            quints_legal += 1;
        }
    }
    let (mut sexts, mut sexts_legal) = (0i64, 0i64);
    for p in draw_samples(&mut rnd, &names, 6, sext_sample) {
        let (legal, dangling, unbridged) = verdict(&p);
        sexts += 1;
        if legal {
            sexts_legal += 1;
        } else if failures.len() < 10 {
            failures.push(Json::Object(vec![
                ("combo".to_string(), str_json(&p)),
                ("dangling".to_string(), Json::Array(dangling)),
                ("unbridged".to_string(), Json::Array(unbridged)),
            ]));
        }
    }
    let all_legal = pairs == pairs_legal
        && triples == triples_legal
        && quads == quads_legal
        && quints == quints_legal
        && sexts == sexts_legal;
    Json::Object(vec![
        ("packs".to_string(), Json::Int(names.len() as i64)),
        ("pairs".to_string(), Json::Int(pairs)),
        ("pairs_legal".to_string(), Json::Int(pairs_legal)),
        ("triples".to_string(), Json::Int(triples)),
        ("triples_legal".to_string(), Json::Int(triples_legal)),
        ("quads".to_string(), Json::Int(quads)),
        ("quads_legal".to_string(), Json::Int(quads_legal)),
        ("quints".to_string(), Json::Int(quints)),
        ("quints_legal".to_string(), Json::Int(quints_legal)),
        ("sexts".to_string(), Json::Int(sexts)),
        ("sexts_legal".to_string(), Json::Int(sexts_legal)),
        ("failures".to_string(), Json::Array(failures)),
        ("all_legal".to_string(), Json::Bool(all_legal)),
    ])
}

/// 两两组合的合法性计数（失败样本最多记 10 条）。
pub(crate) fn count_pairs(
    names: &[String],
    verdict: &dyn Fn(&[String]) -> (bool, Vec<Json>, Vec<Json>),
    failures: &mut Vec<Json>,
) -> (i64, i64) {
    let mut pairs = 0i64;
    let mut pairs_legal = 0i64;
    for i in 0..names.len() {
        for j in (i + 1)..names.len() {
            let combo = vec![names[i].clone(), names[j].clone()];
            let (legal, dangling, unbridged) = verdict(&combo);
            pairs += 1;
            if legal {
                pairs_legal += 1;
            } else if failures.len() < 10 {
                failures.push(Json::Object(vec![
                    ("combo".to_string(), str_json(&combo)),
                    ("dangling".to_string(), Json::Array(dangling)),
                    ("unbridged".to_string(), Json::Array(unbridged)),
                ]));
            }
        }
    }
    (pairs, pairs_legal)
}

/// 无放回抽样：按 size 抽 want 组（去重后排序输出）。
pub(crate) fn draw_samples(
    r: &mut crate::pyrandom::PyRandom,
    names: &[String],
    size: usize,
    want: usize,
) -> Vec<Vec<String>> {
    let mut picks: BTreeSet<Vec<String>> = BTreeSet::new();
    if names.len() >= size {
        while picks.len() < std::cmp::min(want, 5000) {
            let mut s = r.sample(names, size);
            s.sort();
            picks.insert(s);
        }
    }
    picks.into_iter().collect()
}

/// 真源 `declared`。
pub(crate) fn declared(root: &Path) -> Json {
    let text = std::fs::read_to_string(root.join(crate::output_tables::CERT_REL));
    match text
        .ok()
        .and_then(|t| crate::jsonmini::parse(&t).ok().map(|r| r.value))
    {
        Some(v) => v,
        None => Json::Object(vec![
            (
                "schema".to_string(),
                Json::Str("nf-combo-certificates/1".to_string()),
            ),
            ("certificates".to_string(), Json::Array(vec![])),
        ]),
    }
}

/// 真源 `_certificate_lines`（缓存层不移植）。
pub(crate) fn certificate_lines(ctx: &Ctx, cert: &Json) -> Vec<String> {
    let schema = crate::jsonmini::parse(crate::output_tables::CERT_SCHEMA_JSON)
        .map(|r| r.value)
        .unwrap_or(Json::Object(vec![]));
    let schema_errs = crate::json_schema::json_schema_check(cert, &schema);
    let (sub, _st) = verify_certificate(ctx, cert);
    let name = {
        let l = s_of(obj_get(cert, "label"));
        if !l.is_empty() {
            l
        } else {
            let joined = str_list(obj_get(cert, "packs")).join("+");
            if joined.is_empty() {
                "<空>".to_string()
            } else {
                joined
            }
        }
    };
    let mut out: Vec<String> = schema_errs
        .iter()
        .take(4)
        .map(|e| format!("组合 {}: 证书不合 schema: {}", name, e))
        .collect();
    out.extend(sub.into_iter().map(|s| format!("组合 {}: {}", name, s)));
    out
}

/// 真源 `scan` → `(issues, stats)`。
pub(crate) fn scan(root: &Path) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let doc = declared(root);
    let certs = arr_of(obj_get(&doc, "certificates"));
    let contracts = pc::module_contracts(root);
    let prof = pc::profiles(root);
    let ctx = Ctx::build(root, contracts.clone(), prof.clone());
    let witness = pc::combo_witness(
        &prof,
        &contracts,
        &(
            ctx.by_id.clone(),
            ctx.pub_index.clone(),
            ctx.core_pub.clone(),
        ),
    );
    let _ = witness;
    for cert in &certs {
        issues.extend(certificate_lines(&ctx, cert));
    }
    let br = breadth(root, &ctx, 400, 200, 120, 60, 20260923);
    let all_legal = matches!(obj_get(&br, "all_legal"), Some(Json::Bool(true)));
    if !all_legal {
        let g = |k: &str| pyval::py_int_or(obj_get(&br, k), 0);
        issues.push(format!(
            "广度证明不成立：两两 {}/{} · 三元 {}/{} · 四元 {}/{} · 五元 {}/{} · 六元 {}/{}（样本 {}）",
            g("pairs_legal"),
            g("pairs"),
            g("triples_legal"),
            g("triples"),
            g("quads_legal"),
            g("quads"),
            g("quints_legal"),
            g("quints"),
            g("sexts_legal"),
            g("sexts"),
            pyval::py_repr_list(&arr_of(obj_get(&br, "failures")).into_iter().take(2).collect::<Vec<_>>())
        ));
    }
    (
        issues,
        Json::Object(vec![
            (
                "declared_certificates".to_string(),
                Json::Int(certs.len() as i64),
            ),
            ("breadth".to_string(), br),
        ]),
    )
}

/// 真源 `pack_combo.prof_get_module`：按 id（或末段）取模块记录。
pub(crate) fn prof_get_module(root: &Path, module_id: &str) -> Json {
    let contracts = pc::module_contracts(root);
    let (by_id, _pub, _core) = pc::indexes(root, &contracts);
    let mut hit = by_id
        .iter()
        .find(|(k, _)| k == module_id)
        .map(|(_, v)| v.clone());
    if hit.is_none() {
        let tail = module_id.rsplit(':').next().unwrap_or(module_id);
        hit = by_id
            .iter()
            .find(|(k, _)| k == tail)
            .map(|(_, v)| v.clone());
    }
    hit.unwrap_or(Json::Object(vec![]))
}

/// 真源 `pack_combo.combine(root, packs=..., extra_modules=..., extra_assets=...)` 的一次性入口。
///
/// 索引每次重建（真源用 `_CACHE` 兜住）。**只在少量调用点用**：`breadth` 里 6,900 次组合必须
/// 共用一份 `Ctx`，否则慢到不可用——见 `Ctx::build`。
pub(crate) fn combine_fresh(
    root: &Path,
    packs: &[String],
    extra_modules: &[String],
    extra_assets: &[String],
) -> Json {
    let contracts = pc::module_contracts(root);
    let prof = pc::profiles(root);
    let ctx = Ctx::build(root, contracts, prof);
    combine(&ctx, packs, extra_modules, extra_assets)
}
