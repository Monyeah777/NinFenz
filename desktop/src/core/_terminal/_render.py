"""terminal · _render（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from ._catalog import (
    families_for,
    families_without_zone,
    zone_by_key,
    zones_of_family,
)
from ._const import (
    SHELL_VERSION,
)
from ._forms import (
    zone_action_dicts,
)
from ._parse import (
    did_you_mean,
    search,
)
from ._tables import (
    FAMILIES,
    ZONES,
)
from ._ui import (
    _row,
    clip,
    style,
    term_width,
)


def banner(baseline: str = "", color: bool = False) -> str:
    """终端开场横幅：版本 + 基线 + 最快上手路径（无时间戳 → 可逐字节复现）。"""
    lines = ["NinFenz 终端 v%s（端壳退役后的人机入口；命令真源 = nf CLI）"
             % SHELL_VERSION]
    if baseline:
        lines.append("  基线：%s" % baseline)
    lines += [
        "  数字 0-7 看能力菜单 · /map 能力地图 · /find <词> 检索 · /commands 列全部 · quit 退出",
        "  任意 nf 命令可直接直通（例：nf doctor / nf market --list）；行尾 \\ 可续行",
        "  写入类命令（--write/--apply/--register…）须二次确认，终端不替你拍板",
    ]
    lines[0] = style(lines[0], "head", color)
    return "\n".join(lines)




def menu(width=None, color: bool = False) -> str:
    """渲染能力菜单（人读表 + 可执行示例入口）。"""
    w = term_width(width)
    lines = [style("== NF 能力菜单（%d 区 → CLI 命令面）==" % len(ZONES), "head", color), ""]
    for item in ZONES:
        # 键固定 1 显示宽度（0-9），故不补宽——保持 `[0] 标题 —— 摘要` 的既有格式契约
        left = style("[%s]" % item["key"], "cmd", color)
        lines.append("%s %s —— %s"
                     % (left, item["title"], clip(item["summary"], max(20, w - 30))))
    lines += ["",
              "看某区示例：输入编号（如 4）或 /zone 4；执行：把示例里的命令打进终端。"]
    rest = families_without_zone()
    if rest:
        lines.append("  本菜单是**任务路径**（%d 区）；完整面见 /map（%d 族）。"
                     "未在此列的族：%s（在那几族里用 /find <词> 或 /commands 定位）"
                     % (len(ZONES), len(FAMILIES), "、".join(rest)))
    return "\n".join(lines)




def zone_detail(key: str, color: bool = False) -> str:
    """渲染单个能力区的示例命令（未命中键 → 给可用键清单，不抛栈）。"""
    item = zone_by_key(key)
    if item is None:
        return ("未识别的菜单键「%s」（可用键：%s；示例：输入 0 看环境自检）"
                % (key, "、".join(z["key"] for z in ZONES)))
    lines = [style("== [%s] %s ==" % (item["key"], item["title"]), "head", color),
             "  %s" % item["summary"]]
    if item.get("examples"):
        lines.append("  示例命令（复制即用）：")
        lines += ["    " + style(ex, "cmd", color) for ex in item["examples"]]
    else:
        # 无示例的区（表单区）：列它投影出的动作——行模式用 `/form <id>` 逐项追问
        lines.append("  本区动作（`/form <id>` 逐项追问，或在全屏视图里回车运行）：")
        lines += ["    " + style("/form %s" % act["key"], "cmd", color) + "  —— %s"
                  % act["title"] for act in zone_action_dicts(item)]
    return "\n".join(lines)




def render_search(index, query: str, limit: int = 8, width=None,
                  color: bool = False) -> tuple:
    """渲染检索结果 → (文本, 命中数)。未命中给确定性的下一步指引，不空手而归。"""
    hits = search(index, query, limit=limit)
    if not hits:
        near = did_you_mean(query, [str(e.get("path")).split(" ")[0] for e in index or []])
        tip = ("；你是不是想找：%s" % "、".join(near)) if near else ""
        return ("未命中命令：「%s」%s\n  （用 /commands 列全部命令面；或用 nf --help 看总览）"
                % (query, tip), 0)
    w = term_width(width)
    lines = [style("== 命令检索：「%s」（%d 命中）==" % (query, len(hits)), "head", color)]
    for _score, e in hits:
        lines.append(_row("nf " + str(e.get("path")), str(e.get("summary") or ""), w,
                          color, hl=query))
    lines.append("  用法：直接输入 `nf <命令> …`；二级见 `nf <命令> --help`")
    return "\n".join(lines), len(hits)




def render_commands(index, filt: str = "", limit: int = 0, width=None,
                     color: bool = False) -> str:
    """列出全部可达命令（可按子串过滤）——把「最全功能」摊开成一张可检视的表。"""
    f = str(filt or "").strip().lower()
    rows = _filtered_rows(index, f)
    tops = {str(e.get("path")).split(" ")[0] for e in index or []}
    w = term_width(width)
    lines = [style("== nf 命令面（顶层 %d · 含二级 %d 条%s）=="
                   % (len(tops), len(rows), ("，过滤：%s" % filt) if f else ""),
                   "head", color)]
    shown = _shown_rows(rows, limit)
    for e in shown:
        lines.append(_row("nf " + str(e.get("path")), str(e.get("summary") or ""), w, color))
    if len(shown) < len(rows):
        lines.append(style("  … 还有 %d 条（--limit 0 看全部，或加过滤词收敛）"
                           % (len(rows) - len(shown)), "dim", color))
    lines.append("  检索：/find <词>（或 nf shell --search <词>）；菜单：/menu")
    return "\n".join(lines)


def _filtered_rows(index, f: str) -> list:
    """按过滤词收窄并排序的命令行。"""
    return sorted((e for e in index or []
                   if not f or f in str(e.get("path")).lower()
                   or f in str(e.get("summary") or "").lower()),
                  key=lambda e: str(e.get("path")))


def _shown_rows(rows, limit) -> list:
    """limit=0/未给 → 全量；否则取前 limit 条。"""
    return rows if not limit or int(limit) <= 0 else rows[:int(limit)]




def render_map(filt: str = "", width=None, color: bool = False) -> str:
    """渲染能力地图（全功能分面）：每族给一句话定位 + 该族命令清单。"""
    w = term_width(width)
    lines = [style("== NF 能力地图（%d 族 · 覆盖 CLI 全部顶层命令）==" % len(FAMILIES),
                   "head", color)]
    for fam in families_for(filt):
        cmds = list(fam["commands"])
        lines.append("")
        _zones = zones_of_family(fam["id"])
        lines.append("%s %s —— %s%s"
                     % (style("[%s]" % fam["id"], "cmd", color), fam["name"],
                        clip(fam["summary"], max(20, w - 34)),
                        ("　（菜单快捷区：%s）" % "、".join(_zones)) if _zones
                        else "　（菜单无快捷区——用 /find <词> 或 /commands 定位）"))
        lines.append("    " + style(" · ".join("nf %s" % c for c in cmds), "dim", color))
    lines.append("")
    lines.append("  单族用法：/map <族名或命令片段>；命令详情：/find <词>；逐条列出：/commands")
    return "\n".join(lines)
