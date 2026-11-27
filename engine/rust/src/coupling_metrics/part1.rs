use super::*;

pub(crate) const BASELINE_REL: &str = "protocol/coupling_baseline.json";

/// 从（已剥注释与字符串的）源码抽同包模块依赖。
///
/// 分支次序**照抄真源**——`n.module == "core"` 在 `level` 判断**之前**，
/// 故 `from .core import x`（level=1, module="core"）走的是第一支。
pub(crate) fn module_deps(src: &str, stem: &str, known: &BTreeSet<String>) -> BTreeSet<String> {
    let stripped = pysrc::strip_comments_and_strings(src);
    let lines: Vec<&str> = stripped.lines().collect();
    let mut out: BTreeSet<String> = BTreeSet::new();
    let mut i = 0usize;
    while i < lines.len() {
        let t = lines[i].trim_start();
        if let Some(rest) = t.strip_prefix("import ") {
            for alias in rest.split(',') {
                let name = alias.trim().split_whitespace().next().unwrap_or("");
                if let Some(post) = name.strip_prefix("core.") {
                    out.insert(post.split('.').next().unwrap_or("").to_string());
                }
            }
        } else if let Some(rest) = t.strip_prefix("from ") {
            // 括号多行：`from core import (\n a,\n b,\n)` —— 拼到右括号为止
            let stmt = join_from_stmt(&lines, &mut i, rest);
            let Some((module_part, names_part)) = stmt.split_once(" import") else {
                i += 1;
                continue;
            };
            from_names_deps(module_part, names_part, &mut out);
        }
        i += 1;
    }
    out.retain(|d| known.contains(d) && d != stem);
    out
}

fn join_from_stmt(lines: &[&str], i: &mut usize, rest: &str) -> String {
    let mut stmt = rest.to_string();
    if stmt.contains('(') && !stmt.contains(')') {
        *i += 1;
        while *i < lines.len() {
            stmt.push(' ');
            stmt.push_str(lines[*i]);
            if lines[*i].contains(')') {
                break;
            }
            *i += 1;
        }
    }
    stmt.replace(['(', ')'], " ").trim().to_string()
}

fn from_names_deps(module_part: &str, names_part: &str, out: &mut BTreeSet<String>) {
    let module_part = module_part.trim();
    let level = module_part.chars().take_while(|c| *c == '.').count();
    let module = &module_part[level..];
    let names: Vec<String> = names_part
        .split(',')
        .map(|n| n.trim().split_whitespace().next().unwrap_or("").to_string())
        .filter(|n| !n.is_empty() && n != "*")
        .collect();
    if module == "core" {
        for n in &names {
            out.insert(n.split('.').next().unwrap_or("").to_string());
        }
    } else if module.starts_with("core.") {
        out.insert(module.split('.').nth(1).unwrap_or("").to_string());
    } else if level > 0 && !module.is_empty() {
        out.insert(module.split('.').next().unwrap_or("").to_string());
    } else if level > 0 && module.is_empty() {
        for n in &names {
            out.insert(n.split('.').next().unwrap_or("").to_string());
        }
    }
}

pub(crate) struct Graph {
    pub deps: BTreeMap<String, BTreeSet<String>>,
    /// 模块 → I（Ce/(Ca+Ce)，4 位舍入）
    pub i_of: BTreeMap<String, f64>,
    /// Ca / Ce 是包度量的原始量（当前消费者只用 `i_of`；`write()` 那条线要用它们）。
    #[allow(dead_code)]
    pub ca: BTreeMap<String, i64>,
    #[allow(dead_code)]
    pub ce: BTreeMap<String, i64>,
}

/// 真源 `graph`。
pub(crate) fn graph(root: &Path) -> Graph {
    let mut files = crate::glob::expand(root, "desktop/src/core/*.py");
    files.sort();
    let known: BTreeSet<String> = files
        .iter()
        .map(|rel| {
            rel.rsplit('/')
                .next()
                .unwrap_or(rel)
                .trim_end_matches(".py")
                .to_string()
        })
        .filter(|s| s != "__init__")
        .collect();

    let mut deps: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for rel in &files {
        let stem = rel
            .rsplit('/')
            .next()
            .unwrap_or(rel)
            .trim_end_matches(".py")
            .to_string();
        if stem == "__init__" {
            continue;
        }
        let src = std::fs::read_to_string(root.join(rel)).unwrap_or_default();
        deps.insert(stem.clone(), module_deps(&src, &stem, &known));
    }

    let mut ca: BTreeMap<String, i64> = BTreeMap::new();
    let mut ce: BTreeMap<String, i64> = BTreeMap::new();
    let mut i_of: BTreeMap<String, f64> = BTreeMap::new();
    for m in deps.keys() {
        let c = deps.values().filter(|ds| ds.contains(m)).count() as i64;
        ca.insert(m.clone(), c);
    }
    for (m, ds) in &deps {
        ce.insert(m.clone(), ds.len() as i64);
    }
    for m in deps.keys() {
        let a = *ca.get(m).unwrap_or(&0);
        let e = *ce.get(m).unwrap_or(&0);
        let v = if a + e != 0 {
            pyfloat::round_to(e as f64 / (a + e) as f64, 4)
        } else {
            0.0
        };
        i_of.insert(m.clone(), v);
    }
    Graph { deps, i_of, ca, ce }
}

/// 真源 `cycles`：模块级环（去重、成员排序后返回）。
pub(crate) fn cycles(deps: &BTreeMap<String, BTreeSet<String>>) -> Vec<Vec<String>> {
    fn dfs(
        u: &str,
        deps: &BTreeMap<String, BTreeSet<String>>,
        color: &mut BTreeMap<String, i32>,
        stack: &mut Vec<String>,
        found: &mut BTreeSet<Vec<String>>,
    ) {
        color.insert(u.to_string(), 1);
        stack.push(u.to_string());
        if let Some(vs) = deps.get(u) {
            for v in vs {
                match color.get(v).copied().unwrap_or(0) {
                    1 => {
                        if let Some(pos) = stack.iter().position(|x| x == v) {
                            let cyc: BTreeSet<String> = stack[pos..].iter().cloned().collect();
                            found.insert(cyc.into_iter().collect());
                        }
                    }
                    0 => dfs(v, deps, color, stack, found),
                    _ => {}
                }
            }
        }
        stack.pop();
        color.insert(u.to_string(), 2);
    }
    let mut color: BTreeMap<String, i32> = BTreeMap::new();
    let mut found: BTreeSet<Vec<String>> = BTreeSet::new();
    for m in deps.keys() {
        if color.get(m).copied().unwrap_or(0) == 0 {
            let mut stack: Vec<String> = Vec::new();
            dfs(m, deps, &mut color, &mut stack, &mut found);
        }
    }
    let mut out: Vec<Vec<String>> = found.into_iter().collect();
    out.sort();
    out
}

/// 真源 `sdp_violations`：A 依赖 B 而 B 比 A 更不稳（I 更大）→ `(A, B)`。
pub(crate) fn sdp_violations(g: &Graph) -> Vec<(String, String)> {
    let mut out: Vec<(String, String)> = Vec::new();
    for (m, ds) in &g.deps {
        for d in ds {
            let di = g.i_of.get(d).copied().unwrap_or(0.0);
            let mi = g.i_of.get(m).copied().unwrap_or(0.0);
            if di > mi + 1e-9 {
                out.push((m.clone(), d.clone()));
            }
        }
    }
    out.sort();
    out
}

/// 真源 `metrics_face_issues`：基线的 metrics 面必须**被读到**（审计 §11v.4 F1）。
/// 缺失/非数值/越界/自相矛盾 → issue；数值漂移只进 stats（代码演进不算债）。
pub(crate) fn metrics_face(base: &Option<Json>, g: &Graph) -> (Vec<String>, i64, i64, i64) {
    let mut issues: Vec<String> = Vec::new();
    let pairs: Vec<(String, Json)> = match base.as_ref().and_then(|b| get(b, "metrics")) {
        Some(Json::Object(p)) if !p.is_empty() => p.clone(),
        _ => {
            issues.push(
                "耦合基线缺 metrics 面（修复指引：python scripts/coupling_metrics.py --write）"
                    .to_string(),
            );
            return (issues, 0, 0, g.deps.len() as i64);
        }
    };
    let mut drift = 0i64;
    for (m, mv) in &pairs {
        let (int_of_ca, int_of_ce, int_of_i) = metric_triplet(mv);
        let (Some(ca), Some(ce), Some(i)) = (int_of_ca, int_of_ce, int_of_i) else {
            issues.push(format!("基线 metrics[{}] 含非数值（ca/ce/i）", m));
            continue;
        };
        if !metric_bounds_ok(m, ca, ce, i, &mut issues) {
            continue;
        }
        let want = if ca + ce != 0 {
            pyfloat::round_to(ce as f64 / (ca + ce) as f64, 4)
        } else {
            0.0
        };
        if (i - want).abs() > 1e-9 {
            issues.push(format!(
                "基线 metrics[{}] 自相矛盾：I={:.4} ≠ Ce/(Ca+Ce)={:.4}",
                m, i, want
            ));
            continue;
        }
        match (g.ca.get(m), g.ce.get(m)) {
            (Some(a), Some(e)) if (*a, *e) == (ca, ce) => {}
            _ => drift += 1,
        }
    }
    let missing = g
        .deps
        .keys()
        .filter(|m| !pairs.iter().any(|(k, _)| k == *m))
        .count() as i64;
    (issues, pairs.len() as i64, drift, missing)
}

fn metric_bounds_ok(m: &str, ca: i64, ce: i64, i: f64, issues: &mut Vec<String>) -> bool {
    if ca < 0 || ce < 0 || !(0.0..=1.0).contains(&i) {
        issues.push(format!(
            "基线 metrics[{}] 越界（ca={} ce={} i={}）",
            m, ca, ce, i
        ));
        return false;
    }
    true
}

fn metric_triplet(mv: &Json) -> (Option<i64>, Option<i64>, Option<f64>) {
    let int_of = |k: &str| match get(mv, k) {
        Some(Json::Int(n)) => Some(*n),
        _ => None,
    };
    let i_of = match get(mv, "i") {
        Some(Json::Float(f)) => Some(*f),
        Some(Json::Int(n)) => Some(*n as f64),
        _ => None,
    };
    (int_of("ca"), int_of("ce"), i_of)
}

pub(crate) fn load_baseline(root: &Path) -> Option<Json> {
    if !root.join(BASELINE_REL).is_file() {
        return None;
    }
    jsonread::read_file(root, BASELINE_REL)
}

pub(crate) struct CouplingScan {
    pub issues: Vec<String>,
    pub warns: Vec<String>,
    pub stats: Json,
}

/// 真源 `scan` → `(issues, warns, stats)`。
pub(crate) fn scan(root: &Path) -> CouplingScan {
    let g = graph(root);
    let cyc = cycles(&g.deps);
    let sdp = sdp_violations(&g);
    let base = load_baseline(root);
    let base_present = base
        .as_ref()
        .map(|b| !crate::pyval::obj_is_empty(b))
        .unwrap_or(false);

    let mut known_cyc: BTreeSet<Vec<String>> = BTreeSet::new();
    let mut known_sdp: BTreeSet<(String, String)> = BTreeSet::new();
    if let Some(b) = base.as_ref().filter(|_| base_present) {
        let (kc, ks) = registered_sets(b);
        known_cyc = kc;
        known_sdp = ks;
    }

    let mut issues: Vec<String> = Vec::new();
    let mut warns: Vec<String> = Vec::new();
    if !base_present {
        warns.push(format!(
            "无耦合基线 {}（本次按「零容忍」判：修复指引 python scripts/coupling_metrics.py --write 登记存量债）",
            BASELINE_REL
        ));
        known_cyc.clear();
        known_sdp.clear();
    }
    for c in &cyc {
        if !known_cyc.contains(c) {
            let mut chain = c.clone();
            chain.push(c[0].clone());
            issues.push(format!(
                "新增模块级环：{}（修复指引：断开其中一条依赖——常是惰性 import 循环；确属设计债须评审后 python scripts/coupling_metrics.py --write 登记）",
                chain.join(" → ")
            ));
        }
    }
    for (a, b) in &sdp {
        if !known_sdp.contains(&(a.clone(), b.clone())) {
            issues.push(format!(
                "新增 SDP 违例：{}(I={:.2}) 依赖了更不稳的 {}(I={:.2})（修复指引：把依赖反向——让稳定侧定义接口、由不稳侧实现；确属存量债须评审后 --write 登记）",
                a,
                g.i_of.get(a).copied().unwrap_or(0.0),
                b,
                g.i_of.get(b).copied().unwrap_or(0.0)
            ));
        }
    }
    let cur_cyc: BTreeSet<Vec<String>> = cyc.iter().cloned().collect();
    let cur_sdp: BTreeSet<(String, String)> = sdp.iter().cloned().collect();
    for c in known_cyc.difference(&cur_cyc) {
        let mut chain = c.clone();
        chain.push(c[0].clone());
        warns.push(format!(
            "登记环已消除：{}（修复指引：从 {} 的 cycles 移除）",
            chain.join(" → "),
            BASELINE_REL
        ));
    }
    for (a, b) in known_sdp.difference(&cur_sdp) {
        warns.push(format!(
            "登记 SDP 违例已消除：{} → {}（修复指引：从 {} 的 sdp 移除）",
            a, b, BASELINE_REL
        ));
    }

    let (mut face_issues, metrics_recorded, metrics_drift, metrics_missing) =
        metrics_face(&base, &g);
    issues.append(&mut face_issues);
    let stats = Json::Object(vec![
        ("modules".to_string(), Json::Int(g.deps.len() as i64)),
        ("cycles".to_string(), Json::Int(cyc.len() as i64)),
        ("sdp".to_string(), Json::Int(sdp.len() as i64)),
        (
            "registered_cycles".to_string(),
            Json::Int(known_cyc.len() as i64),
        ),
        (
            "registered_sdp".to_string(),
            Json::Int(known_sdp.len() as i64),
        ),
        ("metrics_recorded".to_string(), Json::Int(metrics_recorded)),
        ("metrics_drift".to_string(), Json::Int(metrics_drift)),
        ("metrics_missing".to_string(), Json::Int(metrics_missing)),
    ]);
    let _ = py_str(None);
    CouplingScan {
        issues,
        warns,
        stats,
    }
}

/// 基线里登记的已知环 / 已知 SDP 违例（SDP 有方向——不排序，按 (依赖方, 被依赖方) 精确比对）。
pub(crate) fn registered_sets(base: &Json) -> (BTreeSet<Vec<String>>, BTreeSet<(String, String)>) {
    let mut known_cyc: BTreeSet<Vec<String>> = BTreeSet::new();
    let mut known_sdp: BTreeSet<(String, String)> = BTreeSet::new();
        for c in arr_items(get(base, "cycles")) {
            let mut v: Vec<String> = arr_items(Some(c)).iter().map(|x| plain_str(x)).collect();
            v.sort();
            known_cyc.insert(v);
        }
        // SDP 有**方向**——不排序，按 (依赖方, 被依赖方) 精确比对
        for p in arr_items(get(base, "sdp")) {
            let pair: Vec<String> = arr_items(Some(p)).iter().map(|x| plain_str(x)).collect();
            if pair.len() == 2 {
                known_sdp.insert((pair[0].clone(), pair[1].clone()));
            }
        }
    (known_cyc, known_sdp)
}
