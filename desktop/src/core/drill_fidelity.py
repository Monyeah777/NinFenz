"""演练保真度**量化**（动态可执行面 · 顶层化：drill 全绿 / 回合级回放 / 保真度量化）。

为什么需要：既有两套演练此前只有「逐例 PASS/FAIL」的文本结论——**没有一个数**。于是
「保真度」无法比较、无法回归、无法作为发布判据（顶层化实测：全仓 `保真` 一词只出现在
`import_adapter` 的「高保真重建」，与演练无关）。

本模块把演练结果压成**保真度数字**并给判据：

- **执行演练保真度**：逐个用例集跑 `execution_drill.run_case`，判「捕获无漏报
  （expect_captured ⊆ hits）+ guard 无误报（无期望命中时不得有命中）」，保真度 = 通过例数 / 总例数。
- **回合级回放保真度**：对 `fixtures/execution/rounds/*.json` 逐个回放，判实测 verdict
  是否复现样本声明（`good → conformant` / `bad → non-conformant`），保真度 = 复现数 / 样本数。
- **真实语料命中裁定**（2026-10-20 加）：把唯一真实战例 `docs/完整版样本_西幻生存流P03.md`
  逐非空行回放 `execution_drill`，命中必须逐条给出 TP/FP 裁定与依据（裁定表写在待裁定回合样本的
  `real_corpus.adjudications` 里）；**命中未裁定 / TP 命中消失 /
  裁定声称现存而实测已消失** 都判 FAIL。
  这条判据的动机：74/74 的 drill 全是自造样本（写样本的人与写实现的人互证），
  保真度 100% 是**自指绿**；
  真实语料上的命中精度必须单列成数（`metrics.hits / tp / fp`）。
- **待裁定样本**（`verdict/label_status = pending`）：不参与「声明 vs 实测」分子分母
  （未裁定就无声明可复现），
  但**必须解析出回合标记**（parse 失败 ⇒ 裁定前提不成立，判 FAIL），其命中同样须逐条裁定。
- **正例对照**（2026-10-20 加）：真实语料 hits 从 5 降到 0 有两种解释——语料干净（好）或
  判据被改弱到什么都不报（坏）。对原版 P03 逐份注入**已知违规**生成变体，要求「注入行必中期望规则 +
  其它行零附带命中」，同时「原版必须仍 0 命中」；变体须逐字节等于「语料+注入」（防夹具漂移）。
- **判据**：任一例不达标 → FAIL（保真度必须 100%）；**找不到用例/样本 → FAIL**（标准不得无载体）。

纪律：纯标准库；只读（唯 `write()` 落盘度量结果供机器消费）；错误消息带修复指引。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from core import atomic_write, json_doc

# 实现分片：原模块逻辑在私有子包 _drill_fidelity/，本门面按原模块面显式再导出（API 不变）。
from core._drill_fidelity._part1 import (
    EXEC_GLOB,
    PENDING,
    POSITIVE_CONTROLS_REL,
    REAL_CORPUS_REL,
    REGISTRY_ROW,
    REPORT_REL,
    ROUND_GLOB,
    SCHEMA,
    VERDICT_MAP,
    _corpus_forward,
    _corpus_live_hits,
    _corpus_meta_problems,
    _exec_sets,
    _pc_case,
    _pc_source,
    _real_corpus_block,
    _registry_ids,
    _round_adjudications,
    _round_sample,
    _round_samples,
    _text_hits,
    positive_controls,
)
from core._drill_fidelity._part2 import (
    _corpus_adjudicate,
    _corpus_reverse,
    _exec_issues,
    _round_issues,
    measure,
    real_corpus,
    scan,
    write,
)

# 读点：契约 JSON 解析一律走 core.json_doc.loads / core.json_doc.load（N11）；实现分片见同目录私有子包。
