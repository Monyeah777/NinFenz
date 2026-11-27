use super::*;

/// 真源 `retrieval`。
pub(crate) fn retrieval(rows: &[Row], k: usize) -> Result<Json, String> {
    let mut groups: BTreeMap<String, Vec<(i64, i64)>> = BTreeMap::new();
    for r in rows {
        groups
            .entry(get(r, "query_id"))
            .or_default()
            .push((num(r, "rank")? as i64, flag(r, "relevant")?));
    }
    let (mut recalls, mut precisions, mut rrs, mut ndcgs, mut aps) =
        (Vec::new(), Vec::new(), Vec::new(), Vec::new(), Vec::new());
    for (_, items) in groups.iter() {
        let mut it = items.clone();
        it.sort();
        let rel: Vec<i64> = it.iter().map(|(_, y)| *y).collect();
        let topk = &rel[..rel.len().min(k)];
        let total_rel: i64 = rel.iter().sum();
        recalls.push(safe_div(topk.iter().sum::<i64>() as f64, total_rel as f64));
        precisions.push(safe_div(topk.iter().sum::<i64>() as f64, k as f64));
        let mut rr = 0.0;
        for (i, y) in rel.iter().enumerate() {
            if *y != 0 {
                rr = 1.0 / (i as f64 + 1.0);
                break;
            }
        }
        rrs.push(rr);
        let dcg: f64 = rel
            .iter()
            .take(k)
            .enumerate()
            .map(|(i, y)| *y as f64 / ((i as f64 + 2.0).log2()))
            .sum();
        let ideal: f64 = (1..=(total_rel.min(k as i64)))
            .map(|i| 1.0 / ((i as f64 + 1.0).log2()))
            .sum();
        ndcgs.push(safe_div(dcg, ideal));
        let mut hits = 0i64;
        let mut ap = 0.0;
        for (i, y) in rel.iter().enumerate() {
            if *y != 0 {
                hits += 1;
                ap += hits as f64 / (i as f64 + 1.0);
            }
        }
        aps.push(safe_div(ap, total_rel as f64));
    }
    let avg = |v: &[f64]| {
        if v.is_empty() {
            0.0
        } else {
            v.iter().sum::<f64>() / v.len() as f64
        }
    };
    Ok(Json::Object(vec![
        ("family".to_string(), Json::Str("retrieval".to_string())),
        ("k".to_string(), Json::Int(k as i64)),
        ("queries".to_string(), Json::Int(groups.len() as i64)),
        ("n".to_string(), Json::Int(rows.len() as i64)),
        ("recall_at_k".to_string(), jnum(r6(avg(&recalls)))),
        ("precision_at_k".to_string(), jnum(r6(avg(&precisions)))),
        ("mrr".to_string(), jnum(r6(avg(&rrs)))),
        ("ndcg_at_k".to_string(), jnum(r6(avg(&ndcgs)))),
        ("map".to_string(), jnum(r6(avg(&aps)))),
    ]))
}

/// 真源 `extraction`。
pub(crate) fn extraction(rows: &[Row]) -> Result<Json, String> {
    let (mut em, mut tp, mut fp, mut fnn) = (0i64, 0i64, 0i64, 0i64);
    for r in rows {
        let g = json_str_set(&get(r, "gold_fields"))?;
        let p = json_str_set(&get(r, "pred_fields"))?;
        if g == p {
            em += 1;
        }
        tp += g.intersection(&p).count() as i64;
        fp += p.difference(&g).count() as i64;
        fnn += g.difference(&p).count() as i64;
    }
    let pr = safe_div(tp as f64, (tp + fp) as f64);
    let rc = safe_div(tp as f64, (tp + fnn) as f64);
    let n = rows.len() as f64;
    Ok(Json::Object(vec![
        ("family".to_string(), Json::Str("extraction".to_string())),
        ("n".to_string(), Json::Int(rows.len() as i64)),
        ("exact_match".to_string(), jnum(r6(em as f64 / n))),
        ("field_precision".to_string(), jnum(r6(pr))),
        ("field_recall".to_string(), jnum(r6(rc))),
        (
            "field_f1".to_string(),
            jnum(r6(safe_div(2.0 * pr * rc, pr + rc))),
        ),
        ("tp".to_string(), Json::Int(tp)),
        ("fp".to_string(), Json::Int(fp)),
        ("fn".to_string(), Json::Int(fnn)),
    ]))
}

pub(crate) fn json_str_set(s: &str) -> Result<std::collections::BTreeSet<String>, String> {
    let parsed = crate::jsonmini::parse(s).map_err(|e| e.to_string())?;
    Ok(match parsed.value {
        Json::Array(a) => a.iter().map(pyval::plain_str).collect(),
        _ => std::collections::BTreeSet::new(),
    })
}

/// 真源 `generation`（字符集合用**字符**去重，词集合按空白切）。
pub(crate) fn generation(rows: &[Row]) -> Result<Json, String> {
    let (mut em, mut char_f1, mut set_f1) = (0i64, Vec::new(), Vec::new());
    for r in rows {
        let g = get(r, "reference");
        let p = get(r, "output");
        if g == p {
            em += 1;
        }
        let gs: std::collections::BTreeSet<char> = g.chars().collect();
        let ps: std::collections::BTreeSet<char> = p.chars().collect();
        let inter = gs.intersection(&ps).count() as f64;
        let prec = safe_div(inter, ps.len() as f64);
        let rec = safe_div(inter, gs.len() as f64);
        char_f1.push(safe_div(2.0 * prec * rec, prec + rec));
        let gt: std::collections::BTreeSet<&str> = g.split_whitespace().collect();
        let pt: std::collections::BTreeSet<&str> = p.split_whitespace().collect();
        let i2 = gt.intersection(&pt).count() as f64;
        let p2 = safe_div(i2, pt.len() as f64);
        let r2 = safe_div(i2, gt.len() as f64);
        set_f1.push(safe_div(2.0 * p2 * r2, p2 + r2));
    }
    let n = rows.len() as f64;
    Ok(Json::Object(vec![
        ("family".to_string(), Json::Str("generation".to_string())),
        ("n".to_string(), Json::Int(rows.len() as i64)),
        ("exact_match".to_string(), jnum(r6(em as f64 / n))),
        (
            "char_f1".to_string(),
            jnum(r6(char_f1.iter().sum::<f64>() / n)),
        ),
        (
            "token_set_f1".to_string(),
            jnum(r6(set_f1.iter().sum::<f64>() / n)),
        ),
    ]))
}

/// 真源 `regression`。
pub(crate) fn regression(rows: &[Row]) -> Result<Json, String> {
    let g: Vec<f64> = rows
        .iter()
        .map(|r| num(r, "gold"))
        .collect::<Result<_, _>>()?;
    let p: Vec<f64> = rows
        .iter()
        .map(|r| num(r, "pred"))
        .collect::<Result<_, _>>()?;
    let n = rows.len() as f64;
    let mae = g.iter().zip(&p).map(|(a, b)| (a - b).abs()).sum::<f64>() / n;
    let rmse = (g.iter().zip(&p).map(|(a, b)| (a - b).powi(2)).sum::<f64>() / n).sqrt();
    let mg = g.iter().sum::<f64>() / n;
    let ss_tot: f64 = g.iter().map(|a| (a - mg).powi(2)).sum();
    let ss_res: f64 = g.iter().zip(&p).map(|(a, b)| (a - b).powi(2)).sum();
    let nz: Vec<(f64, f64)> = g
        .iter()
        .zip(&p)
        .filter(|(a, _)| **a != 0.0)
        .map(|(a, b)| (*a, *b))
        .collect();
    let mape = if nz.is_empty() {
        0.0
    } else {
        nz.iter().map(|(a, b)| ((a - b) / a).abs()).sum::<f64>() / nz.len() as f64
    };
    Ok(Json::Object(vec![
        ("family".to_string(), Json::Str("regression".to_string())),
        ("n".to_string(), Json::Int(rows.len() as i64)),
        ("mae".to_string(), jnum(r6(mae))),
        ("rmse".to_string(), jnum(r6(rmse))),
        ("r2".to_string(), jnum(r6(1.0 - safe_div(ss_res, ss_tot)))),
        ("mape".to_string(), jnum(r6(mape))),
        ("mape_samples".to_string(), Json::Int(nz.len() as i64)),
    ]))
}

/// 真源 `calibration`。
pub(crate) fn calibration(rows: &[Row], bins: usize) -> Result<Json, String> {
    let mut pairs: Vec<(f64, i64)> = Vec::new();
    for r in rows {
        pairs.push((num(r, "prob")?, flag(r, "gold")?));
    }
    if pairs.iter().any(|(p, _)| !(0.0..=1.0).contains(p)) {
        return Err("prob 必须在 [0,1]".to_string());
    }
    let n = pairs.len() as f64;
    let brier = pairs
        .iter()
        .map(|(p, y)| (p - *y as f64).powi(2))
        .sum::<f64>()
        / n;
    let mut buckets: Vec<Json> = Vec::new();
    let mut ece = 0.0;
    for b in 0..bins {
        let lo = b as f64 / bins as f64;
        let hi = (b + 1) as f64 / bins as f64;
        let sel: Vec<(f64, i64)> = pairs
            .iter()
            .filter(|(p, _)| (lo <= *p && *p < hi) || (b == bins - 1 && *p == 1.0))
            .cloned()
            .collect();
        if sel.is_empty() {
            continue;
        }
        let conf = sel.iter().map(|(p, _)| *p).sum::<f64>() / sel.len() as f64;
        let acc = sel.iter().map(|(_, y)| *y as f64).sum::<f64>() / sel.len() as f64;
        ece += (sel.len() as f64 / n) * (conf - acc).abs();
        buckets.push(Json::Object(vec![
            (
                "range".to_string(),
                Json::Str(format!("[{:.1},{:.1}]", lo, hi)),
            ),
            ("n".to_string(), Json::Int(sel.len() as i64)),
            ("confidence".to_string(), jnum(r6(conf))),
            ("accuracy".to_string(), jnum(r6(acc))),
            ("gap".to_string(), jnum(r6((conf - acc).abs()))),
        ]));
    }
    Ok(Json::Object(vec![
        ("family".to_string(), Json::Str("calibration".to_string())),
        ("n".to_string(), Json::Int(rows.len() as i64)),
        ("bins".to_string(), Json::Int(bins as i64)),
        ("nonempty_bins".to_string(), Json::Int(buckets.len() as i64)),
        ("ece".to_string(), jnum(r6(ece))),
        ("brier".to_string(), jnum(r6(brier))),
        ("buckets".to_string(), Json::Array(buckets)),
    ]))
}

/// 真源 `agreement`。
pub(crate) fn agreement(rows: &[Row]) -> Result<Json, String> {
    let mut labels: Vec<String> = Vec::new();
    for r in rows {
        for k in ["a", "b"] {
            let v = get(r, k);
            if !labels.contains(&v) {
                labels.push(v);
            }
        }
    }
    labels.sort();
    let n = rows.len() as f64;
    let mut cm: BTreeMap<(String, String), i64> = BTreeMap::new();
    for r in rows {
        *cm.entry((get(r, "a"), get(r, "b"))).or_insert(0) += 1;
    }
    let po = labels
        .iter()
        .map(|l| *cm.get(&(l.clone(), l.clone())).unwrap_or(&0) as f64)
        .sum::<f64>()
        / n;
    let pe: f64 = labels
        .iter()
        .map(|l| {
            let row_sum: i64 = labels
                .iter()
                .map(|y| *cm.get(&(l.clone(), y.clone())).unwrap_or(&0))
                .sum();
            let col_sum: i64 = labels
                .iter()
                .map(|g| *cm.get(&(g.clone(), l.clone())).unwrap_or(&0))
                .sum();
            (row_sum as f64 / n) * (col_sum as f64 / n)
        })
        .sum();
    let confusion: Vec<(String, Json)> = labels
        .iter()
        .map(|x| {
            let row: Vec<(String, Json)> = labels
                .iter()
                .map(|y| {
                    (
                        y.clone(),
                        Json::Int(*cm.get(&(x.clone(), y.clone())).unwrap_or(&0)),
                    )
                })
                .collect();
            (x.clone(), Json::Object(row))
        })
        .collect();
    Ok(Json::Object(vec![
        ("family".to_string(), Json::Str("agreement".to_string())),
        ("n".to_string(), Json::Int(rows.len() as i64)),
        ("labels".to_string(), Json::Int(labels.len() as i64)),
        ("observed_agreement".to_string(), jnum(r6(po))),
        ("expected_agreement".to_string(), jnum(r6(pe))),
        (
            "cohen_kappa".to_string(),
            jnum(r6(safe_div(po - pe, 1.0 - pe))),
        ),
        ("confusion".to_string(), Json::Object(confusion)),
    ]))
}
