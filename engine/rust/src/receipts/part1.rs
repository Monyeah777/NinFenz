use super::*;

pub(crate) const SCHEMA: &str = "nf-receipts/1";

pub(crate) const ALGORITHM: &str = "RFC6962-style sha256 domain-separated";

/// 真源 `protocol_subjects()` 的固定段——**顺序敏感**，真源按此序取件、不排序。
/// 改动本表即改变根：任何增删都必须同步 `desktop/src/core/receipts.py`。
pub(crate) const FIXED: [&str; 54] = [
    "STRATEGY.md",
    "01_核心协议.md",
    "02_联动注册表.md",
    "06_Agent执行协议.md",
    "07_官方核心出厂与社区预设导航.md",
    "llms.txt",
    "library/INDEX.md",
    "library/ALIAS.md",
    "protocol/event_registry.json",
    "protocol/world_slots.json",
    "protocol/export_conformance.json",
    "protocol/community_asset_ledger.json",
    "protocol/external_events.json",
    "protocol/type_backlog.json",
    "protocol/pipeline_advisory.json",
    "protocol/score_baseline.json",
    "protocol/module_signatures.json",
    "protocol/conformance_report.json",
    "protocol/asset_line_baseline.json",
    "protocol/asset_contracts.json",
    "protocol/schema/asset_contracts.schema.json",
    "protocol/role_coordinates.json",
    "protocol/code_metrics_baseline.json",
    "protocol/coupling_baseline.json",
    "protocol/drill_fidelity.json",
    "protocol/instruction_evidence.json",
    "protocol/perf_budget.json",
    "protocol/repo_stats.json",
    "protocol/sast_baseline.json",
    "protocol/CONFORMANCE.md",
    "protocol/driver.json",
    "protocol/rfc_index.json",
    "protocol/endpoint_contract.json",
    "protocol/knowledge_sources.json",
    "protocol/transform_log.json",
    "protocol/knowledge_usage.json",
    "protocol/assertions.json",
    "protocol/LAYERS.json",
    "protocol/locales.json",
    "protocol/release_policy.json",
    "protocol/vocabularies.json",
    "protocol/normative.json",
    "protocol/data_contracts.json",
    "decisions/INDEX.md",
    "protocol/handover.json",
    "protocol/postmortem.json",
    "protocol/audit.json",
    "protocol/glossary.json",
    "protocol/execution_modes.json",
    "protocol/st_quality.json",
    "protocol/mcp_package.json",
    "protocol/state_front.json",
    "protocol/decision_layer.json",
    "desktop/src/core/registry.json",
];

/// 目录内按名排序的匹配件 → 仓库相对 POSIX 路径。
/// 真源用 `sorted(Path.glob(...))`；因同目录前缀相同，按文件名排序与按路径排序同解。
pub(crate) fn glob_sorted(root: &Path, rel_dir: &str, prefix: &str, suffix: &str) -> Vec<String> {
    let mut names: Vec<String> = Vec::new();
    if let Ok(rd) = std::fs::read_dir(root.join(rel_dir)) {
        for entry in rd.flatten() {
            let name = entry.file_name().to_string_lossy().into_owned();
            if name.starts_with(prefix) && name.ends_with(suffix) {
                names.push(name);
            }
        }
    }
    names.sort();
    names
        .into_iter()
        .map(|n| format!("{}/{}", rel_dir, n))
        .collect()
}

/// 真源 `protocol_subjects(root)`：固定段（原序）→ `protocol/schema/*.json`（排序）
/// → `decisions/ADR-*.md`（排序）→ `postmortems/PO-*.md`（排序）→ 过滤掉不存在的件。
pub(crate) fn protocol_subjects(root: &Path) -> Vec<String> {
    let mut subs: Vec<String> = FIXED.iter().map(|s| (*s).to_string()).collect();
    subs.extend(glob_sorted(root, "protocol/schema", "", ".json"));
    subs.extend(glob_sorted(root, "decisions", "ADR-", ".md"));
    subs.extend(glob_sorted(root, "postmortems", "PO-", ".md"));
    // 去重（2026-11-04）：固定清单已含 protocol/schema/asset_contracts.schema.json，
    // 上面的 schema glob 会再收一次——同一成员在根里出现两次会破坏成员集自洽。
    // 与真源 receipts.protocol_subjects 同口径：按**首次出现**去重，顺序不变。
    let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
    subs.retain(|rel| !seen.contains(rel) && seen.insert(rel.clone()));
    subs.retain(|rel| root.join(rel).is_file());
    subs
}

/// 叶载荷字节：`{"digest":"…","id":"…"}`（紧凑、键序）。
pub(crate) fn payload_bytes(rel: &str, digest_hex: &str) -> Vec<u8> {
    Json::Object(vec![
        ("digest".to_string(), Json::Str(digest_hex.to_string())),
        ("id".to_string(), Json::Str(rel.to_string())),
    ])
    .dumps_compact()
    .into_bytes()
}

/// 真源 `build_scope(root, scope="protocol")` 的等价物（以 `Json` 值形态返回）。
pub(crate) fn build_scope(root: &Path, scope: &str) -> Json {
    build_scope_for(root, &protocol_subjects(root), scope)
}

/// 按**给定件序**构回执（真源 `build_scope(root, subjects)` 的等价物）。
/// `verify_scope` 用它按在盘 entries 的 id 子集重建（与真源同口径）。
pub(crate) fn build_scope_for(root: &Path, rels: &[String], scope: &str) -> Json {
    struct Row {
        rel: String,
        digest: String,
        payload: Vec<u8>,
    }

    let mut rows: Vec<Row> = Vec::with_capacity(rels.len());
    let mut leaves: Vec<Hash> = Vec::with_capacity(rels.len());

    for rel in rels {
        let bytes = match std::fs::read(root.join(rel.as_str())) {
            Ok(b) => b,
            Err(_) => continue, // 真源在此亦跳过；subjects 已按 is_file 过滤，此处为兜底
        };
        let digest = merkle::hex(&merkle::sha256(&bytes));
        let payload = payload_bytes(rel.as_str(), &digest);
        leaves.push(merkle::leaf_hash(&payload));
        rows.push(Row {
            rel: rel.clone(),
            digest,
            payload,
        });
    }

    let root_hash = merkle::merkle_root(&leaves);
    let entries: Vec<Json> = rows
        .iter()
        .enumerate()
        .map(|(i, row)| {
            let leaf = merkle::leaf_hash(&row.payload);
            let proof: Vec<Json> = merkle::inclusion_proof(&leaves, i)
                .iter()
                .map(|step| {
                    Json::Object(vec![
                        ("hash".to_string(), Json::Str(merkle::hex(&step.hash))),
                        (
                            "side".to_string(),
                            Json::Str(
                                if step.sibling_is_left {
                                    "left"
                                } else {
                                    "right"
                                }
                                .to_string(),
                            ),
                        ),
                    ])
                })
                .collect();
            Json::Object(vec![
                ("id".to_string(), Json::Str(row.rel.clone())),
                ("path".to_string(), Json::Str(row.rel.clone())),
                ("digest".to_string(), Json::Str(row.digest.clone())),
                ("leaf".to_string(), Json::Str(merkle::hex(&leaf))),
                ("proof".to_string(), Json::Array(proof)),
            ])
        })
        .collect();

    Json::Object(vec![
        ("schema".to_string(), Json::Str(SCHEMA.to_string())),
        ("scope".to_string(), Json::Str(scope.to_string())),
        (
            "root".to_string(),
            Json::Str(root_hash.map(|h| merkle::hex(&h)).unwrap_or_default()),
        ),
        ("count".to_string(), Json::Int(entries.len() as i64)),
        ("algorithm".to_string(), Json::Str(ALGORITHM.to_string())),
        ("entries".to_string(), Json::Array(entries)),
    ])
}

/// 真源 `write_scope` 的**落盘字节**（LF、末尾换行、无 BOM）。只返回字节，不写盘。
pub(crate) fn build_scope_bytes(root: &Path, scope: &str) -> Vec<u8> {
    build_scope(root, scope).dumps_file().into_bytes()
}
