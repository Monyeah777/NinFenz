use super::*;

pub(crate) const DECL_REL: &str = "protocol/CONFORMANCE.md";

pub(crate) fn re_row() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"^\|\s*`?([^`|]+?)`?\s*\|\s*`?([^`|]+?)`?\s*\|\s*([^|]+?)\s*\|\s*$")
            .expect("三段行正则固定合法")
    })
}

pub(crate) fn re_row2() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"^\|\s*`?([^`|]+?)`?\s*\|\s*([^|]+?)\s*\|\s*$")
            .expect("两段行正则固定合法")
    })
}

pub(crate) fn re_bullet() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^\s*[-*]\s+`([^`]+)`").expect("bullet 正则固定合法"))
}

pub(crate) fn re_sep() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^[-: ]+$").expect("分隔行正则固定合法"))
}

/// 真源 `_section`：取 `## <title>` 到下一个同级标题之间的行。
pub(crate) fn section(text: &str, title: &str) -> Vec<String> {
    let lines: Vec<&str> = text.lines().collect();
    let want = format!("## {}", title);
    let mut start: Option<usize> = None;
    for (i, ln) in lines.iter().enumerate() {
        if ln.trim() == want {
            start = Some(i + 1);
            continue;
        }
        if start.is_some() && ln.starts_with("## ") {
            return lines[start.unwrap()..i]
                .iter()
                .map(|s| (*s).to_string())
                .collect();
        }
    }
    match start {
        Some(s) => lines[s..].iter().map(|x| (*x).to_string()).collect(),
        None => Vec::new(),
    }
}

/// 真源 `parse` → `(versions 顺序表, scope, excluded)`。
pub(crate) struct Decl {
    /// (name, version, source)，**同键覆盖**（真源是 dict）
    pub versions: Vec<(String, String, String)>,
    pub scope: Vec<String>,
    pub excluded: Vec<(String, String)>,
}

pub(crate) fn parse(root: &Path) -> Decl {
    let text = decl_text(root);
    let versions = parse_versions(&text);
    let scope = parse_scope(&text);
    let excluded = parse_excluded(&text);

    Decl {
        versions,
        scope,
        excluded,
    }
}

/// 声明件正文；缺件按空串（真源同口径）。
fn decl_text(root: &Path) -> String {
    let p = root.join(DECL_REL);
    if p.is_file() {
        std::fs::read_to_string(&p).unwrap_or_default()
    } else {
        String::new()
    }
}

/// 声明段版本表：同键覆盖（真源是 dict）。
fn parse_versions(text: &str) -> Vec<(String, String, String)> {
    let mut versions: Vec<(String, String, String)> = Vec::new();
    for ln in section(text, "声明") {
        let Some(c) = re_row().captures(ln.trim()) else {
            continue;
        };
        let name = c[1].trim().to_string();
        if name == "规范" || re_sep().is_match(&name) {
            continue;
        }
        let rec = (
            name.clone(),
            c[2].trim().to_string(),
            c[3].trim().to_string(),
        );
        match versions.iter_mut().find(|(n, _, _)| *n == name) {
            Some(slot) => *slot = rec,
            None => versions.push(rec),
        }
    }
    versions
}

/// 范围段白名单。
fn parse_scope(text: &str) -> Vec<String> {
    let mut scope: Vec<String> = Vec::new();
    for ln in section(text, "范围") {
        if let Some(c) = re_bullet().captures(&ln) {
            scope.push(c[1].trim().to_string());
        }
    }
    scope
}

/// 排除段清单（表头 / 分隔行跳过）。
fn parse_excluded(text: &str) -> Vec<(String, String)> {
    let mut excluded: Vec<(String, String)> = Vec::new();
    for ln in section(text, "排除") {
        let m = re_row2().captures(ln.trim());
        let cell = m
            .as_ref()
            .map(|c| c[1].trim().to_string())
            .unwrap_or_default();
        if let Some(c) = m {
            if cell != "路径" && !re_sep().is_match(&cell) {
                excluded.push((c[1].trim().to_string(), c[2].trim().to_string()));
            }
        }
    }
    excluded
}

/// 真源 `live_versions`：版本真源（声明必须与这里一致）。
pub(crate) fn live_versions(root: &Path) -> Vec<(String, String)> {
    let mut out: Vec<(String, String)> = Vec::new();

    let reg = root.join("desktop/src/core/registry.json");
    if reg.is_file() {
        let v = jsonread::read_file(root, "desktop/src/core/registry.json")
            .map(|d| plain_str_opt(get(&d, "registry_schema_version")))
            .unwrap_or_default();
        out.push(("registry schema".to_string(), v));
    }

    let contract = root.join("protocol/schema/contract.schema.json");
    if contract.is_file() {
        let enum_vals: Vec<String> =
            jsonread::read_file(root, "protocol/schema/contract.schema.json")
                .map(|d| {
                    crate::pyval::arr_items(
                        get(&d, "properties")
                            .and_then(|p| get(p, "schema"))
                            .and_then(|s| get(s, "enum")),
                    )
                    .iter()
                    .map(|v| plain_str_opt(Some(v)))
                    .collect()
                })
                .unwrap_or_default();
        out.push(("machine_contract schema".to_string(), enum_vals.join(",")));
    }

    let prot = crate::glob::expand(root, "community/*/protocol.yaml");
    if let Some(first) = prot.first() {
        let text = std::fs::read_to_string(root.join(first)).unwrap_or_default();
        static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
        let re = RE.get_or_init(|| {
            regex::Regex::new(r#"schema_version\s*:\s*"?([\w.]+)"?"#).expect("版本正则固定合法")
        });
        out.push((
            "protocol.yaml schema".to_string(),
            re.captures(&text)
                .map(|c| c[1].to_string())
                .unwrap_or_default(),
        ));
    }

    let schemas = crate::glob::expand(root, "protocol/schema/*.json");
    out.push(("IDL schema 集".to_string(), format!("{} 件", schemas.len())));

    let verify_path = root.join("verify.sh");
    let verify = if verify_path.is_file() {
        std::fs::read_to_string(&verify_path).unwrap_or_default()
    } else {
        String::new()
    };
    static VRE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    let vre =
        VRE.get_or_init(|| regex::Regex::new(r"# 版本 : (v[\d.]+)").expect("版本行正则固定合法"));
    let vm = vre.captures(&verify).map(|c| c[1].to_string());
    let qb_text = std::fs::read_to_string(root.join("desktop/src/core/quality_baseline.py"))
        .unwrap_or_default();
    let checks = crate::stats::py_int_const(&qb_text, "EXPECTED_CHECKS").unwrap_or(0);
    let pass = crate::stats::py_int_const(&qb_text, "EXPECTED_PASS").unwrap_or(0);
    out.push((
        "基线".to_string(),
        format!(
            "{} · check1-{} · PASS={}",
            vm.unwrap_or_else(|| "?".to_string()),
            checks,
            pass
        ),
    ));

    out
}

pub(crate) struct DeclScan {
    pub issues: Vec<String>,
    pub versions: usize,
    pub scope: usize,
    pub excluded: usize,
}

/// 真源 `scan`。
pub(crate) fn scan(root: &Path) -> DeclScan {
    let mut issues: Vec<String> = Vec::new();
    let decl = parse(root);
    let live = live_versions(root);

    if decl.versions.is_empty() {
        issues.push(format!(
            "声明文件缺 `## 声明` 版本表（修复指引：见 {}）",
            DECL_REL
        ));
    }
    decl_live_mismatch_issues(&decl, &live, &mut issues);
    decl_unverifiable_issues(&decl, &live, &mut issues);
    decl_scope_issues(root, &decl, &mut issues);
    if decl.excluded.is_empty() {
        issues.push("声明文件缺 `## 排除` 清单（显式排除是声明的核心价值）".to_string());
    }
    decl_excluded_issues(root, &decl, &mut issues);
    decl_overlap_issues(&decl, &mut issues);

    DeclScan {
        issues,
        versions: decl.versions.len(),
        scope: decl.scope.len(),
        excluded: decl.excluded.len(),
    }
}

/// 声明值必须与真源一致（缺行报 "(缺)"）。
fn decl_live_mismatch_issues(decl: &Decl, live: &[(String, String)], issues: &mut Vec<String>) {
    for (name, want) in live {
        let got = decl
            .versions
            .iter()
            .find(|(n, _, _)| n == name)
            .map(|(_, v, _)| v.clone())
            .unwrap_or_default();
        if got != *want {
            issues.push(format!(
                "声明与真源不一致：{} 声明={} 真源={}（修复指引：改声明对齐真源）",
                name,
                if got.is_empty() { "(缺)" } else { got.as_str() },
                want
            ));
        }
    }
}

/// 声明的规范项必须都有真源可核。
fn decl_unverifiable_issues(decl: &Decl, live: &[(String, String)], issues: &mut Vec<String>) {
    for (name, _, _) in &decl.versions {
        if !live.iter().any(|(n, _)| n == name) {
            issues.push(format!(
                "声明了无法核验的规范项：{}（真源缺失；修复指引：补真源或删该行）",
                name
            ));
        }
    }
}

/// 范围白名单：非空且路径存在。
fn decl_scope_issues(root: &Path, decl: &Decl, issues: &mut Vec<String>) {
    if decl.scope.is_empty() {
        issues.push("声明文件缺 `## 范围` 白名单".to_string());
    }
    for rel in &decl.scope {
        if !root.join(rel).exists() {
            issues.push(format!(
                "范围里的路径不存在：{}（修复指引：删掉或改正）",
                rel
            ));
        }
    }
}

/// 排除清单：glob 须有匹配 / 路径须存在（"允许不存在" 标记者跳过）。
fn decl_excluded_issues(root: &Path, decl: &Decl, issues: &mut Vec<String>) {
    for (rel, reason) in &decl.excluded {
        if rel.is_empty() {
            continue;
        }
        let optional = reason.contains("允许不存在");
        if rel.chars().any(|c| c == '*' || c == '?' || c == '[') {
            if !optional && crate::glob::expand(root, rel).is_empty() {
                issues.push(format!("排除项 glob 无匹配：{}", rel));
            }
        } else if !optional && !root.join(rel).exists() {
            issues.push(format!(
                "排除项路径不存在：{}（修复指引：删除该条或修正路径）",
                rel
            ));
        }
    }
}

/// scope 与排除清单不得重叠（前缀 / 包含两个方向）。
fn decl_overlap_issues(decl: &Decl, issues: &mut Vec<String>) {
    let scope_set: Vec<String> = decl
        .scope
        .iter()
        .map(|s| s.trim_end_matches('/').to_string())
        .collect();
    for (rel_raw, _) in &decl.excluded {
        let rel = rel_raw.trim_end_matches('/').to_string();
        for s in &scope_set {
            if rel == *s
                || rel.starts_with(&format!("{}/", s))
                || s.starts_with(&format!("{}/", rel))
            {
                issues.push(format!(
                    "scope 与排除重叠：{} ↔ {}（同一条不能既在范围又排除）",
                    s, rel
                ));
            }
        }
    }
}
