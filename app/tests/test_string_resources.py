"""Android 中英字符串资源一致性：名称集合、重复名、格式占位符。"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZH = ROOT / "android/app/src/main/res/values/strings.xml"
EN = ROOT / "android/app/src/main/res/values-en/strings.xml"
PLACEHOLDER = re.compile(r"%(\d+\$)?[a-zA-Z]")


def _entries(path: Path):
    root = ET.parse(path).getroot()
    found = {}
    duplicates = []
    for element in root:
        if element.tag not in {"string", "plurals"}:
            continue
        name = element.get("name", "")
        if name in found:
            duplicates.append(name)
        found[name] = element
    return found, duplicates


def _placeholders(element) -> set[str]:
    values = [element.text or ""]
    for item in element:
        values.append(item.text or "")
    result = set()
    for value in values:
        result.update(match.group(0) for match in PLACEHOLDER.finditer(value))
    return result


def test_zh_en_names_match_and_are_unique():
    zh, zh_dup = _entries(ZH)
    en, en_dup = _entries(EN)
    assert not zh_dup, f"values 重复字符串：{zh_dup}"
    assert not en_dup, f"values-en 重复字符串：{en_dup}"
    assert set(zh) == set(en), (
        f"中英资源名不一致；zh-only={sorted(set(zh) - set(en))} "
        f"en-only={sorted(set(en) - set(zh))}"
    )


def test_placeholders_match_per_key():
    zh, _ = _entries(ZH)
    en, _ = _entries(EN)
    mismatched = {
        name: (_placeholders(zh[name]), _placeholders(en[name]))
        for name in zh.keys() & en.keys()
        if _placeholders(zh[name]) != _placeholders(en[name])
    }
    assert not mismatched, f"占位符不一致：{mismatched}"
