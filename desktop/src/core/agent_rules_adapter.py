"""AGENTS.md / CLAUDE.md 出口适配器（v2.1.0 A1：techdoc + project_rules → 项目约定）。

产物×适配矩阵第三格（25 方案）：
- SKILL（18 方案）接 techdoc IR 的「能力语义」（可复用任务流程）→ SKILL.md；
- 本适配器接 techdoc IR 的「项目约定语义」（classify_doc_semantics ==
  project_rules：绑定本仓库的构建/测试/提交纪律/目录规则）→ AGENTS.md /
  CLAUDE.md——读者需「常驻知道」，agent 进 repo 自动加载（两判据裁决的
  AGENTS 侧）。
- narrative IR / 能力语义 techdoc 请求 agents → 拒出（0 文件 + warnings
  说明，语义错配防混，同 skill 拒 narrative 纪律）；能力语义请走 skill。

格式锚点：AGENTS.md / CLAUDE.md = 仓库级 agent 工作规则 Markdown（顶层章节
按 IR 层/模块组织，正文消费 IR 模块内容——同 CCV3/SKILL 共用 IR 真源）。

用法：export(ir, 'agents', dest_dir) / export(ir, 'claude', dest_dir)
（exporter._REGISTRY 注册）。
"""
from __future__ import annotations

import re
from pathlib import Path

from .ir import IRDocument
from .semantics import classify_doc_semantics, PROJECT_RULES
from core import atomic_write


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", name).strip("-") or "rules"
    return s.lower()


def _agents_parts(ir: IRDocument):
    """project_rules IR → AGENTS.md 片段流（顶层不拼整篇）。"""
    yield "# Agent Operating Rules"
    yield ""
    for layer in ir.layers:
        yield f"## {layer.name or layer.id}"
        for m in layer.modules:
            yield f"### {m.full_id} · {m.name}"
            yield m.content or "（无正文）"
    if ir.extra_modules:
        yield "## 附加规则"
        for m in ir.extra_modules:
            yield f"### {m.full_id} · {m.name}"
            yield m.content or "（无正文）"
    if ir.asset_refs:
        yield "## 资产引用"
        for k, v in ir.asset_refs.items():
            if v is None:
                continue
            yield f"### {k}\n\n{v}"


def _append_once(values, value: str) -> None:
    if value not in values:
        values.append(value)


def export_agents(ir: IRDocument, dest_dir: Path, res) -> None:
    """AGENTS 适配器主体（注册进 exporter._REGISTRY['agents']）。"""
    if classify_doc_semantics(ir) != PROJECT_RULES:
        res.warnings.append(
            "AGENTS 出口仅接受项目约定语义（project_rules）——当前装配为"
            "能力/叙事语义，请用 SKILL / CCV3 / 原生 MD 导出（产物×适配矩阵："
            "AGENTS=项目常驻约定，SKILL=可复用能力包）")
        return
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    agents_path = dest_dir / "AGENTS.md"
    atomic_write.write_lines(agents_path, _agents_parts(ir), separator="\n\n")
    _append_once(res.files, str(agents_path))


def export_claude(ir: IRDocument, dest_dir: Path, res) -> None:
    """CLAUDE.md 变体（同裁决：project_rules 才接；内容同 AGENTS，Claude 入口）。"""
    if classify_doc_semantics(ir) != PROJECT_RULES:
        res.warnings.append(
            "CLAUDE 出口仅接受项目约定语义（project_rules）——当前装配为"
            "能力/叙事语义，请用 SKILL / CCV3 / 原生 MD 导出")
        return
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    claude_path = dest_dir / "CLAUDE.md"
    atomic_write.write_lines(claude_path, _agents_parts(ir), separator="\n\n")
    _append_once(res.files, str(claude_path))
