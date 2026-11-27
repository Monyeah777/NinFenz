use super::*;

/// 本线自算（第三组）：knowledge / contract / license / coupling / 审计面。
pub(crate) fn native_c(id: &str, root: &Path) -> Option<Called> {
    match id {
        "knowledge" => {
            let k = crate::knowledge::scan(root);
            Some(Called {
                status: k
                    .status
                    .map(|s| s.to_string())
                    .unwrap_or_else(|| status_of(&k.issues, &k.warns)),
                issues: k.issues,
                warns: k.warns,
                stats: k.stats,
            })
        }
        "contract" => {
            let m = crate::machine_contract::scan(root);
            Some(Called {
                status: status_of(&m.issues, &m.warns),
                issues: m.issues,
                warns: m.warns,
                stats: m.stats,
            })
        }
        "license" => {
            let l = crate::license_gate::scan(root);
            Some(Called {
                status: status_of(&l.issues, &[]),
                issues: l.issues,
                warns: Vec::new(),
                stats: l.stats,
            })
        }
        "coupling" => {
            let c = crate::coupling_metrics::scan(root);
            Some(Called {
                status: status_of(&c.issues, &c.warns),
                issues: c.issues,
                warns: c.warns,
                stats: c.stats,
            })
        }
        "judgement_coverage" => {
            let j = crate::judgement_coverage::scan(root);
            Some(Called {
                status: status_of(&j.issues, &j.warns),
                issues: j.issues,
                warns: j.warns,
                stats: j.stats,
            })
        }
        "audit" => {
            let a = crate::audit::scan(root);
            Some(Called {
                status: status_of(&a.issues, &a.warns),
                issues: a.issues,
                warns: a.warns,
                stats: a.stats,
            })
        }
        "workflow_policy" => {
            let w = crate::workflow_policy::scan(root);
            Some(Called {
                status: status_of(&w.issues, &w.warns),
                issues: w.issues,
                warns: w.warns,
                stats: w.stats,
            })
        }
        "rating_decided" => {
            // Z3：`scan` 判「声明在场且合词表」（显式 unrated 也算合格 ⇒ 覆盖率恒 100%）；
            // 本判据判第二层：只声明未定级的件算不算数（`rating.allow_unrated` fail-closed）。
            let got = crate::rating_gate::decided(root);
            Some(Called {
                status: status_of(&got.issues, &[]),
                issues: got.issues,
                warns: Vec::new(),
                stats: got.stats,
            })
        }
        "rating" => {
            let r = crate::rating_gate::scan(root);
            Some(Called {
                status: status_of(&r.issues, &[]),
                issues: r.issues,
                warns: Vec::new(),
                stats: r.stats,
            })
        }
        _ => None,
    }
}

/// 本线自算（第四组）：library / projection / key_naming / intake / payload / 账本面。
pub(crate) fn native_d(id: &str, root: &Path) -> Option<Called> {
    match id {
        "library" => {
            let l = crate::library::verify(root);
            Some(Called {
                status: status_of(&l.issues, &l.warns),
                issues: l.issues,
                warns: l.warns,
                stats: l.stats,
            })
        }
        // 形态 `list`：真源直接返回 issues 列表
        "library_projection" => {
            let issues = crate::library::check_projection(root);
            Some(Called {
                status: status_of(&issues, &[]),
                issues,
                warns: Vec::new(),
                stats: empty_obj(),
            })
        }
        "key_naming" => {
            let k = crate::key_naming::scan(root);
            // 三态：issues 非空 = fail；否则 warns 非空 = warn；都空 = pass
            let status = k
                .status
                .map(|s| s.to_string())
                .unwrap_or_else(|| status_of(&k.issues, &k.warns));
            Some(Called {
                status,
                issues: k.issues,
                warns: k.warns,
                stats: k.stats,
            })
        }
        "intake" => {
            let k = crate::intake::scan(root);
            Some(Called {
                status: status_of(&k.issues, &[]),
                issues: k.issues,
                warns: Vec::new(),
                stats: k.stats,
            })
        }
        "payload" => {
            let (issues, stats) = crate::payload_registry::scan(root);
            Some(Called {
                status: status_of(&issues, &[]),
                issues,
                warns: Vec::new(),
                stats: stats.map(|s| s.to_json()).unwrap_or_else(empty_obj),
            })
        }
        "assets_ledger" => {
            let (issues, stats) = crate::asset_ledger_projection::verify(root);
            Some(Called {
                status: status_of(&issues, &[]),
                issues,
                warns: Vec::new(),
                stats: stats.unwrap_or_else(empty_obj),
            })
        }
        "instruction" => {
            let (issues, stats) = crate::instruction_step_audit::scan(root);
            Some(Called {
                status: status_of(&issues, &[]),
                issues,
                warns: Vec::new(),
                stats: stats.map(|s| s.to_json()).unwrap_or_else(empty_obj),
            })
        }
        // 真源 `check_strict` 是 `repo_stats.check` 的别名（模块里并无该属性）
        "self_stats" => {
            let (issues, stats) = crate::stats::check(root);
            Some(Called {
                status: status_of(&issues, &[]),
                issues,
                warns: Vec::new(),
                stats: stats.to_json(),
            })
        }
        _ => None,
    }
}

/// 真源 `_call`：先本线自算，未移植则取喂入值。
pub(crate) fn call(spec: &Spec, root: &Path, supplied: &HashMap<String, Supplied>) -> Called {
    if let Some(c) = native(spec, root) {
        return c;
    }
    match supplied.get(spec.id) {
        Some(s) => Called {
            status: s.status.clone().unwrap_or_else(|| status_of(&s.issues, &s.warns)),
            issues: s.issues.clone(),
            warns: s.warns.clone(),
            stats: s.stats.clone(),
        },
        None => Called {
            status: "error".to_string(),
            issues: vec![format!(
                "{}.{} 未移植且未喂入结果（修复指引：本线尚未移植该扫描器；用 --results 提供它的 issues/warns/stats）",
                spec.module, spec.entry
            )],
            warns: Vec::new(),
            stats: empty_obj(),
        },
    }
}

/// 真源 `_declared` + `build` 对声明面的两口补充（判据条数 + 「判据级抽查面 ≠ check 全量」）。
pub(crate) fn declared(root: &Path) -> Json {
    let (ec, ep) = baseline::constants(root);
    let (_, stats) = baseline::scan(root);
    let vv = stats.map(|s| s.verify_version);
    let note = format!(
        "判据级抽查面 {} 条，各对应 verify.sh 的一道或多道门禁；≠ 声明 check 总数 {}（两者不可互替）",
        SPECS.len(),
        ec.map(|n| n.to_string()).unwrap_or_else(|| "None".to_string())
    );
    Json::Object(vec![
        (
            "expected_checks".to_string(),
            ec.map(Json::Int).unwrap_or(Json::Null),
        ),
        (
            "expected_pass".to_string(),
            ep.map(Json::Int).unwrap_or(Json::Null),
        ),
        (
            "verify_version".to_string(),
            vv.map(Json::Str).unwrap_or(Json::Null),
        ),
        ("report_items".to_string(), Json::Int(SPECS.len() as i64)),
        ("coverage_note".to_string(), Json::Str(note)),
    ])
}

/// 真源 `build` 的基准日：**UTC 今天**（YYYY-MM-DD）。
///
/// 为什么用 UTC 而非本机日历：报告是跨平台复算的（CI 跑 UTC、作者机常在东八区）；
/// 本机日历会让同一提交在不同时区生成不同 `built_for_date`，「提交件 == 实时重算」必红
/// （真源 `verify_report.build` 的注释有 2026-11-07 实测）。这里用 SystemTime→天数→
/// 公历（Howard Hinnant 算法），不引 chrono/time 依赖。
pub(crate) fn today_utc_iso() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let z = (secs / 86400) as i64 + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let mut y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    if m <= 2 {
        y += 1;
    }
    format!("{:04}-{:02}-{:02}", y, m, d)
}

/// 真源 `build`：跑全部判据 → 报告 dict（含声明/实测并排 + 稳定 digest）。
pub(crate) fn build(root: &Path, supplied: &HashMap<String, Supplied>) -> Json {
    let mut items: Vec<Json> = Vec::new();
    let mut counts: HashMap<&str, i64> = HashMap::new();
    for spec in SPECS.iter() {
        let c = call(spec, root, supplied);
        *counts
            .entry(match c.status.as_str() {
                "pass" => "pass",
                "fail" => "fail",
                "warn" => "warn",
                _ => "error",
            })
            .or_insert(0) += 1;
        let sample: Vec<Json> = c
            .issues
            .iter()
            .take(3)
            .map(|x| Json::Str(x.chars().take(200).collect()))
            .collect();
        items.push(Json::Object(vec![
            ("id".to_string(), Json::Str(spec.id.to_string())),
            ("name".to_string(), Json::Str(spec.name.to_string())),
            ("source".to_string(), Json::Str(spec.source())),
            ("status".to_string(), Json::Str(c.status)),
            ("issues".to_string(), Json::Int(c.issues.len() as i64)),
            ("warns".to_string(), Json::Int(c.warns.len() as i64)),
            ("stats".to_string(), c.stats),
            ("sample".to_string(), Json::Array(sample)),
        ]));
    }
    let summary = Json::Object(
        ["pass", "fail", "warn", "error"]
            .iter()
            .map(|k| ((*k).to_string(), Json::Int(*counts.get(k).unwrap_or(&0))))
            .collect(),
    );
    let mut body = Json::Object(vec![
        ("schema".to_string(), Json::Str(SCHEMA.to_string())),
        ("items".to_string(), Json::Array(items)),
        ("summary".to_string(), summary),
        ("declared".to_string(), declared(root)),
        ("built_for_date".to_string(), Json::Str(today_utc_iso())),
    ]);
    let digest_src = body.dumps_default();
    let digest = merkle::hex(&merkle::sha256(digest_src.as_bytes()));
    if let Json::Object(pairs) = &mut body {
        pairs.push(("root_digest".to_string(), Json::Str(digest)));
    }
    body
}

/// 真源 `render`：`json.dumps(..., indent=2, sort_keys=True) + "\n"`（LF）。
pub(crate) fn render(report: &Json) -> Vec<u8> {
    report.dumps_file().into_bytes()
}

/// 真源 `check`：提交件 == 实时重算 → `(issues, live)`。
pub(crate) fn check(root: &Path, supplied: &HashMap<String, Supplied>) -> (Vec<String>, Json) {
    let live = build(root, supplied);
    let p = root.join(REPORT_REL);
    if !p.is_file() {
        return (
            vec![format!(
                "缺 {}（修复指引：python scripts/verify_report.py --write）",
                REPORT_REL
            )],
            live,
        );
    }
    let recorded =
        jsonread::read_file(root, REPORT_REL).unwrap_or_else(|| Json::Object(Vec::new()));
    let mut issues: Vec<String> = Vec::new();
    if py_str(get(&recorded, "root_digest")) != py_str(get(&live, "root_digest")) {
        let a = py_str(get(&recorded, "root_digest"));
        let b = py_str(get(&live, "root_digest"));
        issues.push(format!(
            "{} 与实时重算不一致（记录={} 实测={}）（修复指引：重跑 python scripts/verify_report.py --write）",
            REPORT_REL,
            trunc(&a, 12),
            trunc(&b, 12)
        ));
    }
    if plain_str_opt(get(&recorded, "schema")) != SCHEMA {
        issues.push(format!(
            "{} schema 不匹配（期望 {}）（修复指引：重跑 --write）",
            REPORT_REL, SCHEMA
        ));
    }
    (issues, live)
}

pub(crate) fn trunc(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

/// 真源 `summary_line`。
pub(crate) fn summary_line(report: &Json) -> String {
    let s = get(report, "summary");
    let d = get(report, "declared");
    let g = |o: Option<&Json>, k: &str| -> String {
        match o.and_then(|x| get(x, k)) {
            Some(Json::Null) | None => "None".to_string(),
            Some(v) => crate::pyval::plain_str(v),
        }
    };
    format!(
        "判据 {} 条：PASS {} · FAIL {} · WARN {} · ERROR {}；声明 check1-{} / PASS={} · verify {}（判据级抽查面，非 check 全量）",
        crate::pyval::arr_items(get(report, "items")).len(),
        g(s, "pass"),
        g(s, "fail"),
        g(s, "warn"),
        g(s, "error"),
        g(d, "expected_checks"),
        g(d, "expected_pass"),
        g(d, "verify_version")
    )
}
