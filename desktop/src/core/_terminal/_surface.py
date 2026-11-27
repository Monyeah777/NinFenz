"""terminal · _surface（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import hashlib
import pprint

from core import attest

from ._const import (
    BLOCKED_IN_SHELL,
    CONFIRM_FLAG_PAIRS,
    CONFIRM_FLAGS,
    CONFIRM_VERBS,
    SURFACE_MODULE_HEAD,
    SURFACE_MODULE_PATH,
    SURFACE_SCHEMA,
    SURFACE_SOURCE,
)
from ._forms import (
    zone_action_dicts,
)
from ._tables import (
    FAMILIES,
    FORMS,
    ZONES,
)
from ._ui import (
    _row,
    style,
    term_width,
)


def _surface_params(items) -> list:
    """参数槽归一：只有这五个字段进投影（视图侧不许私加语义）。"""
    return [{"name": str(p["name"]), "label": str(p.get("label") or p["name"]),
             "kind": str(p.get("kind") or "text"),
             "required": bool(p.get("required", True))}
            for p in items or ()]




def surface_payload(commands=(), root_flags=()) -> dict:
    """终端面机器快照——**唯一**投影源，四个视图都由它派生（JSON 原生类型，可序列化）。

    各节含义：`zones` 能力菜单（含 `actions` 动作目录）/ `families` 能力族策展 /
    `forms` 写盘表单 / `gates` 写盘闸门三表（flags / verbs / pairs）/ `blocked` 会话内
    不直接执行的动词与指引 / `commands`·`root_flags` 来自 argparse 面（存在性真源）。
    `digest` 是除自身外全量的规范摘要——视图侧可用它做一次廉价对账。
    """
    zones = [{"key": str(z["key"]), "id": str(z["id"]), "title": str(z["title"]),
              "family": str(z.get("family") or ""), "summary": str(z.get("summary") or ""),
              "examples": [str(e) for e in z.get("examples") or ()],
              # `forms: True` = 本区动作由 FORMS 投影（视图据此识别表单区，不必猜 id）
              "forms": bool(z.get("forms")),
              "actions": [{"key": str(a["key"]), "title": str(a["title"]),
                           "argv": [str(t) for t in a.get("argv") or ()],
                           "params": _surface_params(a.get("params")),
                           "note": str(a.get("note") or "")}
                          for a in zone_action_dicts(z)]}
             for z in ZONES]
    families = [{"id": str(f["id"]), "name": str(f["name"]),
                 "summary": str(f.get("summary") or ""),
                 "commands": [str(c) for c in f.get("commands") or ()]}
                for f in FAMILIES]
    forms = [{"id": str(f["id"]), "title": str(f["title"]), "summary": str(f.get("summary") or ""),
              "steps": [{"key": str(s["key"]), "prompt": str(s.get("prompt") or ""),
                         "required": bool(s.get("required")),
                         "hint": str(s.get("hint") or "")}
                        for s in f.get("steps") or ()],
              "argv": [str(t) for t in f.get("argv") or ()]}
             for f in FORMS]
    payload = {
        "kind": "nf-terminal-surface",
        "schema": SURFACE_SCHEMA,
        # 拷贝一份：投影是可被调用方改写的数据，不许把模块级常量交出去当可写对象
        "source": {k: (list(v) if isinstance(v, list) else v)
                   for k, v in SURFACE_SOURCE.items()},
        "commands": sorted(str(c) for c in commands or ()),
        "root_flags": sorted(str(f) for f in root_flags or ()),
        "zones": zones,
        "families": families,
        "forms": forms,
        "gates": {"flags": [str(x) for x in CONFIRM_FLAGS],
                  "verbs": [[str(a), str(b)] for a, b in CONFIRM_VERBS],
                  "pairs": [[str(a), str(b)] for a, b in CONFIRM_FLAG_PAIRS]},
        "blocked": {str(k): str(v) for k, v in sorted(BLOCKED_IN_SHELL.items())},
    }
    payload["digest"] = surface_digest(payload)
    return payload




def surface_digest(payload) -> str:
    """投影内容摘要（除 `digest` 自身外全量；键序归一，故与构造顺序无关）。"""
    body = {k: v for k, v in (payload or {}).items() if k != "digest"}
    # 规范化字节编码收成单一实现（审计 Z1）：attest.canonical 与内联表达式同字节。
    return "sha256:" + hashlib.sha256(attest.canonical(body)).hexdigest()




def render_surface_module(payload) -> str:
    """把机器快照渲染成可 import 的生成件（确定性：同输入逐字节一致）。"""
    def lit(value):
        return pprint.pformat(value, width=96, sort_dicts=False)

    parts = [SURFACE_MODULE_HEAD, ""]
    for name, key in (("KIND", "kind"), ("SCHEMA", "schema"), ("DIGEST", "digest"),
                      ("SOURCE", "source"), ("COMMANDS", "commands"),
                      ("ROOT_FLAGS", "root_flags")):
        parts.append("%s = %s" % (name, lit(payload[key])))
    for name, key in (("ZONES", "zones"), ("FAMILIES", "families"), ("FORMS", "forms"),
                      ("GATES", "gates"), ("BLOCKED", "blocked")):
        parts.append("")
        parts.append("%s = %s" % (name, lit(payload[key])))
    text = "\n".join(parts).rstrip("\n") + "\n"
    return text.replace("\r\n", "\n")




def surface_module_text(commands=(), root_flags=()) -> str:
    """生成件应有内容（check39 与单测都用它重算，不另存第二份）。"""
    return render_surface_module(surface_payload(commands, root_flags))




def surface_sync_issues(module_text: str, commands=(), root_flags=()) -> list:
    """投影件对账：重算 → 与在场文本逐字节比对；返回问题清单（空 = 同步）。"""
    expected = surface_module_text(commands, root_flags)
    if str(module_text) == expected:
        return []
    got = str(module_text).splitlines()
    want = expected.splitlines()
    where = "（在场 %d 行 / 应为 %d 行）" % (len(got), len(want))
    for i, line in enumerate(want):
        if i >= len(got) or got[i] != line:
            where = "首个不一致在第 %d 行：在场 %r / 应为 %r" % (
                i + 1, (got[i] if i < len(got) else "<缺行>"), line)
            break
    return ["%s 与真源不同步%s（修复指引：python scripts/nf.py shell --surface-write %s）"
            % (SURFACE_MODULE_PATH, where, SURFACE_MODULE_PATH)]




def render_surface(payload, width=None, color: bool = False) -> str:
    """人读面：逐区列出动作与示例条数（机器面用 `--surface --json`）。"""
    w = term_width(width)
    lines = [style("== NF 终端面投影（%s · 命令 %d · 能力族 %d · 表单 %d）=="
                   % (payload.get("schema"), len(payload.get("commands") or []),
                      len(payload.get("families") or []), len(payload.get("forms") or [])),
                   "head", color)]
    for z in payload.get("zones") or []:
        acts = z.get("actions") or []
        lines.append(_row("[%s] %s" % (z["key"], z["title"]),
                          "%s · 动作 %d：%s" % (z.get("family") or "", len(acts),
                                                "、".join(str(a["title"]) for a in acts)),
                          w, color))
    g = payload.get("gates") or {}
    lines.append("  写盘闸门：旗标 %d · 动词 %d · 命令+旗标 %d · 会话内不直跑 %d"
                 % (len(g.get("flags") or []), len(g.get("verbs") or []),
                    len(g.get("pairs") or []), len(payload.get("blocked") or {})))
    lines.append("  四项视图同源：nf shell（示例/族/表单）· tui/nf.py（动作目录）· "
                 "--surface --json（机器面）· %s（生成件）" % SURFACE_MODULE_PATH)
    lines.append("  对账：nf shell --verify（终端自检）· verify check39（投影与真源同步）")
    return "\n".join(lines)
