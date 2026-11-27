use super::*;

/// 真源 `preference`。
pub(crate) fn preference(rows: &[Row]) -> Result<Json, String> {
    let n = rows.len() as f64;
    let agree = rows
        .iter()
        .filter(|r| get(r, "judge") == get(r, "human"))
        .count() as i64;
    let win = rows.iter().filter(|r| get(r, "judge") == "a").count() as i64;
    let loss = rows.iter().filter(|r| get(r, "judge") == "b").count() as i64;
    let tie = rows.len() as i64 - win - loss;
    Ok(Json::Object(vec![
        ("family".to_string(), Json::Str("preference".to_string())),
        ("n".to_string(), Json::Int(rows.len() as i64)),
        ("agreement".to_string(), jnum(r6(agree as f64 / n))),
        ("win".to_string(), Json::Int(win)),
        ("loss".to_string(), Json::Int(loss)),
        ("tie".to_string(), Json::Int(tie)),
        (
            "win_rate_excl_tie".to_string(),
            jnum(r6(safe_div(win as f64, (win + loss) as f64))),
        ),
    ]))
}

/// 真源 `exact_judgement`。
pub(crate) fn exact_judgement(rows: &[Row], k: usize) -> Result<Json, String> {
    let mut groups: BTreeMap<String, Vec<i64>> = BTreeMap::new();
    for r in rows {
        groups
            .entry(get(r, "task_id"))
            .or_default()
            .push(flag(r, "passed")?);
    }
    let (mut pass1, mut passk, mut skipped, mut used) = (Vec::new(), Vec::new(), 0i64, 0i64);
    for (_, ys) in groups.iter() {
        let n = ys.len();
        let c: i64 = ys.iter().sum();
        pass1.push(c as f64 / n as f64);
        if n < k {
            skipped += 1;
            continue;
        }
        used += 1;
        if c == 0 {
            passk.push(0.0);
            continue;
        }
        if (n as i64 - c) < k as i64 {
            passk.push(1.0);
            continue;
        }
        let mut numv = 1.0;
        for i in 0..k {
            numv *= (n as f64 - c as f64 - i as f64) / (n as f64 - i as f64);
        }
        passk.push(1.0 - numv);
    }
    let avg = |v: &[f64]| {
        if v.is_empty() {
            0.0
        } else {
            v.iter().sum::<f64>() / v.len() as f64
        }
    };
    Ok(Json::Object(vec![
        (
            "family".to_string(),
            Json::Str("exact_judgement".to_string()),
        ),
        ("k".to_string(), Json::Int(k as i64)),
        ("tasks".to_string(), Json::Int(groups.len() as i64)),
        ("n".to_string(), Json::Int(rows.len() as i64)),
        ("pass_at_1".to_string(), jnum(r6(avg(&pass1)))),
        ("pass_at_k".to_string(), jnum(r6(avg(&passk)))),
        ("tasks_used_for_passk".to_string(), Json::Int(used)),
        (
            "tasks_skipped_insufficient_samples".to_string(),
            Json::Int(skipped),
        ),
    ]))
}

/// 真源 `latency_cost`。
pub(crate) fn latency_cost(rows: &[Row], pin: f64, pout: f64) -> Result<Json, String> {
    let mut lat: Vec<f64> = rows
        .iter()
        .map(|r| num(r, "latency_ms"))
        .collect::<Result<_, _>>()?;
    lat.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let pct = |q: f64| -> f64 {
        let idx =
            ((q * lat.len() as f64).ceil() as i64 - 1).clamp(0, lat.len() as i64 - 1) as usize;
        r6(lat[idx])
    };
    let tin: f64 = rows
        .iter()
        .map(|r| num(r, "tokens_in"))
        .collect::<Result<Vec<_>, _>>()?
        .iter()
        .sum();
    let tout: f64 = rows
        .iter()
        .map(|r| num(r, "tokens_out"))
        .collect::<Result<Vec<_>, _>>()?
        .iter()
        .sum();
    let n = rows.len() as f64;
    let cost = (tin / 1000.0) * pin + (tout / 1000.0) * pout;
    Ok(Json::Object(vec![
        ("family".to_string(), Json::Str("latency_cost".to_string())),
        ("n".to_string(), Json::Int(rows.len() as i64)),
        ("p50_ms".to_string(), jnum(pct(0.50))),
        ("p95_ms".to_string(), jnum(pct(0.95))),
        ("p99_ms".to_string(), jnum(pct(0.99))),
        ("mean_ms".to_string(), jnum(r6(lat.iter().sum::<f64>() / n))),
        ("max_ms".to_string(), jnum(r6(*lat.last().unwrap_or(&0.0)))),
        ("tokens_in".to_string(), Json::Int(tin as i64)),
        ("tokens_out".to_string(), Json::Int(tout as i64)),
        ("price_per_1k_in".to_string(), jnum(r6(pin))),
        ("price_per_1k_out".to_string(), jnum(r6(pout))),
        ("cost_total".to_string(), jnum(r6(cost))),
        ("cost_per_1k_calls".to_string(), jnum(r6(cost / n * 1000.0))),
    ]))
}

/// 真源 `drift`。
pub(crate) fn drift(rows: &[Row]) -> Result<Json, String> {
    let eps = 1e-6;
    let mut psi = 0.0;
    let mut detail: Vec<Json> = Vec::new();
    for r in rows {
        let p = num(r, "expected")? + eps;
        let q = num(r, "actual")? + eps;
        let term = (p - q) * (p / q).ln();
        psi += term;
        detail.push(Json::Object(vec![
            ("bucket".to_string(), Json::Str(get(r, "bucket"))),
            ("expected".to_string(), jnum(r6(p))),
            ("actual".to_string(), jnum(r6(q))),
            ("term".to_string(), jnum(r6(term))),
        ]));
    }
    Ok(Json::Object(vec![
        ("family".to_string(), Json::Str("drift".to_string())),
        ("buckets".to_string(), Json::Int(rows.len() as i64)),
        ("psi".to_string(), jnum(r6(psi))),
        ("smoothing_epsilon".to_string(), Json::Float(eps)),
        ("detail".to_string(), Json::Array(detail)),
    ]))
}

/// 真源 `contract_compliance`。
pub(crate) fn contract_compliance(rows: &[Row]) -> Result<Json, String> {
    let n = rows.len() as f64;
    let mut ok = 0i64;
    for r in rows {
        if flag(r, "valid")? == 1 {
            ok += 1;
        }
    }
    let mut missing: BTreeMap<String, i64> = BTreeMap::new();
    for r in rows {
        let raw = get(r, "missing_fields").replace('|', ",").replace(';', ",");
        for f in raw.split(',') {
            let f = f.trim();
            if !f.is_empty() {
                *missing.entry(f.to_string()).or_insert(0) += 1;
            }
        }
    }
    let mut items: Vec<(String, i64)> = missing.into_iter().collect();
    // `sorted(missing.items(), key=lambda kv: (-kv[1], kv[0]))[:5]`
    items.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    let top: Vec<Json> = items
        .into_iter()
        .take(5)
        .map(|(k, v)| {
            Json::Object(vec![
                ("field".to_string(), Json::Str(k)),
                ("count".to_string(), Json::Int(v)),
            ])
        })
        .collect();
    Ok(Json::Object(vec![
        (
            "family".to_string(),
            Json::Str("contract_compliance".to_string()),
        ),
        ("n".to_string(), Json::Int(rows.len() as i64)),
        ("compliance_rate".to_string(), jnum(r6(ok as f64 / n))),
        ("violations".to_string(), Json::Int(rows.len() as i64 - ok)),
        ("missing_top".to_string(), Json::Array(top)),
    ]))
}

/// 真源 `evaluate(family, rows, **params)`。
pub(crate) fn evaluate(family: &str, rows: &[Row], params: &[(String, Json)]) -> Result<Json, String> {
    if !FAMILIES.contains(&family) {
        return Err(format!(
            "未登记度量族：{}（可选：{:?}）",
            pyval::py_repr(&Json::Str(family.to_string())),
            {
                let mut f = FAMILIES.to_vec();
                f.sort();
                f
            }
        ));
    }
    let pget = |k: &str| {
        params
            .iter()
            .find(|(kk, _)| kk == k)
            .map(|(_, v)| v.clone())
    };
    let pnum = |k: &str, d: f64| -> f64 {
        match pget(k) {
            Some(Json::Int(i)) => i as f64,
            Some(Json::Float(f)) => f,
            Some(Json::Bool(b)) => {
                if b {
                    1.0
                } else {
                    0.0
                }
            }
            _ => d,
        }
    };
    let mut body = match family {
        "classification" => classification(rows)?,
        "retrieval" => retrieval(rows, pnum("k", 5.0) as usize)?,
        "extraction" => extraction(rows)?,
        "generation" => generation(rows)?,
        "regression" => regression(rows)?,
        "calibration" => calibration(rows, pnum("bins", 10.0) as usize)?,
        "agreement" => agreement(rows)?,
        "preference" => preference(rows)?,
        "exact_judgement" => exact_judgement(rows, pnum("k", 4.0) as usize)?,
        "latency_cost" => latency_cost(
            rows,
            pnum("price_per_1k_in", 0.0),
            pnum("price_per_1k_out", 0.0),
        )?,
        "drift" => drift(rows)?,
        "contract_compliance" => contract_compliance(rows)?,
        _ => return Err("未登记度量族".to_string()),
    };
    if let Json::Object(o) = &mut body {
        o.push(("digits".to_string(), Json::Int(DIGITS as i64)));
        o.push((
            "note".to_string(),
            Json::Str(
                "样例集上的口径值（非模型能力声明）；口径公式见 docs/domain-packs.md；本报告由 core/domain_metrics.py 确定性复算（T4）"
                    .to_string(),
            ),
        ));
    }
    Ok(body)
}
