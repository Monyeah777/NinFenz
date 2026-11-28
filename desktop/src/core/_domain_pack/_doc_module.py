"""domain_pack · _doc_module（自 domain_pack.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from typing import Any, Dict

from core import io_types as _iot

from ._doc_domain import (
    _event_names,
)


def module_md(spec: Dict[str, Any], which: int, alloc: Dict[str, Any]) -> str:  # noqa: ARG001 - 调用契约：测试按 alloc= 关键字传入
    """which: 1 = P40 口径层，2 = P60 收口层。"""
    code, cat, name = spec["code"], spec["category"], spec["name"]
    mid = "%s:M%02d" % (cat, which)
    title = spec["module_titles"][which - 1]
    layer, layer_name = _layer_meta(which)
    ready_ev, conflict_ev = _event_names(spec, which)
    duty, outs, pub, sub_ev, assets = _module_meta(spec, which, ready_ev, conflict_ev)
    lines = [
        "# 模块 %s · %s" % (mid, title),
        "",
        "> 类别：%s｜来源：社区（%s自带，类内段）｜挂载点：%s %s（active，default）｜"
        "依赖：M00、M50%s｜发布：%s｜状态：active"
        % (cat, spec["pack_name"], layer, layer_name,
           ("、%s:M01" % cat) if which == 2 else "", "、".join(pub)),
        "> 用途：%s。" % duty,
        "",
        "```yaml",
        "machine_contract:",
        '  conformance: "L2"',
        '  schema: "1"',
        "  id: %s" % mid,
        "  name: %s" % title,
        "  category: %s" % cat,
        '  layer: %s' % layer,
        "  inputs: [M00, M50%s]" % (", '%s:M01'" % cat if which == 2 else ""),
        "  outputs: [%s]" % ", ".join(outs),
        "  events:",
        "    publish: [%s]" % ", ".join(pub),
        "    subscribe: [%s]" % ", ".join(sub_ev),
        "  interfaces: [%s_query]" % outs[0],
    ]
    # io_types 块**由 `core.io_types.render_io_types` 渲染**（单一真相源）：生成器与
    # `nf module types --write` 必须产出**逐字相同**的形态（键序 + 是否引号），否则工厂自检
    # `domain_pack.verify` 立刻判「与生成器漂移」——2026-10-02 实测：一次 --write 归一了键序与
    # 引号写法，A01 包当场飘红。生成模块的 outputs 恒为 `untyped`（无事件证据可依，不许编造）。
    _ins: Dict[str, str] = {"M00": "state", "M50": "untyped"}
    if which == 2:
        _ins["%s:M01" % cat] = "untyped"
    lines += _iot.render_io_types({"outputs": {o: "untyped" for o in outs},
                                   "inputs": _ins}).splitlines()
    lines += [
        "```",
        "",
        "## 1. 职责",
        "",
        duty + "。",
        "",
        "域知识结构不写死在模块里：概念前置在资产 `CONCEPT_GRAPH`，口径在资产 `DOMAIN_SPEC`"
        "（图 = 内容，口径 = 机制，三正交分离）。",
        "",
        "## 2. 协议声明（01 §2 模块协议）",
        "",
        "```yaml",
        "Module:",
        "  id: %s" % mid,
        "  name: %s" % title,
        "  layer: %s" % layer,
        "  inputs: [M00, M50%s]" % (", '%s:M01'" % cat if which == 2 else ""),
        "  outputs: [%s]" % ", ".join(outs),
        "  events:",
        "    publish: [%s]" % ", ".join(pub),
        "    subscribe: [%s]" % ", ".join(sub_ev),
        "  core:",
        "    assets: [%s]" % assets,
        "    logic:",
    ]
    if which == 1:
        logic = {
            "读口径": "从 DOMAIN_SPEC 读 %d 条细分的定义 / 判据 / 失效模式" % len(spec["subdivision"
                "s"]),
            "登记": "逐条登记 Spec 条目（id ∈ 条目键表，判据非空，锚为绝对 URL）",
            "校验": "判据齐备且锚可达性已记档 → 通过；缺项 / 锚非 URL → spec_conflict",
            "落槽": "写 DomainSpecState{subdivisions, conflicts, tick}",
            "发布": "全通过 → %s；否则逐条 %s" % (ready_ev, conflict_ev),
        }
    else:
        logic = {
            "读口径": "读 %s:M01 的口径状态（spec 齐备才继续）" % cat,
            "复算": "由 samples/CASES.csv 按度量族重算域报告（core/domain_metrics）",
            "对齐": "报告字段 ⊆ 口径表条目键；对不上 → %s" % conflict_ev,
            "派生": "由 CONCEPT_GRAPH 派生分层图（Mermaid / GraphML）",
            "发布": "全部一致 → %s；否则 %s" % (ready_ev, conflict_ev),
        }
    for k, v in logic.items():
        lines.append("      %s: %s" % (k, v))
    lines += [
        "```",
        "",
        "## 3. 产出面（可机验）",
        "",
        "| 产出 | 形态 | 档位 | 说明 |",
        "|---|---|---|---|",
        "| `outputs/DOMAIN_SPEC.json` | 结构化数据 | T3 | 口径表机读投影（与资产双源一致） |",
        "| `outputs/REPORT.json` | 可复算报告 | T4 | 度量族重算（check32 逐字段比对） |",
        "| `outputs/charts/*.vega.json` | 图表规格 | T3 | 由报告确定性生成 |",
        "| `outputs/CONCEPT_DAG.graphml` 等 | 图结构 | T3 | 由概念图确定性派生 |",
        "",
        "## 4. 事件联动（机读契约）",
        "",
    ]
    if which == 1:
        events = [
            (ready_ev, "{ subdivisions: number, checked: number, tick: number }",
             "口径面齐备（%d 条全过判据）" % len(spec["subdivisions"])),
            (conflict_ev,
             "{ field: string, reason: string, blocking: boolean }",
             "口径缺项 / 越词表 / 锚非 URL"),
        ]
    else:
        events = [
            (ready_ev,
             "{ family: string, metrics: number, tick: number }",
             "度量复算完成且与口径表同源"),
            (conflict_ev,
             "{ field: string, reason: string, blocking: boolean }",
             "复算结果与在盘报告不一致 / 报告字段越口径表"),
        ]
    for name, payload, note in events:
        lines += [
            "```yaml",
            "event: %s" % name,
            "payload: %s" % payload,
            "description: %s" % note,
            "```",
            "",
        ]
    lines += [
        "## 5. 边界与不宣称",
        "",
        "- 本模块**不产出模型能力结论**：报告是样例集上的口径值，不是能力评测结论。",
        "- 外部锚只作口径参照，不作质量背书；口径表正文自撰。",
        "- 域包不承担该域的教学职能：包外前置族（%s-00）须装载方自备。" % code,
    ]
    return "\n".join(lines) + "\n"


def _layer_meta(which):
    layer = "P40" if which == 1 else "P60"
    layer_name = "行为决策" if which == 1 else "长期演变"
    return layer, layer_name


def _module_meta(spec, which, ready_ev, conflict_ev):
    if which == 1:
        duty = ("逐条登记本域 %d 个细分口径（定义 / 可机验判据 / 失效模式），校验齐备性与词表边界；"
                "越界或缺项即发布口径冲突事件" % len(spec["subdivisions"]))
        outs = ["domain_spec", "spec_conflict_list"]
        pub = [ready_ev, conflict_ev]
        # 事件面闭合（2026-09-23 实测修）：本模块发布的 spec_* 必须有人订阅，否则 check16 ③
        # 判「发布面 ⊄ 邻居订阅面」；收口层订阅 spec_ready/spec_conflict = 口径 ↔ 收口反馈对。
        sub_ev = _event_names(spec, 2)[:]      # [report_ready, report_conflict]
        assets = "CONCEPT_GRAPH, DOMAIN_SPEC, STANDARDS_ANCHORS"
    else:
        duty = ("把口径面收口为**可复算产出**：由样例与度量族重算域报告（T4），并从概念图派生图形态"
            "；"
                "报告与图与口径表三段同源，任一漂移即发布收口冲突事件")
        outs = ["domain_report", "closure_conflict_list"]
        pub = [ready_ev, conflict_ev]
        sub_ev = (_event_names(spec, 1)[0], _event_names(spec, 1)[1])
        assets = "DOMAIN_SPEC, CONCEPT_GRAPH"
    return duty, outs, pub, sub_ev, assets




def pipeline_md(spec: Dict[str, Any], alloc: Dict[str, Any]) -> str:
    code, cat, name = spec["code"], spec["category"], spec["name"]
    pid = alloc["pipeline"]
    lines = [
        "# 管线 %s · %s装配流" % (pid, name),
        "",
        "> 社区版「%s」使用的管线（域包工厂生成；派生自 P00 通用骨架，九层位名沿用骨架）。"
        "以「口径先行」为流主轴：官方核心 M00 数据槽承载口径状态，通用:M10 节拍定拍，"
        "M50 主循环在回卷点推进；本包自带 %s:M01 挂 P40 做**口径登记**，"
        "%s:M02 挂 P60 做**收口与派生**；P80 输出呈现由官方核心 M80 承担（gate 唯一出口）。"
        % (spec["pack_name"], cat, cat),
        "> **允许编号段固化（R2）**：本包 `allowed_modules` 只含官方核心承载件与本包类内段编号；"
        "references=[] 零跨包零借阅。",
        "> **挂载层规避**：本包 P40/P60 default 用的是类内段唯一编号，与既有各包同层 default 无交集"
        "（独立装载不冲突）。",
        "```yaml",
        "Pipeline:",
        "  id: %s" % pid,
        "  name: %s装配流" % name,
        "  structure:",
        "    type: linear",
        "    flow:",
    ]
    order = ["P00", "P10", "P20", "P30", "P40", "P50", "P60", "P70", "P80"]
    for i, lay in enumerate(order):
        nxt = order[i + 1] if i + 1 < len(order) else "P00"
        cond = ("",
                "\n        condition: =data_bus.round.phase == \"roll\" && event.tick_day"
                    "")[nxt == "P00"]
        lines += ["      - from: %s" % lay, "        to: %s%s" % (nxt, cond)]
    layer_names = {"P00": "数据基座", "P10": "世界推进", "P20": "角色状态", "P30": "事件生产",
                   "P40": "行为决策", "P50": "交互执行", "P60": "长期演变", "P70": "叙事素材",
                   "P80": "输出呈现"}
    core_allow = {"P00": ["M00"],
 "P10": ["通用:M10"],
 "P20": ["M23"],
 "P30": ["事件:M22",
 "M06",
 "M13"],
                  "P50": ["M12"], "P70": ["M20", "M24"], "P80": ["M80"]}
    lines.append("  layers:")
    for lay in order:
        if lay == "P40":
            desc = "本包自带 %s:M01 做「%s」口径登记（%d 条细分判据齐备性）" % (
                cat, spec["module_titles"][0], len(spec["subdivisions"]))
            default = "['%s:M01']" % cat
            allow = "['%s:M01']" % cat
        elif lay == "P60":
            desc = "本包自带 %s:M02 做收口（度量复算 + 图形态派生）" % cat
            default = "['%s:M02']" % cat
            allow = "['%s:M02']" % cat
        else:
            desc = "由官方核心 %s 承载（本体驻官方核心位不搬移，本包零重复挂载）" % \
                   "、".join(core_allow[lay])
            default = "[]"
            allow = "[%s]" % ", ".join(core_allow[lay])
        lines += [
            "    - id: %s" % lay,
            "      name: %s" % layer_names[lay],
            "      description: %s" % desc,
            "      optional: false",
            "      default_modules: %s" % default,
            "      allowed_modules: %s" % allow,
        ]
    lines += [
        "```",
        "",
        "## 说明",
        "",
        "- 九层位名与 P00 骨架一致；本域只在 P40/P60 驻留自有模块，其余层位由官方核心承载。",
        "- M50 主循环是全局调度器（无层挂载），以 core 依赖引用参与回卷。",
        "- 本管线为域包工厂生成件：`nf domain build --spec %s`（幂等，重跑逐字节一致）。" % code,
    ]
    return "\n".join(lines) + "\n"
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
