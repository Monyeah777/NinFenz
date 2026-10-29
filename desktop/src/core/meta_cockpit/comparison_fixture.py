"""横向链的仓库内真实夹具（P03 / NF-1 / techdoc）。

验 N/A 单元格：
- 真实域并非每个维度都适用；
- 强行填满会逼模型编造（当前 schema 看不出来，因为缺省 applicability=applicable）；
- N/A-aware 矩阵必须给 reason 且禁止 value/evidence/check。
"""

from __future__ import annotations

from pathlib import Path

from . import json_asset
from . import schema_compat as jsonschema
from .criteria_lexicon import CONCRETE
from .repo_context import repository_root

BASE = Path(__file__).parent
SCHEMA = json_asset.load(BASE / "cognition_method.schema.json")
MATRIX_V = jsonschema.Draft202012Validator(
    {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": "#/$defs/comparison_matrix"}
)

_REPOSITORY = repository_root()
OBJECTS = {
    "O1": ("西幻生存流", _REPOSITORY / "docs" / "完整版样本_西幻生存流P03.md"),
    "O2": ("校园情感流", _REPOSITORY / "library" / "NF-1.md"),
    "O3": ("技术文档流", _REPOSITORY / "docs" / "examples" / "state-front" / "techdoc_front.md"),
}
DIMS = [
    ("D1", "生存压力", ["生存", "消耗", "vitals", "健康"]),
    ("D2", "经济闭环", ["经济", "交易", "资源", "预算"]),
    ("D3", "失败成本", ["死亡", "失败", "返工", "回滚", "遗憾", "关系破裂"]),
]
APPLICABLE = {
    ("O1", "D1"): True,
    ("O1", "D2"): True,
    ("O1", "D3"): True,
    ("O2", "D1"): False,
    ("O2", "D2"): False,
    ("O2", "D3"): True,
    ("O3", "D1"): False,
    ("O3", "D2"): False,
    ("O3", "D3"): True,
}
REASONS = {
    ("O2", "D1"): "情感流无生存消耗机制",
    ("O2", "D2"): "情感流无经济结算闭环",
    ("O3", "D1"): "技术文档无生存压力维度",
    ("O3", "D2"): "技术文档无经济闭环维度",
}
CURATED = {
    ("O1", "D1"): ("每10分钟消耗", "numeric"),
    ("O1", "D2"): ("交易结算表", "qualitative"),
    ("O1", "D3"): ("死亡成本=遗物丢失", "condition"),
    ("O2", "D3"): ("失败成本=关系破裂", "condition"),
    ("O3", "D3"): ("失败成本=返工", "condition"),
}


def find_line(text: str, kws: list[str]):
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip() and any(k in line for k in kws):
            return line.strip()[:70], n
    return "", 0


def build(naware: bool) -> dict:
    cells = []
    texts = {oid: path.read_text(encoding="utf-8") for oid, (_n, path) in OBJECTS.items()}
    for oid in OBJECTS:
        for did, _dname, kws in DIMS:
            if APPLICABLE[(oid, did)]:
                line, lineno = find_line(texts[oid], kws)
                value, kind = CURATED[(oid, did)]
                cells.append(
                    {
                        "object": oid,
                        "dimension": did,
                        "applicability": "applicable",
                        "value": value if line else "（缺失）",
                        "value_kind": kind,
                        "evidence": (f"{OBJECTS[oid][1].name} 行号 {lineno}")
                        if line
                        else "（缺失）",
                        "check": "check" + did[1:],
                    }
                )
            elif naware:
                cells.append(
                    {
                        "object": oid,
                        "dimension": did,
                        "applicability": "not_applicable",
                        "reason": REASONS[(oid, did)],
                    }
                )
            else:
                # 旧式填满：把不适用也伪装成适用
                cells.append(
                    {
                        "object": oid,
                        "dimension": did,
                        "value": "无",
                        "value_kind": "qualitative",
                        "evidence": "—",
                        "check": "check" + did[1:],
                    }
                )
    return {"schema": "nf/comparison-matrix/1", "cells": cells}


def metrics(matrix: dict) -> dict:
    cells = matrix["cells"]
    app = [c for c in cells if APPLICABLE[(c["object"], c["dimension"])]]
    na = [c for c in cells if not APPLICABLE[(c["object"], c["dimension"])]]
    filled = [c for c in app if c.get("value") and c.get("evidence") and c.get("check")]
    fabricated = [c for c in na if any(k in c for k in ("value", "evidence", "check"))]
    justified = [c for c in na if c.get("applicability") == "not_applicable" and c.get("reason")]
    return {
        "cells": len(cells),
        "applicable": len(app),
        "na": len(na),
        "cell_coverage": round(len(filled) / len(app), 3) if app else 0.0,
        "na_justification_rate": round(len(justified) / len(na), 3) if na else 1.0,
        "fabricated_na": len(fabricated),
    }


if __name__ == "__main__":
    for label, naware in [("FILLED-ALL", False), ("NA-AWARE", True)]:
        m = build(naware)
        errs = list(MATRIX_V.iter_errors(m))
        met = metrics(m)
        ok = (
            not errs
            and met["cell_coverage"] == 1.0
            and met["na_justification_rate"] == 1.0
            and met["fabricated_na"] == 0
        )
        print("[{}] schema={} {} -> {}".format(label, not errs, met, "PASS" if ok else "FAIL"))
        if errs:
            print("  schema:", errs[0].message)
        print(
            "  na_criteria=%s"
            % (
                "PASS"
                if (met["na_justification_rate"] == 1.0 and met["fabricated_na"] == 0)
                else "FAIL"
            )
        )

    print("[CONCRETENESS]")
    texts = {oid: path.read_text(encoding="utf-8") for oid, (_n, path) in OBJECTS.items()}
    for oid in OBJECTS:
        for did, _dname, kws in DIMS:
            if APPLICABLE[(oid, did)]:
                line, _lineno = find_line(texts[oid], kws)
                print(f"  {oid} {did} concrete={bool(CONCRETE.search(line))} | {line[:40]}")
