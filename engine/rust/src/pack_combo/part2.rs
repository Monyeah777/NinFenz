use super::*;

pub(crate) fn str_json(v: &[String]) -> Json {
    Json::Array(v.iter().map(|s| Json::Str(s.clone())).collect())
}

/// 真源 `_pack_assets`。
pub(crate) fn pack_assets(root: &Path, pkg_dir: &str) -> Vec<Json> {
    let doc = read_json_opt(
        root,
        &format!("community/{}/assets/provenance.json", pkg_dir),
    )
    .unwrap_or(Json::Object(vec![]));
    arr_of(obj_get(&doc, "assets"))
        .iter()
        .map(|a| {
            Json::Object(vec![
                ("key".to_string(), Json::Str(s_of(obj_get(a, "key")))),
                ("file".to_string(), Json::Str(s_of(obj_get(a, "file")))),
                ("module".to_string(), Json::Str(s_of(obj_get(a, "module")))),
                ("source_package".to_string(), Json::Str(pkg_dir.to_string())),
            ])
        })
        .collect()
}

/// 真源 `profiles`：每个包的组合画像（**不移植两层缓存**——缓存只决定要不要重算）。
pub(crate) fn profiles(root: &Path) -> Vec<(String, Json)> {
    let contracts = module_contracts(root);
    let mut out: Vec<(String, Json)> = Vec::new();
    for d in pack_dirs(root) {
        let proto = parse_protocol(&root.join("community").join(&d).join("protocol.yaml"));
        let own = profile_modules(&proto, &contracts);
        let mut layers: Vec<(String, Vec<String>)> = Vec::new();
        for rec in &own {
            let lay = s_of(obj_get(rec, "layer"));
            if !lay.is_empty() {
                let id = s_of(obj_get(rec, "id"));
                match layers.iter_mut().find(|(k, _)| *k == lay) {
                    Some(e) => {
                        if !e.1.contains(&id) {
                            e.1.push(id);
                        }
                    }
                    None => layers.push((lay, vec![id])),
                }
            }
        }
        let mut layers_sorted: Vec<(String, Json)> = layers
            .into_iter()
            .map(|(k, v)| {
                let mut s: Vec<String> = v;
                s.sort();
                s.dedup();
                (k, str_json(&s))
            })
            .collect();
        layers_sorted.sort_by(|a, b| a.0.cmp(&b.0));
        let mut pub_set: BTreeSet<String> = BTreeSet::new();
        let mut sub_set: BTreeSet<String> = BTreeSet::new();
        for r in &own {
            for e in str_list(obj_get(r, "publish")) {
                pub_set.insert(e);
            }
            for e in str_list(obj_get(r, "subscribe")) {
                sub_set.insert(e);
            }
        }
        let rec = Json::Object(vec![
            ("package".to_string(), Json::Str(proto.id.clone())),
            ("pipeline".to_string(), Json::Str(proto.pipeline.clone())),
            (
                "modules".to_string(),
                str_json(
                    &own.iter()
                        .map(|r| s_of(obj_get(r, "id")))
                        .collect::<Vec<_>>(),
                ),
            ),
            ("module_recs".to_string(), Json::Array(own)),
            (
                "references".to_string(),
                Json::Array(
                    proto
                        .references
                        .iter()
                        .map(|(a, b)| {
                            Json::Object(vec![
                                ("source_package".to_string(), Json::Str(a.clone())),
                                ("module_id".to_string(), Json::Str(b.clone())),
                            ])
                        })
                        .collect(),
                ),
            ),
            ("layers".to_string(), Json::Object(layers_sorted)),
            ("assets".to_string(), Json::Array(pack_assets(root, &d))),
            (
                "publishes".to_string(),
                str_json(&pub_set.into_iter().collect::<Vec<_>>()),
            ),
            (
                "subscribes".to_string(),
                str_json(&sub_set.into_iter().collect::<Vec<_>>()),
            ),
        ]);
        out.push((proto.id, rec));
    }
    out
}

/// 单包的模块记录（契约查不到时给空壳，真源同款）。
pub(crate) fn profile_modules(proto: &Proto, contracts: &[(String, Json)]) -> Vec<Json> {
    let mut own: Vec<Json> = Vec::new();
    for mid in &proto.module_ids {
        let rec = contracts
            .iter()
            .find(|(k, _)| k == mid)
            .map(|(_, v)| v.clone())
            .or_else(|| {
                let tail = mid.rsplit(':').next().unwrap_or(mid);
                contracts
                    .iter()
                    .find(|(k, _)| k == tail)
                    .map(|(_, v)| v.clone())
            });
        own.push(rec.unwrap_or_else(|| {
            Json::Object(vec![
                ("id".to_string(), Json::Str(mid.clone())),
                ("layer".to_string(), Json::Str(String::new())),
                ("inputs".to_string(), Json::Array(vec![])),
                ("publish".to_string(), Json::Array(vec![])),
                ("subscribe".to_string(), Json::Array(vec![])),
                ("pack".to_string(), Json::Str(proto.id.clone())),
            ])
        }));
    }
    own
}

pub(crate) type Index = (
    Vec<(String, Json)>,
    Vec<(String, Vec<Json>)>,
    BTreeSet<String>,
);

/// 真源 `indexes`：`(by_id, pub_index, core_pub)`。
pub(crate) fn indexes(root: &Path, contracts: &[(String, Json)]) -> Index {
    let mut by_id: Vec<(String, Json)> = Vec::new();
    let mut pub_index: Vec<(String, Vec<Json>)> = Vec::new();
    for (_, r) in contracts {
        if s_of(obj_get(r, "path")).is_empty() {
            continue;
        }
        let id = s_of(obj_get(r, "id"));
        if !by_id.iter().any(|(k, _)| *k == id) {
            by_id.push((id, r.clone()));
        }
        for e in str_list(obj_get(r, "publish")) {
            match pub_index.iter_mut().find(|(k, _)| *k == e) {
                Some(slot) => slot.1.push(r.clone()),
                None => pub_index.push((e, vec![r.clone()])),
            }
        }
    }
    let mut core_pub: BTreeSet<String> = BTreeSet::new();
    for (_, r) in core_contracts(root) {
        for e in str_list(obj_get(&r, "publish")) {
            core_pub.insert(e);
        }
    }
    (by_id, pub_index, core_pub)
}

/// 真源 `_canon`：`json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)`。
///
/// ⚠️ **必须走 `dumps_default()`**（扁平、默认分隔符 `", "` / `": "`），**不能**用 `dumps()`
/// ——后者是**缩进**排版。实测（2026-10-04）：用 `dumps()` 时同一份证书的规范 JSON 长 2246 字符
/// （真源 1652），摘要随之全错 ⇒ 18 张证书全部报 `digest` 不一致。
pub(crate) fn canon(obj: &Json) -> String {
    obj.dumps_default()
}

/// 真源 `_digest`：去掉 `digest` 键后的规范 JSON 摘要（取前 32 位）。
pub(crate) fn digest_of_cert(obj: &Json) -> String {
    let stripped = match obj {
        Json::Object(o) => Json::Object(
            o.iter()
                .filter(|(k, _)| k != "digest")
                .map(|(k, v)| (k.clone(), v.clone()))
                .collect(),
        ),
        other => other.clone(),
    };
    crate::merkle::hex(&crate::merkle::sha256(canon(&stripped).as_bytes()))[..32].to_string()
}

/// 真源 `_combo_witness`。
pub(crate) fn combo_witness(
    prof: &[(String, Json)],
    contracts: &[(String, Json)],
    by_id: &Index,
) -> String {
    let decl_keys = [
        "package",
        "pipeline",
        "references",
        "assets",
        "layers",
        "publishes",
        "subscribes",
    ];
    // 真源是增量 `hashlib.sha256().update(...)`；本线的 merkle 模块只给一次性接口 ⇒
    // 累积字节后一次哈希。**结果逐位相同**（同一串字节、同一算法），且少一次 API 改动。
    let mut buf: Vec<u8> = Vec::new();
    let mut names: Vec<&String> = prof.iter().map(|(k, _)| k).collect();
    names.sort();
    for p in names {
        let rec = prof
            .iter()
            .find(|(k, _)| k == p)
            .map(|(_, v)| v.clone())
            .unwrap_or(Json::Object(vec![]));
        let mut decl: Vec<(String, Json)> = Vec::new();
        for k in decl_keys {
            decl.push((
                k.to_string(),
                obj_get(&rec, k).cloned().unwrap_or(Json::Null),
            ));
        }
        let payload = Json::Array(vec![
            Json::Str("decl".to_string()),
            Json::Str(p.clone()),
            Json::Object(decl),
        ]);
        buf.extend_from_slice(canon(&payload).as_bytes());
    }
    let mut mids: Vec<&String> = contracts.iter().map(|(k, _)| k).collect();
    mids.sort();
    for mid in mids {
        let rec = contracts
            .iter()
            .find(|(k, _)| k == mid)
            .map(|(_, v)| v.clone())
            .unwrap_or(Json::Null);
        let payload = Json::Array(vec![
            Json::Str("contract".to_string()),
            Json::Str(mid.clone()),
            rec,
        ]);
        buf.extend_from_slice(canon(&payload).as_bytes());
    }
    let core: Vec<Json> = by_id.2.iter().map(|s| Json::Str(s.clone())).collect();
    let payload = Json::Array(vec![Json::Str("core_pub".to_string()), Json::Array(core)]);
    buf.extend_from_slice(canon(&payload).as_bytes());
    crate::merkle::hex(&crate::merkle::sha256(&buf))
}
