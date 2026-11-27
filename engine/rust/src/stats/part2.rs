use super::*;

// ---------------------------------------------------------------- compute / check

/// 真源 `compute`：实算全部自述数字 + 收集 issue（issue 顺序与真源逐条对齐）。
pub(crate) fn compute(root: &Path) -> (Stats, Vec<String>) {
    let mut issues: Vec<String> = Vec::new();
    let mut s = Stats::default();

    let reg = jsonread::read_file(root, "desktop/src/core/registry.json");
    issues.extend(registry_face_issues(&reg));
    let reg = match reg {
        Some(v) if matches!(v, Json::Object(_)) => v,
        _ => Json::Object(Vec::new()),
    };
    s.core_modules = len_of(obj_get(&reg, "modules"));
    s.registered_packs = len_of(obj_get(&reg, "protocols"));

    // 03_管线库/P*.md → 文件名前 3 字符，排序
    let mut pipes: Vec<String> = names_in(&root.join("03_管线库"))
        .into_iter()
        .filter(|n| n.starts_with('P') && n.ends_with(".md"))
        .map(|n| n.chars().take(3).collect::<String>())
        .collect();
    pipes.sort();
    s.core_pipelines = pipes;

    s.pack_dirs = count_in_subdirs(&root.join("community"), "", "protocol.yaml");
    if s.pack_dirs > 0 && s.pack_dirs != s.registered_packs {
        issues.push(format!(
            "盘上包目录 {} ≠ registry 登记 {}（登记三要件与盘上实况不一致）",
            s.pack_dirs, s.registered_packs
        ));
    }

    s.pack_assets = count_suffix_in_subdirs(&root.join("community"), "assets", ".md");
    s.concept_graphs = count_in_subdirs(&root.join("community"), "assets", "CONCEPT_GRAPH.md");

    fill_standards_coverage(root, &mut s, &mut issues);

    let bind = jsonread::read_file(root, "protocol/standards_binding.json")
        .unwrap_or(Json::Object(Vec::new()));
    s.standard_bindings = int_of(obj_get(&bind, "bindings_total"));

    let manifest =
        jsonread::read_file(root, "protocol/domain_packs.json").unwrap_or(Json::Object(Vec::new()));
    s.domain_packs = int_of(obj_get(&manifest, "count"));
    s.subdivisions_total = int_of(obj_get(&manifest, "subdivisions_total"));

    let lib = names_in(&root.join("library"));
    s.library_items = lib
        .iter()
        .filter(|f| f.ends_with(".md") && *f != "INDEX.md" && *f != "ALIAS.md")
        .count() as i64;

    let vtext = match std::fs::read_to_string(root.join("verify.sh")) {
        Ok(t) => t,
        Err(_) => {
            issues.push("取不到 verify.sh（质量凭证口径缺失）".into());
            String::new()
        }
    };
    s.verify_checks = count_checks(&vtext);
    s.verify_version = parse_version(&vtext);
    issues.extend(verify_face_issues(&s));
    issues.extend(baseline_face_issues(root, &mut s));

    (s, issues)
}

/// registry.json 缺件/非对象：一条 issue。
fn registry_face_issues(reg: &Option<Json>) -> Vec<String> {
    match reg {
        Some(v) if matches!(v, Json::Object(_)) => Vec::new(),
        _ => vec!["取不到 registry.json（官方核心模块/登记包口径缺失）".into()],
    }
}

/// verify.sh 面：版本行 / check 数。
fn verify_face_issues(s: &Stats) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    if s.verify_version.is_empty() {
        issues.push("verify.sh 头部缺「# 版本 : vX」版本行".into());
    }
    if s.verify_checks < 1 {
        issues.push("verify.sh 未扫到任何 checkN() 定义".into());
    }
    issues
}

/// quality_baseline 面：取常量并核对 check 数一致。
fn baseline_face_issues(root: &Path, s: &mut Stats) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    match std::fs::read_to_string(root.join("desktop/src/core/quality_baseline.py")) {
        Ok(qb) => {
            s.baseline_checks = py_int_const(&qb, "EXPECTED_CHECKS").unwrap_or(s.verify_checks);
            s.baseline_pass = py_int_const(&qb, "EXPECTED_PASS").unwrap_or(0);
        }
        Err(e) => {
            s.baseline_checks = s.verify_checks;
            s.baseline_pass = 0;
            issues.push(format!(
                "取不到 quality_baseline.EXPECTED_*：{}（基线句无法生成）",
                e
            ));
        }
    }
    if s.baseline_checks != s.verify_checks {
        issues.push(format!(
            "基线 check 数 {} ≠ verify.sh 实扫 {}（同步 quality_baseline.EXPECTED_CHECKS）",
            s.baseline_checks, s.verify_checks
        ));
    }
    issues
}

/// 标准目录 coverage 的齐全性检查与计数（缺键即报）。
pub(crate) fn fill_standards_coverage(root: &Path, s: &mut Stats, issues: &mut Vec<String>) {
    let cat = jsonread::read_file(root, "protocol/standards_catalog.json")
        .unwrap_or(Json::Object(Vec::new()));
    let cov = obj_get(&cat, "coverage")
        .cloned()
        .unwrap_or(Json::Object(Vec::new()));
    for key in [
        "standards",
        "reachable",
        "unreachable",
        "bodies",
        "depends_edges",
        "by_layer",
    ] {
        if obj_get(&cov, key).is_none() {
            issues.push(format!("标准目录 coverage 缺 {}（口径不完整）", key));
        }
    }
    s.standards_total = int_of(obj_get(&cov, "standards"));
    s.standards_reachable = int_of(obj_get(&cov, "reachable"));
    s.standards_unreachable = int_of(obj_get(&cov, "unreachable"));
    s.standards_bodies = int_of(obj_get(&cov, "bodies"));
    s.standards_edges = int_of(obj_get(&cov, "depends_edges"));
    s.standards_by_layer = layer_of(obj_get(&cov, "by_layer"));
}

/// 真源 `check`：compute + 生成区比对 + 在盘记录比对（**全只读**）。
pub(crate) fn check(root: &Path) -> (Vec<String>, Stats) {
    let (stats, mut issues) = compute(root);
    let blocks = render(&stats);
    for (rel, block) in blocks.iter() {
        let path = root.join(rel);
        let Ok(text) = std::fs::read_to_string(&path) else {
            issues.push(format!("缺入口文件 {}", rel));
            continue;
        };
        match replace_block(&text, block) {
            None => issues.push(format!("{} 缺 marker 区", rel)),
            Some(new) if new != text => issues.push(format!(
                "{} 的生成区与实算不一致（跑 `nf stats --write` 重写）",
                rel
            )),
            Some(_) => {}
        }
    }
    let recorded = jsonread::read_file(root, STATS_REL);
    let live = stats.to_json();
    match recorded {
        Some(r) if jsonread::json_eq(&r, &live) => {}
        _ => issues.push(format!(
            "{} 与实算不一致（跑 `nf stats --write` 重写）",
            STATS_REL
        )),
    }
    (issues, stats)
}

/// 真源 `_replace_block`：marker 包围区整体替换；缺 marker → `None`。
pub(crate) fn replace_block(text: &str, block: &str) -> Option<String> {
    let i = text.find(BEGIN)?;
    let j = text.find(END)?;
    if j < i {
        return None;
    }
    let mut out = String::with_capacity(text.len() + block.len());
    out.push_str(&text[..i]);
    out.push_str(block);
    out.push_str(&text[j + END.len()..]);
    Some(out)
}

// ---------------------------------------------------------------- 生成区渲染（三入口件）

/// 真源 `render`：入口件 → 生成区块（顺序 = README.md / README.en.md / llms.txt）。
pub(crate) fn render(stats: &Stats) -> Vec<(&'static str, String)> {
    vec![
        (BLOCK_FILES[0], zh(stats)),
        (BLOCK_FILES[1], en(stats)),
        (BLOCK_FILES[2], llms(stats)),
    ]
}

pub(crate) fn layer_txt(stats: &Stats) -> String {
    if stats.standards_by_layer.is_empty() {
        return "—".into();
    }
    let mut ls = stats.standards_by_layer.clone();
    ls.sort_by(|a, b| a.0.as_bytes().cmp(b.0.as_bytes()));
    ls.iter()
        .map(|(k, v)| format!("{} {}", k, v))
        .collect::<Vec<_>>()
        .join(" · ")
}

pub(crate) fn pipes_txt(stats: &Stats) -> String {
    if stats.core_pipelines.is_empty() {
        "—".into()
    } else {
        stats.core_pipelines.join(" / ")
    }
}

pub(crate) fn zh(s: &Stats) -> String {
    [
        BEGIN.to_string(),
        format!(
            "**官方核心**：{} 模块 · {} 管线（{}） · 核心协议件 01–07",
            s.core_modules,
            s.core_pipelines.len(),
            pipes_txt(s)
        ),
        format!(
            "**社区规模**：{} 登记包 · {} 资产档 · {} 概念图 · {} 域包/{} 细分 · 标准目录 {} 条（可达 {} / 不可达 {} · 机构 {} · {} 条依赖边） · 标准绑定 {} 条",
            s.registered_packs, s.pack_assets, s.concept_graphs,
            s.domain_packs, s.subdivisions_total,
            s.standards_total, s.standards_reachable, s.standards_unreachable,
            s.standards_bodies, s.standards_edges, s.standard_bindings
        ),
        format!(
            "**质量凭证**：verify v{} · check1-{} · PASS={}（`bash verify.sh` 单入口；期望基线取自 `quality_baseline.EXPECTED_*`） · 馆藏 {} 件",
            s.verify_version, s.baseline_checks, s.baseline_pass, s.library_items
        ),
        String::new(),
        format!("分层：{} （按标准目录 layer）", layer_txt(s)),
        String::new(),
        "> 本区由 `python scripts/nf.py stats --write` 生成，禁止手改；口径与实算真源见 `protocol/repo_stats.json`。".to_string(),
        END.to_string(),
    ]
    .join("\n")
}

pub(crate) fn en(s: &Stats) -> String {
    [
        BEGIN.to_string(),
        format!(
            "**Official core**: {} modules · {} pipelines ({}) · protocol files 01-07",
            s.core_modules,
            s.core_pipelines.len(),
            pipes_txt(s)
        ),
        format!(
            "**Community scale**: {} registered packs · {} asset files · {} concept graphs · {} domain packs / {} subdivisions · standards catalog {} (reachable {} / unreachable {} · {} bodies · {} dependency edges) · standard bindings {}",
            s.registered_packs, s.pack_assets, s.concept_graphs,
            s.domain_packs, s.subdivisions_total,
            s.standards_total, s.standards_reachable, s.standards_unreachable,
            s.standards_bodies, s.standards_edges, s.standard_bindings
        ),
        format!(
            "**Quality evidence**: verify v{} · check1-{} · PASS={} (`bash verify.sh`; expectations from `quality_baseline.EXPECTED_*`) · library {} items",
            s.verify_version, s.baseline_checks, s.baseline_pass, s.library_items
        ),
        String::new(),
        "> Generated by `python scripts/nf.py stats --write`. Do not edit by hand; sources in `protocol/repo_stats.json`.".to_string(),
        END.to_string(),
    ]
    .join("\n")
}

pub(crate) fn llms(s: &Stats) -> String {
    [
        BEGIN.to_string(),
        format!(
            "- 质量凭证（可静态实算）：verify v{} · check1-{} · PASS={}（`bash verify.sh` 单入口；期望基线取自 `quality_baseline.EXPECTED_*`，本行由生成器写入）。",
            s.verify_version, s.baseline_checks, s.baseline_pass
        ),
        format!(
            "- 规模（实算真源 `protocol/repo_stats.json`）：{} 登记包 · {} 资产档 · {} 概念图 · 标准目录 {} 条（可达 {}） · 标准绑定 {} 条 · 馆藏 {} 件。",
            s.registered_packs, s.pack_assets, s.concept_graphs,
            s.standards_total, s.standards_reachable, s.standard_bindings, s.library_items
        ),
        "- 标准目录 GEO 出口（可引用）：`docs/standards/index.md` · 机读 `protocol/geo_export.json`。".to_string(),
        END.to_string(),
    ]
    .join("\n")
}
