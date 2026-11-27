use super::*;

pub(crate) const DIGITS: usize = 6;

/// 真源 `FAMILIES` 的键（12 族）。
pub(crate) const FAMILIES: [&str; 12] = [
    "classification",
    "retrieval",
    "extraction",
    "generation",
    "regression",
    "calibration",
    "agreement",
    "preference",
    "exact_judgement",
    "latency_cost",
    "drift",
    "contract_compliance",
];

/// 真源 `_r`（`round(x, 6)`，**银行家舍入**）。
pub(crate) fn r6(x: f64) -> f64 {
    crate::pyfloat::round_to(x, DIGITS)
}

/// 真源 `_safe_div`。
pub(crate) fn safe_div(a: f64, b: f64) -> f64 {
    if b == 0.0 {
        0.0
    } else {
        a / b
    }
}

pub(crate) type Row = BTreeMap<String, String>;

/// 真源 `load_rows`：`csv.DictReader(text.splitlines())`。
pub(crate) fn load_rows(path: &std::path::Path) -> Result<Vec<Row>, String> {
    let text = match std::fs::read(path) {
        Ok(b) => String::from_utf8_lossy(&b).into_owned(),
        Err(e) => return Err(format!("不可读：{}", e)),
    };
    let table = crate::asset_contract::csv_rows(&text);
    if table.is_empty() {
        return Err(format!(
            "空表（{}）",
            path.file_name()
                .map(|s| s.to_string_lossy().to_string())
                .unwrap_or_default()
        ));
    }
    let header = table[0].clone();
    let mut rows: Vec<Row> = Vec::new();
    for line in table.iter().skip(1) {
        if line.len() == 1 && line[0].is_empty() {
            continue;
        }
        let mut m: Row = BTreeMap::new();
        for (i, h) in header.iter().enumerate() {
            // `csv.DictReader`：多余列收进 `None` 键（本仓样例用不到），缺列给 `None`
            m.insert(h.clone(), line.get(i).cloned().unwrap_or_default());
        }
        rows.push(m);
    }
    if rows.is_empty() {
        return Err(format!(
            "空表（{}）",
            path.file_name()
                .map(|s| s.to_string_lossy().to_string())
                .unwrap_or_default()
        ));
    }
    Ok(rows)
}

/// 真源 `_num`。
pub(crate) fn num(row: &Row, key: &str) -> Result<f64, String> {
    let v = row.get(key).cloned().unwrap_or_default();
    v.trim()
        .parse::<f64>()
        .map_err(|_| format!("列 {} 非数值：{}", key, pyval::py_repr(&Json::Str(v))))
}

/// 真源 `_flag`。
pub(crate) fn flag(row: &Row, key: &str) -> Result<i64, String> {
    let v = row
        .get(key)
        .cloned()
        .unwrap_or_default()
        .trim()
        .to_lowercase();
    if ["1", "true", "yes", "y", "正", "是"].contains(&v.as_str()) {
        return Ok(1);
    }
    if ["0", "false", "no", "n", "负", "否"].contains(&v.as_str()) {
        return Ok(0);
    }
    Err(format!(
        "列 {} 非 0/1：{}",
        key,
        pyval::py_repr(&Json::Str(row.get(key).cloned().unwrap_or_default()))
    ))
}

pub(crate) fn get(row: &Row, key: &str) -> String {
    row.get(key).cloned().unwrap_or_default().trim().to_string()
}

/// 真源 `_r()` 的返回值**恒为 `float`** ⇒ JSON 里整值也写 `1.0` / `0.0`（不是 `1` / `0`）。
///
/// ⚠️ 别做「整数就转 Int」的聪明事：实测（2026-10-04）`extraction` 的 `field_recall` 因此写成
/// `1` 而真源是 `1.0`，T4 复算判据当场红。
pub(crate) fn jnum(x: f64) -> Json {
    Json::Float(x)
}

/// 真源 `_auc`（Mann-Whitney 口径，并列取平均秩）。
pub(crate) fn auc(pairs: &[(f64, i64)]) -> f64 {
    let pos: Vec<f64> = pairs
        .iter()
        .filter(|(_, y)| *y == 1)
        .map(|(s, _)| *s)
        .collect();
    let neg: Vec<f64> = pairs
        .iter()
        .filter(|(_, y)| *y == 0)
        .map(|(s, _)| *s)
        .collect();
    if pos.is_empty() || neg.is_empty() {
        return 0.0;
    }
    let mut wins = 0.0;
    for s in &pos {
        for t in &neg {
            wins += if s > t {
                1.0
            } else if s == t {
                0.5
            } else {
                0.0
            };
        }
    }
    wins / (pos.len() as f64 * neg.len() as f64)
}

/// 真源 `classification`。
pub(crate) fn classification(rows: &[Row]) -> Result<Json, String> {
    let mut labels: Vec<String> = Vec::new();
    for r in rows {
        for k in ["gold", "pred"] {
            let v = get(r, k);
            if !labels.contains(&v) {
                labels.push(v);
            }
        }
    }
    labels.sort();
    let mut cm: BTreeMap<(String, String), i64> = BTreeMap::new();
    for r in rows {
        *cm.entry((get(r, "gold"), get(r, "pred"))).or_insert(0) += 1;
    }
    let n = rows.len() as f64;
    let correct: i64 = labels
        .iter()
        .map(|l| *cm.get(&(l.clone(), l.clone())).unwrap_or(&0))
        .sum();
    let per = per_label_metrics(&labels, &cm);
    let macro_of = |k: &str| -> f64 {
        let s: f64 = per
            .iter()
            .map(|(_, v)| match v {
                Json::Object(o) => match o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv) {
                    Some(Json::Float(f)) => *f,
                    Some(Json::Int(i)) => *i as f64,
                    _ => 0.0,
                },
                _ => 0.0,
            })
            .sum();
        r6(s / labels.len() as f64)
    };
    let confusion: Vec<(String, Json)> = labels
        .iter()
        .map(|g| {
            let row: Vec<(String, Json)> = labels
                .iter()
                .map(|p| {
                    (
                        p.clone(),
                        Json::Int(*cm.get(&(g.clone(), p.clone())).unwrap_or(&0)),
                    )
                })
                .collect();
            (g.clone(), Json::Object(row))
        })
        .collect();
    let mut out = vec![
        (
            "family".to_string(),
            Json::Str("classification".to_string()),
        ),
        ("n".to_string(), Json::Int(rows.len() as i64)),
        ("accuracy".to_string(), jnum(r6(correct as f64 / n))),
        (
            "macro".to_string(),
            Json::Object(vec![
                ("precision".to_string(), jnum(macro_of("precision"))),
                ("recall".to_string(), jnum(macro_of("recall"))),
                ("f1".to_string(), jnum(macro_of("f1"))),
            ]),
        ),
        ("confusion".to_string(), Json::Object(confusion)),
        ("per_label".to_string(), Json::Object(per)),
    ];
    if rows
        .iter()
        .all(|r| ["0", "1"].contains(&get(r, "gold").as_str()))
        && rows.iter().all(|r| r.contains_key("score"))
    {
        let mut pairs: Vec<(f64, i64)> = Vec::new();
        for r in rows {
            let s = get(r, "score").parse::<f64>().unwrap_or(0.0);
            pairs.push((s, flag(r, "gold")?));
        }
        out.push(("roc_auc".to_string(), jnum(r6(auc(&pairs)))));
    }
    Ok(Json::Object(out))
}

/// 逐标签 precision / recall / f1 / support（真源 `classification` 的 `per` 段）。
pub(crate) fn per_label_metrics(
    labels: &[String],
    cm: &BTreeMap<(String, String), i64>,
) -> Vec<(String, Json)> {
    labels
        .iter()
        .map(|l| {
            let tp = *cm.get(&(l.clone(), l.clone())).unwrap_or(&0);
            let fp: i64 = labels
                .iter()
                .filter(|g| *g != l)
                .map(|g| *cm.get(&(g.clone(), l.clone())).unwrap_or(&0))
                .sum();
            let fnn: i64 = labels
                .iter()
                .filter(|p| p != &l)
                .map(|p| *cm.get(&(l.clone(), p.clone())).unwrap_or(&0))
                .sum();
            let p = safe_div(tp as f64, (tp + fp) as f64);
            let rc = safe_div(tp as f64, (tp + fnn) as f64);
            let f1 = safe_div(2.0 * p * rc, p + rc);
            (
                l.clone(),
                Json::Object(vec![
                    ("precision".to_string(), jnum(r6(p))),
                    ("recall".to_string(), jnum(r6(rc))),
                    ("f1".to_string(), jnum(r6(f1))),
                    ("support".to_string(), Json::Int(tp + fnn)),
                ]),
            )
        })
        .collect()
}
