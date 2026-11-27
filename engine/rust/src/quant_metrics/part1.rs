use super::*;

pub(crate) const DIGITS: usize = 6;

/// 真源 `ANNUAL_FACTORS`。
pub(crate) fn annual_factor(freq: &str) -> Option<i64> {
    match freq {
        "daily" => Some(252),
        "weekly" => Some(52),
        "monthly" => Some(12),
        _ => None,
    }
}

/// 真源 `GIPS_ALIGNMENT`（披露面原文）。
pub(crate) const GIPS_ALIGNMENT: &str = "口径与披露面（收益口径/年化因子/无风险利率/基准/费用与成交假设）逐项显式；**非 GIPS 合规声明**——合规需第三方鉴证与合成组合全量数据";

/// 真源 `_r`（`round(x, 6)`，**银行家舍入**；返回值恒为 float）。
pub(crate) fn r6(x: f64) -> Json {
    Json::Float(crate::pyfloat::round_to(x, DIGITS))
}

/// 真源 `_r` 的数值版（内部计算用，不落 JSON）。
pub(crate) fn rn(x: f64) -> f64 {
    crate::pyfloat::round_to(x, DIGITS)
}

/// 真源 `load_equity_curve` → `(series, err)`。
pub(crate) fn load_equity_curve(path: &Path) -> Result<Json, String> {
    let text = match std::fs::read(path) {
        Ok(b) => String::from_utf8_lossy(&b).into_owned(),
        Err(e) => return Err(format!("不可读：{}", e)),
    };
    let table = crate::asset_contract::csv_rows(&text);
    if table.is_empty() {
        return Err("空表".to_string());
    }
    let header = table[0].clone();
    let mut cols: Vec<String> = header
        .iter()
        .filter(|c| !c.is_empty())
        .map(|c| c.trim().to_lowercase())
        .collect();
    cols.sort();
    required_curve_cols(&cols)?;
    let has_bench = cols.iter().any(|c| c == "benchmark");
    let (dates, equity, bench) = collect_curve_rows(&table, &header, has_bench)?;
    if equity.len() < 3 {
        return Err("样本过短（< 3 个净值点）".to_string());
    }
    if equity.iter().any(|v| *v <= 0.0) {
        return Err("净值须为正数（口径：净值序列，非累计收益）".to_string());
    }
    Ok(Json::Object(vec![
        (
            "dates".to_string(),
            Json::Array(dates.into_iter().map(Json::Str).collect()),
        ),
        (
            "equity".to_string(),
            Json::Array(equity.into_iter().map(Json::Float).collect()),
        ),
        (
            "benchmark".to_string(),
            if has_bench {
                Json::Array(bench.into_iter().map(Json::Float).collect())
            } else {
                Json::Null
            },
        ),
    ]))
}

/// 必需列：date / equity（缺失时报 Python 列表 repr 的实际列）。
fn required_curve_cols(cols: &[String]) -> Result<(), String> {
    for need in ["date", "equity"] {
        if !cols.iter().any(|c| c == need) {
            // 真源是 sorted(cols) 的 Python 列表 repr（单引号）
            let shown = crate::pyval::py_repr_list(
                &cols
                    .iter()
                    .map(|c| Json::Str(c.clone()))
                    .collect::<Vec<_>>(),
            );
            return Err(format!("缺列 {}（实际列：{}）", need, shown));
        }
    }
    Ok(())
}

/// 逐行取值：dates / equity / benchmark（数值不可解析即报行号）。
fn collect_curve_rows(
    table: &[Vec<String>],
    header: &[String],
    has_bench: bool,
) -> Result<(Vec<String>, Vec<f64>, Vec<f64>), String> {
    let find = |row: &[String], lower: &str| -> Option<String> {
        header
            .iter()
            .position(|h| h.trim().to_lowercase() == lower)
            .and_then(|i| row.get(i).cloned())
    };
    let (mut dates, mut equity, mut bench) = (Vec::new(), Vec::new(), Vec::new());
    for (idx, row) in table.iter().skip(1).enumerate() {
        if row.len() == 1 && row[0].is_empty() {
            continue;
        }
        let line_no = idx + 2;
        // 真源 row.get("date") or row.get("Date")：原样键优先，其次大小写变体
        let d = find(row, "date").unwrap_or_default();
        dates.push(d.trim().to_string());
        let ev = find(row, "equity").unwrap_or_default();
        match ev.trim().parse::<f64>() {
            Ok(v) => equity.push(v),
            Err(_) => return Err(format!("第 {} 行数值不可解析", line_no)),
        }
        if has_bench {
            let bv = find(row, "benchmark").unwrap_or_default();
            match bv.trim().parse::<f64>() {
                Ok(v) => bench.push(v),
                Err(_) => return Err(format!("第 {} 行数值不可解析", line_no)),
            }
        }
    }
    Ok((dates, equity, bench))
}

pub(crate) fn nums(series: &Json, key: &str) -> Vec<f64> {
    match series {
        Json::Object(o) => match o.iter().find(|(k, _)| k == key).map(|(_, v)| v) {
            Some(Json::Array(a)) => a
                .iter()
                .map(|v| match v {
                    Json::Float(f) => *f,
                    Json::Int(i) => *i as f64,
                    _ => 0.0,
                })
                .collect(),
            _ => Vec::new(),
        },
        _ => Vec::new(),
    }
}

/// 真源 `simple_returns`。
pub(crate) fn simple_returns(prices: &[f64]) -> Vec<f64> {
    (1..prices.len())
        .map(|i| prices[i] / prices[i - 1] - 1.0)
        .collect()
}

/// 真源 `log_returns`。
pub(crate) fn log_returns(prices: &[f64]) -> Vec<f64> {
    (1..prices.len())
        .map(|i| (prices[i] / prices[i - 1]).ln())
        .collect()
}

/// 真源 `returns(prices, kind)`。
pub(crate) fn returns(prices: &[f64], kind: &str) -> Result<Vec<f64>, String> {
    match kind {
        "simple" => Ok(simple_returns(prices)),
        "log" => Ok(log_returns(prices)),
        other => Err(format!(
            "收益口径只支持 simple / log，实为 {}",
            crate::pyval::py_repr(&Json::Str(other.to_string()))
        )),
    }
}

/// 真源 `cumulative_return`。
pub(crate) fn cumulative_return(prices: &[f64]) -> f64 {
    prices[prices.len() - 1] / prices[0] - 1.0
}

/// 真源 `annualized_return`。
pub(crate) fn annualized_return(prices: &[f64], af: i64) -> f64 {
    let n = prices.len() as i64 - 1;
    if n <= 0 {
        return 0.0;
    }
    let growth = prices[prices.len() - 1] / prices[0];
    growth.powf(af as f64 / n as f64) - 1.0
}

/// 真源 `_mean`。
pub(crate) fn mean_of(xs: &[f64]) -> f64 {
    if xs.is_empty() {
        0.0
    } else {
        xs.iter().sum::<f64>() / xs.len() as f64
    }
}

/// 真源 `_stdev`（样本标准差 ddof=1）。
pub(crate) fn stdev(xs: &[f64]) -> f64 {
    let n = xs.len();
    if n < 2 {
        return 0.0;
    }
    let mu = mean_of(xs);
    (xs.iter().map(|x| (x - mu).powi(2)).sum::<f64>() / (n as f64 - 1.0)).sqrt()
}

/// 真源 `annualized_volatility`。
pub(crate) fn annualized_volatility(rets: &[f64], af: i64) -> f64 {
    stdev(rets) * (af as f64).sqrt()
}

/// 真源 `max_drawdown`。
pub(crate) fn max_drawdown(prices: &[f64]) -> f64 {
    let mut peak = prices[0];
    let mut mdd: f64 = 0.0;
    for p in prices {
        peak = peak.max(*p);
        mdd = mdd.max((peak - p) / peak);
    }
    mdd
}

/// 真源 `drawdown_series`。
pub(crate) fn drawdown_series(prices: &[f64]) -> Vec<f64> {
    let mut peak = prices[0];
    let mut out = Vec::new();
    for p in prices {
        peak = peak.max(*p);
        out.push((peak - p) / peak);
    }
    out
}

/// 真源 `sharpe`。
pub(crate) fn sharpe(rets: &[f64], rf_annual: f64, af: i64) -> f64 {
    let sd = stdev(rets);
    if sd == 0.0 {
        return 0.0;
    }
    let rf_period = (1.0 + rf_annual).powf(1.0 / af as f64) - 1.0;
    (mean_of(rets) - rf_period) / sd * (af as f64).sqrt()
}

/// 真源 `calmar`。
pub(crate) fn calmar(annual_ret: f64, mdd: f64) -> f64 {
    if mdd == 0.0 {
        0.0
    } else {
        annual_ret / mdd
    }
}

/// 真源 `tracking_error`。
pub(crate) fn tracking_error(rets: &[f64], bench: &[f64], af: i64) -> f64 {
    let n = rets.len().min(bench.len());
    if n < 2 {
        return 0.0;
    }
    let active: Vec<f64> = (0..n).map(|i| rets[i] - bench[i]).collect();
    stdev(&active) * (af as f64).sqrt()
}

/// 真源 `information_ratio`。
pub(crate) fn information_ratio(rets: &[f64], bench: &[f64], af: i64) -> f64 {
    let n = rets.len().min(bench.len());
    if n < 2 {
        return 0.0;
    }
    let active: Vec<f64> = (0..n).map(|i| rets[i] - bench[i]).collect();
    let sd = stdev(&active);
    if sd == 0.0 {
        return 0.0;
    }
    mean_of(&active) / sd * (af as f64).sqrt()
}

/// 真源 `_rank`（平均秩，并列取平均）。
pub(crate) fn rank(xs: &[f64]) -> Vec<f64> {
    let mut order: Vec<usize> = (0..xs.len()).collect();
    order.sort_by(|a, b| {
        xs[*a]
            .partial_cmp(&xs[*b])
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let mut ranks = vec![0.0; xs.len()];
    let mut i = 0usize;
    while i < order.len() {
        let mut j = i;
        while j + 1 < order.len() && xs[order[j + 1]] == xs[order[i]] {
            j += 1;
        }
        let avg = (i + j) as f64 / 2.0 + 1.0;
        for k in i..=j {
            ranks[order[k]] = avg;
        }
        i = j + 1;
    }
    ranks
}

/// 真源 `_pearson`。
pub(crate) fn pearson(a: &[f64], b: &[f64]) -> f64 {
    let n = a.len().min(b.len());
    if n < 2 {
        return 0.0;
    }
    let ma = mean_of(&a[..n]);
    let mb = mean_of(&b[..n]);
    let num: f64 = (0..n).map(|i| (a[i] - ma) * (b[i] - mb)).sum();
    let da = (0..n).map(|i| (a[i] - ma).powi(2)).sum::<f64>().sqrt();
    let db = (0..n).map(|i| (b[i] - mb).powi(2)).sum::<f64>().sqrt();
    if da == 0.0 || db == 0.0 {
        0.0
    } else {
        num / (da * db)
    }
}

/// 真源 `information_coefficient`。
pub(crate) fn information_coefficient(factor: &[f64], fwd: &[f64], method: &str) -> Result<f64, String> {
    match method {
        "spearman" => Ok(pearson(&rank(factor), &rank(fwd))),
        "pearson" => Ok(pearson(factor, fwd)),
        other => Err(format!(
            "IC 口径只支持 spearman / pearson，实为 {}",
            crate::pyval::py_repr(&Json::Str(other.to_string()))
        )),
    }
}

/// 真源 `turnover`。
pub(crate) fn turnover(weights: &[Vec<f64>], single_side: bool) -> Vec<f64> {
    let mut out = Vec::new();
    for i in 1..weights.len() {
        let m = weights[i].len().min(weights[i - 1].len());
        let gross: f64 = (0..m)
            .map(|j| (weights[i][j] - weights[i - 1][j]).abs())
            .sum();
        out.push(if single_side { gross / 2.0 } else { gross });
    }
    out
}

/// 真源 `_block`。
pub(crate) fn block(prices: &[f64], af: i64, rf: f64, kind: &str) -> Result<Json, String> {
    let rets = returns(prices, kind)?;
    let ann = annualized_return(prices, af);
    let mdd = max_drawdown(prices);
    Ok(Json::Object(vec![
        ("cumulative".to_string(), r6(cumulative_return(prices))),
        ("annualized".to_string(), r6(ann)),
        (
            "volatility_annualized".to_string(),
            r6(annualized_volatility(&rets, af)),
        ),
        ("sharpe".to_string(), r6(sharpe(&rets, rf, af))),
        ("max_drawdown".to_string(), r6(mdd)),
        ("calmar".to_string(), r6(calmar(ann, mdd))),
    ]))
}

pub(crate) fn pstr(params: &[(String, Json)], k: &str, d: &str) -> String {
    match params.iter().find(|(kk, _)| kk == k).map(|(_, v)| v) {
        Some(Json::Str(s)) => s.clone(),
        Some(Json::Null) | None => d.to_string(),
        Some(other) => crate::pyval::plain_str(other),
    }
}

pub(crate) fn pnum(params: &[(String, Json)], k: &str, d: f64) -> f64 {
    match params.iter().find(|(kk, _)| kk == k).map(|(_, v)| v) {
        Some(Json::Int(i)) => *i as f64,
        Some(Json::Float(f)) => *f,
        Some(Json::Bool(b)) => {
            if *b {
                1.0
            } else {
                0.0
            }
        }
        _ => d,
    }
}
