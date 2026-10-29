"""从原子表 + 节点组合生成 AI 可读的原子菜单。"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from . import json_asset

BASE = Path(__file__).parent
CAT = json_asset.load(BASE / "meta_atoms.json")
NODES = [json_asset.load(p) for p in sorted(BASE.glob("method_*.json"))]

pairs: dict[str, Counter] = {a["id"]: Counter() for a in CAT["atoms"]}
for n in NODES:
    for a in n["atoms"]:
        for b in n["atoms"]:
            if a != b:
                pairs[a][b] += 1

lines = [
    "# NF 元认知原子菜单（AI 可读）",
    "",
    "> 用法：先读当前 need；只选 1-3 个原子；下轮重新读 need，不要一次排完整计划。",
    "",
]
for fn, title in [
    ("knowledge", "知识"),
    ("monitoring", "监控"),
    ("control", "控制"),
    ("evaluation", "评价"),
    ("integration", "整合"),
]:
    lines += ["## " + title, ""]
    for a in [x for x in CAT["atoms"] if x["function"] == fn]:
        common = ", ".join(f"`{x}`" for x, _ in pairs[a["id"]].most_common(3))
        lines.append(
            "- `{}` {}（{}-{}）：{}；产出：{}；常配：{}".format(
                a["id"],
                a["name"],
                a["level_min"],
                a["level_max"],
                a["trigger"],
                "/".join(a["output"]),
                common or "—",
            )
        )
    lines.append("")

lines += [
    "## 快速组合（按当前 need）",
    "",
    "- understand → `k.represent`, `k.partition`, `k.define`",
    "- relate → `k.relate`, `m.trace`",
    "- challenge → `e.falsify`",
    "- resolve → `i.reconcile`",
    "- synthesize → `k.abstract`, `i.compose`",
    "- ground → `m.trace`, `e.verify`",
    "",
    "> 这些不是固定管线；need 一变就立刻换簇。",
    "",
]
(BASE / "ATOM_MENU.md").write_text("\n".join(lines), encoding="utf-8")
print(f"wrote ATOM_MENU.md atoms={len(CAT['atoms'])}")
