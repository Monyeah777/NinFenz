//! 馆藏与投影契约（library / schema / patterns / handover / postmortem / module-signature / doc-kinds / canonical）。
//!
//! 自 `contracts.rs` 按族拆出：判据实现逐字搬运，逻辑与文案未改；由父模块 glob 引入分派面。

use crate::pyjson::Json;
use std::path::Path;

/// 真源 `_c_library_projection`：投影一致（只看 issues）。
pub(super) fn library_projection(root: &Path) -> (bool, String) {
    let issues = crate::library::check_projection(root);
    let ok = issues.is_empty();
    let detail = if ok {
        "投影一致".to_string()
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

/// 真源 `_c_library_verify`：馆藏 frontmatter 真源零 FAIL（只看 issues）。
pub(super) fn library_verify(root: &Path) -> (bool, String) {
    let issues = crate::library::verify(root).issues;
    let ok = issues.is_empty();
    let detail = if ok {
        "馆藏 frontmatter 真源零 FAIL".to_string()
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

/// 真源 `_c_schema`：IDL 单一真相零漂移。
pub(super) fn schema_clean(root: &Path) -> (bool, String) {
    let (issues, stats) = crate::schema_lint::scan(root);
    let ok = issues.is_empty();
    let detail = if ok {
        // 真源 `len(stats)` 取的是 stats 字典的**键数**（恒为 6），不是某个计数
        format!("schema 零漂移（{} 类件）", 6)
    } else {
        issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    let _ = stats;
    (ok, detail)
}

/// 真源 `_c_patterns`：格式 + 可证 + 投影一致。
pub(super) fn patterns(root: &Path) -> (bool, String) {
    let (mut issues, n) = crate::patterns::scan_issues(root);
    issues.extend(crate::patterns::check_projection(root));
    let ok = issues.is_empty();
    let detail = if ok {
        format!("实践包 {} 条（格式/可证/投影）", n)
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

/// 真源 `_c_handover`：交接件数 · 未决条数。
pub(super) fn handover(root: &Path) -> (bool, String) {
    let s = crate::handover::scan(root);
    let ok = s.issues.is_empty();
    let detail = if ok {
        format!("交接件 {} 件 · 未决 {} 条", s.handovers, s.pending)
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

/// 真源 `_c_postmortem`：复盘件数 · 行动项条数。
pub(super) fn postmortem(root: &Path) -> (bool, String) {
    let s = crate::postmortem::scan(root);
    let ok = s.issues.is_empty();
    let detail = if ok {
        format!("复盘 {} 件 · 行动项 {} 条", s.postmortems, s.actions)
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

/// 真源 `_c_modeling`：词表 · 规范/说明件 · 数据契约。
pub(super) fn modeling(root: &Path) -> (bool, String) {
    let s = crate::modeling::scan(root);
    let ok = s.issues.is_empty();
    let detail = if ok {
        format!(
            "词表 {} · 规范件 {} / 说明件 {} · 数据契约 {}",
            s.schemes, s.normative, s.informative_files, s.contracts
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

/// 真源 `_c_event_backing`：事件数 · 跨包数 · 挂账数（挂账 = 已登记为外部通道、无仓内发布方）。
pub(super) fn event_backing(root: &Path) -> (bool, String) {
    let s = crate::registry_cross::scan(root);
    let ok = s.issues.is_empty();
    let detail = if ok {
        format!(
            "事件 {} · 跨包 {} · 挂账 {}",
            s.events, s.cross_pkg, s.allowlisted
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

/// 真源 `_c_module_signature`：模块边界零漂移。
pub(super) fn module_signature(root: &Path) -> (bool, String) {
    let issues = crate::module_signature::verify_issues(root);
    let ok = issues.is_empty();
    let detail = if ok {
        "模块边界零漂移".to_string()
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

/// 真源 `_c_doc_kinds`：四型覆盖（issues）+ 写法（warns 只计数进 detail）。
pub(super) fn doc_kinds(root: &Path) -> (bool, String) {
    let issues = crate::doc_hygiene::kind_coverage();
    let warns = crate::doc_hygiene::kind_rules(root);
    let ok = issues.is_empty();
    let detail = if ok {
        format!("四型全覆盖 · 写法 WARN {}", warns.len())
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

/// 真源 `_c_canonical`：同一对象**换键序**后规范摘要必须一致。
///
/// 真源口径 = `attest.canonical` = `json.dumps(sort_keys=True, ensure_ascii=False,
/// separators=(",",":"))` —— 与 `pyjson::dumps_compact` **同式**，故本线直接复用它。
/// 这条判据是"所有溯源的地基"：键序若渗进摘要，整个证据链就不可复现。
pub(super) fn canonical_determinism() -> (bool, String) {
    let a = Json::Object(vec![
        ("b".to_string(), Json::Int(2)),
        ("a".to_string(), Json::Int(1)),
    ])
    .dumps_compact();
    let b = Json::Object(vec![
        ("a".to_string(), Json::Int(1)),
        ("b".to_string(), Json::Int(2)),
    ])
    .dumps_compact();
    if a == b {
        (true, "canonical digest 两遍一致".to_string())
    } else {
        (false, "不一致".to_string())
    }
}
