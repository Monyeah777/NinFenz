//! XML 子集解析实现：DTD 防护 / 解析器主体 / 实体解码 / 属性解析。

use super::*;

/// 真源 `_xml_guard`：拒 DTD/ENTITY 声明（堵实体展开 / 十亿笑声类攻击）。
pub fn dtd_guard(text: &str) -> String {
    // `re.compile(r"<!\s*(?:DOCTYPE|ENTITY)", re.I)`
    let lower = text.to_lowercase();
    let bytes: Vec<char> = lower.chars().collect();
    let mut i = 0;
    while i + 1 < bytes.len() {
        if bytes[i] == '<' && bytes[i + 1] == '!' {
            let mut j = i + 2;
            while j < bytes.len() && bytes[j].is_whitespace() {
                j += 1;
            }
            let rest: String = bytes[j..].iter().take(7).collect();
            if rest.starts_with("doctype") || rest.starts_with("entity") {
                return "含 DTD/ENTITY 声明（本仓 XML 产出面禁 DTD：堵实体展开类攻击）".to_string();
            }
        }
        i += 1;
    }
    String::new()
}

/// 真源 `ET.fromstring` 的对应物：解析成树；不良构 → `Err`（**文本与 CPython 不可比**）。
pub fn parse(text: &str) -> Result<XNode, String> {
    let chars: Vec<char> = text.chars().collect();
    let mut i = 0usize;
    let mut stack: Vec<XNode> = Vec::new();
    let mut root: Option<XNode> = None;
    // ⚠️ 判「根之前/之后有内容」要看**根的开始标签是否出现过**，**不能**用 `root.is_none()`：
    // 根元素是在**结束标签**处才赋值的，用它判会把文档中途的所有叶子文本（`P40`、`directed`…）
    // 全误判成"根之前的内容"。实测（2026-10-04）：105 份真 GraphML 因此**全部**解析失败。
    let mut started = false;
    let mut root_closed = false;

    while i < chars.len() {
        if chars[i] != '<' {
            text_segment(&chars, &mut i, started, root_closed)?;
            continue;
        }
        // 注释 / 声明 / CDATA
        // 注释 / 声明 / CDATA
        if skip_meta(&chars, &mut i)? {
            continue;
        }
        // 结束标签
        // 结束标签
        if chars[i..].starts_with(&['<', '/']) {
            end_tag(&chars, &mut i, &mut stack, &mut root, &mut root_closed)?;
            continue;
        }
        // 开始标签
        let mut j = i + 1;
        let mut quote: Option<char> = None;
        while j < chars.len() {
            let c = chars[j];
            match quote {
                Some(q) => {
                    if c == q {
                        quote = None;
                    }
                }
                None => {
                    if c == '"' || c == '\'' {
                        quote = Some(c);
                    } else if c == '>' {
                        break;
                    }
                }
            }
            j += 1;
        }
        if j >= chars.len() {
            return Err("开始标签未闭合".to_string());
        }
        let raw: String = chars[i + 1..j].iter().collect();
        let raw = raw.trim().to_string();
        let self_closing = raw.ends_with('/');
        let raw = if self_closing {
            raw[..raw.len() - 1].trim().to_string()
        } else {
            raw
        };
        let (tag, attr_str) = match raw.find(char::is_whitespace) {
            Some(k) => (raw[..k].to_string(), raw[k..].to_string()),
            None => (raw.clone(), String::new()),
        };
        if tag.is_empty() {
            return Err("空标签名".to_string());
        }
        let attrs = parse_attrs(&attr_str)?;
        started = true;
        let node = XNode {
            tag,
            attrs,
            children: Vec::new(),
        };
        if self_closing {
            match stack.last_mut() {
                Some(parent) => parent.children.push(node),
                None => {
                    if root.is_some() {
                        return Err("多个根元素".to_string());
                    }
                    started = true;
                    root = Some(node);
                    root_closed = true;
                }
            }
        } else {
            stack.push(node);
        }
        i = j + 1;
    }
    if !stack.is_empty() {
        return Err(format!("标签未闭合：<{}>", stack.last().unwrap().tag));
    }
    root.ok_or_else(|| "空文档".to_string())
}

/// 纯文本段：判「根之前 / 之后有内容」，并把游标前移到下一个标记。
pub(crate) fn text_segment(chars: &[char], i: &mut usize, started: bool, root_closed: bool) -> Result<(), String> {
    let start = *i;
    while *i < chars.len() && chars[*i] != '<' {
        *i += 1;
    }
    let seg: String = chars[start..*i].iter().collect();
    if !seg.trim().is_empty() {
        if !started {
            return Err("内容出现在根元素之前".to_string());
        }
        if root_closed {
            return Err("内容出现在根元素之后".to_string());
        }
    }
    Ok(())
}

/// 跳过注释 / 处理指令 / CDATA 段；返回 true 表示已跳过一段。
pub(crate) fn skip_meta(chars: &[char], i: &mut usize) -> Result<bool, String> {
        if chars[*i..].starts_with(&['<', '!', '-', '-']) {
            let mut j = *i + 4;
            while j + 2 < chars.len() && !chars[j..].starts_with(&['-', '-', '>']) {
                j += 1;
            }
            if j + 2 >= chars.len() {
                return Err("注释未闭合".to_string());
            }
            *i = j + 3;
            return Ok(true);
        }
        if chars[*i..].starts_with(&['<', '?']) {
            let mut j = *i + 2;
            while j + 1 < chars.len() && !chars[j..].starts_with(&['?', '>']) {
                j += 1;
            }
            if j + 1 >= chars.len() {
                return Err("处理指令未闭合".to_string());
            }
            *i = j + 2;
            return Ok(true);
        }
        if chars[*i..].starts_with(&['<', '!', '[', 'C', 'D']) {
            let mut j = *i + 9;
            while j + 2 < chars.len() && !chars[j..].starts_with(&[']', ']', '>']) {
                j += 1;
            }
            if j + 2 >= chars.len() {
                return Err("CDATA 未闭合".to_string());
            }
            *i = j + 3;
            return Ok(true);
        }
    Ok(false)
}

/// 解析结束标签：标签匹配、挂到父节点或收根；游标前移。
pub(crate) fn end_tag(
    chars: &[char],
    i: &mut usize,
    stack: &mut Vec<XNode>,
    root: &mut Option<XNode>,
    root_closed: &mut bool,
) -> Result<(), String> {
    let mut j = *i + 2;
    while j < chars.len() && chars[j] != '>' {
        j += 1;
    }
    if j >= chars.len() {
        return Err("结束标签未闭合".to_string());
    }
    let name: String = chars[*i + 2..j].iter().collect();
    let name = name.trim().to_string();
    match stack.pop() {
        None => return Err(format!("多余的结束标签 </{}>", name)),
        Some(node) => {
            if node.tag != name {
                return Err(format!("标签不匹配：<{}> 对 </{}>", node.tag, name));
            }
            match stack.last_mut() {
                Some(parent) => parent.children.push(node),
                None => {
                    *root = Some(node);
                    *root_closed = true;
                }
            }
        }
    }
    *i = j + 1;
    Ok(())
}

/// 真源 XML 的实体解码：五个预定义实体 + 数字字符引用（`&#NN;` / `&#xHH;`）。
///
/// 其余命名实体按真源语义**拒**（未定义实体 = ParseError）；字符串里没有 `&` 时零拷贝短路。
pub(crate) fn decode_entities(s: &str) -> Result<String, String> {
    if !s.contains('&') {
        return Ok(s.to_string());
    }
    let chars: Vec<char> = s.chars().collect();
    let mut out = String::new();
    let mut i = 0usize;
    while i < chars.len() {
        if chars[i] != '&' {
            out.push(chars[i]);
            i += 1;
            continue;
        }
        let j = match chars[i..].iter().position(|c| *c == ';') {
            Some(k) => i + k,
            None => return Err(format!("实体未闭合：{}", s)),
        };
        let body: String = chars[i + 1..j].iter().collect();
        let decoded = match body.as_str() {
            "amp" => '&',
            "lt" => '<',
            "gt" => '>',
            "quot" => '"',
            "apos" => '\'',
            _ => {
                let num = match body.strip_prefix('#') {
                    Some(rest) => rest,
                    None => return Err(format!("未定义实体 &{};", body)),
                };
                let hex = num.strip_prefix('x').or_else(|| num.strip_prefix('X'));
                let code = match hex {
                    Some(h) => u32::from_str_radix(h, 16),
                    None => num.parse::<u32>(),
                }
                .map_err(|_| format!("非法字符引用 &{};", body))?;
                char::from_u32(code).ok_or_else(|| format!("非法码位 &{};", body))?
            }
        };
        out.push(decoded);
        i = j + 1;
    }
    Ok(out)
}

pub(crate) fn parse_attrs(s: &str) -> Result<Vec<(String, String)>, String> {
    let chars: Vec<char> = s.chars().collect();
    let mut out: Vec<(String, String)> = Vec::new();
    let mut i = 0usize;
    while i < chars.len() {
        while i < chars.len() && chars[i].is_whitespace() {
            i += 1;
        }
        if i >= chars.len() {
            break;
        }
        let start = i;
        while i < chars.len() && chars[i] != '=' && !chars[i].is_whitespace() {
            i += 1;
        }
        let name: String = chars[start..i].iter().collect();
        if name.is_empty() {
            return Err("属性名缺失".to_string());
        }
        while i < chars.len() && chars[i].is_whitespace() {
            i += 1;
        }
        if i >= chars.len() || chars[i] != '=' {
            return Err(format!("属性 {} 缺 =", name));
        }
        i += 1;
        while i < chars.len() && chars[i].is_whitespace() {
            i += 1;
        }
        if i >= chars.len() || (chars[i] != '"' && chars[i] != '\'') {
            return Err(format!("属性 {} 的值未加引号", name));
        }
        let q = chars[i];
        i += 1;
        let vstart = i;
        while i < chars.len() && chars[i] != q {
            i += 1;
        }
        if i >= chars.len() {
            return Err(format!("属性 {} 的值未闭合", name));
        }
        // 实体解码（审计 Z1）：与真源 ElementTree 同语义，不能再把 a&amp;b 原样当值。
        let raw_value: String = chars[vstart..i].iter().collect();
        let value = decode_entities(&raw_value)?;
        i += 1;
        if out.iter().any(|(n, _)| *n == name) {
            return Err(format!("属性重复：{}", name));
        }
        out.push((name, value));
    }
    Ok(out)
}
