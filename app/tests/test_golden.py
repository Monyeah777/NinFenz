"""Golden 逐字节对账：app/fixtures/golden/<op>/*.json 由核心生成，Python 复核。

期望值不是手写：expected_sha256 = sha256(核心 stdout 原始字节)，expected 为解析后的信封。
夹具由 app/cli/tools/bless_golden.py --bless 生成（人工审 diff 后入仓）。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from conftest import run_core_raw

REPO = Path(__file__).resolve().parents[2]
GOLDEN = REPO / "app" / "fixtures" / "golden" / "ops"
FIXTURE_TOKEN = "$fixtures"


def _resolve(obj):
    if isinstance(obj, str) and obj.startswith(FIXTURE_TOKEN + "/"):
        return str(REPO / "app" / "fixtures" / obj[len(FIXTURE_TOKEN) + 1 :])
    if isinstance(obj, list):
        return [_resolve(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _resolve(value) for key, value in obj.items()}
    return obj


CASES = sorted(GOLDEN.glob("*/*.json"))


def test_golden_fixtures_exist(core: Path) -> None:
    assert CASES, "app/fixtures/golden 为空：先跑 python app/cli/tools/bless_golden.py --bless"


@pytest.mark.parametrize("path", CASES, ids=[f"{p.parent.name}/{p.stem}" for p in CASES])
def test_golden_matches_core(core: Path, path: Path) -> None:
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["schema"] == "nf-golden-case/1"
    request = _resolve(record["request"])
    exit_code, stdout, stderr = run_core_raw(core, record["op"], request)
    assert stdout.strip(), f"核心无输出（exit={exit_code}, stderr={stderr[:300]!r}）"
    assert exit_code == record["expected_exit"], (exit_code, record["expected_exit"])
    digest = hashlib.sha256(stdout).hexdigest()
    assert digest == record["expected_sha256"], f"{path} 与核心输出字节不一致"
    envelope = json.loads(stdout.decode("utf-8"))
    assert envelope == record["expected"], "信封语义不一致"
    expect = record.get("expect") or {}
    if "ok" in expect:
        assert envelope["ok"] is expect["ok"], (expect, envelope.get("error"))
    if expect.get("code"):
        assert (envelope.get("error") or {}).get("code") == expect["code"], envelope.get("error")
