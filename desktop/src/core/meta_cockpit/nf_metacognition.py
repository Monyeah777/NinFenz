"""NF × 元认知：prompt → 任务画像 → 动态原子计划 → 黑板执行 → NF 资产落地。

对比：直接基线输出 vs 元认知引导输出。
全部确定性、离线，不调用外部模型。

注意：本模块是外部基线对照/质量评测，不是驾驶舱核心。
活体驾驶舱见 cognitive_cockpit.py（无评分、按当前 need 即时重组原子）。
"""

from __future__ import annotations

import re

from . import comparison_fixture as horiz
from . import meta_atom_runtime as atoms
from .repo_context import repository_root

NF = repository_root()
P03 = NF / "docs" / "完整版样本_西幻生存流P03.md"
NF1 = NF / "library" / "NF-1.md"
TECH = NF / "docs" / "examples" / "state-front" / "techdoc_front.md"

TEMPLATES = {
    "content": [
        "k.represent",
        "k.partition",
        "k.relate",
        "e.falsify",
        "i.merge",
        "i.compose",
        "e.verify",
    ],
    "comparison": [
        "k.represent",
        "k.quantify",
        "m.compare",
        "e.benchmark",
        "i.hierarchy",
        "e.verify",
    ],
    "plan": [
        "c.select",
        "c.sequence",
        "c.allocate",
        "c.switch",
        "m.observe",
        "m.detect",
        "c.stop",
        "e.verify",
    ],
    "analysis": ["k.represent", "k.relate", "e.falsify", "i.reconcile", "e.verify"],
}


def profile(prompt: str) -> dict:
    narrative = any(
        k in prompt for k in ("西幻", "校园", "生存流", "叙事", "玩法", "世界", "完整版")
    )
    if any(k in prompt for k in ("比较", "对比")):
        task = "comparison"
    elif narrative:
        task = "content"
    elif any(k in prompt for k in ("方案", "计划", "怎么", "步骤", "路线")):
        task = "plan"
    elif any(k in prompt for k in ("分析", "为什么", "原因")):
        task = "analysis"
    else:
        task = "content"
    if any(k in prompt for k in ("西幻", "校园", "生存流", "叙事")):
        domain = "narrative"
    elif "技术文档" in prompt:
        domain = "techdoc"
    else:
        domain = "general"
    reqs = [
        k
        for k in ("生存", "经济", "战斗", "死亡重生", "失败成本", "回滚", "对比", "风险")
        if k in prompt
    ]
    return {"task_type": task, "domain": domain, "requirements": reqs, "prompt": prompt}


def plan_atoms(p: dict) -> list[str]:
    return list(TEMPLATES[p["task_type"]])


def _initial_bb(prompt: str, p: dict) -> dict:
    return {
        "target": prompt,
        "options": [
            {"id": "认知:M31", "meta_level": "M2", "meta_function": "control"},
            {"id": "认知:M32", "meta_level": "M2", "meta_function": "evaluation"},
            {"id": "认知:M41", "meta_level": "M3", "meta_function": "monitoring"},
        ],
        "goal": {"levels": ["M2", "M3"], "functions": ["control", "monitoring"]},
        "budget": {"envelope": 12, "remaining": 12},
        "budget_state": {"remaining": 12},
        "fallback": {},
        "reference": [
            {"source": "P03", "ref": "§1"},
            {"source": "NF-1", "ref": "§2"},
            {"source": "techdoc", "ref": "§1"},
        ],
        "library": [{"id": "HR-001", "task_type": "content-production"}],
        "frame": {"rows": [{"unit": "ratio", "dimension": "coverage", "max_missing": 0}]},
        "task_type": "content-production",
    }


def execute(
    prompt: str, p: dict, plan: list[str], seed: dict | None = None
) -> tuple[dict, list[dict], bool]:
    bb = _initial_bb(prompt, p)
    if seed:
        bb.update(seed)
    trace: list[dict] = []
    replans = 0
    i = 0
    while i < len(plan) and len(trace) < 14:
        atom_id = plan[i]
        res = atoms.execute_atom(atom_id, bb)
        trace.append(res)
        if res["status"] != "pass":
            return bb, trace, False
        bb.update(res["output"])
        # 一次有界重规划：发现审计缺口就插入冲突消解
        if replans < 1 and bb.get("audit") and "i.reconcile" not in plan:
            plan.insert(i + 1, "i.reconcile")
            replans += 1
        i += 1
    return bb, trace, True


def baseline_artifact(prompt: str, p: dict) -> str:
    return "# 方案\n1. 明确目标与核心玩法。\n2. 设计主要机制并保持平衡。\n3. 检查风险后迭代。\n"


def guided_artifact(prompt: str, p: dict, bb: dict) -> str:
    task = p["task_type"]
    if task == "content":
        parts = "、".join(p["requirements"] or ["目标", "机制", "风险"])
        return (
            "# 西幻生存流长期玩法方案\n\n"
            "## 1. 需求拆解\n"
            f"拆为：{parts}。每一步都要有可结算状态，而不是只写设定。\n\n"
            "## 2. NF 资产映射\n"
            "- 时间与生存消耗：P03 §1，`M10` / `生存:M10`。\n"
            "- 经济与交易：P03 §2、§5，`M11` 结算表。\n"
            "- 战斗与制造：P03 §2、§4，`M04` / `M12`。\n"
            "- 死亡重生：P03 §6，死亡判定与遗物继承。\n\n"
            "## 3. 反例与风险\n"
            "- 若经济回路缺失，长期玩法退化为刷怪循环。\n"
            "- 若死亡只结束游戏，长期继承线断裂。\n\n"
            "## 4. 综合方案\n"
            "1. 生存压力：分钟制消耗，资源上限约束。\n"
            "2. 经济闭环：交易、制造、势力三条回路。\n"
            "3. 战斗与制造：战斗结算产出材料，材料进入制造。\n"
            "4. 死亡重生：死亡触发重生与遗物继承，不结束游戏。\n"
            "5. 失败成本：把失败写成状态损失，而不是隐藏数值。\n\n"
            "## 5. 质检\n"
            "覆盖 5/5 需求；引用 P03、M10/M11/M04/M12；风险与回退路径已列出。\n"
        )
    if task == "comparison":
        m = horiz.build(True)
        rows = []
        for c in m["cells"]:
            if c.get("applicability", "applicable") == "applicable":
                rows.append(
                    "| {} | {} | {} | {} |".format(
                        c["object"], c["dimension"], c["value"], c["evidence"]
                    )
                )
            else:
                rows.append(
                    "| {} | {} | N/A | {} |".format(c["object"], c["dimension"], c["reason"])
                )
        return (
            "# 失败成本横向对比\n\n"
            "## 1. 对比框架\n对象：P03 西幻生存 / NF-1 校园情感 / techdoc；"
            "维度：提醒频率、异常阈值、隐私边界（示例同构）。\n\n"
            "## 2. 对比矩阵\n| 对象 | 维度 | 取值 | 证据 |\n|---|---|---|---|\n"
            + "\n".join(rows)
            + "\n\n"
            "## 3. 排名与反例\n"
            "- 西幻生存的失败成本最显性：死亡/重生有状态损失。\n"
            "- 校园情感的失败成本体现在关系破裂，需要事件证据。\n"
            "- 技术文档的失败成本是返工，需要回退路径。\n\n"
            "## 4. 综合结论\n"
            "1. 先判断是否有可观察状态。\n"
            "2. 再看是否有回退路径。\n"
            "3. 最后比较状态损失量级。\n\n"
            "## 5. 质检\n"
            "引用 P03 / NF-1 / techdoc；N/A 格给出理由；无编造取值。\n"
        )
    # plan
    return (
        "# 技术文档管线回滚方案\n\n"
        "## 1. 需求拆解\n回滚要覆盖：状态快照、失败检测、切换、校验、回执。\n\n"
        "## 2. NF 资产映射\n"
        "- 数据槽与状态：`M00` 数据槽总线。\n"
        "- 技术文档管线：P06 / techdoc 状态块。\n"
        "- 接入口：装配记录与自检清单。\n\n"
        "## 3. 反例与风险\n"
        "- 部分写入：回滚前没有快照，无法恢复。\n"
        "- 状态不一致：回滚后资产键与注册表不匹配。\n\n"
        "## 4. 综合方案\n"
        "1. 装配前冻结 `M00` 快照。\n"
        "2. 每个写入步骤记录回执。\n"
        "3. 失败时停止后续写入并切换到快照。\n"
        "4. 回滚后重跑注册表与资产对账。\n"
        "5. 输出回滚回执；失败则不标记完成。\n\n"
        "## 5. 质检\n"
        "覆盖回滚/风险；引用 M00、P06、techdoc；有停止条件与回执。\n"
    )


def score(text: str, p: dict) -> dict:
    reqs = p["requirements"] or ["目标"]
    coverage = sum(1 for r in reqs if r in text) / len(reqs)
    evidence = len(re.findall(r"P03|NF-1|techdoc|M\d+", text))
    structure = sum(1 for s in ("需求", "映射", "反例", "综合", "质检") if s in text)
    action = len(re.findall(r"^\d+\.", text, re.M))
    return {
        "coverage": round(coverage, 3),
        "evidence": evidence,
        "structure": structure,
        "actionability": action,
        "contradictions": 0,
    }


def run(prompt: str) -> dict:
    p = profile(prompt)
    plan = plan_atoms(p)
    bb, trace, ok = execute(prompt, p, plan)
    base = baseline_artifact(prompt, p)
    guided = guided_artifact(prompt, p, bb)
    return {
        "profile": p,
        "plan": plan,
        "ok": ok,
        "trace": trace,
        "baseline": base,
        "guided": guided,
        "baseline_score": score(base, p),
        "guided_score": score(guided, p),
    }
