"""互操作导出面（外部标准净吸收：OpenAPI 3.1 / AsyncAPI 3.0 / in-toto Statement v1 /
SPDX 2.3 / CloudEvents 属性 / RFC 9457 Problem Details）。

内部差距（本波实证）：NF 的**声明面**已经很厚——8 条服务端点契约、43 条事件载荷、
48 条协议层回执（Merkle 单根）、依赖登记面（hard/soft import）——但**没有一条能直接
喂给外部标准工具**的导出面：外部读者只能读 NF 自己的 JSON 形状，无法用 OpenAPI 校验器、
AsyncAPI 代码生成器、in-toto 校验器或 SPDX 扫描器对接。

定位纪律：**纯派生，不新增真源**。所有字段都从既有声明件实时算出，此处绝不引入新的
手工维护值；因此「导出面漂移」在结构上不可能发生——门禁断言的是**覆盖完整 + 形状合法
+ 确定性**（同输入两次导出逐字节一致）。

落点：check33「新面汇总」（不新增 check 序号，ADR-0002）。
"""

# 读点：契约/注册表读入在 _interop._base 里仍走 json_doc.loads（N11）。

from __future__ import annotations

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
import sys as _sys
import types as _types

# 依赖面：逐字保留原模块 import 面（含函数内 core import 的边）——
# 耦合图/纯度面按模块级 import 计算，勿删（见 re-export 说明）。
from core import json_doc
from core import purity_scan as ps
from core import quality_baseline as qb
from core import quality_baseline as _qb
from core import purity_scan as _ps

from ._interop._base import (
    CONTRACT_REL,
    EVENTS_REL,
    EXTERNAL_EVENTS_REL,
    LICENSE_NAME,
    RECEIPTS_REL,
    _DATE_RE,
    _DATE_SOURCES,
    _DEP_ALIAS,
    _HEAD,
    _TYPE_MAP,
    _declared_max_date,
    _pinned_versions,
    _ptr,
    _read_json,
    _schema_for,
)
from ._interop._docs_a import (
    asyncapi_doc,
    intoto_statement,
    openapi_doc,
    sbom_doc,
    slsa_provenance,
)
from ._interop._docs_b import (
    a2a_agent_card,
    c2pa_manifest,
    cid_index,
    cyclonedx_doc,
    decision_surface,
    prov_document,
    vc_document,
)
from ._interop._render import (
    KINDS,
    render,
)
from ._interop._checks import (
    _arr,
    _c2pa_hash,
    _check_a2a,
    _check_asyncapi,
    _check_c2pa,
    _check_cid,
    _check_cyclonedx,
    _check_cyclonedx_deps,
    _check_decision,
    _check_determinism,
    _check_intoto,
    _check_openapi,
    _check_prov,
    _check_prov_relations,
    _check_sbom,
    _check_slsa,
    _check_vc,
    _obj,
    _vc_issuer_ok,
)
from ._interop._verify import (
    summary,
    verify,
)
