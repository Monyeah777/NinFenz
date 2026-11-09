"""15 个元动作的契约：每个动作必须带「框架变化见证」（frame_delta），否则就是换皮。

为什么这么严：认知核最容易退化成「元认知表演」——每轮都 reframe/steelman，但问题没变。
判据是把「动作」写成「必须留下什么变化」，没变化就拒绝（fail-closed）。
"""
from __future__ import annotations

from typing import Any

SCHEMA = "nf-cognitive-move/1"

#: frame_delta 的合法种类 → 该种类必须携带的字段
DELTA_KINDS: dict[str, tuple[str, ...]] = {
    "question_restated": ("before_digest", "after_digest", "changed_terms"),
    "assumption_suspended": ("assumption_id", "reason"),
    "assumption_revived": ("assumption_id", "reason"),
    "concept_clarified": ("concept", "distinctions"),
    "tension_added": ("between", "statement"),
    "hypothesis_proposed": ("hypothesis", "expected_observation"),
    # witness（第 93 轮，对抗层）：反例必须是**可复算的证人**（文件 + 用例 id），否则只是叙述
    "counterexample_found": ("claim", "case", "breaks", "witness"),
    "mapping_added": ("source", "target", "preserved", "broken"),
    "stakeholder_added": ("perspective", "obligations"),
    "provenance_added": ("origin", "lineage"),
    "boundary_added": ("case", "near_miss"),
    "objection_strengthened": ("objection", "reasons"),
    "subquestions_added": ("subquestions",),
    "commitment_formed": ("claim", "evidence_standard"),
    "evidence_standard": ("claim_kind", "required"),
}

#: 15 个 meta move：id → 契约（触发条件 / 允许的 delta / 失败模式 / 说明）
MOVES: dict[str, dict[str, Any]] = {
    "reframe": {
        "name": "重新表述问题",
        "when": "问题读起来自相矛盾、或解不动、或术语含糊时",
        "delta_kinds": ("question_restated",),
        "failure_mode": "只换词不换问题（before/after digest 相同）",
        "note": "重述必须改变问题的可解性条件；digest 不同只是最低门槛",
    },
    "bracket": {
        "name": "悬置假设",
        "when": "发现某个默认前提未经验证、且它一旦为假结论就翻",
        "delta_kinds": ("assumption_suspended", "assumption_revived"),
        "failure_mode": "悬置了不存在的假设，或没说为什么悬置",
        "note": "悬置要能被后续回合恢复（revive）才叫悬置，不是删除",
    },
    "conceptual_analysis": {
        "name": "概念分析",
        "when": "两个词被当同义用，或概念边界模糊到无法判真伪",
        "delta_kinds": ("concept_clarified",),
        "failure_mode": "只给定义不区分（distinctions 为空）",
        "note": "必须给出至少一组区分，否则定义无法判真",
    },
    "dialectic": {
        "name": "正反合",
        "when": "存在两个都有理由的对立立场，且不能简单折中",
        "delta_kinds": ("tension_added",),
        "failure_mode": "把张力写成「各有道理」而不给冲突点",
        "note": "张力必须写成 between + statement，可被后续 counterexample 攻击",
    },
    "thought_experiment": {
        "name": "思想实验",
        "when": "现实不可操作、但可以设一个可判的假设场景",
        "delta_kinds": ("hypothesis_proposed",),
        "failure_mode": "没有可观察结果（expected_observation 为空）",
        "note": "思想实验的价值在「能预测什么」，不在故事好听",
    },
    "counterexample": {
        "name": "反例",
        "when": "某个主张看起来成立，但边界可疑",
        "delta_kinds": ("counterexample_found",),
        "failure_mode": "举的例子其实不违反主张（breaks=false）",
        "note": "必须明确 breaks=true 并说清破坏了哪条前提",
    },
    "analogy": {
        "name": "类比",
        "when": "需要把已有领域的结构迁移到新问题",
        "delta_kinds": ("mapping_added",),
        "failure_mode": "只给相似处，不给断点（broken 为空）",
        "note": "类比的可用性取决于断点，不给断点就是骗人",
    },
    "perspective_shift": {
        "name": "视角转换",
        "when": "结论只在单一利益相关者视角下成立",
        "delta_kinds": ("stakeholder_added",),
        "failure_mode": "加了视角但没说该视角要求什么（obligations 为空）",
        "note": "视角必须带来义务，否则只是修辞",
    },
    "value_conflict": {
        "name": "价值冲突",
        "when": "两个目标不可同时最大化（如鲁棒 vs 不可见）",
        "delta_kinds": ("tension_added",),
        "failure_mode": "把权衡写成「都要」，回避取舍",
        "note": "必须写明冲突的两端与不可兼得的原因",
    },
    "genealogy": {
        "name": "谱系",
        "when": "概念/做法有历史来源，当前用法可能已偏离",
        "delta_kinds": ("provenance_added",),
        "failure_mode": "只给时间线，不给「谁改的、为什么」",
        "note": "lineage 要能指向可查来源",
    },
    "reductio": {
        "name": "归谬",
        "when": "对方主张看起来无懈可击，怀疑其前提过强",
        "delta_kinds": ("hypothesis_proposed",),
        "failure_mode": "推出的荒谬结论其实不荒谬（夸大）",
        "note": "归谬的力量来自「按对方逻辑必然推出」",
    },
    "boundary_case": {
        "name": "边界案例",
        "when": "规则在大样本上成立，但临界情形未测",
        "delta_kinds": ("boundary_added",),
        "failure_mode": "举的例子离边界很远（near_miss=false）",
        "note": "near_miss 必须是「差一点就跨过」的案例",
    },
    "steelman": {
        "name": "最强反驳",
        "when": "准备下结论前，需要先把对手论证到最强",
        "delta_kinds": ("objection_strengthened",),
        "failure_mode": "稻草人（reasons 为空或明显弱）",
        "note": "steelman 的质量 = 对方是否愿意认领这个版本",
    },
    "meta_question": {
        "name": "元问题",
        "when": "问题本身问错了/问法决定了不可能有好答案",
        "delta_kinds": ("question_restated",),
        "failure_mode": "把「换个说法」当元问题",
        "note": "元问题要改变问题的层级（问「为什么问这个」）",
    },
    "decomposition": {
        "name": "分解",
        "when": "问题太大，无法单步验证",
        "delta_kinds": ("subquestions_added",),
        "failure_mode": "分解后子问题不可独立判定",
        "note": "子问题必须能各自被证据回答",
    },
}

MOVE_IDS = tuple(MOVES)


def _digest(obj: Any) -> str:
    import hashlib
    import json

    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _witness_shape_issues(witness: Any) -> list[str]:
    """反例证人的**形状**判据：必须是 {file, case} 两键（第 93 轮，对抗层）。

    只判形状、不判文件存在：本模块是纯语义层不做 IO；文件是否真存在由带仓库根的一侧核对。
    """
    if not isinstance(witness, dict):
        return ["反例缺 witness 证人（修复指引："
                + "给 {file: 相对路径, case: 用例 id}）"]
    issues: list[str] = []
    for key in ("file", "case"):
        if not str(witness.get(key) or "").strip():
            issues.append("witness 缺 " + key + "（修复指引：证人是文件 + 用例 id）")
    return issues


def _witness_file_issues(witness: Any, root: str) -> list[str]:
    """带仓库根时核对证人文件是否真的存在（第 94 轮）。

    为什么拆开：`validate_delta` 默认保持纯函数（不做 IO）；调用方给 root 才做存在性核对。
    「格式对」不等于「证人真在场」——这一层补的正是后者。
    """
    from pathlib import Path

    if not isinstance(witness, dict):
        return []
    rel = str(witness.get("file") or "").strip()
    if not rel:
        return []
    if not (Path(root) / rel).is_file():
        return ["witness 文件不存在：" + rel + "（修复指引：证人必须指向仓库里真实存在的复现件）"]
    return []


def validate_delta(move_id: str, delta: Any, root: str = "") -> list[str]:
    """校验一个 move 的 frame_delta → 问题列表（空 = 合法）。

    给 `root` 时额外核对反例证人的文件是否真的存在（不给则保持纯函数、不做 IO）。
    """
    issues: list[str] = []
    if move_id not in MOVES:
        return ["未知元动作：" + str(move_id) + "（可用：" + "、".join(MOVE_IDS) + "）"]
    contract = MOVES[move_id]
    if not isinstance(delta, dict):
        return ["frame_delta 必须是对象（修复指引：见 moves.DELTA_KINDS）"]
    kind = str(delta.get("kind") or "")
    if kind not in contract["delta_kinds"]:
        return ["动作 " + move_id + " 不接受 frame_delta.kind=" + repr(kind)
                + "（允许：" + "、".join(contract["delta_kinds"]) + "）"]
    for field in DELTA_KINDS[kind]:
        if field not in delta:
            issues.append("frame_delta[" + kind + "] 缺 " + field
                          + "（修复指引：把这次动作留下的变化写清）")
    if issues:
        return issues
    # 每种 delta 的语义判据（不是格式检查，是「有没有真变化」检查）
    if kind == "question_restated":
        if str(delta["before_digest"]) == str(delta["after_digest"]):
            issues.append("问题重述前后 digest 相同——只换词没换问题（判失败）")
        if not isinstance(delta["changed_terms"], list) or not delta["changed_terms"]:
            issues.append("changed_terms 为空——没写清改了什么")
    elif kind == "counterexample_found":
        if delta["breaks"] is not True:
            issues.append("breaks 必须为 true——例子不违反主张就不算反例")
        issues.extend(_witness_shape_issues(delta.get("witness")))
        if root:
            issues.extend(_witness_file_issues(delta.get("witness"), root))
    elif kind == "boundary_added":
        if delta["near_miss"] is not True:
            issues.append("near_miss 必须为 true——离边界很远的例子不算边界案例")
    elif kind == "concept_clarified":
        if not isinstance(delta["distinctions"], list) or not delta["distinctions"]:
            issues.append("distinctions 为空——定义必须给出至少一组区分")
    elif kind == "mapping_added":
        if not isinstance(delta["broken"], list) or not delta["broken"]:
            issues.append("broken 为空——类比必须给断点")
    elif kind == "tension_added":
        if not isinstance(delta["between"], list) or len(delta["between"]) < 2:
            issues.append("between 至少两端——张力必须写明冲突双方")
    elif kind == "subquestions_added":
        if not isinstance(delta["subquestions"], list) or len(delta["subquestions"]) < 2:
            issues.append("subquestions 至少两条——否则不叫分解")
    return issues


def describe(move_id: str) -> dict[str, Any]:
    """给 CLI/文档用的动作说明（未知动作为空对象）。"""
    cfg = MOVES.get(move_id)
    if not cfg:
        return {}
    return {"id": move_id, "schema": SCHEMA, **cfg}
