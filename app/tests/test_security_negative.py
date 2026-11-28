"""安全负例：zip slip / zip bomb / symlink / YAML alias bomb / JSON 深度 / 路径穿越。

夹具在 tmp_path 里用 Python zipfile 真实构造（不是描述性样例）。
同时校验错误码都是登记过的 NF-SEC / NF-IMP 码且 exit 与登记一致。
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from nf_app.errors import AppError, exit_for
from nf_app.security import (
    assert_share_safe,
    check_rel_path,
    extract_zip_safe,
    find_sensitive,
    inspect_zip_entries,
    loads_yaml_secure,
    parse_json_secure,
    safe_join,
    sanitize_text,
)


def _zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return buffer.getvalue()


def _zip_symlink_bytes(name: str = "link", target: str = "/etc/passwd") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        info = zipfile.ZipInfo(name)
        info.create_system = 3  # Unix，才带 symlink mode
        info.external_attr = (0o120777 << 16)
        zf.writestr(info, target.encode())
    return buffer.getvalue()


def _assert_code(exc_info, code: str) -> None:
    assert exc_info.value.code == code, (exc_info.value.code, exc_info.value.message)
    assert exit_for(code) == 3, f"{code} 的登记退出码必须是 3（拒绝）"


# ---------------------------------------------------------------- zip slip

@pytest.mark.parametrize(
    "entry",
    ["../evil.txt", "../../etc/passwd", "/abs/evil.txt", "C:/evil.txt", "..\\evil.txt", "a/../../evil.txt"],
)
def test_zip_slip_rejected(tmp_path: Path, entry: str) -> None:
    path = tmp_path / "slip.zip"
    path.write_bytes(_zip_bytes([(entry, b"x")]))
    with pytest.raises(AppError) as exc:
        inspect_zip_entries(path)
    _assert_code(exc, "NF-SEC-001")


def test_zip_backslash_and_absolute_bytes_variant(tmp_path: Path) -> None:
    data = _zip_bytes([("/etc/passwd", b"x")])
    with pytest.raises(AppError) as exc:
        inspect_zip_entries(data)
    _assert_code(exc, "NF-SEC-001")


def test_zip_duplicate_entries_rejected(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("a.md", b"1")
        zf.writestr("a.md", b"2")
    path = tmp_path / "dup.zip"
    path.write_bytes(buffer.getvalue())
    with pytest.raises(AppError) as exc:
        inspect_zip_entries(path)
    _assert_code(exc, "NF-SEC-001")


def test_extract_zip_safe_slip_writes_nothing_outside(tmp_path: Path) -> None:
    path = tmp_path / "slip.zip"
    path.write_bytes(_zip_bytes([("../evil.txt", b"x")]))
    out = tmp_path / "out"
    with pytest.raises(AppError) as exc:
        extract_zip_safe(path, out)
    _assert_code(exc, "NF-SEC-001")
    assert not (tmp_path / "evil.txt").exists()


# ---------------------------------------------------------------- symlink

def test_zip_symlink_rejected(tmp_path: Path) -> None:
    path = tmp_path / "symlink.zip"
    path.write_bytes(_zip_symlink_bytes())
    with pytest.raises(AppError) as exc:
        inspect_zip_entries(path)
    _assert_code(exc, "NF-SEC-002")


# ---------------------------------------------------------------- zip bomb

def test_zip_bomb_ratio_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bomb.zip"
    path.write_bytes(_zip_bytes([("zero.bin", b"\x00" * (5 * 1024 * 1024))]))
    with pytest.raises(AppError) as exc:
        inspect_zip_entries(path)
    _assert_code(exc, "NF-SEC-003")


def test_zip_total_size_limit_override(tmp_path: Path) -> None:
    path = tmp_path / "total.zip"
    path.write_bytes(_zip_bytes([("a.bin", b"\x00" * 100), ("b.bin", b"\x00" * 100)]))
    with pytest.raises(AppError) as exc:
        inspect_zip_entries(path, lim={"zip": {"max_total_unpacked_bytes": 10}})
    _assert_code(exc, "NF-SEC-003")


def test_zip_entry_count_limit_override(tmp_path: Path) -> None:
    path = tmp_path / "many.zip"
    path.write_bytes(_zip_bytes([(f"f{i}.txt", b"x") for i in range(5)]))
    with pytest.raises(AppError) as exc:
        inspect_zip_entries(path, lim={"zip": {"max_entries": 3}})
    _assert_code(exc, "NF-SEC-003")


def test_zip_nested_depth_rejected(tmp_path: Path) -> None:
    inner = _zip_bytes([("deep.txt", b"x")])
    middle = _zip_bytes([("inner.zip", inner)])
    path = tmp_path / "nested.zip"
    path.write_bytes(_zip_bytes([("middle.zip", middle)]))
    with pytest.raises(AppError) as exc:
        inspect_zip_entries(path)
    _assert_code(exc, "NF-SEC-003")


def test_zip_bad_file_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.zip"
    path.write_bytes(b"PK\x03\x04this-is-not-a-zip")
    with pytest.raises(AppError) as exc:
        inspect_zip_entries(path)
    _assert_code(exc, "NF-SEC-001")


def test_zip_ok_passes(tmp_path: Path) -> None:
    path = tmp_path / "ok.zip"
    path.write_bytes(_zip_bytes([("docs/a.md", b"hello")]))
    entries = inspect_zip_entries(path)
    assert [e["name"] for e in entries] == ["docs/a.md"]


# ---------------------------------------------------------------- YAML

def _yaml_alias_bomb() -> str:
    lines = ["a: &a [" + ", ".join(["x"] * 9) + "]"]
    prev = "a"
    for name in "bcdefg":
        lines.append(f"{name}: &{name} [" + ", ".join([f"*{prev}"] * 9) + "]")
        prev = name
    return "\n".join(lines) + "\n"


def test_yaml_alias_bomb_rejected() -> None:
    with pytest.raises(AppError) as exc:
        loads_yaml_secure(_yaml_alias_bomb())
    _assert_code(exc, "NF-SEC-004")


def test_yaml_depth_rejected() -> None:
    lines = []
    for i in range(70):
        lines.append("  " * i + f"k{i}:")
    with pytest.raises(AppError) as exc:
        loads_yaml_secure("\n".join(lines) + "\n")
    _assert_code(exc, "NF-SEC-004")


def test_yaml_small_ok() -> None:
    assert loads_yaml_secure("a: [1, 2]\nb: ok\n") == {"a": [1, 2], "b": "ok"}


# ---------------------------------------------------------------- JSON

def test_json_depth_rejected() -> None:
    deep = "[" * 65 + "]" * 65
    with pytest.raises(AppError) as exc:
        parse_json_secure(deep)
    _assert_code(exc, "NF-IMP-003")


def test_json_float_rejected() -> None:
    with pytest.raises(AppError) as exc:
        parse_json_secure('{"x": 1.5}')
    _assert_code(exc, "NF-IMP-003")


def test_json_duplicate_key_rejected() -> None:
    with pytest.raises(AppError) as exc:
        parse_json_secure('{"a": 1, "a": 2}')
    _assert_code(exc, "NF-IMP-003")


def test_json_malformed_rejected() -> None:
    with pytest.raises(AppError) as exc:
        parse_json_secure("{oops")
    _assert_code(exc, "NF-IMP-001")


def test_json_bytes_limit_override() -> None:
    with pytest.raises(AppError) as exc:
        parse_json_secure(b'{"a": 1}', lim={"json": {"max_bytes": 3}})
    _assert_code(exc, "NF-IMP-003")


def test_json_ok() -> None:
    assert parse_json_secure('{"b": 2, "a": [true, null]}') == {"b": 2, "a": [True, None]}


# ---------------------------------------------------------------- 路径穿越

@pytest.mark.parametrize(
    "bad",
    [
        "",
        "../x.md",
        "../../etc/passwd",
        "/abs/x.md",
        "C:/Windows/x",
        "C:\\Windows\\x",
        "a\\b.md",
        "a//b.md",
        "a/./b.md",
        "a/../b.md",
        "CON",
        "a/\x00b.md",
    ],
)
def test_unsafe_rel_path_rejected(bad: str) -> None:
    with pytest.raises(AppError) as exc:
        check_rel_path(bad)
    assert exc.value.code == "NF-PCK-003"
    assert exit_for(exc.value.code) == 3


@pytest.mark.parametrize("good", ["a.md", "docs/x y.md", "assets/中文.md", "a/b/c.json"])
def test_safe_rel_path_passes(good: str) -> None:
    assert check_rel_path(good) == good


def test_safe_join_escape_rejected(tmp_path: Path) -> None:
    with pytest.raises(AppError) as exc:
        safe_join(tmp_path, "../outside.txt")
    assert exc.value.code == "NF-EXP-002"
    assert exit_for("NF-EXP-002") == 3


def test_safe_join_inside_ok(tmp_path: Path) -> None:
    target = safe_join(tmp_path, "a/b.txt")
    assert target == (tmp_path / "a" / "b.txt").resolve()


# ---------------------------------------------------------------- 分享脱敏

def test_sanitize_masks_paths_and_secrets() -> None:
    raw = (
        "路径 C:\\Users\\alice\\proj\\a.md 与 /home/bob/x，"
        "邮箱 a@b.com，token sk-" "abcdefghijklmnopqrstuvwxyz012345，"
        "AWS AKIA" "ABCDEFGHIJKLMNOP。"
    )
    text, masks = sanitize_text(raw)
    assert find_sensitive(text) == []
    assert "<home>" in text and "<email>" in text and "<secret>" in text
    assert masks, "脱敏必须记录掩码种类/次数"


def test_sanitize_obj_recurses() -> None:
    from nf_app.security import sanitize_obj

    obj = {"a": ["x /home/bob/y"], "b": {"c": "u@v.com"}}
    out, masks = sanitize_obj(obj)
    assert out["b"]["c"] == "<email>"
    assert "<home>" in out["a"][0]
    assert masks


def test_assert_share_safe_rejects_secret() -> None:
    with pytest.raises(AppError) as exc:
        assert_share_safe("key=sk-" "abcdefghijklmnopqrstuvwxyz012345")
    assert exc.value.code == "NF-E-002"


def test_assert_share_safe_ok() -> None:
    assert_share_safe("正常分享文本，没有敏感模式。<repo>/app/docs/CONTRACT.md")
