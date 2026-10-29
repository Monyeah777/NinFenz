"""单一真源：方法节点共用的确定性判据词表（暗雷十三的修法）。

纪律：节点不得本地重定义下列词表名，只能 `from criteria_lexicon import ...`。
`drift_scan()` 扫描节点文件，发现本地重定义即报 issue。
纯标准库，不落公开仓。
"""

from __future__ import annotations

import re
from pathlib import Path

LEXICON_VERSION = "3"  # v2 -> v3：additive 增加 invariant 原语（V1 只增不删）

#: 判据原语词表（节点 criteria.primitive 只能取这里的值）
PRIMITIVES = {
    "coverage",
    "concreteness",
    "check_ref",
    "evidence_anchor",
    "linkage",
    "disposition",
    "uniqueness",
    "count",
    "invariant",
}

#: 因果方向链
ARROW = re.compile(r"→|->|导致|经由|通过|=>")
#: 可检引用（测试号 / 门禁 / schema / 字段+操作符）
CHECK = re.compile(r"t\d+|check\d+|M\d+|schema|门禁|测试|#|>=|<=|[<>]=")
#: 证据锚
EVID = re.compile(r"§|M\d+|测试|行号|观测|observation")
#: 具体条件（触发/混杂共用一个词表——这正是暗雷十三的修法）
CONCRETE = re.compile(r"\d|若|当|如果|=|≥|≤|空|缺失|未|重复|越界|为0|为 0|冲突|阈值|上限")
CONF = CONCRETE
#: 空话
VAGUE = {"其他原因", "其他", "未知", "无"}
#: 裁决词表
DISPOSITIONS = {"refuted", "survived", "needs_evidence"}
#: 置信度词表
CONFIDENCE = {"high", "medium", "low"}
#: 交付物标记
DELIVERABLE = re.compile(r"产出|交付|输出|产物|artifact|deliverable|→|路径|文件")
#: 可检形式
CHECKABLE_FORM = re.compile(r"表|清单|状态机|公式|schema|路径|文件|测试|门禁|验证")

_LEXICON_NAMES = (
    "ARROW",
    "CHECK",
    "EVID",
    "CONCRETE",
    "CONF",
    "VAGUE",
    "DISPOSITIONS",
    "CONFIDENCE",
    "DELIVERABLE",
    "CHECKABLE_FORM",
    "PRIMITIVES",
)


def frac(items, pred) -> float:
    """满足 pred 的比例；空集记 0。"""
    return round(sum(1 for x in items if pred(x)) / len(items), 3) if items else 0.0


def coverage_rate(hit_ids, universe) -> float:
    """hit_ids 覆盖 universe 的比例。"""
    universe = set(universe)
    return round(len(set(hit_ids) & universe) / len(universe), 3) if universe else 0.0


def drift_scan(paths) -> list[str]:
    """扫节点文件是否本地重定义了词表名（应 import，不应复制）。"""
    issues: list[str] = []
    for p in paths:
        text = Path(p).read_text(encoding="utf-8")
        for name in _LEXICON_NAMES:
            if re.search(rf"^{name}\s*=", text, re.M):
                issues.append(f"{Path(p).name}: 本地重定义 {name}（应 import criteria_lexicon）")
    return issues
