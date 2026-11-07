"""结构化文档原子：JSON 读取（带顶层形状校验）/ JSON Schema 校验 / YAML 安全读取。

三个动作本仓都已有**单一实现**（json_doc / json_schema / lazy_yaml），这里只做两件事：
把「坏件」折算成数据（None 或错误列表），以及把三个面收成同一组签名。**不新写解析器**。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core import json_doc, json_schema, lazy_yaml


def json_load_validated(path: Path, expect: Any = dict, what: str = "") -> Any | None:
    """读 JSON 并校**顶层形状**；不在场 / 坏 JSON / 形状不对 → None。

    「坏件」和「缺席」在原子层被有意合成同一个值（None）：两者都不是**内容**，
    要不要区分、要不要判红，是能力层的事（本仓 json_doc.load 已经给出带修复指引的报错，
    能力层需要文案时直接调它，不必经过这里）。
    """
    try:
        return json_doc.load(path, expect, what=what)
    except ValueError:
        return None


def json_schema_validate(instance: Any, schema: Any) -> list[str]:
    """→ 违规清单（空列表 = 合规）；校验器是 core.json_schema 的唯一实现。

    为什么原子不返回布尔：空/非空清单本身携带「逐字段」粒度，布尔会把它丢掉，
    调用方也就无法把「缺哪个字段」写进失败文案。
    """
    if not isinstance(schema, dict):
        raise ValueError(
            f"JSON Schema 顶层须是对象，实为 {type(schema).__name__}"
            "（修复指引：传入 schema 本体，不要传文件路径或数组）")
    return list(json_schema.json_schema_check(instance, schema, path="$"))


def yaml_load_safe(path: Path) -> Any | None:
    """安全加载 YAML；缺 PyYAML / 不在场 / 坏件 → None。

    走 lazy_yaml（本仓口径：import yaml 冷启动约 40 ms），且只用 safe_load
    （purity_scan R6 把 yaml.load 列为危险 sink）。
    """
    module = lazy_yaml.module()
    if module is None:
        return None
    text = _read(path)
    if text is None:
        return None
    try:
        return module.safe_load(text)
    except Exception:
        return None


def _read(path: Path) -> str | None:
    """读文本（独立出来是为了让 yaml_load_safe 的失败面只有一条：None）。"""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
