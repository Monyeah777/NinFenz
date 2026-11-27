"""pack_combo 私有子模块 _const：常量与真源路径（证书/扫描输入面、缓存上界、组合证书 schema）。

门面 core.pack_combo 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

from typing import Any, Dict

from core import official_core


CERT_REL = "protocol/combo_certificates.json"

CORE13 = list(official_core.CORE_MODULES)   # 单一实现（审计 Z1 F6）


#: 进程级画像缓存（root 绝对路径 → {"prof", "contracts", "by_id", "pub_index", "core_pub"}）。
#: 必要性（实测 2026-09-23）：广度证明要跑 C(N,2)+抽样数千次组合，若每次重解析
#: 235 个模块文档，代价 O(N²·files) 直接跑不完——缓存后单次组合降为纯集合运算。
_CACHE: Dict[str, Dict[str, Any]] = {}

_CACHE_MAX = 32



#: **内容键**派生缓存（键 = 诸输入的内容指纹）。与上面按 root 的 `_CACHE` 互补：
#: 后者由守护**逐请求清空**（保证「写命令之后不读旧值」），前者按**内容**自证——
#: 输入没变 ⇒ 派生结果必然相同；输入一变指纹就变。故它可以跨请求复用，不必清。
#: 收益（实测）：广度证明 ~0.92 s、包画像 0.3–0.5 s，每次重命令都白交一遍。
_CONTENT_CACHE: Dict[Any, Any] = {}

_CONTENT_CACHE_MAX = 32



#: 包画像 / 广度证明的**输入面**（协议声明 + 模块契约 + 核心模块 + 资产台账 + registry）。
INPUT_PATTERNS = ("community/*/protocol.yaml", "community/*/modules/*.md",
                  "04_模块库/*/*.md", "community/*/assets/provenance.json",
                  "desktop/src/core/registry.json")

#: **包画像单独的输入面**：只含 `profiles()` 真正读的那些件（包声明 + 社区模块契约 + 资产台账）。
#: 为什么要与 `INPUT_PATTERNS` 分开（2026-09-29 仪器化实测）：`profiles()` **不读** `04_模块库`
#: ——那是 `_core_contracts` 的面，只有广度证明的闭包需要它——而 `INPUT_PATTERNS` 把它一并算了进来，
#: 于是「改一页 04 模块库正文」会白白重算 **111 个包画像**（守护**逐请求清空按根缓存**，这一笔
#: 让新状态多付 ~50 ms）。收窄是**可判的**：`test_pack_combo.ProfileInputFaceTest` 用读追踪在真
#: 仓库上断言「读到的件 ⊆ 本面」，并在合成树上断言「面外改动不换键、面内改动必换键」。
PROFILE_PATTERNS = ("community/*/protocol.yaml", "community/*/modules/*.md",
                    "community/*/assets/provenance.json")

#: 模块契约面 / 核心契约面各自的输入面（`_module_contracts` / `_core_contracts` 的内容键）。
MODULE_CONTRACT_PATTERNS = ("community/*/modules/*.md",)

CORE_CONTRACT_PATTERNS = ("04_模块库/*/*.md",)

#: 契约解析结果的**内容键缓存**（进程内）。
#: 依据（2026-09-29 实测）：守护**逐请求清空按根缓存**，而这两个函数此前只有按根缓存 ⇒ 每次新内容
# : 状态都要把 235 份社区模块 + 13 份核心模块的 `machine_contract` 围栏重新解析一遍（`_module_contra
# cts`
# : 实测 ~34 ms）。「解析结果只是**这几份正文**的纯函数」——改 `04_模块库` 之外的件时社区契约必然不变
# ，
#: 反之亦然；键即内容 ⇒ 无陈旧面。判据：`test_pack_combo.ContractCacheTest`。
_CONTRACTS_CACHE: Dict[str, Any] = {}

_CONTRACTS_CACHE_MAX = 64



#: **逐组合**判决缓存（进程内）：键 = (参与包名, 本轮**全局见证**)。
#:
#: 依据（实测，2026-09-29）：广度证明要跑 **6910** 次组合、约 **723 ms**（唯一新状态里最大单项），
#: 而「该组合合不合法 + 悬挂/未桥证据」只是「包声明 + 模块契约 + 核心发布集」的纯函数。
#:
#: **为什么见证必须是全局的（别改回「参与包碰得到的模块」那种细键）**：组合闭包会经 `by_id`
#: 拉入**任意第三方包**的模块（`inputs` 依赖），并经 `pub_index` 拉入**任意发布方**的模块
#: （事件闭包）。所以 A+B 的判决依赖**整棵模块契约面**，而不只是 A、B 自己加上它们
#: `references` 点名的模块——细键在跨包闭包上会**静默读到陈旧判决**（假绿）。判据见
#: `test_pack_combo.ComboCacheTest.test_witness_covers_cross_pack_closure`（变异注入）。
#: 取全局后：任一声明/契约一变 ⇒ 全量重算，与无缓存同价，不会假绿。
#: 收益场景（唯一新状态实测）：新增/编辑 `04_模块库` 正文、包内正文、`registry.json` 这类
#: **不改 `machine_contract` 与协议声明**的编辑 ⇒ 见证不变 ⇒ 6910 次组合全命中。
#: 只做进程内一层：6910 条结果落盘不划算（外层 `pack-breadth` 已有跨进程内容缓存）。
_COMBO_CACHE: Dict[Any, Any] = {}

_COMBO_CACHE_MAX = 65536



#: 组合证书形状（自带 JSON Schema 2020-12 子集；用 output_forms 的自家校验器判）
CERT_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "nf-combo/1 组合证书",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema", "packs", "modules", "module_count", "layer_stacks",
                 "dependency_closure", "event_closure", "legal", "digest"],
    "properties": {
        "schema": {"const": "nf-combo/1"},
        "label": {"type": "string", "minLength": 2},
        "note": {"type": "string", "minLength": 4},
        "packs": {"type": "array", "items": {"type": "string", "minLength": 2}},
        "unknown_packs": {"type": "array", "items": {"type": "string"}},
        "extra_modules": {"type": "array", "items": {"type": "string"}},
        "modules": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "module_count": {"type": "integer", "minimum": 1},
        "layer_stacks": {
            "type": "array", "minItems": 1,
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["layer", "modules"],
                      "properties": {
                          "layer": {"type": "string", "minLength": 3},
                          "modules": {"type": "array", "minItems": 1,
                                      "items": {"type": "string", "minLength": 2}}}}},
        "dependency_closure": {
            "type": "object", "additionalProperties": False,
            "required": ["core", "explicit", "dangling"],
            "properties": {"core": {"type": "array"}, "explicit": {"type": "array"},
                           "dangling": {"type": "array", "maxItems": 0}}},
        "event_closure": {
            "type": "object", "additionalProperties": False,
            "required": ["published", "unbridged"],
            "properties": {"published": {"type": "array"},
                           "unbridged": {"type": "array", "maxItems": 0}}},
        "events_unpublished": {"type": "array", "maxItems": 0},
        "assets_borrowed": {"type": "array"},
        "modules_borrowed": {"type": "array"},
        "references_unresolved": {"type": "array", "maxItems": 0},
        "assets_unresolved": {"type": "array", "maxItems": 0},
        "module_missing_contract": {"type": "array", "maxItems": 0},
        "legal": {"const": True},
        "digest": {"type": "string", "pattern": "^[0-9a-f]{32}$"},
    },
}



#: `scan()` 的**真读面**（收窄，2026-09-29 实测）：原来是 `community/**/*`——2191 件，其中
#: **1156 件是 `community/*/outputs/**`（派生产物）**，而本扫描器一件都不读它们（T4 复算是拿包声明 +
#: 模块契约 + 核心契约重算，不读产物）。收窄后同一张面从 2191 件降到 ~1035 件，指纹成本随之下降。
#: 「读盘面 ⊆ 申报输入面」由 `test_conformance_scan.DerivedResultCacheTest` 逐站点守着——少申报
#: 一件就会当场红。
SCAN_INPUTS = ("community/*/protocol.yaml", "community/*/modules/*.md",
               "community/*/assets/provenance.json", "04_模块库/*/*.md",
               "protocol/*.json", "desktop/src/core/registry.json")
