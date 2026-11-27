use super::*;

/// 名录单包：包目录 / protocol.yaml / outputs/INDEX.json 的在场与声明核对。
pub(crate) fn check_pack_files(
    root: &Path,
    p: &Json,
    pkg: &str,
    issues: &mut Vec<String>,
) -> Option<Vec<Json>> {
    let proto = root.join("community").join(&pkg).join("protocol.yaml");
    if !proto.is_file() {
        issues.push(format!("{}：包目录或 protocol.yaml 缺失", pkg));
        return None;
    }
    let text = read_text(&proto);
    for tok in [obj_get(&p, "pipeline"), obj_get(&p, "category")] {
        let t = tok.map(pyval::plain_str).unwrap_or_default();
        if !text.contains(&t) {
            issues.push(format!("{}：protocol.yaml 缺名录声明 {}", pkg, t));
        }
    }
    let idx_path = root
        .join("community")
        .join(&pkg)
        .join("outputs")
        .join("INDEX.json");
    if !idx_path.is_file() {
        issues.push(format!("{}：缺 outputs/INDEX.json", pkg));
        return None;
    }
    let faces: Vec<Json> = match read_json_opt(&idx_path) {
        Some(v) => arr_of(obj_get(&v, "outputs")),
        None => Vec::new(),
    };
Some(faces)
}

/// 名录单包：可机验产出占比 / T4 面 / 面数对账。
pub(crate) fn check_pack_faces(p: &Json, pkg: &str, faces: &[Json], thr: f64, issues: &mut Vec<String>) {
    let t234 = faces
        .iter()
        .filter(|e| {
            matches!(obj_get(e, "tier"), Some(Json::Str(s)) if s == "T2" || s == "T3" || s == "T4")
        })
        .count() as f64;
    let denom = std::cmp::max(1, faces.len()) as f64;
    // 真源 `round(x, 4)`：Python 的银行家舍入
    let ratio = crate::pyfloat::round_to(t234 / denom, 4);
    if ratio < thr {
        issues.push(format!(
            "{}：可机验产出占比 {:.4} < 门槛 {:.2}（产出面必须 ≥95%% 可机验）",
            pkg, ratio, thr
        ));
    }
    if !faces
        .iter()
        .any(|e| matches!(obj_get(e, "tier"), Some(Json::Str(s)) if s == "T4"))
    {
        issues.push(format!(
            "{}：无 T4 可复算面（域包必须有一个可重算产出）",
            pkg
        ));
    }
    let of = pyval::py_int_or(obj_get(&p, "output_faces"), 0);
    if of != faces.len() as i64 {
        issues.push(format!(
            "{}：名录产出面数 {} ≠ INDEX 实况 {}",
            pkg,
            pyval::py_str(obj_get(&p, "output_faces")),
            faces.len()
        ));
    }
}

/// 名录单包：标准绑定覆盖率 / 概念密度 / 数据真实性 / 可达率。
pub(crate) fn check_pack_spec(
    root: &Path,
    p: &Json,
    pkg: &str,
    cat: &[String],
    dens_min: f64,
    auth_min: f64,
    reach_min: f64,
    issues: &mut Vec<String>,
) -> bool {
    let code = match obj_get(&p, "code") {
        Some(Json::Null) | None => String::new(),
        Some(v) => pyval::plain_str(v),
    };
    let spec_path = root.join(SPEC_DIR).join(format!("{}.json", code));
if !spec_path.is_file() {
    return false;
}
        let payload = root
            .join("community")
            .join(&pkg)
            .join("outputs")
            .join("DOMAIN_SPEC.json");
        let payload = read_json_opt(&payload).unwrap_or(Json::Object(vec![]));
        let subs = arr_of(obj_get(&payload, "subdivisions"));
        bad_ref_issues(&subs, cat, pkg, issues);
        pack_metric_issues(p, pkg, dens_min, auth_min, reach_min, issues);

true
}

/// 名录单包：绑定表须带在册证明与实测日期。
pub(crate) fn check_pack_bindings(pkg: &str, bp: &Json, cat: &[String], issues: &mut Vec<String>) {
        let bindings = arr_of(obj_get(&bp, "bindings"));
        let bad_binding: Vec<Json> = bindings
            .iter()
            .filter(|r| {
                let st = obj_get(r, "standard")
                    .map(pyval::plain_str)
                    .unwrap_or_default();
                let sup = obj_get(r, "support_standard")
                    .map(pyval::plain_str)
                    .unwrap_or_default();
                let d1 = obj_get(r, "standard_probe_date")
                    .map(pyval::plain_str)
                    .unwrap_or_default();
                let d2 = obj_get(r, "support_standard_probe_date")
                    .map(pyval::plain_str)
                    .unwrap_or_default();
                !cat.contains(&st) || !cat.contains(&sup) || d1.is_empty() || d2.is_empty()
            })
            .cloned()
            .collect();
        if !bad_binding.is_empty() {
            let head: Vec<Json> = bad_binding
                .iter()
                .take(4)
                .map(|r| obj_get(r, "subdivision").cloned().unwrap_or(Json::Null))
                .collect();
            issues.push(format!(
                "{}：绑定表缺在册证明或实测记录：{}",
                pkg,
                pyval::py_repr_list(&head)
            ));
        }
}

/// 真源 `scan` → `(issues, stats)`（缓存层不移植：纯函数优化，不改结论）。
pub(crate) fn scan(root: &Path) -> (Vec<String>, Json) {
    manifest_verify(root)
}

/// 细分项 standard_ref 必须在类目词表内（真源报前 4 个 id）。
fn bad_ref_issues(subs: &[Json], cat: &[String], pkg: &str, issues: &mut Vec<String>) {
    let bad_ref: Vec<String> = subs
        .iter()
        .filter(|s| {
            let r = match obj_get(s, "standard_ref") {
                Some(Json::Null) | None => String::new(),
                Some(v) => pyval::plain_str(v),
            };
            !cat.contains(&r)
        })
        .map(|s| pyval::py_str(obj_get(s, "id")))
        .collect();
    if !bad_ref.is_empty() {
        let head: Vec<Json> = bad_ref
            .iter()
            .take(4)
            .map(|s| Json::Str(s.clone()))
            .collect();
        issues.push(format!(
            "{}：细分未绑可扩展标准或引用不在册：{}",
            pkg,
            pyval::py_repr_list(&head)
        ));
    }
}

/// 标准绑定 / 概念密度 / 真实性 / 可达性 阈值面。
fn pack_metric_issues(
    p: &Json,
    pkg: &str,
    dens_min: f64,
    auth_min: f64,
    reach_min: f64,
    issues: &mut Vec<String>,
) {
        let cov = py_float_or(obj_get(&p, "standards_binding_coverage"), 0.0);
        if cov < 1.0 {
            issues.push(format!(
                "{}：标准绑定覆盖率 {:.2} < 1.0（每条细分须绑一个目录内标准）",
                pkg, cov
            ));
        }
        let dens = py_float_or(obj_get(&p, "concept_density"), 0.0);
        if dens < dens_min {
            issues.push(format!(
                "{}：概念密度 {:.3} < 门槛 {:.3}（边/节点；含标准节点与绑定边）",
                pkg, dens, dens_min
            ));
        }
        let bound = pyval::py_int_or(obj_get(&p, "standards_bound"), 0);
        if bound < 3 {
            issues.push(format!(
                "{}：绑定标准数 {} < 3（单包至少要贴 3 条不同标准）",
                pkg,
                pyval::py_str(obj_get(&p, "standards_bound"))
            ));
        }
        let sup = py_float_or(obj_get(&p, "support_binding_coverage"), 0.0);
        if sup < 1.0 {
            issues.push(format!(
                "{}：辅锚覆盖率 {:.2} < 1.0（每条细分须另绑一条产出承载标准）",
                pkg, sup
            ));
        }
        let dep = pyval::py_int_or(obj_get(&p, "standards_dep_edges"), 0);
        if dep < 1 {
            issues.push(format!(
                "{}：概念图无标准依赖边（绑定标准的 depends_on 未入图）",
                pkg
            ));
        }
        let auth = py_float_or(obj_get(&p, "data_authenticity"), 0.0);
        if auth < auth_min {
            issues.push(format!(
                "{}：数据真实性分 {:.4} < 门槛 {:.2}（在册 × 实测可达 × 证据齐备）",
                pkg, auth, auth_min
            ));
        }
        let rr = py_float_or(obj_get(&p, "standards_reachable_ratio"), 0.0);
        if rr < reach_min {
            issues.push(format!(
                "{}：绑定标准本机实测可达率 {:.4} < 门槛 {:.2}",
                pkg, rr, reach_min
            ));
        }
}
