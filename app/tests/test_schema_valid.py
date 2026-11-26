"""正样例：app/fixtures/schema/valid/<schema>/*.json 必须通过对应 schema。"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

VALID_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "schema" / "valid"
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"


def _cases() -> list[tuple[str, Path]]:
    cases: list[tuple[str, Path]] = []
    for schema_dir in sorted(p for p in VALID_DIR.iterdir() if p.is_dir()):
        for doc in sorted(schema_dir.glob("*.json")):
            cases.append((schema_dir.name, doc))
    return cases


CASES = _cases()


def _validator(stem: str) -> jsonschema.Draft202012Validator:
    schema = json.loads((SCHEMA_DIR / f"{stem}.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


@pytest.mark.parametrize("stem,path", CASES, ids=[f"{s}/{p.name}" for s, p in CASES])
def test_valid_fixture_passes_schema(stem: str, path: Path) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    errors = sorted(_validator(stem).iter_errors(doc), key=lambda e: list(e.absolute_path))
    assert errors == [], f"{path.name} 应通过 {stem} schema，实际错误: {[e.message for e in errors]}"


def test_every_schema_has_valid_fixture() -> None:
    stems = sorted(p.name[: -len(".schema.json")] for p in SCHEMA_DIR.glob("*.schema.json"))
    assert len(stems) == 41, stems  # 34 + 4 0.3.6 free-layer contracts
    for stem in stems:
        docs = list((VALID_DIR / stem).glob("*.json"))
        assert docs, f"{stem} 缺正样例"


def test_valid_fixtures_are_canonicalizable() -> None:
    """正样例必须能被 canonical 序列化（禁浮点/非字符串键）。"""
    from nf_app.canonical import CanonicalError, canonical_bytes

    for _, path in CASES:
        doc = json.loads(path.read_text(encoding="utf-8"))
        try:
            canonical_bytes(doc)
        except CanonicalError as exc:  # pragma: no cover - 夹具错误时给出可读信息
            pytest.fail(f"{path} 不可 canonical: {exc}")
