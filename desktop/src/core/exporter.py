"""导出层 exporter（v2.0.0 T2：格式注册表 + CCV3 JSON/PNG 封装，2.0 E1）。

- export(ir, fmt='ccv3', dest_dir) -> ExportResult：经适配器注册表把 IR 导出
  为外部标准格式。CCV3 为第一适配器（默认首发出口）。
- CCV3 双产物：chara.json（chara_card_v3 dict，内嵌 character_book 世界书——
  SillyTavern 卡内嵌书）+ world.json（独立世界书，供 .world/世界书导入）。
- write_png_card：单卡 PNG（QImage tEXt 'chara' 键，base64 JSON）——CCV3 PNG
  分发形态；PySide6 QImage 零新依赖（探针实证写读回 match）。
- 未启用适配器不出厂（范围纪律）：_REGISTRY 只挂已交付适配器。

格式扩展（v2.0.x）：AGENTS/SKILL/MCP 适配器实现后注册进 _REGISTRY，各带
目标格式版本锚点——export() 不改，只加注册表项。
"""
from __future__ import annotations

import base64
import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .ir import IRDocument, iter_md
from core import atomic_write
from .import_adapter import parse_ccv3, parse_skill

if TYPE_CHECKING:          # 静态引用（dead-code 判据可见），运行时按需 import
    from .ccv3_adapter import map_ir_to_ccv3, world_entries  # noqa: F401
    from .skill_adapter import export_skill  # noqa: F401
    from .agent_rules_adapter import export_agents, export_claude  # noqa: F401
    from .mcp_adapter import export_mcp  # noqa: F401
    from .mvu_adapter import export_mvu  # noqa: F401


def _lazy(module: str, func: str) -> Callable[..., Any]:
    """按需导入适配器（微内核注册表：新增出口不改本文件的分派逻辑）。"""
    def call(*args: Any, **kwargs: Any) -> Any:
        mod = importlib.import_module(module, __package__)
        return getattr(mod, func)(*args, **kwargs)
    call.__name__ = func
    return call


@dataclass
class ExportResult:
    fmt: str
    files: List[str] = field(default_factory=list)   # 产出文件绝对路径
    warnings: List[str] = field(default_factory=list)


# ------------------------------------------------------------------ 适配器
def _export_ccv3(ir: IRDocument, dest_dir: Path, res: ExportResult) -> None:
    from .ccv3_adapter import map_ir_to_ccv3, world_entries
    chara = map_ir_to_ccv3(ir)
    world: Dict[str, Any] = {
        "name": f"{ir.title} · 世界书",
        "entries": world_entries(ir),
    }
    dest_dir.mkdir(parents=True, exist_ok=True)
    chara_path = dest_dir / "chara.json"
    world_path = dest_dir / "world.json"
    # 原子写（2026-09-30 收口）：交付件不留半截（半截 JSON 会被消费方读成「卡损坏」）。
    atomic_write.write_text(chara_path, json.dumps(chara, ensure_ascii=False, indent=2))
    atomic_write.write_text(world_path, json.dumps(world, ensure_ascii=False, indent=2))
    res.files.extend([str(chara_path), str(world_path)])
    # 未映射检查（映射不静默丢弃不变量）：IR 叙事层模块应全部进 world
    narrative = [m.full_id for l in ir.layers if l.id not in ("P00", "P80")
                 for m in l.modules]
    mapped = {k for e in world["entries"] for k in (e.get("keys") or [])}
    unmapped = [f for f in narrative if f not in mapped
                and f not in "".join(mapped)]
    if unmapped:
        res.warnings.append("以下叙事模块未入 world 条目（映射缺口）："
                            + "、".join(unmapped))


def _export_md(ir: IRDocument, dest_dir: Path, res: ExportResult) -> None:
    """IR → 原生 Markdown（顶层核心出口；流式原子写）。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "document.md"
    atomic_write.write_lines(path, iter_md(ir))
    if str(path) not in res.files:
        res.files.append(str(path))


_REGISTRY = {
    "md": _export_md,
    "mvu": _lazy(".mvu_adapter", "export_mvu"),
    "ccv3": _export_ccv3,
    "skill": _lazy(".skill_adapter", "export_skill"),
    "agents": _lazy(".agent_rules_adapter", "export_agents"),
    "claude": _lazy(".agent_rules_adapter", "export_claude"),
    "mcp": _lazy(".mcp_adapter", "export_mcp"),
}

# 读入反向符号登记（v2.3.0 34 方案：A4 双向读入——外部→NF 反向解析层）。
# 与上方 export-only 五出口对称：格式 → 解析函数。范围纪律（未启用不出厂）：
# 只挂已交付的 skill/ccv3 两格——agents/claude/mcp 暂无读入适配器，不登记，
# 防止消费方误以为可 round-trip 未交付格式。
_REGISTRY_IN = {
    "skill": parse_skill,
    "ccv3": parse_ccv3,
}


# ------------------------------------------------------------------ 入口
def export(ir: IRDocument, fmt: str = "ccv3",
           dest_dir: Optional[str | Path] = None) -> ExportResult:
    """经适配器注册表导出 IR 为外部格式。fmt 未注册 → KeyError。"""
    if fmt not in _REGISTRY:
        raise KeyError(f"未注册的导出格式：{fmt}（已注册：{sorted(_REGISTRY)}）")
    dest = Path(dest_dir) if dest_dir else Path.cwd()
    res = ExportResult(fmt=fmt)
    _REGISTRY[fmt](ir, dest, res)
    return res


def write_png_card(ir: IRDocument, path: Optional[str | Path] = None) -> str:
    """产单卡 PNG（tEXt 'chara' = base64 chara JSON）。返回文件路径。"""
    from .ccv3_adapter import map_ir_to_ccv3
    chara = map_ir_to_ccv3(ir)
    payload = base64.b64encode(
        json.dumps(chara, ensure_ascii=False).encode("utf-8")).decode("ascii")
    try:
        from PySide6.QtGui import QImage
    except ImportError as exc:
        raise ImportError(
            "写 PNG 卡面需要 PySide6（当前环境缺该依赖）：请先安装 PySide6 后重试，"
            "或改用 JSON 卡面导出（不依赖 Qt）") from exc
    img = QImage(512, 512, QImage.Format.Format_RGB32)
    img.fill(0xFF222233)      # 深色占位底（无卡面素材）
    img.setText("chara", payload)
    dest = Path(path) if path else Path.cwd() / "chara_card.png"
    if not dest.suffix:
        dest = dest.with_suffix(".png")
    if not img.save(str(dest)):
        raise OSError(f"PNG 写入失败：{dest}——请先检查输出目录可写/磁盘空间后重试")
    return str(dest)
