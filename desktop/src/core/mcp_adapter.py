"""MCP server 定义导出（v2.1.0 A2：techdoc IR → MCP 资源型 server 定义）。

产物×适配矩阵第四格（27 方案）：
- SKILL（能力包）/ AGENTS（项目约定）接文本规则 IR；
- 本适配器接协议/规则类 techdoc IR → MCP server 定义 JSON（mcp.json），
  Resources 承载规则正文——MCP 官方定义 Resources = "contextual data
  attached and managed by the client"（modelcontextprotocol.io 2025-06-18
  实证），NF 协议/规则库恰是这种上下文数据。

诚实映射裁决（防造假）：MCP 的 Tools 原语需结构化 inputSchema 参数——NF
techdoc IR 模块正文是自由 markdown（协议条款/规则），无工具参数结构，硬造
Tool 会伪造 schema。本版只产 Resources 型；Tool/Prompt 留待有结构化参数源。

矩阵纪律：narrative IR 请求 mcp → 拒出（0 文件 + warnings 说明，同
skill/agents 拒出纪律）。

用法：export(ir, 'mcp', dest_dir)（exporter._REGISTRY 注册）。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .ir import IRDocument
from core import atomic_write


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", name).strip("-") or "mod"
    return s


def _resource(pid: str, layer_id: str, module) -> dict:
    """IR 模块 → MCP Resource（uri 层级编码 pipeline/layer/module）。"""
    num = str(module.full_id).split(":")[-1]
    # 唯一命名空间：layer + full_id 的密码学短哈希，防同名/同号模块撞 URI。
    ns = "%s/%s/%s" % (pid, layer_id or "extra", module.full_id)
    short = hashlib.sha256(ns.encode("utf-8")).hexdigest()[:8]
    source = str(getattr(module, "source_path", "") or module.full_id)
    return {
        "uri": f"nf://{pid}/{layer_id or 'extra'}/{_slug(module.name)}"
               f"-{num}-{short}",
        "name": f"{module.full_id} · {module.name}",
        "mimeType": "text/markdown",
        "text": module.content or "（无正文）",
        # 溯源/信任元数据：运行时据此对社区来源打 nf.trust 标注（官方来源无前缀则不标）。
        "source": source,
        "_meta": {"nf.source": source},
    }


def _build_mcp_json(ir: IRDocument) -> dict:
    """techdoc IR → MCP server 定义 dict（capabilities.resources 声明）。"""
    name = f"{ir.pipeline_id}-mcp" if ir.pipeline_id else "nf-mcp"
    resources = []
    seen = set()
    for layer in ir.layers:
        for m in layer.modules:
            item = _resource(ir.pipeline_id, layer.id, m)
            if item["uri"] in seen:
                raise ValueError("MCP 资源 uri 重复：%s（修复指引：核对模块 full_id/layer）"
                                 % item["uri"])
            seen.add(item["uri"])
            resources.append(item)
    for m in ir.extra_modules:
        item = _resource(ir.pipeline_id, m.layer, m)
        if item["uri"] in seen:
            raise ValueError("MCP 资源 uri 重复：%s（修复指引：核对模块 full_id/layer）"
                             % item["uri"])
        seen.add(item["uri"])
        resources.append(item)
    return {
        "mcp": {
            "name": name,
            "version": "0.1.0",
            "capabilities": {"resources": {}},
            "resources": resources,
        }
    }


def export_mcp(ir: IRDocument, dest_dir: Path, res) -> None:
    """MCP 适配器主体（注册进 exporter._REGISTRY['mcp']）。"""
    if ir.type != "techdoc":
        res.warnings.append(
            "MCP 出口仅接受协议/规则类装配（techdoc）——当前是 narrative 叙事类"
            "产物，请用 CCV3 / 原生 MD 导出（产物×出口适配矩阵）")
        return
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    mcp_path = dest_dir / "mcp.json"
    # 原子写（2026-09-30 收口）：交付件不留半截（MCP 客户端会在装载时读它）。
    atomic_write.write_text(mcp_path, json.dumps(_build_mcp_json(ir),
                                                 ensure_ascii=False, indent=2,
                                                 sort_keys=True))
    res.files.append(str(mcp_path))
