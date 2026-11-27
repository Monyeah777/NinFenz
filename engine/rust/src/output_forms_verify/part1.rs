use super::*;

/// 真源 `output_forms._pack_dirs`：有 `community/<包>/outputs/INDEX.json` 的包目录名（有序）。
///
/// ⚠️ 与 `pack_combo._pack_dirs`（要求 `protocol.yaml`）**不是同一个面**，别混用。
pub(crate) fn pack_dirs(root: &Path) -> Vec<String> {
    let mut rels = crate::glob::expand(root, "community/*/outputs/INDEX.json");
    rels.sort();
    let mut out: Vec<String> = Vec::new();
    for rel in rels {
        if let Some(pkg) = rel.split('/').nth(1) {
            if !out.contains(&pkg.to_string()) {
                out.push(pkg.to_string());
            }
        }
    }
    out.sort();
    out
}

/// 真源 `_count`：按某键计数（键为 `str(...)`，结果按键排序）。
pub(crate) fn count(rows: &[Json], key: &str) -> Json {
    let mut m: BTreeMap<String, i64> = BTreeMap::new();
    for r in rows {
        *m.entry(pyval::plain_str(
            &obj_get(r, key).cloned().unwrap_or(Json::Null),
        ))
        .or_insert(0) += 1;
    }
    Json::Object(m.into_iter().map(|(k, v)| (k, Json::Int(v))).collect())
}

/// 真源 `_dump`：文本补齐末尾换行；JSON 走 `indent=2, sort_keys=True` + 换行。
pub(crate) fn dump(value: &GenOut) -> String {
    match value {
        GenOut::Text(s) => {
            if s.ends_with('\n') {
                s.clone()
            } else {
                format!("{}\n", s)
            }
        }
        GenOut::Json(j) => j.dumps_file(),
    }
}

/// 真源 `_deep_diff`。
pub(crate) fn deep_diff(a: &Json, b: &Json, path: &str, out: &mut Vec<String>) {
    match (a, b) {
        (Json::Object(x), Json::Object(y)) => {
            let mut keys: Vec<String> = Vec::new();
            for (k, _) in x {
                if !keys.contains(k) {
                    keys.push(k.clone());
                }
            }
            for (k, _) in y {
                if !keys.contains(k) {
                    keys.push(k.clone());
                }
            }
            keys.sort();
            for k in keys {
                let av = x.iter().find(|(kk, _)| *kk == k).map(|(_, v)| v);
                let bv = y.iter().find(|(kk, _)| *kk == k).map(|(_, v)| v);
                match (av, bv) {
                    (None, Some(_)) => out.push(format!("{}.{} 仅存于在盘", path, k)),
                    (Some(_), None) => out.push(format!("{}.{} 仅存于复算", path, k)),
                    (Some(av), Some(bv)) => deep_diff(av, bv, &format!("{}.{}", path, k), out),
                    (None, None) => {}
                }
            }
        }
        (Json::Array(x), Json::Array(y)) => {
            if x.len() != y.len() {
                out.push(format!("{} 长度 {}≠{}", path, x.len(), y.len()));
            }
            for i in 0..x.len().min(y.len()) {
                deep_diff(&x[i], &y[i], &format!("{}[{}]", path, i), out);
            }
        }
        (Json::Int(x), Json::Int(y)) => {
            if x != y {
                out.push(format!(
                    "{} 数值 {}≠{}",
                    path,
                    pyval::py_repr(a),
                    pyval::py_repr(b)
                ));
            }
        }
        (Json::Float(x), Json::Float(y)) => {
            if (x - y).abs() > 1e-9 {
                out.push(format!(
                    "{} 数值 {}≠{}",
                    path,
                    pyval::py_repr(a),
                    pyval::py_repr(b)
                ));
            }
        }
        (Json::Int(x), Json::Float(y)) | (Json::Float(y), Json::Int(x)) => {
            if ((*x as f64) - *y).abs() > 1e-9 {
                out.push(format!(
                    "{} 数值 {}≠{}",
                    path,
                    pyval::py_repr(a),
                    pyval::py_repr(b)
                ));
            }
        }
        _ => {
            if !crate::jsonread::json_eq(a, b) {
                out.push(format!(
                    "{} {}≠{}",
                    path,
                    pyval::py_repr(a),
                    pyval::py_repr(b)
                ));
            }
        }
    }
}

/// 真源 `_recompute_entry` → `(issues, stats)`。
pub(crate) fn recompute_entry(root: &Path, entry: &Json) -> (Vec<String>, Json) {
    let out_rel = s_of(obj_get(entry, "path"));
    let gid = gen_id(entry);
    if !crate::output_forms_gen::GENERATOR_IDS.contains(&gid.as_str()) {
        return (
            vec![format!(
                "{} 声明复算 {} 无对应引擎（不得假装可复算）",
                out_rel,
                pyval::py_repr(&Json::Str(gid))
            )],
            Json::Object(vec![]),
        );
    }
    let (fresh, errs) = dispatch(root, entry);
    let Some(fresh) = fresh else {
        return (
            errs.into_iter()
                .map(|e| format!("{}: {}", out_rel, e))
                .collect(),
            Json::Object(vec![]),
        );
    };
    let disk_rel = match of::declared_out_rel(
        root,
        &s_of(obj_get(entry, "_pkg")),
        &Json::Str(out_rel.clone()),
    ) {
        Ok(v) => v,
        Err(e) => return (vec![format!("{}: {}", out_rel, e)], Json::Object(vec![])),
    };
    let on_disk = std::fs::read(root.join(&disk_rel)).unwrap_or_default();
    let mut diffs: Vec<String> = Vec::new();
    match &fresh {
        GenOut::Text(_) => {
            if on_disk != dump(&fresh).into_bytes() {
                diffs.push("文本面与复算不一致（逐字节）".to_string());
            }
        }
        GenOut::Json(fresh_json) => {
            let text = String::from_utf8_lossy(&on_disk).into_owned();
            let declared = match crate::jsonmini::parse(&text) {
                Ok(p) => p.value,
                Err(e) => {
                    return (
                        vec![format!("{}: 在盘产物不可解析 {}", out_rel, e)],
                        Json::Object(vec![]),
                    )
                }
            };
            // 真源 `{k: declared.get(k) for k in fresh}`：以**复算值的键**取在盘值
            let projected = match fresh_json {
                Json::Object(o) => Json::Object(
                    o.iter()
                        .map(|(k, _)| {
                            (
                                k.clone(),
                                obj_get(&declared, k).cloned().unwrap_or(Json::Null),
                            )
                        })
                        .collect(),
                ),
                other => other.clone(),
            };
            deep_diff(fresh_json, &projected, "$", &mut diffs);
            if on_disk.windows(2).any(|w| w == b"\r\n") {
                diffs.push("在盘产物含 CRLF（仓库 EOL 契约 = LF）".to_string());
            }
        }
    }
    (
        diffs
            .iter()
            .map(|d| format!("{}: 复算与在盘不一致 {}", out_rel, d))
            .collect(),
        Json::Object(vec![("diff".to_string(), Json::Int(diffs.len() as i64))]),
    )
}
