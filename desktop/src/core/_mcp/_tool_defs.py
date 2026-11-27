"""mcp_runtime · _tool_defs（自 mcp_runtime.py 拆出的只读工具 schema 数据段）。"""
from __future__ import annotations

from ._tool_defs_a import TOOL_DEFS_PART_A
from ._tool_defs_b import TOOL_DEFS_PART_B

TOOL_DEFS = TOOL_DEFS_PART_A + TOOL_DEFS_PART_B


PROMPT_DEFS = [
    {
        "name": "assemble_guide",
        "description": "NF 世界装配引导（作者/agent 五分钟上手 + 取件顺序）。",
    },
]
