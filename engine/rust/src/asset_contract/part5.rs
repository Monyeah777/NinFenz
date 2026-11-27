//! 代码面：告警面（WARN 三规则）与 check_code。

use super::*;

/// 真源 `_warn_null_guard`（规则②）：每处 `from_raw_parts` 前 within 行内须有空指针检查。
pub(crate) fn warn_null_guard(sid: &str, rel: &str, text: &str, rule: &Json) -> Vec<String> {
    let pat = {
        let p = sg_str(rule, "pattern");
        if p.is_empty() {
            "from_raw_parts".to_string()
        } else {
            p
        }
    };
    let guard = {
        let g = sg_str(rule, "guard");
        if g.is_empty() {
            "is_null".to_string()
        } else {
            g
        }
    };
    let within = pyval::py_int_or(obj_get(rule, "within"), 20).max(0) as usize;
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
        let hit = (lo..ln.saturating_sub(1)).any(|i| lines[i].contains(&guard));
        if !hit {
            out.push(format!(
                "代码契约 {} 告警：{}:{} 的 from_raw_parts 前 {} 行内无空指针检查（修复指引：先 `if ptr.is_null() {{ return 0; }}` 再构造切片——null 即使 len=0 也是 UB）",
                sid, rel, ln, within
            ));
        }
    }
    out
}

/// 真源 `_warn_export_no_panic`（规则③）：`#[no_mangle]` 起的导出区块不得 panic/unwrap。
pub(crate) fn warn_export_no_panic(sid: &str, rel: &str, text: &str, rule: &Json) -> Vec<String> {
    let pat = {
        let p = sg_str(rule, "pattern");
        if p.is_empty() {
            r"#\[no_mangle\]".to_string()
        } else {
            p
        }
    };
    let forbid: Vec<String> = sg_array(rule, "forbid")
        .iter()
        .map(|x| pyval::plain_str(x))
        .collect();
    let cut = warn_cut(text, rule);
    let lines = rule_lines(text);
    let Ok(rx) = regex::Regex::new(&pat) else {
        return Vec::new();
    };
    let starts: Vec<usize> = rx.find_iter(&text[..cut]).map(|m| m.start()).collect();
    let mut out: Vec<String> = Vec::new();
    for (i, &pos) in starts.iter().enumerate() {
        let end = starts.get(i + 1).copied().unwrap_or(cut);
        let ln = line_no(text, pos);
        let end_ln = line_no(text, if end > pos { end - 1 } else { pos });
        for idx in (ln - 1)..end_ln {
            let line = lines.get(idx).copied().unwrap_or("");
            if !is_code_line(line) {
                continue;
            }
            for bad in &forbid {
                if line.contains(bad.as_str()) {
                    out.push(format!(
                        "代码契约 {} 告警：{}:{} 起的导出面含 {}（修复指引：C ABI 出口以错误码返回，不 panic/unwrap/expect/assert——越过 ABI 边界 panic 是未定义行为）",
                        sid,
                        rel,
                        idx + 1,
                        pyval::py_repr(&Json::Str(bad.clone()))
                    ));
                }
            }
        }
    }
    out
}

/// 真源 `_code_warns`：代码面的**告警面**（WARN 级，不 FAIL），由声明里的 `warn_rules` 驱动。
///
/// 为什么单开一路：FFI 出口**必然**要 UNSAFE（C ABI 本质），「禁 UNSAFE」不能简单套用；
/// 而「UNSAFE 须带 SAFETY 注释 / `from_raw_parts` 前须挡空指针 / 导出面不许 panic」这类治理
/// 规则在**存量未清**时按 FAIL 接入会立刻逼人重冻或删判据。故先按 WARN 接入：看得见、能逐条
/// 清；清零后再把规则搬进 `forbid_regex` / 新判据升 FAIL。
pub fn code_warns(root: &Path, spec: &Json) -> Vec<String> {
    let rules: Vec<(String, Json)> = match obj_get(spec, "warn_rules") {
        Some(Json::Object(o)) if !o.is_empty() => o.clone(),
        _ => return Vec::new(),
    };
    let rels = resolve(root, spec);
    if rels.is_empty() {
        return Vec::new(); // 未命中面的事由 `check_code` 的 issues 报，不重复告警
    }
    let sid = {
        let s = sg_str(spec, "id");
        if s.is_empty() {
            "?".to_string()
        } else {
            s
        }
    };
    let mut warns: Vec<String> = Vec::new();
    for rel in &rels {
        let (text, err) = sread(root, rel);
        if err.is_some() {
            continue; // 读件失败同样由 issues 面报
        }
        let text = text.unwrap_or_default();
        for (name, rule) in &rules {
            if !matches!(rule, Json::Object(_)) {
                continue;
            }
            match name.as_str() {
                "unsafe_safety_comment" => warns.extend(warn_unsafe_safety(&sid, rel, &text, rule)),
                "null_guard_before" => warns.extend(warn_null_guard(&sid, rel, &text, rule)),
                "export_no_panic" => warns.extend(warn_export_no_panic(&sid, rel, &text, rule)),
                _ => {}
            }
        }
    }
    warns
}

/// 真源 `_check_code`。
pub fn check_code(root: &Path, spec: &Json) -> (Vec<String>, Json) {
    if !sg_array(spec, "forbid_regex").is_empty()
        || !sg_array(spec, "regex_limits").is_empty()
        || obj_get(spec, "warn_rules").is_some()
    {
        return check_code_structural(root, spec);
    }
    let rel = sg_str(spec, "path");
    let lang = {
        let l = sg_str(spec, "lang");
        if l.is_empty() {
            "python".to_string()
        } else {
            l
        }
    };
    if lang != "python" {
        return (
            vec![format!(
                "代码契约 {} 的 lang={} 不在支持面（仅 python 走 AST；Bash/VBA 走脚本面声明式契约）",
                pyval::py_str(obj_get(spec, "id")),
                pyval::py_str(obj_get(spec, "lang"))
            )],
            Json::Object(vec![]),
        );
    }
    let rels = resolve(root, spec);
    if rels.is_empty() {
        return (
            vec![format!(
                "代码契约 {} 未命中任何文件（修复指引：修正 path/glob）",
                pyval::py_str(obj_get(spec, "id"))
            )],
            Json::Object(vec![("files".to_string(), Json::Int(0))]),
        );
    }
    let mut issues: Vec<String> = Vec::new();
    let stats = Json::Object(vec![("files".to_string(), Json::Int(rels.len() as i64))]);
    let deny: std::collections::BTreeSet<String> =
        sg_strs(spec, "deny_calls").into_iter().collect();
    for one in &rels {
        let (text, err) = sread(root, one);
        if let Some(e) = err {
            issues.push(e);
            continue;
        }
        let text = text.unwrap_or_default();
        let Some(tree) = crate::pyast::parse_module(&text) else {
            issues.push(format!(
                "代码件 {} 语法坏：<TEXT>（修复指引：先修语法，AST 判据需要可解析的树）",
                one
            ));
            continue;
        };
        let ls = crate::pyast::LineStarts::new(&text);
        issues.extend(crate::asset_code::denied_calls(&tree, one, &deny, &ls));
        issues.extend(crate::asset_code::none_deref(&tree, one, &ls));
    }
    if !rel.is_empty() {
        issues.extend(check_tests(root, &rel, spec));
    }
    (issues, stats)
}

// ---------------------------------------------------------------- 脚本面

pub(crate) fn io_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"(?m)(?:#|')[ \t]*nf-io:[ \t]*(.+?)[ \t]*$").expect("固定合法")
    })
}

/// 真源 `parse_io_header` → `(inputs, outputs)`；无头 → `None`。
pub fn parse_io_header(text: &str) -> Option<(Vec<String>, Vec<String>)> {
    let m = io_re().captures(text)?;
    let mut ins: Vec<String> = Vec::new();
    let mut outs: Vec<String> = Vec::new();
    for token in m[1].split_whitespace() {
        let Some((key, val)) = token.split_once('=') else {
            continue;
        };
        let key = key.trim().to_lowercase();
        let v = val.trim();
        let list: Vec<String> = if v == "-" || v.is_empty() {
            Vec::new()
        } else {
            v.split(',')
                .map(|x| x.trim().to_string())
                .filter(|x| !x.is_empty())
                .collect()
        };
        match key.as_str() {
            "inputs" => ins = list,
            "outputs" => outs = list,
            _ => {}
        }
    }
    Some((ins, outs))
}

/// 真源 `observed_paths`：脚本里**字面量**形式的文件路径。
pub fn observed_paths(text: &str, lang: &str) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    match lang {
        "python" => {
            let Some(tree) = crate::pyast::parse_module(text) else {
                return out;
            };
            let ls = crate::pyast::LineStarts::new(text);
            for (_, _, _, name, args) in crate::asset_code::calls_with_args(&tree, &ls) {
                if name != "open" && name != "Path" && name != "pathlib.Path" {
                    continue;
                }
                for a in args {
                    if let Some(s) = a {
                        out.push(s);
                    }
                }
            }
        }
        "bash" => {
            let re = regex::Regex::new(r">>?[ \t]*([^\s;|&()]+)|<[ \t]*([^\s;|&()]+)").unwrap();
            for c in re.captures_iter(text) {
                out.push(
                    c.get(1)
                        .or_else(|| c.get(2))
                        .map(|m| m.as_str().to_string())
                        .unwrap_or_default(),
                );
            }
        }
        "vba" => {
            let re = regex::Regex::new(r#"(?i)\bOpen\s+"([^"]+)""#).unwrap();
            for c in re.captures_iter(text) {
                out.push(c[1].to_string());
            }
        }
        _ => {}
    }
    let skip = ["/dev/null", "/dev/stdin", "/dev/stdout", "-"];
    out.into_iter()
        .filter(|p| !p.is_empty() && !skip.contains(&p.as_str()) && !p.starts_with('$'))
        .collect()
}
