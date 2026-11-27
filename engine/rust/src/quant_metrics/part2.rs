use super::*;

pub(crate) fn pbool(params: &[(String, Json)], k: &str, d: bool) -> bool {
    match params.iter().find(|(kk, _)| kk == k).map(|(_, v)| v) {
        Some(Json::Bool(b)) => *b,
        _ => d,
    }
}

/// 真源 `performance_report`（关键字参数走 `params`）。
pub(crate) fn performance_report(series: &Json, params: &[(String, Json)]) -> Result<Json, String> {
    let frequency = pstr(params, "frequency", "daily");
    let af = match annual_factor(&frequency) {
        Some(v) => v,
        None => {
            let mut keys = vec!["daily", "weekly", "monthly"];
            keys.sort();
            // 真源是 `sorted(ANNUAL_FACTORS)` 的 **Python 列表 repr**（单引号）
            let shown = crate::pyval::py_repr_list(
                &keys
                    .iter()
                    .map(|k| Json::Str(k.to_string()))
                    .collect::<Vec<_>>(),
            );
            return Err(format!(
                "频率须在 {} 中，实为 {}",
                shown,
                crate::pyval::py_repr(&Json::Str(frequency))
            ));
        }
    };
    let equity = nums(series, "equity");
    let bench = nums(series, "benchmark");
    let has_bench = bench.len() == equity.len() && !bench.is_empty();
    let period_start = pstr(params, "period_start", "");
    let period_end = pstr(params, "period_end", "");
    let currency = pstr(params, "currency", "CNY");
    let return_basis = pstr(params, "return_basis", "simple");
    let rf = pnum(params, "risk_free_rate_annual", 0.0);
    let benchmark_id = pstr(params, "benchmark_id", "");
    let fee = pnum(params, "cost_bps_fee", 0.0);
    let slip = pnum(params, "cost_bps_slippage", 0.0);
    let fill_rule = pstr(params, "fill_rule", "next_open");
    let single_side = pbool(params, "single_side_turnover", true);
    let as_of = pstr(params, "as_of", "");
    let gross = block(&equity, af, rf, &return_basis)?;
    let rf_txt = crate::pyfloat::repr(rn(rf));
    let fee_txt = crate::pyfloat::repr(rn(fee));
    let slip_txt = crate::pyfloat::repr(rn(slip));
    let effective_as_of = if as_of.is_empty() {
        period_end.clone()
    } else {
        as_of.clone()
    };
    // ⚠️ `benchmark` / `excess` 先在占位处写 `null`，真有值时**必须覆盖**（真源是
    // `doc["benchmark"] = {...}`）。append 会让同一份 JSON 出现**两个同名键**——
    // 实测（2026-10-04）由此整份报告对不上。
    let mut doc: Vec<(String, Json)> = vec![
        ("kind".to_string(), Json::Str("nf-performance/1".to_string())),
        ("as_of".to_string(), Json::Str(effective_as_of)),
        ("currency".to_string(), Json::Str(currency)),
        ("return_basis".to_string(), Json::Str(return_basis.clone())),
        ("frequency".to_string(), Json::Str(frequency.clone())),
        ("annual_factor".to_string(), Json::Int(af)),
        ("risk_free_rate_annual".to_string(), r6(rf)),
        (
            "period".to_string(),
            Json::Object(vec![
                ("start".to_string(), Json::Str(period_start)),
                ("end".to_string(), Json::Str(period_end)),
                ("observations".to_string(), Json::Int(equity.len() as i64)),
            ]),
        ),
        ("gross".to_string(), gross.clone()),
        ("benchmark".to_string(), Json::Null),
        ("excess".to_string(), Json::Null),
        (
            "costs".to_string(),
            Json::Object(vec![
                ("fee_bps".to_string(), r6(fee)),
                ("slippage_bps".to_string(), r6(slip)),
                ("fill_rule".to_string(), Json::Str(fill_rule.clone())),
                (
                    "turnover_basis".to_string(),
                    Json::Str(if single_side { "single_side" } else { "double_side" }.to_string()),
                ),
            ]),
        ),
        (
            "disclosures".to_string(),
            disclosures(&return_basis, af, &frequency, &rf_txt, &fee_txt, &slip_txt, &fill_rule),
        ),
    ];
    apply_benchmark(&mut doc, has_bench, &bench, af, rf, &return_basis, &benchmark_id, &equity, &gross)?;
    Ok(Json::Object(doc))
}

/// 同名键覆盖写入（真源 dict 语义；append 会产生重复键）。
pub(crate) fn set_key(doc: &mut Vec<(String, Json)>, k: &str, v: Json) {
    match doc.iter_mut().find(|(kk, _)| kk == k) {
        Some(slot) => slot.1 = v,
        None => doc.push((k.to_string(), v)),
    }
}

/// 报告的口径披露文本（收益口径 / 年化因子 / 成本 / 成交价假设 / GIPS）。
pub(crate) fn disclosures(
    return_basis: &str,
    af: i64,
    frequency: &str,
    rf_txt: &str,
    fee_txt: &str,
    slip_txt: &str,
    fill_rule: &str,
) -> Json {
    Json::Array(
        vec![
            format!(
                "收益口径 = {}；年化因子 = {}（{}）；无风险利率年化 = {}",
                return_basis, af, frequency, rf_txt
            ),
            format!(
                "绩效为**毛口径**（未扣费）；费用与滑点按申报值计（fee={} bps, slippage={} bps）",
                fee_txt, slip_txt
            ),
            format!(
                "成交价假设 = {}（须晚于信号时点；前视偏差口径见 DATA_CONTRACT §7）",
                fill_rule
            ),
            "最大回撤 / 卡尔玛按净值序列口径；卡尔玛分子分母同区间".to_string(),
            GIPS_ALIGNMENT.to_string(),
        ]
        .into_iter()
        .map(Json::Str)
        .collect(),
    )
}

/// 基准面（benchmark / excess）覆盖写入；无基准或长度不符时不动。
pub(crate) fn apply_benchmark(
    doc: &mut Vec<(String, Json)>,
    has_bench: bool,
    bench: &[f64],
    af: i64,
    rf: f64,
    return_basis: &str,
    benchmark_id: &str,
    equity: &[f64],
    gross: &Json,
) -> Result<(), String> {
if has_bench {
    let mut bblock: Vec<(String, Json)> = vec![(
        "id".to_string(),
        Json::Str(if benchmark_id.is_empty() {
            "UNSPECIFIED".to_string()
        } else {
            benchmark_id.to_string()
        }),
    )];
    if let Json::Object(o) = block(bench, af, rf, &return_basis)? {
        bblock.extend(o);
    }
    let gross_ann = match obj_num(&gross, "annualized") {
        v => v,
    };
    let bench_ann = obj_num(&Json::Object(bblock.clone()), "annualized");
    let rets = returns(equity, &return_basis)?;
    let brets = returns(bench, &return_basis)?;
    set_key(doc, "benchmark", Json::Object(bblock));
    set_key(
        doc,
        "excess",
        Json::Object(vec![
            ("annualized".to_string(), r6(gross_ann - bench_ann)),
            (
                "tracking_error".to_string(),
                r6(tracking_error(&rets, &brets, af)),
            ),
            (
                "information_ratio".to_string(),
                r6(information_ratio(&rets, &brets, af)),
            ),
        ]),
    );
}
Ok(())
}

pub(crate) fn obj_num(v: &Json, k: &str) -> f64 {
    match v {
        Json::Object(o) => match o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv) {
            Some(Json::Float(f)) => *f,
            Some(Json::Int(i)) => *i as f64,
            _ => 0.0,
        },
        _ => 0.0,
    }
}

/// 真源 `vega_equity_curve`。
pub(crate) fn vega_equity_curve(series: &Json, title: &str) -> Json {
    let dates = str_list(series, "dates");
    let equity = nums(series, "equity");
    let bench = nums(series, "benchmark");
    let mut data: Vec<Json> = Vec::new();
    for (d, v) in dates.iter().zip(equity.iter()) {
        data.push(Json::Object(vec![
            ("date".to_string(), Json::Str(d.clone())),
            ("series".to_string(), Json::Str("策略".to_string())),
            ("value".to_string(), Json::Float(*v)),
        ]));
    }
    if !bench.is_empty() {
        for (d, v) in dates.iter().zip(bench.iter()) {
            data.push(Json::Object(vec![
                ("date".to_string(), Json::Str(d.clone())),
                ("series".to_string(), Json::Str("基准".to_string())),
                ("value".to_string(), Json::Float(*v)),
            ]));
        }
    }
    Json::Object(vec![
        (
            "$schema".to_string(),
            Json::Str("https://vega.github.io/schema/vega-lite/v5.json".to_string()),
        ),
        ("description".to_string(), Json::Str(title.to_string())),
        (
            "data".to_string(),
            Json::Object(vec![("values".to_string(), Json::Array(data))]),
        ),
        (
            "mark".to_string(),
            Json::Object(vec![
                ("type".to_string(), Json::Str("line".to_string())),
                ("point".to_string(), Json::Bool(false)),
            ]),
        ),
        (
            "encoding".to_string(),
            Json::Object(vec![
                (
                    "x".to_string(),
                    Json::Object(vec![
                        ("field".to_string(), Json::Str("date".to_string())),
                        ("type".to_string(), Json::Str("temporal".to_string())),
                        ("title".to_string(), Json::Str("日期".to_string())),
                    ]),
                ),
                (
                    "y".to_string(),
                    Json::Object(vec![
                        ("field".to_string(), Json::Str("value".to_string())),
                        ("type".to_string(), Json::Str("quantitative".to_string())),
                        ("title".to_string(), Json::Str("净值".to_string())),
                        (
                            "scale".to_string(),
                            Json::Object(vec![("zero".to_string(), Json::Bool(false))]),
                        ),
                    ]),
                ),
                (
                    "color".to_string(),
                    Json::Object(vec![
                        ("field".to_string(), Json::Str("series".to_string())),
                        ("type".to_string(), Json::Str("nominal".to_string())),
                        ("title".to_string(), Json::Str(String::new())),
                    ]),
                ),
            ]),
        ),
    ])
}

/// 真源 `vega_drawdown`。
pub(crate) fn vega_drawdown(series: &Json, title: &str) -> Json {
    let dd = drawdown_series(&nums(series, "equity"));
    let dates = str_list(series, "dates");
    let data: Vec<Json> = dates
        .iter()
        .zip(dd.iter())
        .map(|(d, v)| {
            Json::Object(vec![
                ("date".to_string(), Json::Str(d.clone())),
                ("value".to_string(), Json::Float(-v.abs())),
            ])
        })
        .collect();
    Json::Object(vec![
        (
            "$schema".to_string(),
            Json::Str("https://vega.github.io/schema/vega-lite/v5.json".to_string()),
        ),
        ("description".to_string(), Json::Str(title.to_string())),
        (
            "data".to_string(),
            Json::Object(vec![("values".to_string(), Json::Array(data))]),
        ),
        (
            "mark".to_string(),
            Json::Object(vec![
                ("type".to_string(), Json::Str("area".to_string())),
                ("line".to_string(), Json::Bool(true)),
            ]),
        ),
        (
            "encoding".to_string(),
            Json::Object(vec![
                (
                    "x".to_string(),
                    Json::Object(vec![
                        ("field".to_string(), Json::Str("date".to_string())),
                        ("type".to_string(), Json::Str("temporal".to_string())),
                        ("title".to_string(), Json::Str("日期".to_string())),
                    ]),
                ),
                (
                    "y".to_string(),
                    Json::Object(vec![
                        ("field".to_string(), Json::Str("value".to_string())),
                        ("type".to_string(), Json::Str("quantitative".to_string())),
                        ("title".to_string(), Json::Str("回撤".to_string())),
                        (
                            "scale".to_string(),
                            Json::Object(vec![("zero".to_string(), Json::Bool(true))]),
                        ),
                    ]),
                ),
            ]),
        ),
    ])
}

pub(crate) fn str_list(series: &Json, key: &str) -> Vec<String> {
    match series {
        Json::Object(o) => match o.iter().find(|(k, _)| k == key).map(|(_, v)| v) {
            Some(Json::Array(a)) => a.iter().map(crate::pyval::plain_str).collect(),
            _ => Vec::new(),
        },
        _ => Vec::new(),
    }
}

/// 真源 `mermaid_declaration_flow`（**静态文本**，末尾带换行）。
pub(crate) fn mermaid_declaration_flow() -> String {
    [
        "%% 口径声明链（QUANT_METRICS 口径纪律的可视化，非新增真源）",
        "flowchart LR",
        "  A[收益口径 simple/log] --> D[绩效报告]",
        "  B[年化因子 252/52/12] --> D",
        "  C[无风险利率 rf] --> D",
        "  E[净值序列] --> D",
        "  D --> F[披露面 disclosures]",
        "  G[成本与滑点申报] --> F",
        "  H[基准与成交价假设] --> F",
    ]
    .join("\n")
        + "\n"
}
