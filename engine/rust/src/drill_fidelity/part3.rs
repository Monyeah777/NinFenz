use super::*;

/// 真源 `s.split(":", 1)[-1]`：无冒号即整串。
pub(crate) fn tail_after_colon(s: &str) -> String {
    match s.split_once(':') {
        Some((_, tail)) => tail.to_string(),
        None => s.to_string(),
    }
}

pub(crate) fn parse_uint(s: &str) -> i64 {
    s.parse::<i64>().unwrap_or(0)
}

// ============================================================ drill_fidelity（外层判据）

pub(crate) struct ExecSet {
    pub(crate) set: String,
    pub(crate) cases: i64,
    pub(crate) passed: i64,
    pub(crate) error: Option<String>,
}

pub(crate) struct RoundSample {
    pub(crate) sample: String,
    pub(crate) declared: String,
    pub(crate) live: String,
    pub(crate) matched: bool,
    pub(crate) first_issue: String,
    /// 真源 `label_status == "pending"` 或 `verdict == "pending"`：未裁定样本。
    pub(crate) pending: bool,
    /// 回合数（parse 成功 ⇔ `turns > 0`；待裁定样本的 parse 是裁定前提）。
    pub(crate) turns: i64,
    /// 样本坏件（真源 `_round_sample` 的 `error` 键）：非空时 `scan` 直接报该条并跳过其余判定。
    pub(crate) error: Option<String>,
}

/// 真源 `_exec_sets`。返回 `(集合, issues)`——坏 JSON 记 issue（措辞自拟，见模块头偏差 1/2）。
pub(crate) fn exec_sets(root: &Path) -> Vec<ExecSet> {
    let mut out: Vec<ExecSet> = Vec::new();
    for rel in crate::glob::expand(root, EXEC_GLOB) {
        let name = rel.rsplit('/').next().unwrap_or(&rel).to_string();
        let Some(data) = jsonread::read_file(root, &rel) else {
            out.push(ExecSet {
                error: Some(format!(
                    "JSON 不可解析：（本线不复刻 CPython 解析器原文，见模块头）"
                )),
                set: name,
                cases: 0,
                passed: 0,
            });
            continue;
        };
        if !matches!(data, Json::Object(_)) {
            out.push(ExecSet {
                error: Some("JSON 顶层非对象（真源在此记 ERROR，本线如实报出）".to_string()),
                set: name,
                cases: 0,
                passed: 0,
            });
            continue;
        }
        let real_ids: Vec<String> = arr_items(get(&data, "real_ids"))
            .iter()
            .map(|v| py_str(Some(v)))
            .collect();
        let other_ids: Vec<String> = arr_items(get(&data, "other_ids"))
            .iter()
            .map(|v| py_str(Some(v)))
            .collect();
        let asset_keys: Vec<String> = arr_items(get(&data, "asset_keys"))
            .iter()
            .map(|v| py_str(Some(v)))
            .collect();
        let semantics = get(&data, "semantics");
        let lexicon = get(&data, "lexicon");
        // 真源 `data.get("source_text", "")`：**键不在场**才取默认；在场为 null 则传 None 下去
        let src_opt: Option<&Json> = get(&data, "source_text");
        let src = plain_str_opt(src_opt);
        let mut n = 0i64;
        let mut ok = 0i64;
        for case in arr_items(get(&data, "cases")) {
            if !matches!(case, Json::Object(_)) {
                // 真源 `case.get` 在此抛 AttributeError ⇒ ERROR；本线按「不通过」计，保守侧
                n += 1;
                continue;
            }
            let hits = run_case(
                case,
                &real_ids,
                semantics,
                &src,
                &other_ids,
                &asset_keys,
                lexicon,
            );
            let expect: Vec<String> = arr_items(get(case, "expect_captured"))
                .iter()
                .map(|v| py_str(Some(v)))
                .collect();
            let good = (expect.is_empty() && hits.is_empty())
                || expect.iter().all(|e| hits.iter().any(|h| h == e));
            n += 1;
            if good {
                ok += 1;
            }
        }
        out.push(ExecSet {
            set: name,
            cases: n,
            passed: ok,
            error: None,
        });
    }
    out
}

/// 真源 `_round_samples`。返回 `(样本, issues)`。
pub(crate) fn round_samples(root: &Path) -> Vec<RoundSample> {
    let mut out: Vec<RoundSample> = Vec::new();
    for rel in crate::glob::expand(root, ROUND_GLOB) {
        let name = rel.rsplit('/').next().unwrap_or(&rel).to_string();
        let declared_of = |d: &Json| -> String {
            // 真源 `VERDICT_MAP.get(str(verdict or "").lower(), str(verdict))`
            let raw = plain_str_opt(get(d, "verdict"));
            let lowered = py_str(get(d, "verdict")).to_lowercase();
            verdict_map(&lowered).map(|s| s.to_string()).unwrap_or(raw)
        };
        let Some(d) = jsonread::read_file(root, &rel) else {
            out.push(RoundSample {
                error: Some(format!(
                    "JSON 不可解析：{} 不是合法 JSON：（本线不复刻 CPython 解析器原文，见模块头）",
                    name
                )),
                sample: name,
                declared: "?".to_string(),
                live: "error".to_string(),
                matched: false,
                pending: false,
                turns: 0,
                first_issue: String::new(),
            });
            continue;
        };
        if !matches!(d, Json::Object(_)) {
            out.push(RoundSample {
                error: Some(format!(
                    "JSON 不可解析：{} 顶层形状不对：（本线不复刻 CPython 解析器原文，见模块头）",
                    name
                )),
                sample: name,
                declared: "?".to_string(),
                live: "error".to_string(),
                matched: false,
                pending: false,
                turns: 0,
                first_issue: String::new(),
            });
            continue;
        }
        let transcript = py_str(get(&d, "transcript"));
        let allowed: Vec<String> = arr_items(get(&d, "allowed"))
            .iter()
            .map(|v| py_str(Some(v)))
            .collect();
        let (issues, turns, _gaps) = round_scan(&transcript, &allowed);
        let live = if issues.is_empty() {
            "conformant"
        } else {
            "non-conformant"
        };
        let declared = declared_of(&d);
        // 真源：`label_status`/`verdict` 为 pending ⇒ 未裁定（不参与「声明 vs 实测」分子分母）。
        let pending = py_str(get(&d, "label_status")).to_lowercase() == "pending"
            || py_str(get(&d, "verdict")).to_lowercase() == "pending";
        out.push(RoundSample {
            sample: name,
            matched: !pending && declared == live,
            declared,
            live: live.to_string(),
            first_issue: issues.first().cloned().unwrap_or_default(),
            pending,
            turns,
            error: None,
        });
    }
    out
}

/// 真源 `round(x, 4) if y else 0.0`（CPython 半偶舍入）。
pub(crate) fn fidelity(pass: i64, total: i64) -> f64 {
    if total == 0 {
        0.0
    } else {
        crate::pyfloat::round_to(pass as f64 / total as f64, 4)
    }
}

/// 真源 `drill_fidelity.scan` → `(issues, warns, stats)`。
pub(crate) fn scan(root: &Path) -> (Vec<String>, Vec<String>, Json) {
    let sets = exec_sets(root);
    let samples = round_samples(root);

    let ex_cases: i64 = sets.iter().map(|s| s.cases).sum();
    let ex_pass: i64 = sets.iter().map(|s| s.passed).sum();
    // 待裁定样本（pending）不参与「声明 vs 实测」分子分母（未裁定就无声明可复现），
    // 但必须解析出回合标记——parse 是裁定前提。
    let adjudicated: Vec<&RoundSample> = samples.iter().filter(|s| !s.pending).collect();
    let rnd_total = adjudicated.len() as i64;
    let rnd_pass = adjudicated.iter().filter(|s| s.matched).count() as i64;
    let total = ex_cases + rnd_total;
    let passed = ex_pass + rnd_pass;

    let mut issues: Vec<String> = Vec::new();
    if ex_cases == 0 {
        issues.push(format!(
            "找不到执行演练用例（修复指引：{} 下须有 p*_drill_cases.json）",
            EXEC_GLOB
        ));
    }
    if rnd_total == 0 {
        issues.push(format!(
            "找不到回合级回放样本（修复指引：{} 下须有样本，含 transcript/allowed/verdict）",
            ROUND_GLOB
        ));
    }
    for s in &sets {
        if let Some(e) = &s.error {
            issues.push(format!("{} {}", s.set, e));
        } else if s.passed != s.cases {
            issues.push(format!(
                "执行演练保真度不足：{} {}/{}（修复指引：先修样本集自身或捕获逻辑，演练集不达标不得入库）",
                s.set, s.passed, s.cases
            ));
        }
    }
    for s in &samples {
        if let Some(err) = &s.error {
            issues.push(format!("{} {}", s.sample, err));
            continue;
        }
        if s.pending {
            if s.turns == 0 {
                issues.push(format!(
                    "待裁定回合样本未解析出回合标记：{}（parse 失败 ⇒ 裁定前提不成立；修复指引：转录须含「回合 N：」/「第 N 回合」）",
                    s.sample
                ));
            }
            continue;
        }
        if !s.matched {
            let head: String = s.first_issue.chars().take(60).collect();
            issues.push(format!(
                "回合级回放未复现声明：{} 声明={} 实测={}（{}）（修复指引：修样本或回合断言——回放须可复现声明结论）",
                s.sample, s.declared, s.live, head
            ));
        }
    }

    // 真源 `stats = m["overall"]` 再 update 两个键 ⇒ 键序为 cases/passed/fidelity/exec_sets/round_samples
    let stats = Json::Object(vec![
        ("cases".to_string(), Json::Int(total)),
        ("passed".to_string(), Json::Int(passed)),
        ("fidelity".to_string(), Json::Float(fidelity(passed, total))),
        ("exec_sets".to_string(), Json::Int(sets.len() as i64)),
        // 真源 `stats["round_samples"]` = 样本文件总数（含待裁定样本）；`cases` 只计已裁定样本。
        ("round_samples".to_string(), Json::Int(samples.len() as i64)),
    ]);
    (issues, Vec::new(), stats)
}
