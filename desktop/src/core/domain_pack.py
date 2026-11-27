"""域包工厂：从一个「域规格」生成整套**过门禁**的社区域包（AI 品类清单工程的机制面）。

为什么要有工厂：清单是 100 大类 / 1200 细分。手工复制 100 遍 = 每包漂移一处就静默破门禁。
工厂把「域包必须满足的一切」写成可复算的生成规则，并把**不可协商项**固化成断言：

- 唯一性：独占类别（R2）/ 模块文件名裸 token（check14 ⑤c）/ 管线 id（check14 ⑧）全局唯一；
- 登记三要件：protocol.yaml + 02 §8 在册（含 `模块（N）`）+ registry protocols[] 投影；
- 资产供应链：assets/*.md 头（`nf-asset`）与 provenance.json 双源一致（check23）；
- 概念图健康：无环 / 无悬空 / 边有溯源 / 层位合法 / 别名唯一 / 分支完备（check32）；
- 产出形态：`outputs/INDEX.json` 声明 T2/T3/T4 面，其中**可机验占比 = 100%**（≥95% 门槛）；
  且必有一个 **T4 可复算面**（core/domain_metrics 重算并与在盘报告逐字段比对）。

内容 vs 机制：**内容**（12 条细分的定义 / 权威锚 / 可机验判据 / 失效模式）来自域规格文件
（作者侧输入，内部档案，不入公开仓）；**机制**（本模块）保证内容的形态与可验证性。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# 依赖面：实现在 _domain_pack 子包；本行履约原模块对 core 的 import 边（勿删）。
# 读点：规格/登记读取在 _domain_pack._io，仍走 json_doc.loads / json_doc.load（N11）。
from core import atomic_write, domain_metrics, json_doc, protocol_projection, registry_sync

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
from core import conformance_scan as csc
from core import io_types as _iot

from ._domain_pack._alloc import (
    _slug,
    _yaml_scalar,
    allocate,
    dump_yaml,
)
from ._domain_pack._catalog import (
    _reachable_first,
    _std_cell,
    _std_layer,
    _std_probe_date,
    _std_reachable,
    authenticity,
    bind_standard,
    bind_support,
    bindings_for,
    bindings_full,
    concept_index,
    spec_issues,
)
from ._domain_pack._const import (
    _STD_BY_CODE,
    _STD_KEYWORD,
    _STD_SECTION_DEFAULT,
    _STD_SUPPORT_KEYWORD,
    _STD_SUPPORT_SECTION,
    AUTHENTICITY_THRESHOLD,
    BINDING_REL,
    DENSITY_THRESHOLD,
    DOC02_REL,
    MANIFEST_REL,
    PIPELINE_POOL,
    REACHABLE_RATIO_THRESHOLD,
    REGISTRY_REL,
    SCAN_INPUTS,
    SPEC_DIR,
    STANDARDS_REL,
    SUB_COUNT,
    SYSTEM_CARD_SCHEMA_JSON,
    VERIFY_REL,
)
from ._domain_pack._doc_concept import (
    concept_graph_md,
)
from ._domain_pack._doc_domain import (
    _event_names,
    domain_spec_md,
    standards_md,
)
from ._domain_pack._doc_module import (
    module_md,
    pipeline_md,
)
from ._domain_pack._doc_pack import (
    protocol_yaml,
    provenance_json,
    readme_md,
)
from ._domain_pack._io import (
    _read_json,
    _read_json_raw,
    _write_text_retry,
    load_spec,
    module_stems,
    standards_catalog,
    used_pipeline_ids,
)
from ._domain_pack._json_faces import (
    domain_spec_json,
    domain_spec_schema,
    output_index,
    report_schema,
    system_card,
)
from ._domain_pack._manifest import (
    _scan_impl,
    _write_binding_table,
    manifest_entry,
    manifest_verify,
    update_manifest,
)
from ._domain_pack._plan import (
    _append_domain_list,
    _append_section02,
    _prune_stale,
    _register_protocols,
    build,
    plan,
    verify,
)


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """check32 子扫描入口：域包名录机检（无名录即中性通过）。

    派生结果按**输入内容指纹**缓存（输入面见 `SCAN_INPUTS`）；**冷进程也走这层**（2026-09-29
    实测：宽面指纹在同一只读作用域内近乎白拿，而重算这条派生账贵得多；见 `quality_depth_scan.scan`）。
    """
    return csc.memo_pair("domain-pack-scan", SCAN_INPUTS, _scan_impl, root,
                         code_modules=("core.domain_pack",))
