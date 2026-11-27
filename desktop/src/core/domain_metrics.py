"""域功能引擎：把「AI 品类域」的口径变成**可复算的数**（产出形态 T4 面）。

背景（内部差距）：用户清单里 100 个 AI 品类，如果每个域包只产出散文，等于把「AI 域知识」
退化成资料页——NF 的质量函数要求产出**功能性 + 可机验**。本模块提供一族**确定性评测口径**，
每个族对应一类域的真实度量（分类 / 检索 / 抽取 / 生成 / 回归 / 校准 / 一致性 / 排序偏好 /
形式化判定 / 时延成本 / 漂移 / 契约合规），域包各自声明用哪一族 + 输入样例，
门禁用本模块重算产出并与在盘报告逐字段比对（T4 可复算）。

纪律：
- **口径显式**：每个族写明公式与统计口径（判据、边界处理），不默认任何隐含约定；
- **确定性**：纯函数、无墙钟、无随机、四舍五入到固定位数 → 同输入逐字节一致；
- **不夸口**：算的是**样例集上的口径值**，不是模型能力声明；报告里必须带 sample 规模与族名。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple

from core import conformance_scan as csc
from core import json_doc

# 实现分片：原模块逻辑在私有子包 _domain_metrics/，本门面按原模块面显式再导出（API 不变）。
from core._domain_metrics._part1 import (
    DIGITS,
    _auc,
    _flag,
    _num,
    _r,
    _safe_div,
    agreement,
    calibration,
    classification,
    drift,
    exact_judgement,
    extraction,
    generation,
    latency_cost,
    load_rows,
    preference,
    regression,
    retrieval,
)
from core._domain_metrics._part2 import (
    FAMILIES,
    _Rng,
    contract_compliance,
    evaluate,
    rows_to_csv,
    synthesize,
)

# 读点：契约 JSON 解析一律走 core.json_doc.loads / core.json_doc.load（N11）；实现分片见同目录私有子包。
