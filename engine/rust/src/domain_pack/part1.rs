use super::*;

pub(crate) const SPEC_DIR: &str = ".rivet/private_archive/ai_packs/specs";

pub(crate) const MANIFEST_REL: &str = "protocol/domain_packs.json";

pub(crate) const REGISTRY_REL: &str = "desktop/src/core/registry.json";

pub(crate) const STANDARDS_REL: &str = "protocol/standards_catalog.json";

pub(crate) const BINDING_REL: &str = "protocol/standards_binding.json";

pub(crate) const AUTHENTICITY_THRESHOLD: f64 = 0.95;

pub(crate) const REACHABLE_RATIO_THRESHOLD: f64 = 0.9;

pub(crate) fn obj_get<'a>(v: &'a Json, k: &str) -> Option<&'a Json> {
    match v {
        Json::Object(o) => o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv),
        _ => None,
    }
}

pub(crate) fn arr_of(v: Option<&Json>) -> Vec<Json> {
    match v {
        Some(Json::Array(a)) => a.clone(),
        _ => Vec::new(),
    }
}

/// 真源 `p.get(k) or <default>` 的浮点版（Python 的 `or` 走**真值**判定）。
pub(crate) fn py_float_or(v: Option<&Json>, default: f64) -> f64 {
    match v {
        Some(x) if pyval::py_truthy(x) => match x {
            Json::Int(i) => *i as f64,
            Json::Float(f) => *f,
            Json::Str(s) => s.parse::<f64>().unwrap_or(default),
            Json::Bool(b) => {
                if *b {
                    1.0
                } else {
                    default
                }
            }
            _ => default,
        },
        _ => default,
    }
}

/// 真源 `_read_json_raw`：缺件/坏件 → `None`（不抛）。
pub(crate) fn read_json_opt(p: &Path) -> Option<Json> {
    let text = std::fs::read_to_string(p).ok()?;
    crate::jsonmini::parse(&text).ok().map(|r| r.value)
}

/// 真源 `_read_json`。
pub(crate) fn read_json(p: &Path) -> Option<Json> {
    read_json_opt(p)
}

pub(crate) fn read_text(p: &Path) -> String {
    std::fs::read(p)
        .map(|b| String::from_utf8_lossy(&b).into_owned())
        .unwrap_or_default()
}

/// 真源 `standards_catalog` → `{标准 id: 条目}`。
pub(crate) fn standards_catalog(root: &Path) -> Vec<String> {
    let doc = read_json(&root.join(STANDARDS_REL)).unwrap_or(Json::Object(vec![]));
    arr_of(obj_get(&doc, "standards"))
        .iter()
        .filter_map(|s| obj_get(s, "id").map(pyval::plain_str))
        .collect()
}

/// 真源 `manifest_verify` → `(issues, stats)`。
pub(crate) fn manifest_verify(root: &Path) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let path = root.join(MANIFEST_REL);
    if !path.is_file() {
        return (
            Vec::new(),
            Json::Object(vec![
                ("packs".to_string(), Json::Int(0)),
                (
                    "note".to_string(),
                    Json::Str("无域包名录（域包工程未启用）".to_string()),
                ),
            ]),
        );
    }
    let doc = read_json(&path).unwrap_or(Json::Object(vec![]));
    let thr = py_float_or(obj_get(&doc, "machine_verifiable_threshold"), 0.95);
    let cat = standards_catalog(root);
    let dens_min = py_float_or(obj_get(&doc, "concept_density_threshold"), 1.0);
    let auth_min = py_float_or(
        obj_get(&doc, "data_authenticity_threshold"),
        AUTHENTICITY_THRESHOLD,
    );
    let reach_min = py_float_or(
        obj_get(&doc, "reachable_ratio_threshold"),
        REACHABLE_RATIO_THRESHOLD,
    );
    let reg = read_json(&root.join(REGISTRY_REL)).unwrap_or(Json::Object(vec![]));
    let by_id: Vec<Json> = arr_of(obj_get(&reg, "protocols"));
    let binding = read_json(&root.join(BINDING_REL)).unwrap_or(Json::Object(vec![]));
    let bind_by: Vec<Json> = arr_of(obj_get(&binding, "packs"));

    let mut packs = 0i64;
    let mut faces_n = 0i64;
    let mut functional = 0i64;
    for p in arr_of(obj_get(&doc, "packs")) {
        let (pkg, bp, of, ff) = check_pack_registry(&p, &by_id, &bind_by, &mut issues);
        packs += 1;
        faces_n += of;
        functional += ff;
        let Some(faces) = check_pack_files(root, &p, &pkg, &mut issues) else {
            continue;
        };
        check_pack_faces(&p, &pkg, &faces, thr, &mut issues);
        if check_pack_spec(root, &p, &pkg, &cat, dens_min, auth_min, reach_min, &mut issues) {
            check_pack_bindings(&pkg, &bp, &cat, &mut issues);
        }
    }
    (
        issues,
        Json::Object(vec![
            ("packs".to_string(), Json::Int(packs)),
            ("faces".to_string(), Json::Int(faces_n)),
            ("functional".to_string(), Json::Int(functional)),
        ]),
    )
}

/// 名录单包：与 registry protocols[] 的包名 / 管线 / 模块 id 对账；顺带回收面数。
pub(crate) fn check_pack_registry(
    p: &Json,
    by_id: &[Json],
    bind_by: &[Json],
    issues: &mut Vec<String>,
) -> (String, Json, i64, i64) {
    let pkg = match obj_get(&p, "package") {
        Some(Json::Null) | None => String::new(),
        Some(v) => pyval::plain_str(v),
    };
    let bp = bind_by
        .iter()
        .find(|b| match (obj_get(b, "code"), obj_get(&p, "code")) {
            (Some(x), Some(y)) => pyval::py_eq(x, y),
            _ => false,
        })
        .cloned()
        .unwrap_or(Json::Object(vec![]));
    let regp = by_id.iter().find(|r| match obj_get(r, "id") {
        Some(Json::Str(s)) => *s == pkg,
        _ => false,
    });
    match regp {
        None => issues.push(format!(
            "{}：registry protocols[] 无该包（名录 ↔ 登记不一致）",
            pkg
        )),
        Some(regp) => {
            let a = obj_get(regp, "pipeline")
                .map(pyval::plain_str)
                .unwrap_or_default();
            let b = obj_get(&p, "pipeline")
                .map(pyval::plain_str)
                .unwrap_or_default();
            if a != b {
                issues.push(format!(
                    "{}：管线不一致（名录 {} / registry {}）",
                    pkg,
                    pyval::py_str(obj_get(&p, "pipeline")),
                    pyval::py_str(obj_get(regp, "pipeline"))
                ));
            }
            let ma: Vec<String> = arr_of(obj_get(regp, "module_ids"))
                .iter()
                .map(pyval::plain_str)
                .collect();
            let mb: Vec<String> = arr_of(obj_get(&p, "module_ids"))
                .iter()
                .map(pyval::plain_str)
                .collect();
            if ma != mb {
                issues.push(format!("{}：模块 id 不一致（名录 ↔ registry）", pkg));
            }
        }
    }
(
    pkg,
    bp,
    pyval::py_int_or(obj_get(p, "output_faces"), 0),
    pyval::py_int_or(obj_get(p, "functional_faces"), 0),
)
}
