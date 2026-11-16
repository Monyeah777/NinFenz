"""UI 内联错误码必须登记在 app/schema/error_codes.json。"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "app" / "schema" / "error_codes.json"
UI = ROOT / "app" / "android" / "app" / "src" / "main" / "java"
PATTERN = re.compile(r'(?:CoreResponse\.failure|CoreError)\(\s*"(NF-[A-Z]+-\d{3})"')


def _registered() -> set[str]:
    data = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return {item["code"] for item in data["codes"]}


def test_ui_error_codes_registered() -> None:
    registered = _registered()
    used: set[str] = set()
    for path in UI.rglob("*.kt"):
        used |= set(PATTERN.findall(path.read_text(encoding="utf-8")))
    missing = sorted(used - registered)
    assert not missing, f"未登记错误码: {missing}"
