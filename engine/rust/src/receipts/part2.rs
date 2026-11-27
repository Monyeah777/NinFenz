use super::*;

/// 自校验：每条回执的审计路径必须折叠回根（真源 `verify_scope` 的自洽判据）。
pub(crate) fn self_check(root: &Path, scope: &str) -> Vec<String> {
    let doc = build_scope(root, scope);
    let mut issues = Vec::new();
    let Json::Object(pairs) = &doc else {
        return vec!["内部错误：回执非对象".to_string()];
    };
    let get = |k: &str| pairs.iter().find(|(n, _)| n == k).map(|(_, v)| v);
    let root_hex = match get("root") {
        Some(Json::Str(s)) => s.clone(),
        _ => return vec!["内部错误：缺根".to_string()],
    };
    if let Some(Json::Array(entries)) = get("entries") {
        for e in entries {
            let Json::Object(ep) = e else { continue };
            let g = |k: &str| ep.iter().find(|(n, _)| n == k).map(|(_, v)| v);
            let (Some(Json::Str(id)), Some(Json::Str(leaf_hex)), Some(Json::Array(proof))) =
                (g("id"), g("leaf"), g("proof"))
            else {
                continue;
            };
            let mut leaf = [0u8; 32];
            if !unhex_into(leaf_hex, &mut leaf) {
                issues.push(format!("回执 leaf 非法：{}", id));
                continue;
            }
            let mut steps = Vec::with_capacity(proof.len());
            for st in proof {
                let Json::Object(sp) = st else { continue };
                let gs = |k: &str| sp.iter().find(|(n, _)| n == k).map(|(_, v)| v);
                let (Some(Json::Str(h)), Some(Json::Str(side))) = (gs("hash"), gs("side")) else {
                    continue;
                };
                let mut hb = [0u8; 32];
                if !unhex_into(h, &mut hb) {
                    continue;
                }
                steps.push(merkle::ProofStep {
                    sibling_is_left: side == "left",
                    hash: hb,
                });
            }
            if merkle::hex(&merkle::fold_proof(&leaf, &steps)) != root_hex {
                issues.push(format!("包含证明不折叠到根：{}", id));
            }
        }
    }
    issues
}

/// 真源 `receipts.verify_scope`：在盘回执 == 实时重算（根 + 逐件摘要 + 包含证明）。
///
/// 与 `self_check` 的分工：`self_check` 核对**实时重算**文档自身的证明折叠；
/// 本函数核对**在盘文档**（entries 顺序即 live 重建顺序）与实时重算是否一致。
pub(crate) fn verify_scope(doc: &Json, root: &Path) -> (Vec<String>, Json) {
    let Json::Object(pairs) = doc else {
        return invalid_scope_result();
    };
    let g = |k: &str| pairs.iter().find(|(n, _)| n == k).map(|(_, v)| v);
    if !matches!(g("schema"), Some(Json::Str(s)) if s == SCHEMA) {
        return invalid_scope_result();
    }
    let committed_root = match g("root") {
        Some(Json::Str(s)) => s.clone(),
        _ => String::new(),
    };
    let entries: &[Json] = match g("entries") {
        Some(Json::Array(a)) => a.as_slice(),
        _ => &[],
    };
    let ids = match scope_ids(entries) {
        Ok(ids) => ids,
        Err(msg) => return (vec![msg], Json::Object(vec![])),
    };
    let live = build_scope_for(root, &ids, "protocol");
    let Json::Object(lp) = &live else {
        return (
            vec!["内部错误：回执非对象".to_string()],
            Json::Object(vec![]),
        );
    };
    let lg = |k: &str| lp.iter().find(|(n, _)| n == k).map(|(_, v)| v);
    let live_root = match lg("root") {
        Some(Json::Str(s)) => s.clone(),
        _ => String::new(),
    };
    let mut issues: Vec<String> = Vec::new();
    if committed_root != live_root {
        issues.push(format!(
            "协议回执根不一致：记录={} 实测={}（修复指引：nf receipts --scope protocol --write）",
            committed_root.chars().take(16).collect::<String>(),
            live_root.chars().take(16).collect::<String>(),
        ));
    }
    let live_by = live_entries_by(lp);
    for e in entries {
        scope_entry_issues(e, &live_by, &committed_root, &mut issues);
    }
    let stats = Json::Object(vec![
        ("entries".to_string(), Json::Int(entries.len() as i64)),
        ("root".to_string(), Json::Str(live_root)),
    ]);
    (issues, stats)
}

/// schema 不匹配时统一的空结论。
fn invalid_scope_result() -> (Vec<String>, Json) {
    (
        vec!["协议回执 schema 不匹配".to_string()],
        Json::Object(vec![]),
    )
}

/// 在盘 entries 的 id 序列（真源 build_scope 的重建顺序）。
fn scope_ids(entries: &[Json]) -> Result<Vec<String>, String> {
    let mut ids: Vec<String> = Vec::with_capacity(entries.len());
    for e in entries {
        let Json::Object(ep) = e else {
            return Err("回执条目不是对象".to_string());
        };
        match ep.iter().find(|(n, _)| n == "id").map(|(_, v)| v) {
            Some(Json::Str(id)) => ids.push(id.clone()),
            _ => return Err("回执条目缺 id".to_string()),
        }
    }
    Ok(ids)
}

/// 单条在盘回执：id 摘要一致 / leaf 合法 / 包含证明折叠到根。
fn scope_entry_issues(
    e: &Json,
    live_by: &[(&str, &str)],
    committed_root: &str,
    issues: &mut Vec<String>,
) {
    let Json::Object(ep) = e else { return };
    let eg = |k: &str| ep.iter().find(|(n, _)| n == k).map(|(_, v)| v);
    let id = match eg("id") {
        Some(Json::Str(s)) => s.clone(),
        _ => return,
    };
    let committed_digest = match eg("digest") {
        Some(Json::Str(s)) => s.as_str(),
        _ => "",
    };
    let live_digest = live_by
        .iter()
        .find(|(i, _)| *i == id)
        .map(|(_, d)| *d)
        .unwrap_or("");
    if live_digest != committed_digest {
        issues.push(format!("文件内容已变：{}", id));
    }
    let leaf_hex = match eg("leaf") {
        Some(Json::Str(s)) => s.as_str(),
        _ => "",
    };
    let mut leaf = [0u8; 32];
    if !unhex_into(leaf_hex, &mut leaf) {
        issues.push(format!("回执 leaf 非法：{}", id));
        return;
    }
    let proof: &[Json] = match eg("proof") {
        Some(Json::Array(a)) => a.as_slice(),
        _ => &[],
    };
    let steps = proof_steps(proof);
    if merkle::hex(&merkle::fold_proof(&leaf, &steps)) != committed_root {
        issues.push(format!("包含证明不折叠到根：{}", id));
    }
}

/// 回执条目按 id → digest 建索引（真源 live 重建的 entries 顺序）。
pub(crate) fn live_entries_by(lp: &[(String, Json)]) -> Vec<(&str, &str)> {
let mut live_by: Vec<(&str, &str)> = Vec::new();
if let Some(Json::Array(le)) = lp.iter().find(|(n, _)| n == "entries").map(|(_, v)| v) {
    for e in le {
        let Json::Object(ep) = e else { continue };
        let id = ep
            .iter()
            .find(|(n, _)| n == "id")
            .and_then(|(_, v)| match v {
                Json::Str(s) => Some(s.as_str()),
                _ => None,
            });
        let dg = ep
            .iter()
            .find(|(n, _)| n == "digest")
            .and_then(|(_, v)| match v {
                Json::Str(s) => Some(s.as_str()),
                _ => None,
            });
        if let (Some(i), Some(d)) = (id, dg) {
            live_by.push((i, d));
        }
    }
}
live_by
}

/// 回执条目 proof 的步骤解析（非法 hex / 缺字段的步骤跳过，真源同款）。
pub(crate) fn proof_steps(proof: &[Json]) -> Vec<merkle::ProofStep> {
let mut steps = Vec::with_capacity(proof.len());
    for st in proof {
        let Json::Object(sp) = st else { continue };
        let sg = |k: &str| sp.iter().find(|(n, _)| n == k).map(|(_, v)| v);
        let (Some(Json::Str(h)), Some(Json::Str(side))) = (sg("hash"), sg("side")) else {
            continue;
        };
        let mut hb = [0u8; 32];
        if !unhex_into(h, &mut hb) {
            continue;
        }
        steps.push(merkle::ProofStep {
            sibling_is_left: side == "left",
            hash: hb,
        });
}
steps
}

pub(crate) fn unhex_into(s: &str, out: &mut [u8; 32]) -> bool {
    if s.len() != 64 {
        return false;
    }
    let b = s.as_bytes();
    for i in 0..32 {
        let hi = (b[i * 2] as char).to_digit(16);
        let lo = (b[i * 2 + 1] as char).to_digit(16);
        match (hi, lo) {
            (Some(h), Some(l)) => out[i] = ((h << 4) | l) as u8,
            _ => return false,
        }
    }
    true
}
