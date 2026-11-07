"""Task-native production projection from a completed cockpit state."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from . import task_profile

SECTION_TITLES = {
    "objects": "对象",
    "tradeoff": "取舍与代价",
    "decision_rule": "决策规则",
    "symptom": "症状",
    "mechanism": "机制",
    "confounder": "混淆因素",
    "components": "组成部分",
    "interactions": "相互作用",
    "failure_path": "失败路径",
    "verification": "验证",
    "criteria": "判据",
    "checks": "检查与裁决",
    "findings": "发现",
    "example": "示例",
    "boundary": "边界",
    "options": "选项",
    "recommendation": "建议",
    "constraints": "约束",
    "coherence": "一致性",
    "revision": "修订",
    "evidence": "证据",
    "synthesis": "综合",
}


def _value(state: dict, key: str):
    artifact = state.get("artifact", {})
    return artifact.get(key, state.get(key))


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def project(state: dict) -> dict:
    profile = task_profile.build(state.get("goal", ""))
    agenda = task_profile.build_facet_agenda(state, profile)
    status = {item["facet"]: item for item in agenda["items"]}
    sections = []
    for facet in profile["required_facets"]:
        item = status[facet]
        keys = []
        for witness in item["witnesses"]:
            for key in witness["keys"]:
                if key not in keys:
                    keys.append(key)
        values = {}
        for key in keys:
            value = _value(state, key)
            if value not in (None, ""):
                values[key] = value
        sections.append(
            {
                "id": facet,
                "title": SECTION_TITLES.get(facet, facet),
                "status": item["status"],
                "source_keys": keys,
                "values": values,
            }
        )
    result = {
        "schema": "nf-task-handoff/1",
        "primary": profile["primary"],
        "modes": profile["modes"],
        "sections": sections,
        "gaps": [item["id"] for item in sections if item["status"] == "open"],
        "no_scoring": True,
    }
    result["digest"] = hashlib.sha256(_canonical(result)).hexdigest()
    return result


def render_markdown(projection: dict) -> str:
    lines = [
        "## 任务原生视图",
        "",
        "> modes：{}".format(" / ".join(projection["modes"])),
        "",
    ]
    for section in projection["sections"]:
        lines.append("### {} · {} [{}]".format(section["title"], section["id"], section["status"]))
        lines.append("")
        if not section["values"]:
            lines.append("- 暂无")
        else:
            for key, value in section["values"].items():
                lines.append(f"- `{key}`: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
        lines.append("")
    return "\n".join(lines).rstrip()
