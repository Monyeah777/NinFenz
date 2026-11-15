"""导出格式：docx（OOXML）/ skill（MCP 脚手架）/ pdf（平台打印，显式 OPEN）。

这些用例只从**核心/CLI 的对外面**取证，不复制核心语义：
- 核心 export op 产出文件与 nf-export-manifest/1（schema 校验）；
- docx 必须是可打开的 OOXML（zip 结构 + document.xml 关键内容）；
- skill 包必须含 SKILL.md/mcp.json/README.md（MCP 脚手架）；
- pdf 不得假装成功：exit 4 + NF-EXP-004（平台打印口径）。
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator

from conftest import run_cli, run_core_raw

MARKDOWN = "# 标题一\n\n正文**加粗**。\n\n## 小标题\n\n- 列表一\n- 列表二\n"


def _export(core: Path, req: dict) -> tuple[int, dict]:
    code, stdout, stderr = run_core_raw(core, "export", req)
    assert stdout.strip(), f"export 无输出（exit={code}, stderr={stderr[:300]!r}）"
    env = json.loads(stdout.decode("utf-8"))
    return code, env


def _validate_manifest(schemas: dict, manifest: dict) -> None:
    Draft202012Validator(schemas["nf-export-manifest"]).validate(manifest)


def test_export_docx_is_valid_ooxml(core: Path, tmp_path: Path, schemas: dict) -> None:
    out = tmp_path / "docx"
    out.mkdir()
    code, env = _export(core, {"markdown": MARKDOWN, "format": "docx", "out_dir": str(out), "title": "演示"})
    assert code == 0, env
    manifest = env["result"]
    assert manifest["format"] == "docx"
    _validate_manifest(schemas, manifest)
    path = out / "result.docx"
    assert manifest["files"][0]["name"] == "result.docx"
    data = path.read_bytes()
    assert manifest["files"][0]["sha256"] == __import__("hashlib").sha256(data).hexdigest()
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        for need in ("[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml"):
            assert need in names, (need, z.namelist())
        doc = z.read("word/document.xml").decode("utf-8")
    assert "Heading1" in doc and "标题一" in doc and "• 列表一" in doc


def test_export_docx_deterministic(core: Path, tmp_path: Path) -> None:
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
    req = {"markdown": MARKDOWN, "format": "docx", "out_dir": ""}
    _, ea = _export(core, dict(req, out_dir=str(tmp_path / "a")))
    _, eb = _export(core, dict(req, out_dir=str(tmp_path / "b")))
    assert ea["result"]["files"][0]["sha256"] == eb["result"]["files"][0]["sha256"]


def test_export_skill_pack_scaffold(core: Path, tmp_path: Path, schemas: dict) -> None:
    out = tmp_path / "skill"
    out.mkdir()
    code, env = _export(core, {"markdown": MARKDOWN, "format": "skill", "out_dir": str(out),
                               "title": "演示技能", "project_id": "demo-project"})
    assert code == 0, env
    manifest = env["result"]
    assert manifest["format"] == "skill"
    _validate_manifest(schemas, manifest)
    with zipfile.ZipFile(out / "result.skill.zip") as z:
        names = set(z.namelist())
        for need in ("SKILL.md", "mcp.json", "README.md", "result.md"):
            assert need in names, (need, z.namelist())
        mcp = json.loads(z.read("mcp.json").decode("utf-8"))
    assert mcp["schema"] == "nf-mcp-scaffold/1"
    assert mcp["server"]["transport"] == "stdio"
    assert mcp["provenance"]["markdown_digest"] == manifest["source"]["markdown_digest"]


def test_export_pdf_is_explicit_open(core: Path, tmp_path: Path) -> None:
    out = tmp_path / "pdf"
    out.mkdir()
    code, env = _export(core, {"markdown": MARKDOWN, "format": "pdf", "out_dir": str(out)})
    assert code == 4, env
    assert env["error"]["code"] == "NF-EXP-004"
    assert "平台打印" in env["error"]["message"]


def test_cli_accepts_docx_and_skill_formats() -> None:
    for fmt in ("docx", "skill"):
        r = run_cli("--json", "export", "--format", fmt)
        assert r.returncode != 2 or "invalid choice" not in (r.stderr or ""), (fmt, r.returncode, r.stderr)
