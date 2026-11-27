"""core.import_adapter 私有实现分片 2/2（对外只经 core.import_adapter 门面导入）： 等"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from core.ir import IRDocument, IRLayer, IRModule

from ._part1 import (
    _RE_COMMENT_LAYER,
    _RE_DESC_CCV3,
    Ccv3ParseResult,
    _entry_to_module,
    _record_asset,
)


def _place_module(m: IRModule, comment: str, layer_map: dict,
                  layers: list, extra: list) -> None:
    """把已解析模块归层：有层名则建层/入层，否则入 extra（不静默丢）。"""
    if not m.layer:
        extra.append(m)
        return
    if m.layer not in layer_map:
        lm = _RE_COMMENT_LAYER.match(comment)
        layer_map[m.layer] = IRLayer(id=m.layer, name=lm.group(2).strip() if lm else m.layer)
        layers.append(layer_map[m.layer])
    layer_map[m.layer].modules.append(m)


def _skip_entry(full_id: str, seen: set) -> bool:
    """world 侧去重判据：无 id 或已在册即跳过。"""
    return not full_id or full_id in seen


@dataclass(frozen=True)
class _IngestContext:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    seen: set
    warnings: list
    layer_map: dict
    layers: list
    extra: list
    asset_refs: dict
    dedupe: bool


def _ingest_entries(entries: list, opts: _IngestContext) -> None:
    """把一批条目归层/记资产（chara 与 world 两处同构；dedupe=True 时按 full_id 去重）。"""

    seen = opts.seen
    warnings = opts.warnings
    layer_map = opts.layer_map
    layers = opts.layers
    extra = opts.extra
    asset_refs = opts.asset_refs
    dedupe = opts.dedupe
    for e in entries:
        keys = e.get("keys") or []
        full_id = str(keys[0]) if keys else str(e.get("name") or "")
        if dedupe and _skip_entry(full_id, seen):
            continue
        if _record_asset(e, full_id, asset_refs, seen):
            continue
        m = _entry_to_module(e, seen, warnings)
        if m is None:
            continue
        _place_module(m, str(e.get("comment") or ""), layer_map, layers, extra)


def parse_ccv3(chara: dict, world: Optional[dict] = None) -> Ccv3ParseResult:
    """chara_card_v3 dict（+可选独立 world dict）→ 叙事型 IR 骨架。

    校验：spec == chara_card_v3 且 spec_version 非空（不符 → ValueError）。
    结构还原：character_book.entries[]（+ world.entries[] 补充）逐条 → IRModule，
    按 comment `NF 层 {id} · {name}` 归层、`NF 层外模块` 归 extra、资产条目还原
    asset_refs；无 NF 层位注释的外部条目归 extra（不静默丢）。
    chara 顶层字段（personality/scenario 等）透传 chara_meta，不冒充语义理解。
    """
    if not isinstance(chara, dict):
        raise ValueError("chara 应为 dict（chara_card_v3 JSON 对象）")
    if chara.get("spec") != "chara_card_v3":
        raise ValueError(f"spec 应为 chara_card_v3，实际：{chara.get('spec')!r}")
    if not chara.get("spec_version"):
        raise ValueError("缺少 spec_version（chara_card_v3 必填）")

    warnings: List[str] = []
    name = str(chara.get("name") or "")
    desc = str(chara.get("description") or "")
    # v3 真形状：内容字段在 `data` 内（外部实证 2026-09-21）；v2 旧形状仍兼容（顶层字段）
    body_raw = chara.get("data")
    body: Any = body_raw if isinstance(body_raw, dict) else chara
    cb = body.get("character_book") or chara.get("character_book") or {}
    entries = list(cb.get("entries") or [])

    # pipeline 字段：chara description 若为 NF 导出格式则回填（round-trip 对称）
    pipeline_id = pipeline_name = ""
    mdesc = _RE_DESC_CCV3.match(desc)
    if mdesc:
        pipeline_name = mdesc.group(1).strip()
        pipeline_id = mdesc.group(2).strip()
    else:
        warnings.append("description 非 NF 装配产物格式，pipeline 字段留空")

    seen: set = set()
    layers: List[IRLayer] = []
    extra: List[IRModule] = []
    asset_refs: dict = {}
    layer_map: dict = {}

    # chara entries
    _ingest_entries(
        entries,
        opts=_IngestContext(
            seen=seen,
            warnings=warnings,
            layer_map=layer_map,
            layers=layers,
            extra=extra,
            asset_refs=asset_refs,
            dedupe=False,
        ),
    )
    # world entries 补充（chara 内嵌 character_book 与独立 world 通常同源，
    # 重复条目按 full_id 去重——不重复入 IR）
    if world is not None:
        if not isinstance(world, dict):
            raise ValueError("world 应为 dict")
        _ingest_entries(
            list(world.get('entries') or []),
            opts=_IngestContext(
                seen=seen,
                warnings=warnings,
                layer_map=layer_map,
                layers=layers,
                extra=extra,
                asset_refs=asset_refs,
                dedupe=True,
            ),
        )

    if not name:
        warnings.append("chara 缺少 name，IR title 留空")
    ir = IRDocument(
        type="narrative", title=name,
        pipeline_id=pipeline_id, pipeline_name=pipeline_name,
        layers=layers, extra_modules=extra,
        asset_refs=asset_refs, asset_missing=[],
        warnings=warnings,
        meta={"adapter_in": "parse_ccv3",
              "source": "chara_card_v3"
                        + (" + world" if world is not None else ""),
              "spec": chara.get("spec"),
              "spec_version": chara.get("spec_version")},
    )
    chara_meta = {
        "chara": {k: v for k, v in chara.items()
                  if k not in ("character_book",)},
        "world_name": (world or {}).get("name") if world else None,
    }
    return Ccv3ParseResult(ok=True, ir=ir, chara_meta=chara_meta,
                           warnings=warnings)
