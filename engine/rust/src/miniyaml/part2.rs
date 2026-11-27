use super::*;

/// 行内值：`[]` / `{}` / `[a, b]` / 引号标量 / 裸标量。
pub(crate) fn parse_inline(s: &str) -> Result<Json, String> {
    let t = s.trim();
    if t == "{}" {
        return Ok(Json::Object(Vec::new()));
    }
    if t == "[]" {
        return Ok(Json::Array(Vec::new()));
    }
    if t.starts_with('{') {
        return parse_flow_map(t);
    }
    if t.starts_with('[') {
        return parse_flow_seq(t);
    }
    if t.starts_with('"') || t.starts_with('\'') {
        return Ok(Json::Str(unquote(t)?));
    }
    plain_scalar(t)
}

/// 流式映射 `{k: v, k: v}`。
fn parse_flow_map(t: &str) -> Result<Json, String> {
    // 流式映射 {k: v, k: v}（真源 protocol.yaml 的 mount_layers 就是这种）。
    // ⚠️ 早先这里对非空流式映射 fail-closed——结果 **111 份 protocol.yaml 全部解析失败**。
    // 教训同变量那条：fail-closed 的粒度要准，拒得越宽，被整件连坐的越多。
    if !t.ends_with('}') {
        return Err(format!("越出子集：花括号不闭合：{}", t));
    }
    let inner = &t[1..t.len() - 1];
    parse_flow_map_inner(inner)
}

/// 流式映射内层：空表 / 逐项键值对。
fn parse_flow_map_inner(inner: &str) -> Result<Json, String> {
    if inner.trim().is_empty() {
        return Ok(Json::Object(Vec::new()));
    }
    let mut pairs: Vec<(String, Json)> = Vec::new();
    for part in split_inline_items(inner) {
        let part = part.trim();
        if part.is_empty() {
            continue;
        }
        parse_flow_pair(part, &mut pairs)?;
    }
    Ok(Json::Object(pairs))
}

/// 流式映射单项：键值解析 + 同键覆盖（真源 dict 语义）。
fn parse_flow_pair(part: &str, pairs: &mut Vec<(String, Json)>) -> Result<(), String> {
    let Some((k, v)) = split_inline_pair(part) else {
        return Err(format!("越出子集：流式映射项不是键值对：{}", part));
    };
    let key = plain_or_quoted(k.trim())?;
    let value = if v.trim().is_empty() {
        Json::Null
    } else {
        parse_inline(v.trim())?
    };
    match pairs.iter_mut().find(|(n, _)| *n == key) {
        Some(slot) => slot.1 = value,
        None => pairs.push((key, value)),
    }
    Ok(())
}

/// 流式列表 `[a, b, [c]]`。
fn parse_flow_seq(t: &str) -> Result<Json, String> {
    if !t.ends_with(']') {
        return Err(format!("越出子集：方括号不闭合：{}", t));
    }
    let inner = &t[1..t.len() - 1];
    if inner.trim().is_empty() {
        return Ok(Json::Array(Vec::new()));
    }
    let mut items = Vec::new();
    for part in split_inline_items(inner) {
        items.push(parse_inline(part.trim())?);
    }
    Ok(Json::Array(items))
}

/// 行内列表切分：只在**引号外**的逗号处切。
pub(crate) fn split_inline_items(inner: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    let mut quote: Option<char> = None;
    let mut depth: i32 = 0;
    let chars: Vec<char> = inner.chars().collect();
    let mut k = 0;
    while k < chars.len() {
        if quote.is_some() {
            k = split_quoted_step(&chars, k, &mut quote, &mut cur);
        } else {
            k = split_plain_step(&chars, k, &mut quote, &mut depth, &mut cur, &mut out);
        }
    }
    out.push(cur);
    out
}

/// 引号内一步：原样拷贝；反斜杠转义 / 闭合引号各占一步。
fn split_quoted_step(
    chars: &[char],
    k: usize,
    quote: &mut Option<char>,
    cur: &mut String,
) -> usize {
    let c = chars[k];
    cur.push(c);
    if c == '\\' && *quote == Some('"') && k + 1 < chars.len() {
        cur.push(chars[k + 1]);
        return k + 2;
    }
    if Some(c) == *quote {
        *quote = None;
    }
    k + 1
}

/// 引号外一步：括号深度 / 顶层逗号切分 / 原样拷贝。
fn split_plain_step(
    chars: &[char],
    k: usize,
    quote: &mut Option<char>,
    depth: &mut i32,
    cur: &mut String,
    out: &mut Vec<String>,
) -> usize {
    let c = chars[k];
    if c == '"' || c == '\'' {
        *quote = Some(c);
        cur.push(c);
    } else if c == '[' || c == '{' {
        *depth += 1;
        cur.push(c);
    } else if c == ']' || c == '}' {
        *depth -= 1;
        cur.push(c);
    } else if c == ',' && *depth == 0 {
        out.push(cur.clone());
        cur.clear();
    } else {
        cur.push(c);
    }
    k + 1
}

/// 剥引号。**首字符必须是引号**——否则 fail-closed。
///
/// ⚠️ 踩过：早先只判「首字符 == 末字符」，于是裸键 `default` 被判为引号标量
/// （`q='d'`，`ends_with('d')` 为真），首尾各剥一个字符 → `efaul`。流式映射的键全被改坏。
pub(crate) fn plain_or_quoted(t: &str) -> Result<String, String> {
    if t.starts_with('"') || t.starts_with('\'') {
        unquote(t)
    } else {
        Ok(t.to_string())
    }
}

pub(crate) fn unquote(t: &str) -> Result<String, String> {
    let q = match t.chars().next() {
        Some(c @ ('"' | '\'')) => c,
        _ => return Err(format!("越出子集：不是引号标量：{}", t)),
    };
    if !t.ends_with(q) || t.chars().count() < 2 {
        return Err(format!("越出子集：引号不闭合：{}", t));
    }
    let inner = &t[1..t.len() - 1];
    if q == '\'' {
        // 单引号里 `''` 表示一个单引号
        return Ok(inner.replace("''", "'"));
    }
    let mut out = String::with_capacity(inner.len());
    let chars: Vec<char> = inner.chars().collect();
    let mut k = 0;
    while k < chars.len() {
        if chars[k] == '\\' && k + 1 < chars.len() {
            let n = chars[k + 1];
            out.push(match n {
                'n' => '\n',
                't' => '\t',
                'r' => '\r',
                '"' => '"',
                '\\' => '\\',
                '0' => '\0',
                other => other,
            });
            k += 2;
            continue;
        }
        out.push(chars[k]);
        k += 1;
    }
    Ok(out)
}

/// 裸标量 → 按 YAML 1.1 解析（与 PyYAML `SafeLoader` 对齐）。
///
/// **为什么必须解析类型而不是一律当字符串**（实测教训 2026-10-03）：一开始本模块对
/// 「看着像非字符串」的裸标量 fail-closed，结果 `M50_调度器.md` 里一个 `tick: 0`
/// 就让**整个模块**解析失败被丢弃，它发布的 `minute_tick` 随之变成"无发布方"，
/// `event-backing` 凭空报出缺口。**fail-closed 必须精确到标量，不能连坐整件。**
///
/// 覆盖 null / bool / int（十·十六·八·二进制）/ float / 字符串；
/// 日期与六十进制（`1:30`）不在子集内，仍 fail-closed。
pub(crate) fn plain_scalar(t: &str) -> Result<Json, String> {
    if is_null_scalar(t) {
        return Ok(Json::Null);
    }
    if let Some(b) = resolve_bool(t) {
        return Ok(Json::Bool(b));
    }
    if let Some(i) = resolve_int(t) {
        return Ok(Json::Int(i));
    }
    if let Some(f) = resolve_float(t) {
        return Ok(Json::Float(f));
    }
    if looks_out_of_subset(t) {
        return Err(format!(
            "越出子集：裸标量 `{}` 在 YAML 1.1 下非字符串，且本线未复刻该类型（不猜）",
            t
        ));
    }
    Ok(Json::Str(t.to_string()))
}

pub(crate) fn is_null_scalar(t: &str) -> bool {
    matches!(t, "~" | "null" | "Null" | "NULL" | "NuLL" | "") || t.trim().is_empty()
}

pub(crate) fn resolve_bool(t: &str) -> Option<bool> {
    match t {
        "yes" | "Yes" | "YES" | "true" | "True" | "TRUE" | "on" | "On" | "ON" => Some(true),
        "no" | "No" | "NO" | "false" | "False" | "FALSE" | "off" | "Off" | "OFF" => Some(false),
        _ => None,
    }
}

pub(crate) fn resolve_int(t: &str) -> Option<i64> {
    let (sign, body) = int_sign_body(t);
    if body.is_empty() {
        return None;
    }
    let clean = body.replace('_', "");
    if let Some(v) = radix_int(&clean, sign) {
        return Some(v);
    }
    // YAML 1.1：前导 0 且全为 0-7 ⇒ 八进制
    if is_legacy_octal(&clean) {
        return i64::from_str_radix(&clean, 8).ok().map(|v| v * sign);
    }
    if !clean.is_empty() && clean.chars().all(|c| c.is_ascii_digit()) {
        return clean.parse::<i64>().ok().map(|v| v * sign);
    }
    None
}

/// 符号与裸体：前导 - / + 各剥一个。
fn int_sign_body(t: &str) -> (i64, &str) {
    match t.strip_prefix('-') {
        Some(r) => (-1i64, r),
        None => match t.strip_prefix('+') {
            Some(r) => (1i64, r),
            None => (1i64, t),
        },
    }
}

/// 0x / 0o / 0b 前缀整数。
fn radix_int(clean: &str, sign: i64) -> Option<i64> {
    if clean.starts_with("0x") || clean.starts_with("0X") {
        return radix_prefixed(clean, 16, sign);
    }
    if clean.starts_with("0o") || clean.starts_with("0O") {
        return radix_prefixed(clean, 8, sign);
    }
    if clean.starts_with("0b") || clean.starts_with("0B") {
        return radix_prefixed(clean, 2, sign);
    }
    None
}

/// 剥两位前缀后按 radix 解析；空体返回 None。
fn radix_prefixed(clean: &str, radix: u32, sign: i64) -> Option<i64> {
    let h = &clean[2..];
    if h.is_empty() {
        return None;
    }
    i64::from_str_radix(h, radix).ok().map(|v| v * sign)
}

/// YAML 1.1 旧式八进制：前导 0 且全为 0-7。
fn is_legacy_octal(clean: &str) -> bool {
    clean.len() > 1 && clean.starts_with('0') && clean.chars().all(|c| ('0'..='7').contains(&c))
}

pub(crate) fn resolve_float(t: &str) -> Option<f64> {
    match t {
        ".inf" | "+.inf" | ".Inf" | "+.Inf" | ".INF" | "+.INF" => return Some(f64::INFINITY),
        "-.inf" | "-.Inf" | "-.INF" => return Some(f64::NEG_INFINITY),
        ".nan" | ".NaN" | ".NAN" => return Some(f64::NAN),
        _ => {}
    }
    let clean = t.replace('_', "");
    // PyYAML 的浮点正则要求有小数点或指数；纯整数归 int
    if !clean.contains('.') && !clean.contains('e') && !clean.contains('E') {
        return None;
    }
    if clean.contains(':') {
        return None; // 六十进制不在子集内
    }
    clean.parse::<f64>().ok()
}

/// 本线**未复刻**但 YAML 1.1 会解析成非字符串的形态（日期 / 六十进制）。
///
/// ⚠️ **不能见冒号就拒**：明文标量里的冒号只要**后面不跟空格**就是内容本身——
/// 真源里 `inputs: [通用:M10]`、`通用:M10: untyped` 都属此列。踩过一次：
/// 一律拒含冒号的标量 ⇒ 大批模块被丢弃 ⇒ `event-backing` 凭空报缺口。
pub(crate) fn looks_out_of_subset(t: &str) -> bool {
    // 入口不 panic：正则不可用（理论上不可能）⇒ 视为「不在子集外」即落回字符串标量，
    // 与"固定合法模式永不失败"的既有语义一致，但不再用 `expect` 裸崩。
    static DATE: std::sync::OnceLock<Option<regex::Regex>> = std::sync::OnceLock::new();
    if let Some(re) = DATE
        .get_or_init(|| regex::Regex::new(r"^\d{4}-\d{2}-\d{2}([Tt ].*)?$").ok())
        .as_ref()
    {
        if re.is_match(t) {
            return true;
        }
    }
    static SEXAGESIMAL: std::sync::OnceLock<Option<regex::Regex>> = std::sync::OnceLock::new();
    SEXAGESIMAL
        .get_or_init(|| regex::Regex::new(r"^[-+]?\d+(:[0-5]?\d)+(\.\d+)?$").ok())
        .as_ref()
        .is_some_and(|sx| sx.is_match(t))
}
