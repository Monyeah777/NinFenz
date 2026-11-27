use super::*;

/// 条目 schema 在场 + 实例校验。
pub(crate) fn verify_entry_schema(
    root: &Path,
    pkg: &str,
    f: &EntryFacts,
    entry: &Json,
    issues: &mut Vec<String>,
) {
    let sch_rel = s_of(obj_get(&entry, "schema"));
    if !sch_rel.is_empty() {
        let full = match of::declared_out_rel(root, pkg, &Json::Str(sch_rel.clone())) {
            Ok(v) => v,
            Err(e) => {
                issues.push(format!("{}: {} {}", f.rel, f.path, e));
                String::new()
            }
        };
        let (schema, serr) = if full.is_empty() {
            (Json::Null, "schema 路径越界".to_string())
        } else {
            oc::read_json(root, &full)
        };
        if !serr.is_empty() {
            issues.push(format!("{}: {} schema {}", f.rel, f.path, serr));
        } else {
            let (inst, ierr) = oc::read_json(root, &f.out_rel);
            if !ierr.is_empty() {
                issues.push(format!("{}: {} {}", f.rel, f.path, ierr));
            } else {
                let errs = crate::json_schema::json_schema_check(&inst, &schema);
                for e in errs.iter().take(8) {
                    issues.push(format!("{}: {} schema 不符 {}", f.rel, f.path, e));
                }
            }
        }
    }
}

/// 产出面清单行（包 / 相对路径 / 形态 / 档位 / 角色）。
pub(crate) fn push_output_row(pkg: &str, f: &EntryFacts, entry: &Json, rows: &mut Vec<Json>) {
    rows.push(Json::Object(vec![
        ("package".to_string(), Json::Str(pkg.to_string())),
        ("path".to_string(), Json::Str(f.path.clone())),
        (
            "form".to_string(),
            Json::Str(if f.form.is_empty() {
            f.got_form.clone()
        } else {
            f.form.clone()
        }),
        ),
        ("tier".to_string(), Json::Str(f.tier.clone())),
        ("role".to_string(), Json::Str(s_of(obj_get(&entry, "role")))),
    ]));
}

/// 真源 `index_verify`（缓存层不移植）→ `(issues, stats)`。
pub(crate) fn index_verify(root: &Path) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let mut rows: Vec<Json> = Vec::new();
    let pkgs = pack_dirs(root);
    for pkg in &pkgs {
        let (i2, r2) = verify_pack(root, pkg);
        issues.extend(i2);
        rows.extend(r2);
    }
    let stats = Json::Object(vec![
        ("packages".to_string(), Json::Int(pkgs.len() as i64)),
        ("outputs".to_string(), Json::Int(rows.len() as i64)),
        ("by_role".to_string(), count(&rows, "role")),
        ("by_tier".to_string(), count(&rows, "tier")),
        ("by_form".to_string(), count(&rows, "form")),
    ]);
    (issues, stats)
}

/// 真源 `meter` → `(issues, stats)`（恒空 issues）。
pub(crate) fn meter(root: &Path) -> (Vec<String>, Json) {
    let mut packages: Vec<(String, Json)> = Vec::new();
    // 资产档面一次枚举（真源走共享枚举器；本线直接按模式枚举）
    let prose_by_pkg = meter_prose_map(root);
    let mut total_mv = 0i64;
    let mut total_fn = 0i64;
    let mut total_prose = 0i64;
    for pkg in pack_dirs(root) {
        let (idx, _err) = oc::read_json(root, &format!("community/{}/{}", pkg, of::INDEX_REL));
        let entries = arr_of(obj_get(&idx, "outputs"));
        let mv: Vec<Json> = entries
            .iter()
            .filter(|e| {
                matches!(obj_get(e, "tier"), Some(Json::Str(s)) if s == "T2" || s == "T3" || s == "T4")
            })
            .cloned()
            .collect();
        let fn_faces: Vec<Json> = entries
            .iter()
            .filter(|e| matches!(obj_get(e, "tier"), Some(Json::Str(s)) if s == "T4"))
            .cloned()
            .collect();
        let prose = prose_by_pkg.get(&pkg).cloned().unwrap_or_default();
        let denom = mv.len() + prose.len();
        let ratio = if denom == 0 {
            0.0
        } else {
            crate::pyfloat::round_to(mv.len() as f64 / denom as f64, 4)
        };
        let role_rows: Vec<Json> = entries
            .iter()
            .map(|e| {
                Json::Object(vec![(
                    "r".to_string(),
                    obj_get(e, "role").cloned().unwrap_or(Json::Null),
                )])
            })
            .collect();
        let tier_rows: Vec<Json> = entries
            .iter()
            .map(|e| {
                Json::Object(vec![(
                    "t".to_string(),
                    obj_get(e, "tier").cloned().unwrap_or(Json::Null),
                )])
            })
            .collect();
        total_mv += mv.len() as i64;
        total_fn += fn_faces.len() as i64;
        total_prose += prose.len() as i64;
        packages.push((
            pkg,
            Json::Object(vec![
                ("machine_verifiable".to_string(), Json::Int(mv.len() as i64)),
                ("functional".to_string(), Json::Int(fn_faces.len() as i64)),
                ("prose_assets".to_string(), Json::Int(prose.len() as i64)),
                ("machine_verifiable_ratio".to_string(), Json::Float(ratio)),
                ("roles".to_string(), count(&role_rows, "r")),
                ("tiers".to_string(), count(&tier_rows, "t")),
            ]),
        ));
    }
    let totals = if packages.is_empty() {
        Json::Object(vec![])
    } else {
        let denom = std::cmp::max(1, total_mv + total_prose) as f64;
        Json::Object(vec![
            ("machine_verifiable".to_string(), Json::Int(total_mv)),
            ("functional".to_string(), Json::Int(total_fn)),
            ("prose_assets".to_string(), Json::Int(total_prose)),
            (
                "machine_verifiable_ratio".to_string(),
                Json::Float(crate::pyfloat::round_to(total_mv as f64 / denom, 4)),
            ),
        ])
    };
    (
        Vec::new(),
        Json::Object(vec![
            ("packages".to_string(), Json::Object(packages)),
            ("totals".to_string(), totals),
        ]),
    )
}

/// 资产档面枚举：包名 → 资产 md 文件名（README 不算）。
fn meter_prose_map(root: &Path) -> BTreeMap<String, Vec<String>> {
    let mut prose_by_pkg: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut rels = crate::glob::expand(root, "community/*/assets/*.md");
    rels.sort();
    for rel in rels {
        let parts: Vec<&str> = rel.split('/').collect();
        if parts.len() == 4 && parts[3] != "README.md" {
            prose_by_pkg
                .entry(parts[1].to_string())
                .or_default()
                .push(parts[3].to_string());
        }
    }
    prose_by_pkg
}

/// 真源 `baseline_verify` → `(issues, stats)`。
pub(crate) fn baseline_verify(root: &Path) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let (base, err) = oc::read_json(root, of::BASELINE_REL);
    let (_, stats) = meter(root);
    if !err.is_empty() {
        return (
            vec![format!(
                "{} 缺失或不可解析（{}；重签：nf output meter --write）",
                of::BASELINE_REL,
                err
            )],
            stats,
        );
    }
    let prev = match obj_get(&base, "packages") {
        Some(Json::Object(o)) => o.clone(),
        _ => Vec::new(),
    };
    if let Some(Json::Object(cur)) = obj_get(&stats, "packages") {
        for (pkg, c) in cur {
            let Some(old) = prev.iter().find(|(k, _)| k == pkg).map(|(_, v)| v) else {
                continue;
            };
            let old_mv = pyval::py_int_or(obj_get(old, "machine_verifiable"), 0);
            let cur_mv = pyval::py_int_or(obj_get(c, "machine_verifiable"), 0);
            if cur_mv < old_mv {
                issues.push(format!(
                    "{} 机验产出面回退：{} → {}（基线 {}）",
                    pkg,
                    old_mv,
                    cur_mv,
                    of::BASELINE_REL
                ));
            }
            let old_fn = pyval::py_int_or(obj_get(old, "functional"), 0);
            let cur_fn = pyval::py_int_or(obj_get(c, "functional"), 0);
            if cur_fn < old_fn {
                issues.push(format!(
                    "{} 功能面（T4 可复算）回退：{} → {}",
                    pkg, old_fn, cur_fn
                ));
            }
        }
    }
    let mut merged: Vec<(String, Json)> = vec![(
        "baseline".to_string(),
        Json::Bool(!matches!(&base, Json::Null)),
    )];
    if let Json::Object(o) = &stats {
        merged.extend(o.clone());
    }
    (issues, Json::Object(merged))
}

/// 真源 `scan`（`memo_pair` 缓存层不移植）→ `(issues, stats)`。
pub(crate) fn scan(root: &Path) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let (reg_issues, reg_stats) = of::registry_verify(root);
    for i in reg_issues {
        issues.push(format!("形态清单: {}", i));
    }
    let (idx_issues, idx_stats) = index_verify(root);
    for i in idx_issues {
        issues.push(format!("包级产出面: {}", i));
    }
    let (base_issues, base_stats) = baseline_verify(root);
    for i in base_issues {
        issues.push(format!("机验率基线: {}", i));
    }
    let meter_pkgs = obj_get(&base_stats, "packages")
        .cloned()
        .unwrap_or(Json::Object(vec![]));
    (
        issues,
        Json::Object(vec![
            ("registry".to_string(), reg_stats),
            ("index".to_string(), idx_stats),
            ("meter".to_string(), meter_pkgs),
        ]),
    )
}
