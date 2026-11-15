"""编码纪律：app/cli、app/tests、app/fixtures 下文本文件必须是 UTF-8 无 BOM + LF。

对应全仓 text_hygiene 门禁口径；Windows 上 Path.write_text 默认 CRLF，是返工高发点。
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ROOTS = [REPO / "app" / "cli", REPO / "app" / "tests", REPO / "app" / "fixtures"]
TEXT_SUFFIXES = {".py", ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache"}


def _files() -> list[Path]:
    out: list[Path] = []
    for root in ROOTS:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if path.suffix.lower() in TEXT_SUFFIXES:
                out.append(path)
    return sorted(out)


FILES = _files()


def test_scanned_files_not_empty() -> None:
    assert len(FILES) > 20, FILES


@pytest.mark.parametrize("path", FILES, ids=[str(p.relative_to(REPO)) for p in FILES])
def test_utf8_no_bom_lf(path: Path) -> None:
    data = path.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf"), f"{path} 带 UTF-8 BOM"
    assert b"\r\n" not in data, f"{path} 用了 CRLF（Windows 默认换行）；必须 LF"
    data.decode("utf-8")  # 非 UTF-8 直接抛错
