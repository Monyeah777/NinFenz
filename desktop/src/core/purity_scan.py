"""42 M3：架构纯度体检（verify check27 · 文档级 grep 断言族）。

每波收口前跑纯度体检，首批四规则（文档级，纯 stdlib）：

R1 层级越界/端壳残留：协议真相源（01/02）不得再出现 android/APK/src/ui/Kivy
    （APK 线裁决 #16 移除后的残留扫描）。
R2 私货/可变物：协议层文档（01/02/06/07）不得出现机器不可复现内容
    （绝对盘符路径 / 临时目录 / TODO-FIXME-XXX-TBD 占位）。
R3 冗余标题：同文档内重复章节标题（同一标题文本出现 >1 次）。
R4 错误信息即微型文档：desktop/src/core 全部 raise 消息须含修复/指引语
    （应为/先/请/须/必填/参考/示例/§ 等动作或出处词——标准批 A #12）。
R5 import 面越界：desktop/src/core + scripts 的第三方 import 面必须**登记**——
    只许 stdlib / 本地模块 / HARD_ALLOW 登记的硬依赖；其余第三方必须**软导入**
    （try/except ImportError 守卫）且在 SOFT_IMPORTS 登记理由；已退役端壳的存量残留
    在 IMPORT_RESIDUE 登记（**WARN 挂账**，带裁决指针，不判死但不得隐身）。
    （内部差距：CONTRIBUTING §4.2「core 零第三方依赖」是成文红线，此前**零判据**。）
R6 危险 sink 面：desktop/src/core + scripts 不得出现**动态执行 / shell 命令 / 不安全
    反序列化 / **不可逆的递归删除**（eval / exec / __import__ / os.system / os.popen /
    subprocess(shell=True) / pickle.load(s) / marshal.loads / yaml.load /
    shutil.rmtree / os.remove / os.rmdir，以及**方法名类**的 `x.unlink()`——确需使用须在
    SINK_ALLOW 登记并写明理由
    （放行可审计；list 参数调用 subprocess 不受限）。
    （内部差距：安全兜底此前**零判据**——NF 只靠人读与本仓之外的 linter；实测 sink 面
    仅 1 处受控 `__import__`，故本条落地即零返工。）
    2026-09-24 渗透 F-10 补：递归删除面此前**不在类目内**，于是 `NF_TEST_HOME=~`
    驱动的静默 `shutil.rmtree` 无判据可拦。现纳入类目（基线 1→5，放行点在册可审计）。
R7 抽象阶梯归属与越界：`protocol/LAYERS.json` 是阶梯唯一真源，语义判据实现在
    `core/layer_model.py`（L1 真源在位 / L2 归属互斥 / L3 接口面子集 / L4 依赖向下无环 /
    L5 入口非真源 / L6 引擎不反向 import 入口 / L7 退役阶不被依赖 / L8 判据可解析 /
    L9 豁免诚实 / L10 生成区==实时渲染）。本规则只做**接线**：把阶梯体检的 issues 汇入
    纯度报告——落地依据是端壳退役的教训（一阶可以整体退役，当时零判据，只能事后补）。
    分工遵 ADR-0003：形状类断言进 protocol/assertions.json，语义判据留代码。

check27 自身用变异注入验证捕获力（mutation testing：test_purity_scan 对
每规则注入典型违规样本，断言可被捕获——「check 的 check」）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

from core import conformance_scan as csc
from core import disk_cache

# 导入闭包指纹：由调用方算（持久层不再反向依赖解析层，见 2026-09-29 拆环）
from core import import_graph as _ig

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade
from core._purity_scan import _part2 as _live_part2

# 实现分片：原模块逻辑在私有子包 _purity_scan/，本门面按原模块面显式再导出（API 不变）。
from core._purity_scan._part1 import (
    _ACTION,
    _DOC_FACTS_CACHE,
    _DOC_FACTS_MAX,
    _END_SHELL,
    _FACTS_CACHE,
    _FACTS_CACHE_MAX,
    _FACTS_READ_MISS,
    _HEAD,
    _NEEDS_AST,
    _PRIVATE,
    DANGEROUS_CALLS,
    HARD_ALLOW,
    IMPORT_RESIDUE,
    IMPORT_SCAN,
    METHOD_SINKS,
    PROTO_DOCS,
    SINK_ALLOW,
    _ast_facts,
    _doc_facts,
    _facts_for,
    _pack_facts,
    _packed_ok,
    _try_guards_import,
    _unpack_facts,
)
from core._purity_scan._part2 import (
    _FILE_FINDINGS,
    _FILE_FINDINGS_MAX,
    OWN_PATTERNS,
    _cache_key,
    _env_fingerprint,
    _file_findings,
    _is_local,
    _scan_impl,
    patterns,
    scan,
)

_install_live_facade(__name__, {
    "SOFT_IMPORTS": _live_part2,
})

# R8：核心文面去叙述（域中立）实现独立成件 core/domain_neutral.py；分片见同目录 _purity_scan/ 私有子包。
