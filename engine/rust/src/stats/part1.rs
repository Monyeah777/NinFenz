use super::*;

pub(crate) const STATS_REL: &str = "protocol/repo_stats.json";

pub(crate) const BEGIN: &str = "<!-- nf:stats:begin -->";

pub(crate) const END: &str = "<!-- nf:stats:end -->";

/// 生成区所在入口件（真源 `BLOCK_FILES` 口径：README 中英 + llms.txt）。
pub(crate) const BLOCK_FILES: [&str; 3] = ["README.md", "README.en.md", "llms.txt"];

/// 自述数字集合（真源 `stats` 字典的等价物）。
#[derive(Default, Clone, Debug)]
pub(crate) struct Stats {
    pub core_modules: i64,
    pub registered_packs: i64,
    pub core_pipelines: Vec<String>,
    pub pack_dirs: i64,
    pub pack_assets: i64,
    pub concept_graphs: i64,
    pub standards_total: i64,
    pub standards_reachable: i64,
    pub standards_unreachable: i64,
    pub standards_bodies: i64,
    pub standards_edges: i64,
    pub standards_by_layer: Vec<(String, i64)>,
    pub standard_bindings: i64,
    pub domain_packs: i64,
    pub subdivisions_total: i64,
    pub library_items: i64,
    pub verify_checks: i64,
    pub verify_version: String,
    pub baseline_checks: i64,
    pub baseline_pass: i64,
}

impl Stats {
    /// 与真源 `stats` 字典同字段、同值（键序在 `pyjson` 发射时统一排序）。
    pub fn to_json(&self) -> Json {
        Json::Object(vec![
            ("schema".into(), Json::Str("nf-repo-stats/1".into())),
            ("core_modules".into(), Json::Int(self.core_modules)),
            ("registered_packs".into(), Json::Int(self.registered_packs)),
            (
                "core_pipelines".into(),
                Json::Array(
                    self.core_pipelines
                        .iter()
                        .map(|s| Json::Str(s.clone()))
                        .collect(),
                ),
            ),
            ("pack_dirs".into(), Json::Int(self.pack_dirs)),
            ("pack_assets".into(), Json::Int(self.pack_assets)),
            ("concept_graphs".into(), Json::Int(self.concept_graphs)),
            ("standards_total".into(), Json::Int(self.standards_total)),
            (
                "standards_reachable".into(),
                Json::Int(self.standards_reachable),
            ),
            (
                "standards_unreachable".into(),
                Json::Int(self.standards_unreachable),
            ),
            ("standards_bodies".into(), Json::Int(self.standards_bodies)),
            ("standards_edges".into(), Json::Int(self.standards_edges)),
            (
                "standards_by_layer".into(),
                Json::Object(
                    self.standards_by_layer
                        .iter()
                        .map(|(k, v)| (k.clone(), Json::Int(*v)))
                        .collect(),
                ),
            ),
            (
                "standard_bindings".into(),
                Json::Int(self.standard_bindings),
            ),
            ("domain_packs".into(), Json::Int(self.domain_packs)),
            (
                "subdivisions_total".into(),
                Json::Int(self.subdivisions_total),
            ),
            ("library_items".into(), Json::Int(self.library_items)),
            ("verify_checks".into(), Json::Int(self.verify_checks)),
            (
                "verify_version".into(),
                Json::Str(self.verify_version.clone()),
            ),
            ("baseline_checks".into(), Json::Int(self.baseline_checks)),
            ("baseline_pass".into(), Json::Int(self.baseline_pass)),
        ])
    }
}

// ---------------------------------------------------------------- JSON 取值助手

pub(crate) fn obj_get<'a>(j: &'a Json, k: &str) -> Option<&'a Json> {
    match j {
        Json::Object(pairs) => pairs.iter().find(|(n, _)| n == k).map(|(_, v)| v),
        _ => None,
    }
}

pub(crate) fn int_of(j: Option<&Json>) -> i64 {
    match j {
        Some(Json::Int(i)) => *i,
        _ => 0,
    }
}

pub(crate) fn len_of(j: Option<&Json>) -> i64 {
    match j {
        Some(Json::Array(a)) => a.len() as i64,
        _ => 0,
    }
}

pub(crate) fn layer_of(j: Option<&Json>) -> Vec<(String, i64)> {
    match j {
        Some(Json::Object(pairs)) => pairs
            .iter()
            .map(|(k, v)| {
                (
                    k.clone(),
                    match v {
                        Json::Int(i) => *i,
                        _ => 0,
                    },
                )
            })
            .collect(),
        _ => Vec::new(),
    }
}

// ---------------------------------------------------------------- 目录扫描（glob 等价物）

pub(crate) fn names_in(dir: &Path) -> Vec<String> {
    let mut out = Vec::new();
    if let Ok(rd) = std::fs::read_dir(dir) {
        for e in rd.flatten() {
            out.push(e.file_name().to_string_lossy().into_owned());
        }
    }
    out
}

pub(crate) fn subdirs_in(dir: &Path) -> Vec<String> {
    let mut out = Vec::new();
    if let Ok(rd) = std::fs::read_dir(dir) {
        for e in rd.flatten() {
            if e.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                out.push(e.file_name().to_string_lossy().into_owned());
            }
        }
    }
    out
}

/// `glob("dir/*.md")` 的计数等价物（Python glob 不筛类型，故按名匹配即可）。
pub(crate) fn count_suffix(dir: &Path, suffix: &str) -> i64 {
    names_in(dir).iter().filter(|n| n.ends_with(suffix)).count() as i64
}

/// `glob("parent/*/sub/name")` 的计数等价物（`sub` 为空表示直接在 `parent/*/` 下找）。
pub(crate) fn count_in_subdirs(parent: &Path, sub: &str, name: &str) -> i64 {
    subdirs_in(parent)
        .iter()
        .filter(|p| {
            let mut d = parent.join(p.as_str());
            if !sub.is_empty() {
                d = d.join(sub);
            }
            d.join(name).exists()
        })
        .count() as i64
}

/// `glob("parent/*/sub/*suffix")` 的计数等价物。
pub(crate) fn count_suffix_in_subdirs(parent: &Path, sub: &str, suffix: &str) -> i64 {
    subdirs_in(parent)
        .iter()
        .map(|p| count_suffix(&parent.join(p.as_str()).join(sub), suffix))
        .sum()
}

// ---------------------------------------------------------------- verify.sh / quality_baseline

/// `^check[0-9]+\(\)` 定义数（真源 `re.findall(..., re.M)`）。
pub(crate) fn count_checks(text: &str) -> i64 {
    let mut n = 0i64;
    for line in text.lines() {
        if let Some(rest) = line.strip_prefix("check") {
            let digits: String = rest.chars().take_while(|c| c.is_ascii_digit()).collect();
            if !digits.is_empty() && rest[digits.len()..].starts_with("()") {
                n += 1;
            }
        }
    }
    n
}

/// `^# 版本\s*:\s*v([0-9][0-9.]*)` 的首个捕获组（无匹配 → 空串，与真源同语义）。
pub(crate) fn parse_version(text: &str) -> String {
    for line in text.lines() {
        let Some(rest) = line.strip_prefix("# 版本") else {
            continue;
        };
        let mut it = rest.chars().peekable();
        skip_ws(&mut it);
        if it.next() != Some(':') {
            continue;
        }
        skip_ws(&mut it);
        if it.next() != Some('v') {
            continue;
        }
        let v = version_digits(&mut it);
        if !v.is_empty() {
            return v;
        }
    }
    String::new()
}

/// 跳过一个字符迭代器当前位置起的所有空白。
fn skip_ws(it: &mut std::iter::Peekable<std::str::Chars<'_>>) {
    while it.peek().map(|c| c.is_whitespace()).unwrap_or(false) {
        it.next();
    }
}

/// 版本号正文：数字段 + 点号（点号不得打头）。
fn version_digits(it: &mut std::iter::Peekable<std::str::Chars<'_>>) -> String {
    let mut v = String::new();
    while let Some(&c) = it.peek() {
        if c.is_ascii_digit() {
            v.push(c);
            it.next();
        } else if c == '.' && !v.is_empty() {
            v.push(c);
            it.next();
        } else {
            break;
        }
    }
    v
}

/// 读 Python 模块级整数常量（真源 `getattr(qb, "EXPECTED_*", …)`）。
///
/// **已知耦合**：本线以源码文本取这两个常量——`quality_baseline` 是 Python 模块，
/// 非 Python 实现没有别的稳定入口。若该文件改成运行时计算，本处须同步改判。
pub(crate) fn py_int_const(text: &str, name: &str) -> Option<i64> {
    for line in text.lines() {
        let t = line.trim_start();
        let Some(rest) = t.strip_prefix(name) else {
            continue;
        };
        // 防前缀误伤（EXPECTED_CHECKS_SOMETHING）
        if rest
            .chars()
            .next()
            .map(|c| c == '_' || c.is_alphanumeric())
            .unwrap_or(false)
        {
            continue;
        }
        let rest = rest.trim_start();
        let Some(rest) = rest.strip_prefix('=') else {
            continue;
        };
        let digits: String = rest
            .trim_start()
            .chars()
            .take_while(|c| c.is_ascii_digit())
            .collect();
        if !digits.is_empty() {
            return digits.parse().ok();
        }
    }
    None
}
