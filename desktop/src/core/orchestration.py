"""智能体工具编排（agent tool orchestration）：工作流 → **可机检的编排计划** → 确定性序 → fail-closed 派发。

内部差距（2026-10-03 实证，逐条可核）：
- `protocol/driver.json` 的工作流只声明**工具集合**（`mcp_tools`）：**顺序 / 先后件 / 每步证据**
  只存在于 fallback 文档的散文里 ⇒ 同一工作流两次执行可以不同序，而这正是该文件
  `fail_closed.why` 点名要防的「产物不可复现」；且没有任何判据能看见它。
- `driver.resolve()` 自己写着「只读；不实际派发」⇒ 机器面路由到**工具名**为止，编排靠执行者自觉。
- MCP 工具面的 `inputSchema` 已声明必填参数，却没有判据管「计划里少传必填」「引用了不存在的
  上游」「依赖成环」这三类**编排错误**。

本模块把「编排」做成三件可证的事（零第三方依赖、不自己起进程、不发网络）：

1. `catalog(root)` —— 能力目录，**派生自两个活真源、不手抄**：工具面取
   `mcp_runtime.TOOL_DEFS`（名字 / 说明 / 必填 / 属性 / 是否封闭），工作流面取 `driver.json`。
2. `compile_plan(root, plan)` —— 校验并**编译**一份编排计划 → 确定性拓扑序 + 问题清单。
   判据：schema 词表 / 工作流在册 / 工具在本工作流的映射集内 / 工具在运行时在册 / 步 id 唯一
   / `needs` 引用存在且**无环** / `args` 满足 `inputSchema`（必填、类型、封闭性）/
   `$<步>.<字段>` 引用必须落在该步 `needs` 的**传递闭包**里（隐式依赖 = FAIL）。
3. `dispatch(order, steps, call)` —— 按编译出的序逐步调用**注入的** `call(tool, args)`：
   首个失败即停（fail-closed），如实报「已执行 / 停在哪 / 未执行」——调用方决定怎么连 MCP。
   每步可声明 `expects`（该步必须产出的字段）：派发时即验，证据不齐同样即停——「完成了」
   不是证据，产物字段才是。

**依赖方向（叶子纪律）**：本模块**不 import 工具面**——运行时工具面由调用方注入
（`catalog(root, tools)` / `compile_plan(root, plan, tools)` / `scan(root, tools)` 的 `tools`）。
理由是可证的：2026-10-03 实测，本模块 import `mcp_runtime` 会让它的 Ca 5→6、I 0.5→0.4545，
**直接造出两条 SDP 违例**（`mcp_runtime → knowledge` / `→ trust_boundary`）。生产侧由
`core.driver` 注入（它本来就是 `mcp_runtime` 的依赖方），命令行入口见
`scripts/orchestrate.py`（在 core 之外，不参与包内耦合度量）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import json_doc

# 实现分片：原模块逻辑在私有子包 _orchestration/，本门面按原模块面显式再导出（API 不变）。
from core._orchestration._part1 import (
    _CIRCUIT,
    _REF,
    _STEP_ID,
    _TYPES,
    DRIVER_REL,
    PLAN_GUIDE,
    SCHEMA,
    DispatchOptions,
    _args_issues,
    _circuit_blocked,
    _circuit_record,
    _closure,
    _needs_issues,
    _skip_remaining,
    _step_ids_issues,
    _tool_issues,
    _topo,
    _type_issue,
    catalog,
    compile_plan,
    workflow_tools,
)
from core._orchestration._part2 import _sample_args, dispatch, scan

# 读点：契约 JSON 解析一律走 core.json_doc.loads / core.json_doc.load（N11）；实现分片见同目录私有子包。
