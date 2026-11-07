"""第二内容链（横向对比），复用判据词表与类型系统。

frame -> matrix -> synthesis(claims)，并把 synthesis 输出接到纵向链的 claims 入口。
目标是证明：同一套 8 个判据原语不需要新增，就能描述第二条完全不同的思想链。
"""

from __future__ import annotations

import re
from pathlib import Path

from . import json_asset
from . import schema_compat as jsonschema
from .criteria_lexicon import CHECK, CONCRETE, EVID, PRIMITIVES, frac

BASE = Path(__file__).parent
SCHEMA = json_asset.load(BASE / "cognition_method.schema.json")

FRAME = {
    "schema": "nf/comparison-frame/1",
    "objects": [
        {"id": "O1", "name": "西幻生存流"},
        {"id": "O2", "name": "校园情感流"},
        {"id": "O3", "name": "技术文档流"},
    ],
    "dimensions": [
        {"id": "D1", "name": "生存压力", "check": "check1"},
        {"id": "D2", "name": "经济闭环", "check": "check2"},
        {"id": "D3", "name": "失败成本", "check": "check3"},
    ],
}

GOOD_CELLS = [
    {
        "object": "O1",
        "dimension": "D1",
        "value": "每10分钟消耗",
        "value_kind": "numeric",
        "evidence": "P03 §1",
        "check": "check1",
    },
    {
        "object": "O1",
        "dimension": "D2",
        "value": "3 条经济回路",
        "value_kind": "numeric",
        "evidence": "P03 §5",
        "check": "check2",
    },
    {
        "object": "O1",
        "dimension": "D3",
        "value": "死亡成本=遗物丢失",
        "value_kind": "condition",
        "evidence": "P03 §6",
        "check": "check3",
    },
    {
        "object": "O2",
        "dimension": "D1",
        "value": "每章1次考试压力",
        "value_kind": "numeric",
        "evidence": "NF-1 §2",
        "check": "check1",
    },
    {
        "object": "O2",
        "dimension": "D2",
        "value": "0 条经济回路",
        "value_kind": "numeric",
        "evidence": "NF-1 §5",
        "check": "check2",
    },
    {
        "object": "O2",
        "dimension": "D3",
        "value": "失败成本=关系破裂",
        "value_kind": "condition",
        "evidence": "NF-1 §6",
        "check": "check3",
    },
    {
        "object": "O3",
        "dimension": "D1",
        "value": "0 生存压力",
        "value_kind": "numeric",
        "evidence": "P90 §1",
        "check": "check1",
    },
    {
        "object": "O3",
        "dimension": "D2",
        "value": "0 经济回路",
        "value_kind": "numeric",
        "evidence": "P90 §2",
        "check": "check2",
    },
    {
        "object": "O3",
        "dimension": "D3",
        "value": "失败成本=返工",
        "value_kind": "condition",
        "evidence": "P90 §3",
        "check": "check3",
    },
]
GOOD_MATRIX = {"schema": "nf/comparison-matrix/1", "cells": GOOD_CELLS}

GOOD_CLAIMS = {
    "schema": "nf/claims/1",
    "claims": [
        {
            "id": "C1",
            "text": "西幻生存流的生存压力最高（每10分钟消耗）",
            "source": "O1:D1",
            "source_kind": "cell",
            "tradeoff": "tradeoff",
        },
        {
            "id": "C2",
            "text": "技术文档流无经济闭环，换来确定性",
            "source": "O3:D2",
            "source_kind": "cell",
            "tradeoff": "tradeoff",
        },
        {
            "id": "C3",
            "text": "三类产物的失败成本不可直接比较",
            "source": "O2:D3",
            "source_kind": "cell",
            "tradeoff": "incomparable",
        },
    ],
}

BAD = (
    {"schema": "nf/comparison-frame/1", "objects": [], "dimensions": []},
    {"schema": "nf/comparison-matrix/1", "cells": []},
    {"schema": "nf/claims/1", "claims": []},
)

GAMING_CELLS = [
    {"object": o, "dimension": d, "value": "好", "evidence": "看起来没问题", "check": "check1"}
    for o in ("O1", "O2", "O3")
    for d in ("D1", "D2", "D3")
]
GAMING = (
    FRAME,
    {"schema": "nf/comparison-matrix/1", "cells": GAMING_CELLS},
    {
        "schema": "nf/claims/1",
        "claims": [
            {
                "id": "C1",
                "text": "整体不错",
                "source": "X1:Y1",
                "source_kind": "cell",
                "tradeoff": "tradeoff",
            }
        ],
    },
)


def validate_def(name: str, payload: dict) -> bool:
    sub = {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"}
    return not list(jsonschema.Draft202012Validator(sub).iter_errors(payload))


def dim_of(source: str) -> str:
    m = re.search(r"D\d+", source)
    return m.group(0) if m else ""


def evaluate(name: str, frame: dict, matrix: dict, claims: dict) -> dict:
    objs, dims, cells = frame["objects"], frame["dimensions"], matrix["cells"]
    cl = claims["claims"]
    cell_keys = {(c["object"], c["dimension"]) for c in cells}
    cell_by_key = {(c["object"], c["dimension"]): c for c in cells}
    expected = {(o["id"], d["id"]) for o in objs for d in dims}
    covered_dims = {dim_of(c.get("source", "")) for c in cl} & {d["id"] for d in dims}

    m = {
        "object_count": len(objs),
        "dimension_count": len(dims),
        "object_distinctness": frac(
            objs, lambda o: sum(1 for x in objs if x["name"] == o["name"]) == 1
        ),
        "dimension_distinctness": frac(
            dims, lambda d: sum(1 for x in dims if x["name"] == d["name"]) == 1
        ),
        "cell_coverage": round(len(cell_keys & expected) / len(expected), 3) if expected else 0.0,
        "evidence_anchor_rate": frac(cells, lambda c: bool(EVID.search(c["evidence"]))),
        "value_concreteness": frac(cells, lambda c: bool(CONCRETE.search(c["value"]))),
        "check_ref_rate": frac(cells, lambda c: bool(CHECK.search(c["check"]))),
        "claim_coverage": round(len(covered_dims) / len(dims), 3) if dims else 0.0,
        "synthesis_evidence": frac(
            cl,
            lambda c: bool(
                EVID.search(cell_by_key.get(tuple(c["source"].split(":")), {}).get("evidence", ""))
            ),
        ),
        "tradeoff_declared": frac(
            cl, lambda c: c.get("tradeoff") in {"tradeoff", "dominant", "incomparable"}
        ),
        "claim_linkage": frac(cl, lambda c: tuple(c["source"].split(":")) in cell_keys),
    }
    ok = all(
        [
            m["object_count"] >= 2,
            m["dimension_count"] >= 2,
            m["object_distinctness"] == 1.0,
            m["dimension_distinctness"] == 1.0,
            m["cell_coverage"] >= 0.995,
            m["evidence_anchor_rate"] >= 0.875,
            m["value_concreteness"] >= 0.995,
            m["check_ref_rate"] >= 0.995,
            m["claim_coverage"] >= 0.995,
            m["synthesis_evidence"] >= 0.875,
            m["tradeoff_declared"] >= 0.995,
            m["claim_linkage"] >= 0.995,
        ]
    )
    print(
        "[{}] {} -> {}".format(
            name, " ".join("{}={}".format(*kv) for kv in m.items()), "PASS" if ok else "FAIL"
        )
    )
    return m


if __name__ == "__main__":
    for label, bundle in [
        ("GOOD", (FRAME, GOOD_MATRIX, GOOD_CLAIMS)),
        ("BAD", BAD),
        ("GAMING", GAMING),
    ]:
        io = all(
            [
                validate_def("comparison_frame", bundle[0]),
                validate_def("comparison_matrix", bundle[1]),
                validate_def("claims", bundle[2]),
            ]
        )
        print(f"[{label}] io={io}")
        evaluate(label, *bundle)

    used = {
        "count",
        "uniqueness",
        "coverage",
        "evidence_anchor",
        "concreteness",
        "check_ref",
        "disposition",
        "linkage",
    }
    print(f"[VOCABULARY] used={len(used)} new={sorted(used - PRIMITIVES)}")

    compose = {
        "schema": "nf/causal-map/1",
        "records": [
            {
                "claim": "C1",
                "mechanism": "每10分钟消耗 → 生存压力上升",
                "evidence": "P03 §1",
                "confounder": "资源上限未触发",
                "counterfactual": "移除消耗后 t41 应失败",
                "confidence": "high",
            },
            {
                "claim": "C2",
                "mechanism": "无经济回路 → 确定性上升",
                "evidence": "P90 §2",
                "confounder": "需求缺失或阈值冲突",
                "counterfactual": "加入经济回路后 t42 应失败",
                "confidence": "medium",
            },
            {
                "claim": "C3",
                "mechanism": "失败成本 → 关系破裂或返工",
                "evidence": "NF-1 §6",
                "confounder": "输入缺失或阈值冲突",
                "counterfactual": "移除关系状态后 t43 应失败",
                "confidence": "low",
            },
        ],
    }
    print(
        "[COMPOSE horizontal→vertical] claims={} causal={}".format(
            validate_def("claims", GOOD_CLAIMS), validate_def("causal_map", compose)
        )
    )
