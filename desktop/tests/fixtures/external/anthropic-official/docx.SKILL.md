---
name: docx
description: "Use this skill whenever a task asks for a Word document deliverable — the phrases 'Word doc' or 'word document', a .docx path, or a request for formatted output such as a report, memo, or letter. Do not use it for spreadsheets, slide decks, or unrelated coding work."
license: NF-Test-Fixture-1.0 (self-authored for parser tolerance tests; not third-party content)
---

# DOCX creation, editing, and analysis

本件是 **NF 自写的测试夹具**，不是任何第三方技能的副本。它保留了几条真实世界 SKILL.md 的
形态特征，供 `import_adapter.parse_skill` 的**外部宽容层**判据使用：

- `description` 用双引号包裹成**单行** YAML 标量，内部含裸单引号（`'Word doc'`）与冒号；
- `description` 之后还有**扩展字段**（`license`），解析器须原样透传而不吞；
- 正文是自由说明文（非 NF 的层级结构），解析器须判 `mode == "external"` 且**不**强套层级。

## 任务的三种形态

| 任务 | 做法 |
|---|---|
| 新建文档 | 从模板派生 `word/document.xml` |
| 编辑既有文档 | 解包 → 改 XML → 重新打包 |
| 读取内容 | 直接解析 XML 各部件 |

## 验证产出

改完之后重新打开产物，核对被改的部件与预期一致。
