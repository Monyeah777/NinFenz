//! 代码面：数据面聚合与摘要联动 + 测试件在场 + 结构契约（禁用式 / 计数棘轮）。

use super::*;

/// 各格式统计的合并（真源对 `no_schema` / `yaml_unavailable` 两个键累加，其余键覆盖）。
pub(crate) fn merge_format_stats(stats: &mut Vec<(String, Json)>, s: Json) {
    if let Json::Object(kv) = s {
        // 真源对 `no_schema` / `yaml_unavailable` 两个键**累加**到顶层，其余键 `update` 覆盖。
        for (k, v) in kv {
            if k == "no_schema" || k == "yaml_unavailable" {
                let add = pyval::py_int_or(Some(&v), 0);
                match stats.iter_mut().find(|(kk, _)| *kk == k) {
                    Some(e) => {
                        let base = pyval::py_int_or(Some(&e.1), 0);
                        e.1 = Json::Int(base + add);
                    }
                    None => stats.push((k, Json::Int(add))),
                }
                continue;
            }
            match stats.iter_mut().find(|(kk, _)| *kk == k) {
                Some(e) => e.1 = v,
                None => stats.push((k, v)),
            }
        }
    }
}

/// 数据件摘要与链接面（声明了 sha256 才查摘要；声明了 link 才查链接）。
pub(crate) fn data_sha_link_issues(
    root: &Path,
    rel: &str,
    spec: &Json,
    has_sha: bool,
    obj: &Option<Json>,
    issues: &mut Vec<String>,
) {
    if has_sha {
        let got = digest_of(&root.join(rel));
        let want = sg_str(spec, "sha256");
        if got != want {
            issues.push(format!(
                "数据件 {} 摘要不符（记录 {} / 实测 {}）（修复指引：核对改动，确认后用 nf asset contract --freeze 重冻）",
                rel,
                head_chars(&want, 12),
                head_chars(&got, 12)
            ));
        }
    }
if pyval::py_truthy(&sg(spec, "link")) {
    if let Some(o) = obj {
        issues.extend(data_link(root, rel, spec, o));
    }
}
}

pub(crate) fn head_chars(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

/// 真源 `_strict_json`：**严格如 RFC 8259**——`NaN` / `Infinity` 出现即报错。
pub fn strict_json(text: &str) -> Result<Json, String> {
    match serde_json::from_str::<serde_json::Value>(text) {
        Ok(v) => crate::jsonread::convert(&v),
        Err(e) => Err(e.to_string()),
    }
}

// ---------------------------------------------------------------- 代码面

/// 真源 `_check_tests`。
pub(crate) fn check_tests(root: &Path, rel: &str, spec: &Json) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    let stem = rel.rsplit_once('.').map(|(s, _)| s).unwrap_or(rel);
    let stem = stem.rsplit_once('/').map(|(_, s)| s).unwrap_or(stem);
    if !pyval::py_truthy(&sg(spec, "tests")) {
        issues.push(format!(
            "代码件 {} 未声明测试件（修复指引：补 tests 列表——没有用例的代码资产不算通过测试）",
            rel
        ));
    }
    for t in sg_strs(spec, "tests") {
        let trel = t.replace('\\', "/");
        let p = root.join(&trel);
        if !p.is_file() {
            issues.push(format!(
                "代码件 {} 声明的测试件不在场：{}（修复指引：先写测试再登记）",
                rel, trel
            ));
            continue;
        }
        let text = std::fs::read(&p)
            .map(|b| String::from_utf8_lossy(&b).into_owned())
            .unwrap_or_default();
        if crate::pyast::parse_module(&text).is_none() {
            // 真源在这里给 CPython 的 SyntaxError 文本 ⇒ **已知偏差**（见模块头）
            issues.push(format!(
                "测试件 {} 语法坏：<TEXT>（修复指引：先修语法）",
                trel
            ));
            continue;
        }
        if !text.contains(stem) {
            issues.push(format!(
                "测试件 {} 未点名被测模块 {}（修复指引：在测试里 import 或引用该模块）",
                trel, stem
            ));
        }
    }
    issues
}

/// spec 里某键的数组条目（非数组 → 空）。
pub(crate) fn sg_array(spec: &Json, k: &str) -> Vec<Json> {
    match obj_get(spec, k) {
        Some(Json::Array(a)) => a.clone(),
        _ => Vec::new(),
    }
}

/// 真源 `_code_structural`（E2 第二实现线结构契约）：不做完整 AST，只判**可证的正则面**——
/// 禁用式（必须 0 处）与计数上限（棘轮只减不增）。真源明说这是「范围与只减不增的计数」，
/// 比「装作 AST 判过」诚实；本线用 `regex` crate 承担同一条语义（模式均来自真源声明）。
pub(crate) fn check_code_structural(root: &Path, spec: &Json) -> (Vec<String>, Json) {
    let sid = {
        let s = sg_str(spec, "id");
        if s.is_empty() {
            "?".to_string()
        } else {
            s
        }
    };
    let rels = resolve(root, spec);
    if rels.is_empty() {
        return (
            vec![format!(
                "代码契约 {} 未命中任何文件（修复指引：修正 path/glob）",
                sid
            )],
            Json::Object(vec![("files".to_string(), Json::Int(0))]),
        );
    }
    let mut texts: Vec<(String, String)> = Vec::new();
    for rel in &rels {
        let (text, err) = sread(root, rel);
        if let Some(e) = err {
            return (
                vec![e],
                Json::Object(vec![("files".to_string(), Json::Int(rels.len() as i64))]),
            );
        }
        texts.push((rel.clone(), text.unwrap_or_default()));
    }
    let mut issues: Vec<String> = Vec::new();
    let mut stats: Vec<(String, Json)> = vec![("files".to_string(), Json::Int(rels.len() as i64))];
    for rule in sg_array(spec, "forbid_regex") {
        let name = sg_str(&rule, "name");
        let pat = sg_str(&rule, "pattern");
        let Ok(rx) = regex::Regex::new(&pat) else {
            continue;
        };
        let mut hits: Vec<String> = Vec::new();
        for (rel, text) in &texts {
            for m in rx.find_iter(text) {
                let line = text[..m.start()].matches('\n').count() + 1;
                hits.push(format!("{}:{}", rel, line));
            }
        }
        stats.push((format!("forbid:{}", name), Json::Int(hits.len() as i64)));
        if !hits.is_empty() {
            let why = {
                let w = sg_str(&rule, "why");
                if w.is_empty() {
                    "换成不越界的等价实现".to_string()
                } else {
                    w
                }
            };
            let sample: Vec<String> = hits.iter().take(3).cloned().collect();
            issues.push(format!(
                "代码契约 {} 命中禁用式 {}（{} 处，例 {}）（修复指引：{}）",
                sid,
                name,
                hits.len(),
                sample.join("、"),
                why
            ));
        }
    }
    for rule in sg_array(spec, "regex_limits") {
        let name = sg_str(&rule, "name");
        let pat = sg_str(&rule, "pattern");
        let Ok(rx) = regex::Regex::new(&pat) else {
            continue;
        };
        let n: i64 = texts
            .iter()
            .map(|(_, t)| rx.find_iter(t).count() as i64)
            .sum();
        let cap = pyval::py_int_or(obj_get(&rule, "max"), 0);
        stats.push((format!("limit:{}", name), Json::Int(n)));
        if n > cap {
            issues.push(format!(
                "代码契约 {} 的 {} 计数 {} > 上限 {}（棘轮只减不增）（修复指引：先降后改声明）",
                sid, name, n, cap
            ));
        }
    }
    (issues, Json::Object(stats))
}

// ---------------------------------------------------------------- 代码面·告警面（WARN）

/// 真源 `_line_no`：字符偏移 → 1 基行号（与编译器/ruff 同口径；换行是单字节，按字节切安全）。
pub(crate) fn line_no(text: &str, pos: usize) -> usize {
    text[..pos].matches('\n').count() + 1
}

/// 真源 `_warn_cut`：`skip_after` 标记之前的区域才判（测试区是脚手架，不是出口契约）。
pub(crate) fn warn_cut(text: &str, rule: &Json) -> usize {
    let marker = sg_str(rule, "skip_after");
    if marker.is_empty() {
        return text.len();
    }
    text.find(&marker).unwrap_or(text.len())
}

/// 真源 `_is_code_line`：只判**代码行**，注释里的词不算出口面（否则 SAFETY 注释自身也会自命中）。
pub(crate) fn is_code_line(line: &str) -> bool {
    let s = line.trim();
    if s.is_empty() {
        return false;
    }
    !(s.starts_with("//") || s.starts_with("/*") || s.starts_with('*'))
}

pub(crate) fn rule_lines(text: &str) -> Vec<&str> {
    text.split('\n')
        .map(|l| l.strip_suffix('\r').unwrap_or(l))
        .collect()
}

/// 真源 `_warn_unsafe_safety`（规则①）：每处 UNSAFE 标记前 within 行内须有 SAFETY: 注释。
pub(crate) fn warn_unsafe_safety(sid: &str, rel: &str, text: &str, rule: &Json) -> Vec<String> {
    let pat = {
        let p = sg_str(rule, "pattern");
        if p.is_empty() {
            r"\bunsafe\b".to_string()
        } else {
            p
        }
    };
    let marker = {
        let m = sg_str(rule, "marker");
        if m.is_empty() {
            "SAFETY:".to_string()
        } else {
            m
        }
    };
    let within = pyval::py_int_or(obj_get(rule, "within"), 3).max(0) as usize;
    let cut = warn_cut(text, rule);
    let lines = rule_lines(text);
    let Ok(rx) = regex::Regex::new(&pat) else {
        return Vec::new();
    };
    let mut out: Vec<String> = Vec::new();
    for m in rx.find_iter(&text[..cut]) {
        let ln = line_no(text, m.start());
        if !is_code_line(lines[ln - 1]) {
            continue;
        }
        let lo = ln.saturating_sub(1 + within);
        let hit = (lo..ln.saturating_sub(1)).any(|i| lines[i].contains(&marker));
        if !hit {
            out.push(format!(
                concat!(
                    "代码契约 {} 告警：{}:{} 的 ",
                    "un",
                    "safe",
                    " 前 {} 行内缺 {} 注释（修复指引：在 ",
                    "un",
                    "safe",
                    " 块/签名紧邻上方写「{} 调用方前置条件」，让审查面可读）"
                ),
                sid, rel, ln, within, marker, marker
            ));
        }
    }
    out
}
