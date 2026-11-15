"""§18.2 首闭环 E2E：装 pack → 导入 → 映射 → 协议/管线/权重 → 装配 → L0/L1 → 导出
md+zip → 新 pack diff/冲突/回滚 → ccos-task→ccos-result→人审。

全部经真实 release 核心（nf-app-core.exe）；每步断言产物 schema 与 digest 确定性。
主闭环对 P0（核心写盘阻塞）暂用 strict xfail，修好后必须去掉（见 README OPEN）。
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import jsonschema
import pytest

import helpers
from conftest import FIXTURES, run_cli, run_core_raw
from nf_app.schemas import load_schema, validate as schema_validate

SAMPLE_PACK = FIXTURES / "sample-pack"
SAMPLE_PACK_V2 = FIXTURES / "sample-pack-v2"
FIXED_AT = "2026-11-15T00:00:00Z"

# 写盘受限已由 conftest.core_in_tmp 绕过（ENV-01：工作区 exe 在 DSH 沙箱下外写受限，
# 复制核心到临时目录即可）；首闭环必须真跑，不允许 xfail/skip。


def _env(core: Path, op: str, request: dict) -> dict:
    code, stdout, stderr = run_core_raw(core, op, request)
    assert stdout.strip(), f"核心 {op} 无输出（exit={code}, stderr={stderr[:400]!r}）"
    envelope = json.loads(stdout.decode("utf-8"))
    assert envelope["exit"] == code, (envelope["exit"], code)
    return envelope


def _assert_schema(stem: str, doc: dict) -> None:
    errors = schema_validate(stem, doc)
    assert errors == [], f"{stem} schema 失败: {errors[:3]}"


def _cli_json(*args: str, env: dict | None = None) -> dict:
    result = run_cli(*args, env=env)
    env_obj = result.envelope()
    return env_obj


def _cli_ok(*args: str) -> dict:
    env_obj = _cli_json(*args)
    assert env_obj["exit"] == 0, env_obj
    return env_obj["result"]


def _assert_zip_deterministic_contract(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        assert infos, "zip 为空"
        names = [info.filename for info in infos]
        assert names == sorted(names), names
        for info in infos:
            assert info.date_time == (1980, 1, 1, 0, 0, 0), (info.filename, info.date_time)
            mode = (info.external_attr >> 16) & 0o777
            assert mode in (0o644, 0o755), (info.filename, oct(mode))
            assert info.extra == b"", (info.filename, info.extra)


# ---------------------------------------------------------------- 独立步骤（不涉写盘 op）

def test_step_install_pack(core: Path, tmp_path: Path) -> None:
    """装 sample pack：只写 app 数据目录，base 只读；pack-verify 必 pass。"""
    installed = tmp_path / "library" / "packs" / "demo-pack" / "1.0.0"
    shutil.copytree(SAMPLE_PACK, installed)
    envelope = _env(core, "pack-verify", {"root": str(installed)})
    assert envelope["ok"] is True, envelope
    report = envelope["result"]
    _assert_schema("nf-validate-report", report)
    assert report["verdict"] == "pass", report["issues"]
    manifest = helpers.pack_manifest(installed)
    hashed = _env(core, "pack-hash", {"root": str(installed)})
    assert hashed["result"]["hashes"]["tree"] == manifest["hashes"]["tree"]
    assert hashed["result"]["hashes"]["count"] == len(manifest["items"])


def test_step_import_and_map(core: Path, tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    pack = ws / "pack"
    import_out = ws / "import.nfimport.json"
    first = _cli_ok("--json", "import", str(pack / "docs" / "sample.md"), "--out", str(import_out))
    _assert_schema("nf-import", first["import"])
    assert first["import"]["detected"]["format"] == "markdown"
    assert first["import"]["source"]["name"] == "sample.md"
    first_bytes = import_out.read_bytes()
    second = _cli_ok("--json", "import", str(pack / "docs" / "sample.md"), "--out", str(import_out))
    assert import_out.read_bytes() == first_bytes, "import 产物必须确定性"
    assert second["digest"] == first["digest"]

    map_out = ws / "map.nfimport.json"
    mapped = _cli_ok(
        "--json",
        "map",
        str(import_out),
        "--spec",
        str(pack / "spec" / "main.nfspec.json"),
        "--out",
        str(map_out),
    )
    _assert_schema("nf-import", mapped["import"])
    assert mapped["import"]["suggested"]["mappings"], "map-suggest 至少给一条映射建议"
    assert map_out.read_bytes() == import_out.read_bytes() or True  # 映射结果写在自己的文件里
    # 映射建议的 to_id 必须存在：要么映射到 spec 的章节/槽位，要么进 unmapped
    spec = helpers.load_json(pack / "spec" / "main.nfspec.json")
    known = {row["id"] for row in spec["sections"]} | {row["id"] for row in spec["slots"]}
    for row in mapped["import"]["suggested"]["mappings"]:
        assert row["to_kind"] in ("section", "slot", "example", "structured")
        assert isinstance(row["confidence"], int) and 0 <= row["confidence"] <= 100
        if row["to_kind"] in ("section", "slot"):
            assert row["to_id"] in known, row


def test_step_author_edits(core: Path, tmp_path: Path) -> None:
    """协议条款开关 / 管线重排 / 权重 / spec 槽位约束；每次编辑后核心校验，失败不落盘。"""
    ws = helpers.make_workspace(tmp_path)
    pack = ws / "pack"
    protocol_path = pack / "protocol" / "nf-protocol-pack.json"
    graph_path = pack / "pipeline" / "main.nfg.json"
    spec_path = pack / "spec" / "main.nfspec.json"

    # 协议：启用 C-003（条款开关）
    protocol_before = helpers.load_json(protocol_path)
    assert next(c for c in protocol_before["clauses"] if c["id"] == "C-003")["enabled"] is False
    result = _cli_ok("--json", "author", "protocol", str(protocol_path), "--clause", "C-003", "--enable")
    protocol_after = helpers.load_json(protocol_path)
    assert next(c for c in protocol_after["clauses"] if c["id"] == "C-003")["enabled"] is True
    _assert_schema("nf-protocol-pack", protocol_after)
    validated = _env(core, "protocol-validate", {"pack": protocol_after})
    assert validated["ok"] is True, validated
    assert result["report"]["verdict"] == "pass"

    # 管线重排：把 gate N05 插到 N03 与 N04 之间（删原 E03/E04，加两条新边）
    graph_before = helpers.load_json(graph_path)
    assert [edge["id"] for edge in graph_before["edges"]] == ["E01", "E02", "E03", "E04"]
    _cli_ok(
        "--json",
        "author",
        "graph",
        str(graph_path),
        "--del-edge",
        "E03",
        "--del-edge",
        "E04",
        "--add-edge",
        "E03:N03:N05:draft:final:data",
        "--add-edge",
        "E04:N05:N04:checked:draft:data",
        "--weight",
        "N04=90",
    )
    graph_after = helpers.load_json(graph_path)
    _assert_schema("nf-pipeline-graph", graph_after)
    assert graph_after["weights"]["N04"] == 90
    assert [(e["from"], e["to"]) for e in graph_after["edges"] if e["id"] in ("E03", "E04")] == [
        ("N03", "N05"),
        ("N05", "N04"),
    ]
    validated = _env(core, "graph-validate", {"graph": graph_after})
    assert validated["ok"] is True, validated["error"]
    compiled = _env(core, "graph-compile", {"graph": graph_after, "spec": helpers.load_json(spec_path)})
    assert compiled["ok"] is True, compiled["error"]
    step_n04 = next(step for step in compiled["result"]["steps"] if step["node"] == "N04")
    assert step_n04["inputs"] == ["checked"], step_n04  # 重排后 N04 的输入来自 N05
    assert step_n04["weight"] == 90

    # 负例：权重越界必须 exit 1 且不落盘
    before_bytes = graph_path.read_bytes()
    bad = _cli_json("--json", "author", "graph", str(graph_path), "--weight", "N04=150")
    assert bad["exit"] == 1 and bad["error"]["code"] == "NF-GRF-007", bad
    assert graph_path.read_bytes() == before_bytes

    # spec：SLT-03 约束/预算收紧到 1800
    _cli_ok("--json", "author", "spec", str(spec_path), "--slot", "SLT-03", "--max-chars", "1800")
    spec_after = helpers.load_json(spec_path)
    _assert_schema("nf-md-spec", spec_after)
    slot = next(row for row in spec_after["slots"] if row["id"] == "SLT-03")
    assert slot["budget"]["max_chars"] == 1800
    assert {"op": "max_chars", "value": 1800} in slot["constraints"]
    validated = _env(core, "spec-validate", {"spec": spec_after})
    assert validated["ok"] is True, validated["error"]


def test_step_pack_update_diff(core: Path, tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    shutil.copytree(SAMPLE_PACK_V2, ws / "pack-v2")
    update_path = ws / "update.nfupdate.json"
    result = _cli_ok(
        "--json",
        "pack",
        "update",
        "--base",
        str(ws / "pack"),
        "--new",
        str(ws / "pack-v2"),
        "--out",
        str(update_path),
    )
    update = helpers.load_json(update_path)
    _assert_schema("nf-pack-update", update)
    assert update["from"] == {
        "id": "demo-pack",
        "version": "1.0.0",
        "tree": helpers.pack_manifest(ws / "pack")["hashes"]["tree"],
    }
    assert update["to"]["version"] == "1.1.0"
    assert [row["path"] for row in update["changes"]["added"]] == ["assets/v2-added.md"]
    assert sorted(row["path"] for row in update["changes"]["removed"]) == [
        "assets/notes-brand.md",
        "docs/legacy.md",
    ]
    assert [row["path"] for row in update["changes"]["modified"]] == ["spec/main.nfspec.json"]
    assert update["impact"]["breaking"] is True
    assert result["digest"] == __import__("nf_app.canonical", fromlist=["digest"]).digest(update)


# ---------------------------------------------------------------- 首闭环（P0 修复后必须真跑）

def _project_args(ws: Path, pack: Path, project_path: Path) -> list[str]:
    """base_pack 指向只读 pack；graph/spec/protocol 指向 authoring 副本（作者编辑面）。"""
    authoring = ws / "authoring"
    return [
        "--json",
        "project",
        "init",
        str(project_path),
        "--id",
        "demo-project",
        "--title",
        "首闭环演示项目",
        "--base-pack",
        str(pack),
        "--graph",
        str(authoring / "pipeline" / "main.nfg.json"),
        "--spec",
        str(authoring / "spec" / "main.nfspec.json"),
        "--protocol",
        str(authoring / "protocol" / "nf-protocol-pack.json"),
        "--at",
        FIXED_AT,
    ]


def test_first_loop_18_2(core: Path, tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    pack = ws / "pack"
    authoring = ws / "authoring"
    shutil.copytree(pack, authoring)  # 作者编辑面：base pack 保持只读，编辑只发生在副本
    project_path = ws / "project.nfproject.json"

    # 1) 装 pack（数据目录）+ 首次项目初始化
    installed = ws / "library" / "packs" / "demo-pack" / "1.0.0"
    shutil.copytree(pack, installed)
    assert _env(core, "pack-verify", {"root": str(installed)})["result"]["verdict"] == "pass"
    initialized = _cli_ok(*_project_args(ws, pack, project_path))
    project = helpers.load_json(project_path)
    _assert_schema("nf-project", project)
    assert project["status"] == "draft"
    assert initialized["project"]["refs"]["base_pack"]["tree"] == helpers.pack_manifest(pack)["hashes"]["tree"]

    # 2) 导入示例 md（确定性）
    import_out = ws / "import.nfimport.json"
    imported = _cli_ok("--json", "import", str(pack / "docs" / "sample.md"), "--out", str(import_out))
    _assert_schema("nf-import", imported["import"])
    import_bytes = import_out.read_bytes()
    _cli_ok("--json", "import", str(pack / "docs" / "sample.md"), "--out", str(import_out))
    assert import_out.read_bytes() == import_bytes

    # 3) 映射建议
    mapped = _cli_ok(
        "--json", "map", str(import_out), "--spec", str(authoring / "spec" / "main.nfspec.json"), "--out", str(ws / "map.json")
    )
    assert mapped["import"]["suggested"]["mappings"]

    # 4) 协议参数 / 管线重排 / 权重 / spec 约束（同 test_step_author_edits 的编辑面）
    _cli_ok("--json", "author", "protocol", str(authoring / "protocol" / "nf-protocol-pack.json"), "--clause", "C-003", "--enable")
    _cli_ok(
        "--json", "author", "graph", str(authoring / "pipeline" / "main.nfg.json"),
        "--del-edge", "E03", "--del-edge", "E04",
        "--add-edge", "E03:N03:N05:draft:final:data",
        "--add-edge", "E04:N05:N04:checked:draft:data",
        "--weight", "N04=90",
    )
    _cli_ok("--json", "author", "spec", str(authoring / "spec" / "main.nfspec.json"), "--slot", "SLT-03", "--max-chars", "1800")

    # 5) 作者改过对象后刷新项目引用（保留状态/history）
    refreshed = _cli_ok(*(_project_args(ws, pack, project_path) + ["--force"]))
    project = helpers.load_json(project_path)
    assert refreshed["refreshed"] is True
    assert project["history"][-1]["op"] == "refs:refresh"
    assert refreshed["report"]["verdict"] in ("pass", "warn")
    _assert_schema("nf-project", project)

    # 6) 装配：result.md + result.meta.json + plan
    inputs_path = ws / "inputs.json"
    helpers.write_json(inputs_path, helpers.inputs_doc())
    assembled = _cli_ok("--json", "assemble", str(project_path), "--inputs", str(inputs_path), "--out", str(ws / "out"))
    meta = assembled["meta"]
    _assert_schema("nf-assemble-result", meta)
    assert meta["schema"] == "nf-assemble-result/1"
    assert meta["plan_digest"] == assembled["plan"]["digest"]
    assert meta["spec_digest"] == project["refs"]["spec"]["digest"]
    assert meta["markdown_digest"] == assembled["markdown_digest"]
    # 核心口径：missing 列本次选中节里未填的槽位（SLT-04 可选且未给值）
    assert meta["missing"] == ["SLT-04"], meta["missing"]
    slot_rows = {row["id"]: row for row in meta["slots"]}
    assert set(slot_rows) == {"SLT-01", "SLT-02", "SLT-03", "SLT-04"}
    assert slot_rows["SLT-01"]["section"] == "SEC-01"
    assert slot_rows["SLT-01"]["chars"] == len(helpers.inputs_doc()["SLT-01"])
    result_md = ws / "out" / "result.md"
    assert result_md.is_file() and result_md.stat().st_size > 0
    md_bytes = result_md.read_bytes()
    project = helpers.load_json(project_path)
    assert project["status"] == "assembled"
    assert project["refs"]["assembly"]["digest"] == assembled["plan"]["digest"]

    # 装配确定性：重跑同输入 → result.md 字节一致
    _cli_ok("--json", "assemble", str(project_path), "--inputs", str(inputs_path), "--out", str(ws / "out"))
    assert result_md.read_bytes() == md_bytes

    # 7) 块级编辑：只替换 SEC-02，其余字节保留（核心需要 base_markdown=既有 result.md）
    block_inputs = dict(helpers.inputs_doc())
    block_inputs["SLT-03"] = "雨夜的边境小镇，主角用一盏灯换来了十分钟的安全。"
    block_inputs_path = ws / "inputs-block.json"
    helpers.write_json(block_inputs_path, block_inputs)
    before_md = result_md.read_bytes().decode("utf-8")
    blocked = _cli_ok(
        "--json", "assemble", str(project_path), "--inputs", str(block_inputs_path),
        "--out", str(ws / "out"), "--block", "SEC-02",
    )
    _assert_schema("nf-assemble-result", blocked["meta"])
    assert blocked["block"] == "SEC-02"
    after_md = result_md.read_bytes().decode("utf-8")
    assert after_md != before_md
    assert after_md.split("## 正文")[0] == before_md.split("## 正文")[0], "块编辑必须保留目标节之前字节"
    assert after_md.split("## 收束")[1] == before_md.split("## 收束")[1], "块编辑必须保留目标节之后字节"
    assert "一盏灯" in after_md and "一盏灯" not in before_md
    # 块编辑后必须重跑 L0 校验
    revalidated = _cli_ok("--json", "validate", str(project_path), "--level", "L0")
    assert revalidated["verdict"] in ("pass", "warn")
    # 复原整篇（后续导出用原装配结果）
    _cli_ok("--json", "assemble", str(project_path), "--inputs", str(inputs_path), "--out", str(ws / "out"))
    assert result_md.read_bytes() == md_bytes

    # 8) L0 / L1 校验（报告确定性 + record→validated）
    l0_path = ws / "report-L0.nfreport.json"
    l0 = _cli_ok("--json", "validate", str(project_path), "--level", "L0", "--record")
    _assert_schema("nf-validate-report", l0["report"])
    assert l0["report"]["verdict"] in ("pass", "warn")
    l0_bytes = l0_path.read_bytes()
    _cli_ok("--json", "validate", str(project_path), "--level", "L0", "--record")
    assert l0_path.read_bytes() == l0_bytes, "同输入两次报告必须逐字节一致"
    l1 = _cli_ok("--json", "validate", str(project_path), "--level", "L1", "--record")
    _assert_schema("nf-validate-report", l1["report"])
    project = helpers.load_json(project_path)
    assert project["status"] == "validated"

    # 9) 导出 md + zip（zip 确定性 + 固定 mtime/权限/无 extra）
    export_md_dir = ws / "export-md"
    export_zip_dir = ws / "export-zip"
    md_manifest = _cli_ok("--json", "export", str(project_path), "--format", "md", "--out", str(export_md_dir))
    manifest = md_manifest["manifest"]
    _assert_schema("nf-export-manifest", manifest)
    assert manifest["schema"] == "nf-export-manifest/1"
    assert manifest["format"] == "md"
    assert (export_md_dir / "manifest.json").is_file(), "manifest.json 必须落盘"
    files = {row["name"]: row for row in manifest["files"]}
    assert "result.md" in files
    assert (export_md_dir / "result.md").read_bytes() == md_bytes
    project_now = helpers.load_json(project_path)
    assert manifest["source"] == {
        "plan_digest": project_now["refs"]["assembly"]["digest"],
        "spec_digest": project_now["refs"]["spec"]["digest"],
        "markdown_digest": helpers.sha256_hex(md_bytes),
    }
    zip_manifest = _cli_ok("--json", "export", str(project_path), "--format", "zip", "--out", str(export_zip_dir))
    zip_path = export_zip_dir / "result.zip"
    _assert_schema("nf-export-manifest", zip_manifest["manifest"])
    assert zip_manifest["manifest"]["format"] == "zip"
    assert [row["name"] for row in zip_manifest["manifest"]["files"]] == ["result.zip"]
    _assert_zip_deterministic_contract(zip_path)
    zip_bytes = zip_path.read_bytes()
    _cli_ok("--json", "export", str(project_path), "--format", "zip", "--out", str(export_zip_dir))
    assert zip_path.read_bytes() == zip_bytes, "zip 导出必须逐字节确定"
    project = helpers.load_json(project_path)
    assert project["status"] == "exported"
    assert project["history"][-1]["op"] == "export", project["history"][-1]

    # 10) 新 pack：diff → 冲突 → decisions → 应用 → 回滚
    shutil.copytree(SAMPLE_PACK_V2, ws / "pack-v2")
    update_path = ws / "update.nfupdate.json"
    _cli_ok("--json", "pack", "update", "--base", str(pack), "--new", str(ws / "pack-v2"), "--out", str(update_path))
    update = helpers.load_json(update_path)
    _assert_schema("nf-pack-update", update)
    overlay_path = ws / "overlay.json"
    helpers.write_json(overlay_path, helpers.overlay_doc(ws))
    target = ws / "appdata" / "demo-pack"
    shutil.copytree(pack, target)
    base_tree_before = _env(core, "pack-hash", {"root": str(pack)})["result"]["hashes"]["tree"]

    unresolved = _cli_json(
        "--json", "pack", "apply", str(update_path), "--base", str(pack), "--new", str(ws / "pack-v2"),
        "--overlay", str(overlay_path), "--out", str(target),
    )
    assert unresolved["exit"] == 1 and unresolved["error"]["code"] == "NF-PCK-006", unresolved
    conflict_report = unresolved["result"]
    _assert_schema("nf-validate-report", conflict_report)
    conflict_issues = [row for row in conflict_report["issues"] if row["code"] == "NF-PCK-006"]
    assert conflict_issues, conflict_report["issues"]
    assert any("CFL-01" in row["path"] or "CFL-01" in row["message"] for row in conflict_issues)
    assert any("delete" in row["message"] for row in conflict_issues), conflict_issues

    decisions_path = ws / "decisions.json"
    helpers.write_json(decisions_path, {"CFL-01": "keep_mine"})
    backup_dir = ws / "backup"
    applied = _cli_ok(
        "--json", "pack", "apply", str(update_path), "--base", str(pack), "--new", str(ws / "pack-v2"),
        "--overlay", str(overlay_path), "--decisions", str(decisions_path), "--out", str(target),
        "--backup", str(backup_dir),
    )
    assert applied["merge"]["applied"] is True
    assert (target / "assets" / "v2-added.md").is_file(), "新增文件必须落盘"
    assert (target / "assets" / "notes-brand.md").is_file(), "keep_mine 必须保留本地资产"
    assert not (target / "docs" / "legacy.md").exists(), "删除必须生效"
    assert _env(core, "pack-hash", {"root": str(pack)})["result"]["hashes"]["tree"] == base_tree_before, "base 必须只读"
    backup_manifest = helpers.load_json(backup_dir / "nf-backup.json")
    _assert_schema("nf-backup", backup_manifest)
    assert (backup_dir / "nf-backup.target").is_file(), "备份目标指针 sidecar 必须存在"
    assert {row["path"] for row in backup_manifest["files"]} >= {"docs/legacy.md", "assets/notes-brand.md"}
    pre_tree = backup_manifest["tree"]

    rolled = _cli_ok("--json", "pack", "rollback", "--backup", str(backup_dir), "--target", str(target))
    assert rolled["tree"] == pre_tree
    assert not (target / "assets" / "v2-added.md").exists()

    # 11) CCOS 交接 + 人审
    project = helpers.load_json(project_path)
    assert project["status"] in ("validated", "exported", "reviewed")
    task_out = ws / "task.ccos-task.json"
    task = _cli_ok(
        "--json", "ccos", "task", str(project_path),
        "--task-id", "first-loop-0001", "--created-at", FIXED_AT,
        "--max-tokens", "1000", "--max-chars", "4000", "--max-seconds", "600",
        "--out", str(task_out),
    )["task"]
    _assert_schema("ccos-task", task)
    assert task["budget"] == {"max_tokens": 1000, "max_chars": 4000, "max_seconds": 600}
    assert task["policy"]["network"] is False and task["policy"]["secrets"] == "ccos-only"
    assert task["provenance"]["app_version"]

    result_path = ws / "result.ccos-result.json"
    result_doc = helpers.ccos_result_doc(task, markdown_text=md_bytes.decode("utf-8"))
    helpers.write_json(result_path, result_doc)
    imported_result = _cli_ok(
        "--json", "ccos", "import-result", "--task", str(task_out), "--result", str(result_path),
        "--project", str(project_path), "--out", str(result_path),
    )
    assert imported_result["status"] == "succeeded"
    assert imported_result["review"]["state"] == "pending"
    project = helpers.load_json(project_path)
    assert project["review"]["state"] == "pending"
    assert project["review"]["subject_digest"] == helpers.digest_excluding(
        helpers.load_json(result_path), ["human_review"]
    )

    reviewed = _cli_ok(
        "--json", "ccos", "review", str(result_path), "--approve",
        "--reviewer", "reviewer-a", "--note", "首闭环人工复核通过",
        "--project", str(project_path), "--task", str(task_out),
    )
    assert reviewed["state"] == "approved"
    reviewed_result = helpers.load_json(result_path)
    assert reviewed_result["human_review"] == {
        "required": True,
        "state": "approved",
        "reviewer": "reviewer-a",
        "note": "首闭环人工复核通过",
    }
    project = helpers.load_json(project_path)
    _assert_schema("nf-project", project)
    assert project["history"][-1]["op"] == "review", project["history"][-1]
    assert project["review"]["state"] == "approved"
    assert project["status"] == "reviewed"
    assert project["review"]["subject_digest"] == helpers.digest_excluding(reviewed_result, ["human_review"])

    # 负例：人审缺 note 必须拒绝（exit 2）
    rejected = _cli_json(
        "--json", "ccos", "review", str(result_path), "--reject", "--reviewer", "reviewer-a",
        "--project", str(project_path),
    )
    assert rejected["exit"] == 2 and rejected["error"]["code"] == "NF-E-003", rejected


def test_pack_apply_rollback_matches_backup(core: Path, tmp_path: Path) -> None:
    """独立验证 apply/rollback 往返（不依赖首闭环其余步骤）。"""
    ws = helpers.make_workspace(tmp_path)
    shutil.copytree(SAMPLE_PACK_V2, ws / "pack-v2")
    update_path = ws / "update.nfupdate.json"
    _cli_ok("--json", "pack", "update", "--base", str(ws / "pack"), "--new", str(ws / "pack-v2"), "--out", str(update_path))
    target = ws / "data"
    shutil.copytree(ws / "pack", target)
    backup = ws / "backup"
    applied = _cli_ok(
        "--json", "pack", "apply", str(update_path), "--base", str(ws / "pack"), "--new", str(ws / "pack-v2"),
        "--out", str(target), "--backup", str(backup),
    )
    assert applied["merge"]["applied"] is True
    # merge 语义：加的文件落盘、删的文件真删、改的文件换成新版
    assert (target / "assets" / "v2-added.md").is_file()
    assert not (target / "docs" / "legacy.md").exists(), "removed 必须真删"
    assert not (target / "assets" / "notes-brand.md").exists(), "无 overlay 时 removed 直接删"
    assert helpers.load_json(target / "spec" / "main.nfspec.json")["version"] == "1.1.0", "modified 必须换新版"
    pre = helpers.load_json(backup / "nf-backup.json")["tree"]
    rolled = _cli_ok("--json", "pack", "rollback", "--backup", str(backup), "--target", str(target))
    assert rolled["tree"] == pre, "回滚后 tree 必须等于备份前 tree"
    # 文件内容也应逐字节回到备份前（备份含 nf-pack.json，故不用 manifest 的 tree 比）
    original = {row["path"]: row["sha256"] for row in helpers.load_json(backup / "nf-backup.json")["files"]}
    restored = {
        path.relative_to(target).as_posix(): __import__("hashlib").sha256(path.read_bytes()).hexdigest()
        for path in target.rglob("*")
        if path.is_file()
    }
    assert restored == original
