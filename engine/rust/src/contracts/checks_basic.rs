//! 根级简单契约（declaration / decisions / mcp-package / pipeline / type-backlog / purity / io-types / endpoint / knowledge / audit / modeling / event / doc-kinds 等轻量判据）。
//!
//! 自 `contracts.rs` 按族拆出：判据实现逐字搬运，逻辑与文案未改；由父模块 glob 引入分派面。

use crate::pyjson::Json;
use std::path::Path;

/// 真源 `_c_declaration`：声明版本数 · scope 数 · 排除数。
pub(super) fn declaration(root: &Path) -> (bool, String) {
    let s = crate::declaration::scan(root);
    let ok = s.issues.is_empty();
    let detail = if ok {
        format!(
            "版本 {} · scope {} · 排除 {}",
            s.versions, s.scope, s.excluded
        )
    } else {
        s.issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}

/// 真源 `_c_decisions`：决策条数 · accepted · 取代链 + 投影一致。
pub(super) fn decisions(root: &Path) -> (bool, String) {
    let (mut issues, n, accepted, chains) = crate::decisions::scan(root);
    issues.extend(crate::decisions::check_projection(root));
    let ok = issues.is_empty();
    let detail = if ok {
        format!("决策 {} 条（accepted {} · 取代链 {}）", n, accepted, chains)
    } else {
        issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}

/// 真源 `_c_mcp_package`：工具数 · 提示数 · 类目 · 目标平台数。
pub(super) fn mcp_package(root: &Path) -> (bool, String) {
    let s = crate::mcp_package::scan(root);
    let ok = s.issues.is_empty();
    let g = |k: &str| match crate::pyval::get(&s.stats, k) {
        Some(Json::Int(n)) => *n,
        _ => 0,
    };
    let detail = if ok {
        format!(
            "工具 {} · 提示 {} · 类目 {} · 目标平台 {}",
            g("tools"),
            g("prompts"),
            crate::mcp_package::category_or_unknown(&s.stats),
            g("targets")
        )
    } else {
        s.issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}

/// 真源 `_c_pipeline_dryrun`：管线条数 · advisory 数。
///
/// ⚠️ 真源 `sweep` **不接** `graph` 抛的 `ValueError`，异常由契约跑者包成
/// `契约执行异常：<exc>`（`ok=false`）；本线让 `sweep` 返回 `Err(消息)` 并拼成**同一句**——
/// 这条可逐字复刻，故不当作"已知偏差"。
pub(super) fn pipeline_dryrun(root: &Path) -> (bool, String) {
    match crate::pipelinerun::sweep(root) {
        Ok(s) => {
            let ok = s.issues.is_empty();
            let detail = if ok {
                format!(
                    "管线 {} 条零 hard 缺陷（advisory {}）",
                    s.pipelines, s.notes
                )
            } else {
                s.issues
                    .iter()
                    .take(2)
                    .cloned()
                    .collect::<Vec<_>>()
                    .join("; ")
            };
            (ok, detail)
        }
        Err(e) => (false, format!("契约执行异常：{}", e)),
    }
}

/// 真源 `_c_type_backlog`：不可推断 untyped 项数（台账同步）。
pub(super) fn type_backlog(root: &Path) -> (bool, String) {
    let (issues, stats) = crate::payload_harvest::verify_backlog(root);
    let ok = issues.is_empty();
    let n = match crate::pyval::get(&stats, "untyped") {
        Some(Json::Int(v)) => *v,
        _ => 0,
    };
    let detail = if ok {
        format!("不可推断 untyped {} 项（台账同步）", n)
    } else {
        issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}

/// 真源 `_c_purity`：纯度零违规。
pub(super) fn purity_clean(root: &Path) -> (bool, String) {
    let (issues, _stats) = crate::purity::scan(root);
    let ok = issues.is_empty();
    let detail = if ok {
        "纯度零违规".to_string()
    } else {
        issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}

/// 真源 `_c_io_types`：可证不匹配数 · 类型覆盖率（一位小数）。
///
/// 真源分别调 `scan` 与 `coverage`（后者内部**再跑一遍 scan**）；本线一次扫描供两处用。
pub(super) fn io_types_contract(root: &Path) -> (bool, String) {
    let (s, cov) = crate::io_types::coverage(root);
    let ok = s.issues.is_empty();
    let g = |k: &str| match crate::pyval::get(&s.stats, k) {
        Some(Json::Int(n)) => *n,
        _ => 0,
    };
    let typed = g("typed_fields");
    let untyped = g("untyped_fields");
    let detail = if ok {
        // Python `%.1f`：一位小数、正确舍入（出口与真源逐字节比对守住这一条）
        format!(
            "可证不匹配 {} · 类型覆盖 {:.1}%（{}/{} 字段）",
            s.issues.len(),
            cov,
            typed,
            typed + untyped
        )
    } else {
        s.issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}

/// 真源 `_c_endpoint`：端点条数 · status。
pub(super) fn endpoint_contract(root: &Path) -> (bool, String) {
    let e = crate::endpoint::scan(root);
    let ok = e.issues.is_empty();
    let gs = |k: &str, dflt: &str| match crate::pyval::get(&e.stats, k) {
        Some(crate::pyjson::Json::Str(s)) => s.clone(),
        _ => dflt.to_string(),
    };
    let gn = |k: &str| match crate::pyval::get(&e.stats, k) {
        Some(crate::pyjson::Json::Int(n)) => *n,
        _ => 0,
    };
    let detail = if ok {
        format!("端点 {}（status={}）", gn("endpoints"), gs("status", "?"))
    } else {
        e.issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}

/// 真源 `_c_knowledge`：源（合同/参考）· 消化记录 · 频次事件。
///
/// 真源把**三条**判据的 issues 合并：`scan` + `verify_transform` + `verify_usage`；
/// 而 detail 只取 `scan` 的 stats + `verify_usage` 的 `events`。
pub(super) fn knowledge_sources(root: &Path) -> (bool, String) {
    let k = crate::knowledge::scan(root);
    let mut issues = k.issues;
    issues.extend(crate::knowledge::verify_transform(root).issues);
    let usage = crate::knowledge::verify_usage(root);
    issues.extend(usage.issues.clone());
    let gi = |j: &Json, key: &str| match crate::pyval::get(j, key) {
        Some(Json::Int(n)) => *n,
        _ => 0,
    };
    let detail = if issues.is_empty() {
        format!(
            "源 {}（合同 {} / 参考 {}）· 消化记录 {} · 频次事件 {}",
            gi(&k.stats, "sources"),
            gi(&k.stats, "contract"),
            gi(&k.stats, "reference"),
            gi(&k.stats, "transforms"),
            gi(&usage.stats, "events")
        )
    } else {
        issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (issues.is_empty(), detail)
}

/// 真源 `_c_audit`：审计件数 · 带审计头 · legacy · 绑定对象数。
pub(super) fn audit_contract(root: &Path) -> (bool, String) {
    let a = crate::audit::scan(root);
    let ok = a.issues.is_empty();
    let g = |k: &str| match crate::pyval::get(&a.stats, k) {
        Some(Json::Int(n)) => *n,
        _ => 0,
    };
    let detail = if ok {
        format!(
            "审计 {} 件（带审计头 {} · legacy {}）· 绑定对象 {}",
            g("audits"),
            g("with_header"),
            g("legacy"),
            g("subjects_ok")
        )
    } else {
        a.issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}
