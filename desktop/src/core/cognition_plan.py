"""认知核 · 研究层 v0：把「深入钻研」拆成**切片 → 检索词 → 方法论路径 → 证据台账**。

为什么单独一层（2026-11-07）：认知核此前只有「行话术语表 + 执行分档」两个门禁——
它们管的是**用词与执行形态**，不管「怎么钻一个问题」。结果是研究过程不可复现：
同一个问题，换个时间/换个会话，切片不同、检索词不同、结论强度不同。

本层只做**计划**，不做结论：
- 切片（slices）：固定 7 个面（定义/机制/证据/边界/对比/量级/落地），按 depth 取前 N 个；
- 检索词（terms）：按主题生成中/英/操作性检索词（可给 web、可给仓内 grep）；
- 方法论路径（paths）：从 protocol/research_methods.json 取方法
  （第一性/对比/溯源/反例/量化/溯因/对抗/收口），每个切片指定该用哪几条、
  以及该片要交出的证据与**证伪条件**；
- 台账（ledger）：每条主张必须落到「来源 + 强度 + 证伪条件」，未证项必须显式写出来。

纪律：纯函数、无时间戳（同输入逐字节一致）；方法论库是数据（新增方法 = 加一条数据）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

SCHEMA = "nf-research-plan/1"
METHODS_REL = "protocol/research_methods.json"
METHODS_SCHEMA = "nf-research-methods/1"
GUIDE = "修复指引："
DEPTHS = (1, 2, 3)

#: 固定切片面（depth=3 全取；depth=2 取前 5；depth=1 取前 3）
SLICES: tuple[dict[str, Any], ...] = (
    {"id": "S1", "title": "定义与边界",
     "q": "{topic} 到底是什么？它的边界在哪、同义词与反义词是什么",
     "terms_zh": ["{topic} 定义", "{topic} 是什么", "{topic} 边界"],
     "terms_en": ["{topic_en} definition", "{topic_en} what is"],
     "ops": ["rg -n '{topic}' <repo>", "site:zhihu.com {topic}"],
     "methods": ["M1", "M3"], "evidence": ["一手定义来源（标准/论文/代码行号）"],
     "falsifier": "若两个一手来源对定义互相矛盾，则该片的定义不成立，须先裁决"},
    {"id": "S2", "title": "机制与数据流",
     "q": "{topic} 内部怎么工作？输入是什么、状态怎么变、输出怎么验",
     "terms_zh": ["{topic} 原理", "{topic} 实现", "{topic} 数据流"],
     "terms_en": ["{topic_en} how it works", "{topic_en} implementation"],
     "ops": ["rg -n 'def .*{topic_key}' <repo>", "site:github.com {topic_en}"],
     "methods": ["M1", "M6"], "evidence": ["机制描述对应到具体代码路径或标准条款"],
     "falsifier": "若按该机制实现不出预期输出（最小复现跑不通），则机制描述错"},
    {"id": "S3", "title": "证据与强度", "q": "关于 {topic} 的每条主张，证据在哪、强度多高",
     "terms_zh": ["{topic} 实测", "{topic} 基准", "{topic} 复现"],
     "terms_en": ["{topic_en} benchmark", "{topic_en} reproduction"],
     "ops": ["rg -n 'test_.*{topic_key}' <repo>", "site:arxiv.org {topic_en}"],
     "methods": ["M3", "M5"], "evidence": ["每条主张的来源 + 强度（实测/条款/推测）"],
     "falsifier": "若某条主张只有二手转述或模型记忆，则该主张降级为『未证』"},
    {"id": "S4", "title": "边界与反例", "q": "{topic} 在什么输入/环境下一定失效？最小反例是什么",
     "terms_zh": ["{topic} 局限", "{topic} 失败案例", "{topic} 攻击"],
     "terms_en": ["{topic_en} limitations", "{topic_en} failure case"],
     "ops": ["rg -n 'boundary|limit|不支持' <repo>", "{topic_en} adversarial"],
     "methods": ["M4", "M7"], "evidence": ["失效条件清单 + 反例（实测或构造）"],
     "falsifier": "若宣称『抗 X』却拿不出 X 的具体攻击面，则该宣称不成立"},
    {"id": "S5", "title": "同类对比", "q": "{topic} 与哪些方案可比？三条轴上谁更优",
     "terms_zh": ["{topic} 对比", "{topic} 替代方案"],
     "terms_en": ["{topic_en} vs", "{topic_en} alternative"],
     "ops": ["rg -n '{topic_key}' docs/ <repo>"],
     "methods": ["M2", "M3"], "evidence": ["≥3 种机制在三轴（成本/可证性/失效）上的对齐表"],
     "falsifier": "若存在第四种方案在三条轴上同时更优，则对比不完整"},
    {"id": "S6", "title": "量级与成本", "q": "{topic} 的时间/空间/误判代价是多少",
     "terms_zh": ["{topic} 性能", "{topic} 耗时", "{topic} 内存"],
     "terms_en": ["{topic_en} performance", "{topic_en} complexity"],
     "ops": ["rg -n 'perf|latency|memory' <repo>"],
     "methods": ["M5", "M6"], "evidence": ["指标表 + 测量方法 + 基线"],
     "falsifier": "若换一种测量口径结论反转，则数字不可作为结论"},
    {"id": "S7", "title": "落地与代价", "q": "把 {topic} 用起来要付出什么？谁维护、错了谁负责",
     "terms_zh": ["{topic} 部署", "{topic} 维护成本"],
     "terms_en": ["{topic_en} deployment", "{topic_en} maintenance"],
     "ops": ["rg -n 'deploy|maintain|owner' <repo>"],
     "methods": ["M8", "M2"], "evidence": ["集成面清单 + 责任/回滚条件"],
     "falsifier": "若落地建议里出现『视情况而定』而无判定条件，则未收口"},
)

#: depth → 取前几个切片
_DEPTH_N = {1: 3, 2: 5, 3: 7}
_METHOD_ORDER = ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8")


def load_methods(root: str) -> dict[str, Any]:
    path = Path(root) / METHODS_REL
    if not path.is_file():
        raise ValueError("方法论库不存在（" + GUIDE + "先恢复 " + METHODS_REL + "）")
    from core import json_doc  # 局部导入：形状校验统一走 json_doc

    doc = json_doc.load(path, dict, what=str(path))
    issues = validate_methods(doc)
    if issues:
        raise ValueError("方法论库不合法：" + "；".join(issues[:3]))
    return doc


def _method_field_issues(m: dict, label: Any) -> list[str]:
    """方法必填字段（title/when/output/falsifier）逐项非空。"""
    issues: list[str] = []
    for field in ("title", "when", "output", "falsifier"):
        if not str(m.get(field) or "").strip():
            issues.append(f"方法 {label} 缺 {field}（" + GUIDE + "补齐，缺了就不可证）")
    return issues


def _method_issues(m: Any, i: int, seen: set[str]) -> list[str]:
    """单条方法：id 唯一 / steps≥2 / title·when·output·falsifier 必填。"""
    issues: list[str] = []
    if not isinstance(m, dict):
        return [f"第 {i} 条方法不是对象（" + GUIDE + "改写成对象）"]
    mid = str(m.get("id") or "").strip()
    if not mid:
        issues.append(f"第 {i} 条方法缺 id（" + GUIDE + "给唯一 id（M1…））")
    elif mid in seen:
        issues.append(f"方法 id 重复：{mid}（" + GUIDE + "改成唯一 id）")
    else:
        seen.add(mid)
    steps = m.get("steps")
    if not isinstance(steps, list) or len(steps) < 2:
        issues.append(f"方法 {mid or i} 的 steps 至少两步（" + GUIDE + "写清怎么走）")
    issues.extend(_method_field_issues(m, mid or i))
    return issues


def validate_methods(doc: Any) -> list[str]:
    """方法论库形状校验（判据面：id 唯一 / steps 非空 / output 与 falsifier 必填）。"""
    issues: list[str] = []
    if not isinstance(doc, dict) or str(doc.get("schema") or "") != METHODS_SCHEMA:
        return ["方法论库 schema 不匹配（" + GUIDE + "需要 " + METHODS_SCHEMA + "）"]
    methods = doc.get("methods")
    if not isinstance(methods, list) or not methods:
        return ["方法论库缺 methods（" + GUIDE + "至少一条方法）"]
    seen: set[str] = set()
    for i, m in enumerate(methods, 1):
        issues.extend(_method_issues(m, i, seen))
    return issues


def _topic_en(topic: str) -> str:
    """英文检索词用的主题形态：ASCII 原样，含 CJK 时退化为词形（去空白）。"""
    ascii_part = "".join(ch if ord(ch) < 128 else " " for ch in topic).split()
    return " ".join(ascii_part) if ascii_part else topic.replace(" ", "-")


def _topic_key(topic: str) -> str:
    """仓内 grep 用的主题键：取首个词（CJK 取前 4 字），避免正则里出现空格。"""
    words = topic.split()
    if not words:
        return topic
    head = words[0]
    return head if len(head) <= 24 else head[:24]


def _expand(template: str, topic: str, topic_en: str, key: str) -> str:
    return (template.replace("{topic_en}", topic_en or topic)
                    .replace("{topic_key}", key)
                    .replace("{topic}", topic))


def _picked_methods(methods: list[str] | None, known: dict[str, Any]) -> list[str]:
    """本次要用的方法 id 序列；出现未知 id 即拒（消息含可用 id）。"""
    picked = methods if methods is not None else list(_METHOD_ORDER)
    unknown = [m for m in picked if m not in known]
    if unknown:
        raise ValueError("未知方法 id：" + ", ".join(unknown) + "（" + GUIDE +
                         "可用 " + ", ".join(sorted(known)) + "）")
    return picked


def _build_slices(topic: str, topic_en: str, key: str, picked: list[str],
                  depth: int) -> list[dict[str, Any]]:
    """按 depth 取切片面，逐片展开检索词/方法论/证据与证伪条件。"""
    # 纯 CJK 主题没有可靠英文译法：英文检索词标记为「需人补」，不编造译名
    en_is_derived = any(ord(ch) < 128 and ch.isalnum() for ch in topic)
    slices: list[dict[str, Any]] = []
    for sl in SLICES[:_DEPTH_N[depth]]:
        use = [m for m in sl["methods"] if m in picked]
        if not use:
            continue
        slices.append({
            "id": sl["id"], "title": sl["title"],
            "question": _expand(sl["q"], topic, topic_en, key),
            "terms": {"zh": [_expand(t, topic, topic_en, key) for t in sl["terms_zh"]],
                      "en": [_expand(t, topic, topic_en, key) for t in sl["terms_en"]],
                      "ops": [_expand(t, topic, topic_en, key) for t in sl["ops"]],
                      "en_needs_human": not en_is_derived},
            "methods": use,
            "evidence_owed": list(sl["evidence"]),
            "falsifier": _expand(sl["falsifier"], topic, topic_en, key),
        })
    return slices


def _build_paths(picked: list[str], slices: list[dict[str, Any]],
                 known: dict[str, Any]) -> list[dict[str, Any]]:
    """方法论路径：按固定顺序取「本次选中且在切片里出现」的方法，逐条展开。"""
    paths: list[dict[str, Any]] = []
    for order, mid in enumerate([m for m in _METHOD_ORDER if m in picked
                                 and any(m in s["methods"] for s in slices)], 1):
        m = known[mid]
        paths.append({"order": order, "method": mid, "title": str(m["title"]),
                      "when": str(m["when"]),
                      "steps": list(m["steps"]), "output": str(m["output"]),
                      "falsifier": str(m["falsifier"])})
    return paths


def _domain_block(root: str, pack_ids: list[str] | None) -> dict[str, Any] | None:
    """域包组合面的只读投影（未给 pack_ids → None）。"""
    if not pack_ids:
        return None
    from core import method_pack as mp
    composed = mp.compose([mp.load_pack(root, pid) for pid in pack_ids])
    return {"packs": composed["packs"],
            "expert_moves": composed["expert_moves"],
            "evidence_standards": composed["evidence_standards"],
            "common_failures": composed["common_failures"]}


def plan(topic: str, depth: int = 2, methods: list[str] | None = None,
         root: str = ".", pack_ids: list[str] | None = None) -> dict[str, Any]:
    """主题 → 研究计划（切片 + 检索词 + 方法论路径 + 证据台账）。纯函数、确定性。"""
    text = str(topic or "").strip()
    if not text:
        raise ValueError("缺主题（" + GUIDE + "用法：nf cognition plan \"<主题>\"）")
    if depth not in DEPTHS:
        raise ValueError(f"depth 只接受 {DEPTHS}（" + GUIDE + "1=快扫3片 / 2=标准5片 / 3=全7片）")
    lib = load_methods(root)
    known = {str(m["id"]): m for m in lib["methods"]}
    picked_methods = _picked_methods(methods, known)
    topic_en = _topic_en(text)
    key = _topic_key(text)
    slices = _build_slices(text, topic_en, key, picked_methods, depth)
    if not slices:
        raise ValueError("方法过滤后没有可执行的切片（" + GUIDE + "至少保留一个切片所需的方法）")
    paths = _build_paths(picked_methods, slices, known)
    domain = _domain_block(root, pack_ids)
    return {"schema": SCHEMA, "topic": text, "depth": depth,
            "topic_en": topic_en, "topic_key": key,
            "domain": domain,
            "slices": slices, "paths": paths,
            "ledger": {"columns": ["claim", "source", "strength", "falsifier", "status"],
                       "strength_scale": ["实测", "一手条款", "一手代码", "推测", "未证"],
                       "rule": "strength=未证 的条目不得进结论；每条 claim 必须有 falsifier"},
            "checklist": ["每个切片的 question 都有来源回答（缺则写未证）",
                          "每条主张落到 ledger 一行（来源 + 强度 + 证伪条件）",
                          "边界片的反例跑过或写明为何不能跑",
                          "量级片的数字带测量口径与基线",
                          "收口建议含触发条件与回滚条件"],
            "note": "这是**计划**不是结论：切片决定钻哪些面，方法论决定怎么钻；"
                    "结论必须回填 ledger 且 strength≠未证"}
