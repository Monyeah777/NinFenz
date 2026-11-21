"""反样例：invalid 夹具必须被对应 schema 拒绝，且错误清单与 EXPECTED.json 一致。"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

APP = Path(__file__).resolve().parents[1]
INVALID_DIR = APP / "fixtures" / "schema" / "invalid"
VALID_DIR = APP / "fixtures" / "schema" / "valid"
SCHEMA_DIR = APP / "schema"
EXPECTED = json.loads((INVALID_DIR / "EXPECTED.json").read_text(encoding="utf-8"))


def _cases() -> list[tuple[str, Path]]:
    cases: list[tuple[str, Path]] = []
    for schema_dir in sorted(p for p in INVALID_DIR.iterdir() if p.is_dir()):
        for doc in sorted(schema_dir.glob("*.json")):
            cases.append((schema_dir.name, doc))
    return cases


CASES = _cases()


def _validator(stem: str) -> jsonschema.Draft202012Validator:
    schema = json.loads((SCHEMA_DIR / f"{stem}.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


@pytest.mark.parametrize("stem,path", CASES, ids=[f"{s}/{p.name}" for s, p in CASES])
def test_invalid_fixture_rejected(stem: str, path: Path) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    errors = list(_validator(stem).iter_errors(doc))
    assert errors, f"{path} 应被 {stem} schema 拒绝，实际通过"


@pytest.mark.parametrize("stem,path", CASES, ids=[f"{s}/{p.name}" for s, p in CASES])
def test_expected_error_code_registered(stem: str, path: Path, error_codes: dict) -> None:
    rel = f"invalid/{stem}/{path.name}"
    entry = EXPECTED["fixtures"].get(rel)
    assert entry is not None, f"EXPECTED.json 缺 {rel} 的期望错误码登记"
    assert entry["schema"] == stem, f"{rel} 登记的 schema ({entry['schema']}) 与目录 ({stem}) 不一致"
    assert entry["violated"].strip(), f"{rel} 必须写明违反的具体约束"
    assert entry["codes"], f"{rel} 必须至少登记 1 个期望错误码"
    for code in entry["codes"]:
        assert code in error_codes, f"{rel} 期望码 {code} 未登记于 app/schema/error_codes.json"
        assert error_codes[code]["exit"] in (1, 2, 3, 4), (code, error_codes[code])


def test_expected_covers_exactly_all_invalid_fixtures() -> None:
    actual = {f"invalid/{stem}/{path.name}" for stem, path in CASES}
    declared = set(EXPECTED["fixtures"])
    assert declared == actual, {
        "未登记": sorted(actual - declared),
        "多余登记": sorted(declared - actual),
    }


def test_each_schema_has_at_least_two_negatives() -> None:
    stems = sorted(p.name[: -len(".schema.json")] for p in SCHEMA_DIR.glob("*.schema.json"))
    assert len(stems) == 17
    for stem in stems:
        files = list((INVALID_DIR / stem).glob("*.json"))
        assert len(files) >= 2, f"{stem} 反样例少于 2 个: {files}"
        assert list((VALID_DIR / stem).glob("*.json")), f"{stem} 缺正样例"


def test_expected_codes_cover_all_prefixes() -> None:
    """登记的错误码必须覆盖契约 §4 的全部前缀族（防止映射退化成单一码）。"""
    codes = {code for entry in EXPECTED["fixtures"].values() for code in entry["codes"]}
    prefixes = {code.split("-")[1] for code in codes}
    assert {"IMP", "PRT", "GRF", "SPC", "ASM", "VAL", "PCK", "CCOS"} <= prefixes, prefixes
