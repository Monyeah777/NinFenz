"""terminal · _catalog（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from ._tables import (
    FAMILIES,
    ZONES,
)


def zone_table() -> tuple:
    """返回能力菜单真源（终端渲染、check39 与文档共用同一份数据，不留第二份）。"""
    return ZONES




def zone_by_key(key: str):
    """按菜单键取条目；未命中返回 None（调用方给修复指引，不抛栈）。"""
    for item in ZONES:
        if item["key"] == str(key).strip():
            return item
    return None




def family_table() -> tuple:
    """能力地图真源（终端渲染、`--map`、自检与 check39 共用同一份）。"""
    return FAMILIES




def family_of(cmd: str):
    """某命令所属族；未登记返回 None（自检会把它判成策展缺口）。"""
    name = str(cmd).strip()
    for fam in FAMILIES:
        if name in fam["commands"]:
            return fam
    return None




def families_for(filt: str = "") -> list:
    """按过滤词取能力族（渲染与 `--map --json` 共用同一判据，免得两处漂移）。"""
    f = str(filt or "").strip().lower()
    out = []
    for fam in FAMILIES:
        if not f or f in str(fam["id"]).lower() or f in str(fam["name"]).lower() \
                or any(f in c for c in fam["commands"]):
            out.append(fam)
    return out




def zones_of_family(fid: str) -> list:
    """哪些菜单区指向该族（菜单 = 任务路径，族 = 完整面；互标让两者可对照）。"""
    return [str(z["key"]) for z in ZONES if str(z.get("family")) == str(fid)]




def families_without_zone() -> list:
    """没被任何菜单区指向的族（不是缺陷：菜单只是快捷路径，但它们该被**显式**告知）。"""
    used = {str(z.get("family")) for z in ZONES}
    return [str(f["id"]) for f in FAMILIES if str(f["id"]) not in used]
