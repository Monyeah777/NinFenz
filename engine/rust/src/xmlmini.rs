//! XML **子集**解析器 —— 复刻真源 `output_forms` 里 `xml.etree.ElementTree` 的**用到的那一层**。
//!
//! **为什么自己写**：真源用标准库 `xml.etree`，而本线的依赖纪律不容 Python 运行时；引第三方
//! （`quick-xml` 等）又要为「只用到 4 个查询」付一整棵 API。路数同 `miniyaml`：**只支持真源
//! 用到的那一层，越出子集即 fail-closed**（不猜、不近似）。
//!
//! 本线**需要**的那一层（全部来自 `output_forms._check_xml` / `_check_graphml`）：
//!
//! | 需要 | 对应 |
//! |---|---|
//! | 良构性（标签配对 / 属性语法 / 单根） | `ET.fromstring` 的 ParseError |
//! | 根元素**局部名** | `r.tag.split("}")[-1]` |
//! | 后代里所有 `graph` | `r.findall(".//{*}graph")` |
//! | 直接子元素 `node` / `edge` | `g.findall("{*}node")` |
//! | 属性取值 | `n.get("id")` / `e.get("source")` |
//!
//! **不做**：DTD（真源在 `_xml_guard` 里**先拒**）、CDATA 的语义、命名空间解析
//! （只取局部名，与 `{*}` 通配同效）。
//!
//! **做**：XML 预定义实体与数字字符引用的解码（2026-10-10 全仓审计 §11am.2 / Z1 补）——
//! 此前不解码，而真源 `ElementTree` 会解：同一份 GraphML 里 `attr="a&amp;b"` 两边取到
//! `a&b` 与 `a&amp;b` 两个值，是**跨语言静默分叉**。

/// 一个元素节点。
#[derive(Debug, Clone)]
pub struct XNode {
    /// 原始标签名（可能带 `ns:` 前缀）。
    pub tag: String,
    pub attrs: Vec<(String, String)>,
    pub children: Vec<XNode>,
}

impl XNode {
    /// 真源 `tag.split("}")[-1]` 的等价物：取**局部名**（去 `ns:` 前缀 / `{uri}` 形式）。
    pub fn local(&self) -> &str {
        let t = self.tag.as_str();
        let t = match t.rfind('}') {
            Some(i) => &t[i + 1..],
            None => t,
        };
        match t.rfind(':') {
            Some(i) => &t[i + 1..],
            None => t,
        }
    }

    /// 真源 `e.get(k)`。
    pub fn attr(&self, k: &str) -> Option<&str> {
        self.attrs
            .iter()
            .find(|(n, _)| n == k)
            .map(|(_, v)| v.as_str())
    }

    /// 真源 `r.findall(".//{*}graph")`：**后代**（不含自身）里局部名匹配者，文档序。
    pub fn descendants(&self, name: &str) -> Vec<&XNode> {
        let mut out = Vec::new();
        for c in &self.children {
            if c.local() == name {
                out.push(c);
            }
            out.extend(c.descendants(name));
        }
        out
    }

    /// 真源 `g.findall("{*}node")`：**直接子元素**里局部名匹配者。
    pub fn children_named(&self, name: &str) -> Vec<&XNode> {
        self.children.iter().filter(|c| c.local() == name).collect()
    }
}

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
fn text_segment(chars: &[char], i: &mut usize, started: bool, root_closed: bool) -> Result<(), String> {
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
fn skip_meta(chars: &[char], i: &mut usize) -> Result<bool, String> {
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
fn end_tag(
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
fn decode_entities(s: &str) -> Result<String, String> {
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

fn parse_attrs(s: &str) -> Result<Vec<(String, String)>, String> {
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

#[cfg(test)]
mod handwritten_tests {
    use super::*;

    /// 手写判据（Z1 / §11am.2：预定义实体与数字引用）。
    /// 迁移前它被放在 GENERATED 区内，生成器重跑会覆盖；迁到生成文件外。
    #[test]
    fn predefined_and_numeric_entities_decode_like_elementtree() {
        // 审计 Z1 / §11am.2：真源 ElementTree 会解码这五个预定义实体与数字字符引用，
        // 而 xmlmini 此前原样保留 —— 同一份 GraphML 两边取到不同的属性值（跨语言静默分叉）。
        let x = r#"<g id="a&amp;b" t="&#65;&#x42;&lt;&gt;&quot;&apos;"/>"#;
        let n = parse(x).unwrap();
        assert_eq!(n.attr("id"), Some("a&b"), "预定义实体须解码");
        assert_eq!(
            n.attr("t"),
            Some("AB<>\"'"),
            "数字引用与预定义实体混用须解码"
        );
        // 非预定义命名实体：真源 ElementTree 报未定义实体 ⇒ 本线也 fail-closed。
        assert!(
            parse(r#"<g id="&foo;"/>"#).is_err(),
            "未定义实体须报错（与真源同）"
        );
        // 无 & 的常见值零拷贝短路，值不变。
        let y = parse(r#"<g id="plain"/>"#).unwrap();
        assert_eq!(y.attr("id"), Some("plain"));
    }
}

#[cfg(test)]
#[path = "generated/xmlmini_gen.rs"]
mod xmlmini_gen;
