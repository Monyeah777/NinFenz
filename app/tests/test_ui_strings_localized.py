"""UI 层中文文案守卫：正常路径须走 values 资源。

CoreCall.kt 在无 Context（纯 JVM）时保留中文回退，单独豁免。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "android/app/src/main/java/dev/ninfenz/mobile/ui"
CHINESE_LITERAL = re.compile(r'"([^"\n]*[\u4e00-\u9fff][^"\n]*)"')
ALLOWED = {"CoreCall.kt", "DesignSystemScreen.kt", "DeliveryScreen.kt"}


def test_ui_has_no_chinese_string_literals_outside_allowlist():
    offenders = []
    for path in sorted(UI.rglob("*.kt")):
        if path.name in ALLOWED or "ui/design" in path.as_posix():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in CHINESE_LITERAL.finditer(line):
                offenders.append(f"{path.relative_to(ROOT)}:{line_no}: {match.group(0)}")
    assert not offenders, "UI 中文硬编码（请改用 strings.xml）：\n" + "\n".join(offenders[:20])
