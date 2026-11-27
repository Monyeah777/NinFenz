"""决策层端口（机制借鉴一句式：非自回归 typed-decision 模型用 choice / noul / score 三原语
报「候选集上的概率 + argmax」，不做生成、不执行动作）。

为什么 NF 需要这一层：装配/质检/流转的**选择**目前散在规则与人的判断里（选哪些模块、走哪条
管线、这一步该不该继续）。把它们写成**类型化问题**交给决策模型，好处是三件可核验的事：
① 问题与答案有 schema（模型不得自造候选、不得只回一句自然语言）；
② 每个决策都带概率与来源（可审计、可回放）；
③ 模型不可用时**abstained**，绝不用猜测补齐（fail-closed）。

架构纪律（STRATEGY「定内容，不定模型」）：
- 本模块是**端口**：模型在端口之外，换模型不改协议、不改内容资产；
- 门禁只用 `stub`（离线确定性、`calibrated=false`）；真实模型（本地 HTTP 或远程 API）
  一律非门禁任务，且经 `protocol/decision_layer.json` 声明后才可用；
- 纯标准库（`urllib` + `json`），无第三方硬依赖。

用法：
    from core import decision_layer as dl
    req = {"state": "…", "questions": {"pick": {"type": "choice", "options": ["A", "B"]}}}
    out = dl.decide(req, adapter="stub")          # 门禁/CI
    out = dl.decide(req, adapter="systemone-http", endpoint="http://127.0.0.1:8791/v1/systemone")
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from core import json_doc
from core._decision_layer import _part2 as _live_part2

# 实现分片：原模块逻辑在私有子包 _decision_layer/，本门面按原模块面显式再导出（API 不变）。
from core._decision_layer._part1 import (
    DECL_REL,
    PRIMITIVES,
    PROB_TOL,
    RESPONSE_SCHEMA,
    SCHEMA,
    DecideOptions,
    _hits,
    _normalize,
    adapter_ids,
    adapter_spec,
    decision_view,
    fingerprint,
    load_decl,
    normalize_probs,
    request_issue,
    response_issue,
    stub_decide,
)
from core._decision_layer._part2 import (
    _post_json,
    _read_json_response,
    decide,
    openai_json_decide,
    scan,
    summary,
    systemone_decide,
)

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade

_install_live_facade(__name__, {
    "MAX_REMOTE_JSON_BYTES": _live_part2,
})

# 读点：契约 JSON 解析一律走 core.json_doc.loads / core.json_doc.load（N11）；实现分片见同目录私有子包。
