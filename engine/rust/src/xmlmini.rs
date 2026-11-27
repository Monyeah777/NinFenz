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

mod part1;

pub(crate) use part1::*;

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
