"""从原子表 + 节点组合生成 AI 可读的原子菜单。"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from . import atomic_io, json_asset

BASE = Path(__file__).parent
CAT = json_asset.load(BASE / "meta_atoms.json")
NODES = [json_asset.load(p) for p in sorted(BASE.glob("method_*.json"))]

pairs: dict[str, Counter] = {a["id"]: Counter() for a in CAT["atoms"]}
for n in NODES:
    for a in n["atoms"]:
        for b in n["atoms"]:
            if a != b:
                pairs[a][b] += 1

def render() -> str:
    """Render the current atom catalog and common pairings."""
    lines = [
        "# NF 元认知原子菜单（AI 可读）",
        "",
        "> 用法：先读当前 need；只选 1-3 个原子；下轮重新读 need，不要一次排完整计划。",
        "",
        "## 怎么读这一页（30 秒）",
        "",
        "- **字段**：`id 名称（元级区间）：触发条件；产出：阶段产物；常配：常见搭配原子`。",
        "- **选择纪律**：单轮 1-3 个原子；不确定就先选更靠前的那条；"
        "need 变了立刻换簇（本页**不是**固定流水线）。",
        "- **与执行器的关系**：每个原子都有确定性执行器，调用返回 "
        "status / output / error / input_digest / output_digest；"
        "未知原子与输出类型不符一律 fail-closed。",
        "- **分组口径**：五个 function 分组（知识 / 监控 / 控制 / 评价 / 整合）来自原子表的 "
        "`function` 字段；同一原子只出现在一组；末段「快速组合」是按 need 的入口示例，不是穷举。",
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
    return "\n".join(lines)


def write(path: Path = BASE / "ATOM_MENU.md") -> Path:
    atomic_io.write_text(path, render())
    return path


def main() -> int:
    target = write()
    print(f"wrote {target.name} atoms={len(CAT['atoms'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
