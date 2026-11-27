use super::*;

/// 真源 `FENCE = re.compile(r"(?ms)```yaml\s*(.*?)```")`。
///
/// 返回 `Option`：本函数是**解析入口**的一部分，M2 要求入口不得 panic——正则编译失败
/// （理论上不可能，模式是常量）就按「无该块」处理（`fence_yaml` → `None`），而不是
/// `expect` 裸崩。语义与真源「except → None」同向。
pub(crate) fn fence_re() -> Option<&'static regex::Regex> {
    static RE: std::sync::OnceLock<Option<regex::Regex>> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"(?s)```yaml\s*(.*?)```").ok())
        .as_ref()
}

// 流式映射的起始字符（与流式序列的 `[` 配对）。
pub(crate) const FLOW_MAP_OPEN: char = '{';

/// 真源 `_fence_yaml(text, marker)`：取**含 marker 的第一个** ```yaml 块并解析；
/// 未命中 / 解析失败 / 顶层不是映射 → `None`（等价于"本件无该块"）。
pub(crate) fn fence_yaml(text: &str, marker: &str) -> Option<Json> {
    let re = fence_re()?; // 入口不 panic：正则不可用 ⇒ 无该块
    for cap in re.captures_iter(text) {
        let body = cap.get(1).map(|m| m.as_str()).unwrap_or("");
        if !body.contains(marker) {
            continue;
        }
        let Ok(parsed) = parse(body) else {
            return None; // 真源此处 except → None
        };
        if matches!(parsed, Json::Object(_)) {
            return Some(parsed);
        }
        return None;
    }
    None
}

/// 解析一段 YAML 子集文本。
pub(crate) fn parse(body: &str) -> Result<Json, String> {
    let lines = meaningful_lines(body);
    if lines.is_empty() {
        return Ok(Json::Null);
    }
    let mut i = 0usize;
    let indent = lines[0].0;
    let v = parse_block(&lines, &mut i, indent)?;
    Ok(v)
}

/// `(缩进, 去尾空白的内容)`，跳过空行与整行注释；**行尾注释也剥掉**。
///
/// YAML 里 `#` 只有在**前面是空白**时才是注释开头——真源语料里
/// `host_consumed:          # 终端事件：…` 正是这种：剥掉后才是「空值 + 子块」，
/// 不剥就会被当成值 `"# 终端事件：…"`，摘要随之漂移。
pub(crate) fn meaningful_lines(body: &str) -> Vec<(usize, String)> {
    let mut out = Vec::new();
    for raw in body.lines() {
        let no_cr = raw.trim_end_matches('\r');
        let indent = no_cr.len() - no_cr.trim_start().len();
        let decomm = strip_comment(no_cr);
        let content = decomm.trim();
        if content.is_empty() || content.starts_with('#') {
            continue;
        }
        out.push((indent, content.trim_end().to_string()));
    }
    out
}

/// 剥行尾注释（引号内的 `#` 不算）。
pub(crate) fn strip_comment(line: &str) -> String {
    let chars: Vec<char> = line.chars().collect();
    let mut out = String::with_capacity(line.len());
    let mut quote: Option<char> = None;
    let mut i = 0usize;
    while i < chars.len() {
        if quote.is_some() {
            i = strip_quoted_char(&chars, i, &mut quote, &mut out);
        } else {
            i = strip_plain_char(&chars, i, &mut quote, &mut out);
        }
    }
    out
}

/// 引号内：原样拷贝；反斜杠转义 / 闭合引号各占一步。
fn strip_quoted_char(
    chars: &[char],
    i: usize,
    quote: &mut Option<char>,
    out: &mut String,
) -> usize {
    let c = chars[i];
    out.push(c);
    if c == '\\' && *quote == Some('"') && i + 1 < chars.len() {
        out.push(chars[i + 1]);
        return i + 2;
    }
    if Some(c) == *quote {
        *quote = None;
    }
    i + 1
}

/// 引号外：开引号 / 行尾注释 / 原样拷贝。
fn strip_plain_char(
    chars: &[char],
    i: usize,
    quote: &mut Option<char>,
    out: &mut String,
) -> usize {
    let c = chars[i];
    if c == '"' || c == '\'' {
        *quote = Some(c);
        out.push(c);
    } else if c == '#' && (i == 0 || chars[i - 1].is_whitespace()) {
        return chars.len();
    } else {
        out.push(c);
    }
    i + 1
}

pub(crate) fn parse_block(lines: &[(usize, String)], i: &mut usize, indent: usize) -> Result<Json, String> {
    if lines[*i].1.starts_with("- ") || lines[*i].1 == "-" {
        return parse_seq(lines, i, indent);
    }
    parse_map(lines, i, indent)
}

pub(crate) fn parse_seq(lines: &[(usize, String)], i: &mut usize, indent: usize) -> Result<Json, String> {
    let mut items = Vec::new();
    while *i < lines.len() && lines[*i].0 == indent {
        let text = lines[*i].1.clone();
        if !(text.starts_with("- ") || text == "-") {
            break;
        }
        let rest = text[1..].trim().to_string();
        *i += 1;
        items.push(parse_seq_item(lines, i, indent, &rest)?);
    }
    Ok(Json::Array(items))
}

/// 单个列表项：空项挂子块 / 流式项 / 列表内映射 / 标量。
fn parse_seq_item(
    lines: &[(usize, String)],
    i: &mut usize,
    indent: usize,
    rest: &str,
) -> Result<Json, String> {
    if rest.is_empty() {
        if *i < lines.len() && lines[*i].0 > indent {
            let child = lines[*i].0;
            return parse_block(lines, i, child);
        }
        return Ok(Json::Null);
    }
    if rest.starts_with(FLOW_MAP_OPEN) || rest.starts_with('[') {
        // ⚠️ **流式**项必须直接走 parse_inline：否则 split_key 会把 {id: C01, ...}
        // 当成"块式映射项"（键 id、值 C01, branch: compute, ...），整条节点被压成一个字符串。
        // 实测（2026-10-04）：概念图资产里节点就写成 - {id: C01, branch: compute, …}，
        // 102 份图里有 2 份（AI系统域包 / 量化金融域包）踩到这里 ⇒ 它们解析出的节点**全部**缺 id。
        return parse_inline(rest);
    }
    if let Some((k, v)) = split_key(rest) {
        // **列表项本身是映射**（真源 tool_face: 就是这个形态）。`- ` 占两列，
        // 故该项内后续键的内容列 = 列表缩进 + 2。
        let child_indent = indent + 2;
        return parse_map_with(lines, i, child_indent, Some((k, v)));
    }
    parse_inline(rest)
}

pub(crate) fn parse_map(lines: &[(usize, String)], i: &mut usize, indent: usize) -> Result<Json, String> {
    parse_map_with(lines, i, indent, None)
}

/// 映射解析；`first` 用于「首对键值已在手」（列表项映射的首行已被 `- ` 消费掉）。
pub(crate) fn parse_map_with(
    lines: &[(usize, String)],
    i: &mut usize,
    indent: usize,
    first: Option<(String, String)>,
) -> Result<Json, String> {
    let mut pairs: Vec<(String, Json)> = Vec::new();
    let mut pending = first;
    loop {
        let (key, val) = match pending.take() {
            Some(kv) => kv,
            None => {
                if *i >= lines.len() || lines[*i].0 != indent {
                    break;
                }
                let text = lines[*i].1.clone();
                if text.starts_with("- ") {
                    break;
                }
                let Some(kv) = split_key(&text) else {
                    return Err(format!("越出子集：不是键值行：{}", text));
                };
                *i += 1;
                kv
            }
        };
        let value = if val.is_empty() {
            if *i < lines.len() && lines[*i].0 > indent {
                let child = lines[*i].0;
                parse_block(lines, i, child)?
            } else {
                Json::Null
            }
        } else {
            parse_inline(&val)?
        };
        // **同键覆盖**：PyYAML / Python dict 都是后者胜——保留第一条会让摘要在重复键上分叉
        match pairs.iter_mut().find(|(k, _)| *k == key) {
            Some(slot) => slot.1 = value,
            None => pairs.push((key, value)),
        }
    }
    Ok(Json::Object(pairs))
}

/// 找键值分隔点：**第一个「冒号+空格」**，或行尾冒号。
/// （YAML 明文标量里的冒号只要后不跟空格就属内容——真源里 `通用:M10: untyped` 正是这种。）
pub(crate) fn find_key_sep(s: &str) -> Option<usize> {
    if let Some(p) = s.find(": ") {
        return Some(p);
    }
    if s.ends_with(':') && !s.ends_with(": ") {
        return Some(s.len() - 1);
    }
    None
}

pub(crate) fn split_key(line: &str) -> Option<(String, String)> {
    let p = find_key_sep(line)?;
    let key = line[..p].trim().to_string();
    let val = line[p + 1..].trim().to_string();
    Some((key, val))
}

/// 流式映射项的分隔点：**第一个「冒号 + 空白/流指示符/串尾」**。
///
/// 与块式 `find_key_sep` 同一条道理——`AI保险:M01` 里的冒号后面跟的是字母，属内容。
pub(crate) fn split_inline_pair(s: &str) -> Option<(&str, &str)> {
    let b = s.as_bytes();
    let mut quote: Option<u8> = None;
    let mut i = 0usize;
    while i < b.len() {
        let c = b[i];
        match quote {
            Some(q) => {
                if c == b'\\' && q == b'"' {
                    i += 2;
                    continue;
                }
                if c == q {
                    quote = None;
                }
            }
            None => {
                if c == b'"' || c == b'\'' {
                    quote = Some(c);
                } else if c == b':' {
                    let next = b.get(i + 1).copied();
                    let is_sep = matches!(
                        next,
                        None | Some(b' ') | Some(b',') | Some(b'}') | Some(b']')
                    );
                    if is_sep {
                        return Some((&s[..i], &s[i + 1..]));
                    }
                }
            }
        }
        i += 1;
    }
    None
}
