"""domain_pack · _doc_domain（自 domain_pack.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from ._catalog import (
    _std_cell,
    bindings_full,
)
from ._io import (
    standards_catalog,
)


def domain_spec_md(spec: Dict[str, Any], root: str = ".") -> str:
    name = spec["name"]
    tier = spec.get("content_tier", "authored")
    tier_note = (
        "> **内容档位（如实标注）**：本包为 **derived 档**——12 条细分名取自品类清单，"
        "判据/失效模式按所属段的**工程口径框架**（输入规格 / 处理参数 / 输出契约 / 验收判据）登记，"
        "**领域细则待作者逐条补全**；权威锚为段级参照，不做领域专属断言。"
        if tier == "derived" else
        "> **内容档位**：authored（逐条撰写，含领域专属判据与权威锚）。")
    lines = [
        '<!-- nf-asset: key="DOMAIN_SPEC" version="1.0" status="active" -->',
        "# 域口径表 · %s" % name,
        "",
        "> 用途：本域包的**内容资产与口径面**——把「%s」这一域的 %d 条细分写成"
        "可判定的口径（定义 / 可机验判据 / 常见失效模式），并逐条挂权威锚。" % (name,
 len(spec["subdivisions"])),
        "> 资产键：`DOMAIN_SPEC`｜机读同源面 = `outputs/DOMAIN_SPEC.json`（双源一致由 "
        "check32 output_forms 断言；**本表是唯一人读真相，JSON 是它的机读投影**）。",
        tier_note,
        "",
        "## 1. 口径纪律",
        "",
        "1. **定义可判定**：每条细分的定义必须能回答「什么算做对/做错」，不允许只给形容词。",
        "2. **判据可机检**：每条细分给出可写进校验器的判据（字段 / 范围 / 词表 / 一致性）。",
        "3. **锚可复核**：每条挂一个外部权威锚（规范 / 论文 / 参考实现），URL 与可达性实测记于 "
        "`STANDARDS_ANCHORS`。",
        "4. **失效模式显式**：写清该细分最常见的错法——它是质检单，不是介绍页。",
        "5. **口径不合并**：不同细分不共用同一条判据文本；相似即拆细。",
        "",
        "## 2. 细分口径表（%d 条）" % len(spec["subdivisions"]),
        "",
        "| 条目键 | 细分 | 定义口径 | 可机验判据 | 常见失效模式 | 主锚（域口径标准） | 辅锚（产出承"
            "载标准） |",
        "|---|---|---|---|---|---|---|",
    ]
    cat = standards_catalog(root)
    _bd = bindings_full(spec, cat)
    for s in spec["subdivisions"]:
        a0 = _std_cell(cat, _bd[s["id"]]["primary"][0])
        a1 = _std_cell(cat, _bd[s["id"]]["support"][0])
        lines.append("| `%s` | %s | %s | %s | %s | %s | %s |"
                     % (s["id"], s["name"], s["definition"], s["check"], s["pitfall"], a0, a1))
    lines += [
        "",
        "## 3. 机读投影契约",
        "",
        "- `outputs/DOMAIN_SPEC.json`：本表的结构化等价物（`kind = nf-domain-spec/1`）；"
        "键集与本节**双向一致**（多一键或少一键即 FAIL）。",
        "- `outputs/REPORT.json`：域内度量的**可复算报告**（T4）——由 `outputs/samples/CASES.csv` "
        "按声明的度量族重算，check32 逐字段比对。",
        "- 度量族：`%s`（口径公式见 `docs/domain-packs.md`）。" % spec["metric_family"],
        "",
        "## 4. 与模块的关系",
        "",
        "- `%s:M01`（P40）：读本表登记口径，校验判据齐备性，越界即发口径冲突事件。"
            "" % spec["category"],
        "- `%s:M02`（P60）：收口度量报告与形态产出，保证「口径 → 数 → 图」三段同源。"
            "" % spec["category"],
    ]
    return "\n".join(lines) + "\n"




def standards_md(spec: Dict[str, Any], root: str = ".") -> str:
    name = spec["name"]
    cat = standards_catalog(root)
    bd = bindings_full(spec, cat)
    lines = [
        '<!-- nf-asset: key="STANDARDS_ANCHORS" version="1.0" status="active" -->',
        "# 权威锚表 · %s" % name,
        "",
        "> 用途：本域 %d 条细分各自的**外部权威锚**（规范 / 论文 / 参考实现）与**可达性实证**。"
        "外部锚只作口径与机制参照，**不作品质背书**（STRATEGY §3.2/§3.3）。"
            "" % len(spec["subdivisions"]),
        "> 资产键：`STANDARDS_ANCHORS`｜细分锚实测日期：2026-09-22（本机 GET，HTTP 状态见下表；"
        "不可达如实记 `✗`，不假装可达）｜标准锚实测日期见下表「标准锚」列（取自 "
        "`protocol/standards_catalog.json` 的本机探针记录）。",
        "",
        "## 1. 锚表",
        "",
        "| 条目键 | 锚类型 | URL | 可达性 | 主锚（域口径标准） | 辅锚（产出承载标准） |",
        "|---|---|---|---|---|---|",
    ]
    for s in spec["subdivisions"]:
        st = s.get("anchor_status")
        mark = "✓ %s" % st if isinstance(st, int) and st == 200 else (
            "✗ %s" % st if st else "未探（如实记档）")
        cells = []
        for role in ("primary", "support"):
            sid, why = bd[s["id"]][role]
            std = cat.get(sid) or {}
            ev = std.get("evidence") or {}
            if not sid:
                cells.append("—")
                continue
            cells.append("`%s` %s（%s｜%s｜%s；%s）"
                         % (sid, std.get("title", ""), std.get("body", ""), std.get("layer", ""),
                            ("✓ %s" % ev.get("probe_date", "")) if ev.get("reachable")
                            else "✗ %s" % (ev.get("http_status") or ""), why or "—"))
        lines.append("| `%s` | %s | %s | %s | %s | %s |"
                     % (s["id"], s.get("anchor_kind", "spec"), s["anchor"], mark,
                        cells[0], cells[1]))
    lines += [
        "",
        "## 2. 使用边界",
        "",
        "- 锚用于**口径复核**（该细分的通行定义/评测口径从何而来），不表示 NF 复制了外部文本；"
        "本包正文自撰。",
        "- **双锚分工**：主锚 = 该细分依据的域口径标准（可能与细分锚不同源，形成第二证据链）；"
        "辅锚 = 该细分产出（数据 / 契约 / 图表 / 图示 / 溯源）所承载的开放标准。",
        "- 标准锚取自 `protocol/standards_catalog.json` 的**本机实测记录**（含取样标题与 sha256），"
        "可达性 false 如实标注，不假装可达。",
        "- 锚不可达时按不可达记档，不影响本包口径面的机检（判据落在本包 schema 与度量族）。",
        "- 锚版本漂移（规范改版）由维护者按需复核；本表不做自动追踪。",
    ]
    return "\n".join(lines) + "\n"




def _event_names(spec: Dict[str, Any], which: int) -> Tuple[str, str]:
    """包内事件名（**单源**：machine_contract 与 §4 事件契约必须同名）。

    命名纪律：事件名按域码命名空间（a01_/b03_…）——01 §1.1「发布方唯一」要求同一事件名
    只能有一个发布方，故跨域同名会被 check16 ④ 判违约（2026-09-22 实测）。
    """
    code = spec["code"].lower()
    kind = "spec" if which == 1 else "report"
    return "%s_%s_ready" % (code, kind), "%s_%s_conflict" % (code, kind)
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
