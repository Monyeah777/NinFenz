"""asset_contract 私有子模块 _const：常量与词表（声明件路径 / 四面 / 语言 / 格式 / nf-io 头正则）。

门面 core.asset_contract 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import re


DECL_REL = "protocol/asset_contracts.json"

EXPORT_REL = "protocol/generated/asset_contract.frictionless.json"

SCHEMA_REL = "protocol/schema/asset_contracts.schema.json"

SCHEMA = "nf-asset-contracts/1"

FACES = ("data", "code", "script", "index")

LANGS = ("python", "bash", "vba", "powershell")

FORMATS = ("json", "csv", "markdown", "text", "yaml", "toml", "jsonl",
           "graphml", "mmd")

#: 脚本自带 I/O 契约头：Python/Bash 用 #，VBA 用单引号——同一条 nf-io: 声明格式；
#: 不锚行首：允许挂在既有注释行尾（不新增行 ⇒ 不触发 code_metrics 行数棘轮）。
_IO_RE = re.compile(r"(?:#|')[ \t]*nf-io:[ \t]*(.+?)[ \t]*$", re.M)

_MISSING = object()



#: Mermaid 图的首关键词（结构判据：只认「这是一张什么图」，不解析图内容）
_MMD_KINDS = ("graph", "flowchart", "sequenceDiagram", "classDiagram", "stateDiagram",
              "erDiagram", "gantt", "pie", "mindmap", "timeline", "journey", "gitGraph",
              "quadrantChart", "xychart-beta", "requirementDiagram", "C4Context", "block-beta")
