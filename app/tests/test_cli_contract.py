"""CLI 契约：子命令参数/JSON 信封/错误码+退出码；核心相关面用真核心或显式 NF-E-005。

覆盖：未知子命令、未知选项、坏 JSON、缺字段/坏 schema、缺核心、状态机回退、
本地安全守卫、pack 备份回滚、share 脱敏、--json 全子命令一致性。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import helpers
from conftest import run_cli, run_core_raw

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SAMPLE_PACK = FIXTURES / "sample-pack"


def _env_missing_core(tmp_path: Path) -> dict:
    return {"NF_APP_CORE": str(tmp_path / "nope" / "nf-app-core")}


def _assert_error(result, code: str, exit_code: int) -> dict:
    env = result.envelope()
    assert env["ok"] is False
    assert env["error"]["code"] == code, env
    assert env["exit"] == exit_code, env
    assert env["error"]["message"]
    assert env["error"]["fix"]
    assert result.returncode == exit_code
    return env


# ---------------------------------------------------------------- 基本参数契约

def test_help_and_version() -> None:
    result = run_cli("--help")
    assert result.returncode == 0
    assert "nf-app" in result.stdout
    result = run_cli("--version")
    assert result.returncode == 0
    assert result.stdout.strip().startswith("nf-app ")


def test_unknown_subcommand_json() -> None:
    _assert_error(run_cli("--json", "bogus"), "NF-E-003", 2)


def test_unknown_subcommand_human() -> None:
    result = run_cli("bogus")
    assert result.returncode == 2
    assert "NF-E-003" in result.stderr


def test_missing_required_arg() -> None:
    _assert_error(run_cli("--json", "import"), "NF-E-003", 2)
    _assert_error(run_cli("--json", "author", "graph"), "NF-E-003", 2)
    _assert_error(run_cli("--json", "project", "set", "x.json"), "NF-E-003", 2)


def test_bad_choice() -> None:
    _assert_error(run_cli("--json", "validate", "x.json", "--level", "L9"), "NF-E-003", 2)
    _assert_error(run_cli("--json", "export", "x.json", "--format", "html"), "NF-E-003", 2)


def test_unknown_option() -> None:
    _assert_error(run_cli("--json", "map", "x.json", "--bogus"), "NF-E-003", 2)


# ---------------------------------------------------------------- 输入错误

def test_import_missing_file(tmp_path: Path) -> None:
    _assert_error(run_cli("--json", "import", str(tmp_path / "nope.md")), "NF-E-004", 2)


def test_map_bad_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    _assert_error(run_cli("--json", "map", str(bad)), "NF-E-004", 2)


def test_map_invalid_import_schema(tmp_path: Path) -> None:
    fixture = FIXTURES / "schema" / "invalid" / "nf-import" / "inv-detected-format-unknown.json"
    _assert_error(run_cli("--json", "map", str(fixture)), "NF-IMP-001", 3)


# ---------------------------------------------------------------- 核心缺失 → NF-E-005 exit 4

def test_missing_core_import(tmp_path: Path) -> None:
    env = _assert_error(
        run_cli(
            "--json",
            "import",
            str(SAMPLE_PACK / "docs" / "sample.md"),
            env=_env_missing_core(tmp_path),
        ),
        "NF-E-005",
        4,
    )
    fix = env["error"]["fix"]
    assert "app/core" in fix or "NF_APP_CORE" in fix, fix


def test_missing_core_selftest(tmp_path: Path) -> None:
    _assert_error(run_cli("--json", "selftest", env=_env_missing_core(tmp_path)), "NF-E-005", 4)


def test_missing_core_export(tmp_path: Path) -> None:
    # 先要过 docx 检查之前的项目加载：用 docx 直接命中 NF-EXP-004，不依赖核心；
    # 这里验证 md 导出在缺核心时是 NF-E-005。
    ws = helpers.make_workspace(tmp_path)
    project = helpers.project_doc(ws)
    pfile = helpers.write_project(ws, project)
    (ws / "out").mkdir()
    (ws / "out" / "result.md").write_bytes(("# 结果" + chr(10) + chr(10) + "正文。" + chr(10)).encode("utf-8"))
    _assert_error(
        run_cli("--json", "export", str(pfile), "--format", "md", env=_env_missing_core(tmp_path)),
        "NF-E-005",
        4,
    )


# ---------------------------------------------------------------- 导出器缺失（OPEN，不冒充）

@pytest.mark.parametrize("fmt", ["docx", "pdf"])
def test_export_docx_pdf_not_implemented(tmp_path: Path, fmt: str) -> None:
    result = run_cli("--json", "export", str(tmp_path / "missing.json"), "--format", fmt)
    env = _assert_error(result, "NF-EXP-004", 4)
    assert "md" in env["error"]["fix"] or "zip" in env["error"]["fix"]


def test_selftest_smoke_all_ops(core: Path) -> None:
    """selftest 必须真实跑核心 op 冒烟，全 op ok 且 exit 0（不是空壳）。"""
    result = run_cli("--json", "selftest")
    envelope = result.envelope()
    report = envelope["result"]
    assert report["schema"] == "nf-app-selftest/1"
    assert report["summary"]["total"] >= 18, report["summary"]
    failed = [step for step in report["ops"] if not step.get("ok")]
    assert not failed, failed
    assert envelope["exit"] == 0
    assert report["ok"] is True


# ---------------------------------------------------------------- 项目状态机

def test_project_set_same_status_noop(tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    project = helpers.project_doc(ws, status="authoring")
    pfile = helpers.write_project(ws, project)
    result = run_cli("--json", "project", "set", str(pfile), "--status", "authoring")
    env = result.envelope()
    assert env["exit"] == 0
    assert env["result"]["changed"] is False
    assert helpers.load_json(pfile)["history"] == []


def test_project_set_retreat_requires_force(tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    pfile = helpers.write_project(ws, helpers.project_doc(ws, status="assembled"))
    _assert_error(
        run_cli("--json", "project", "set", str(pfile), "--status", "draft"),
        "NF-E-003",
        2,
    )
    assert helpers.load_json(pfile)["status"] == "assembled", "失败不落盘"


def test_project_set_force_retreat_writes_history(tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    project = helpers.project_doc(ws, status="assembled")
    pfile = helpers.write_project(ws, project)
    pre_digest = helpers.project_digest(project)
    env = run_cli(
        "--json",
        "project",
        "set",
        str(pfile),
        "--status",
        "draft",
        "--force",
        "--at",
        "2026-11-15T00:00:00Z",
    ).envelope()
    assert env["exit"] == 0
    updated = helpers.load_json(pfile)
    assert updated["status"] == "draft"
    assert len(updated["history"]) == 1
    entry = updated["history"][0]
    assert entry["op"] == "status:force-retreat:assembled->draft"
    assert entry["at"] == "2026-11-15T00:00:00Z"
    assert entry["digest"] == pre_digest, "history digest 必须是变更前项目摘要"
    assert env["result"]["project"]["status"] == "draft"


def test_project_set_forward_needs_core(tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    pfile = helpers.write_project(ws, helpers.project_doc(ws, status="draft"))
    _assert_error(
        run_cli(
            "--json",
            "project",
            "set",
            str(pfile),
            "--status",
            "authoring",
            env=_env_missing_core(tmp_path),
        ),
        "NF-E-005",
        4,
    )
    assert helpers.load_json(pfile)["status"] == "draft", "核心不可用时不得推进状态"


def test_project_init_requires_refs(tmp_path: Path) -> None:
    target = tmp_path / "project.nfproject.json"
    _assert_error(
        run_cli("--json", "project", "init", str(target), "--id", "p1"),
        "NF-E-003",
        2,
    )
    assert not target.exists()


def test_project_init_refuses_overwrite_without_force(tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    target = ws / "project.nfproject.json"
    target.write_text("{}", encoding="utf-8")
    _assert_error(
        run_cli(
            "--json",
            "project",
            "init",
            str(target),
            "--id",
            "p1",
            "--base-pack",
            str(ws / "pack"),
            "--graph",
            str(ws / "pack" / "pipeline" / "main.nfg.json"),
            "--spec",
            str(ws / "pack" / "spec" / "main.nfspec.json"),
        ),
        "NF-E-003",
        2,
    )


# ---------------------------------------------------------------- author 本地守卫

def test_author_graph_weight_out_of_range(tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    graph = ws / "pack" / "pipeline" / "main.nfg.json"
    before = graph.read_bytes()
    _assert_error(run_cli("--json", "author", "graph", str(graph), "--weight", "N04=150"), "NF-GRF-007", 1)
    assert graph.read_bytes() == before


def test_author_graph_duplicate_node(tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    graph = ws / "pack" / "pipeline" / "main.nfg.json"
    _assert_error(
        run_cli("--json", "author", "graph", str(graph), "--add-node", "N02:gate:重复"),
        "NF-GRF-002",
        1,
    )


def test_author_protocol_missing_clause(tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    pack = ws / "pack" / "protocol" / "nf-protocol-pack.json"
    _assert_error(
        run_cli("--json", "author", "protocol", str(pack), "--clause", "C-999", "--enable"),
        "NF-E-003",
        2,
    )


def test_author_spec_missing_slot(tmp_path: Path) -> None:
    ws = helpers.make_workspace(tmp_path)
    spec = ws / "pack" / "spec" / "main.nfspec.json"
    _assert_error(
        run_cli("--json", "author", "spec", str(spec), "--slot", "SLT-99", "--max-chars", "10"),
        "NF-E-003",
        2,
    )


# ---------------------------------------------------------------- pack 备份 / 回滚

def test_pack_rollback_missing_backup(tmp_path: Path) -> None:
    _assert_error(
        run_cli("--json", "pack", "rollback", "--backup", str(tmp_path / "bk"), "--target", str(tmp_path / "t")),
        "NF-PCK-007",
        2,
    )


def test_pack_rollback_roundtrip(tmp_path: Path) -> None:
    from nf_app.commands.pack_cmd import _snapshot

    target = tmp_path / "appdata" / "demo-pack"
    (target / "docs").mkdir(parents=True)
    (target / "docs" / "a.md").write_bytes(b"# A\n")
    (target / "docs" / "b.md").write_bytes(b"# B\n")
    backup = tmp_path / "backup"
    manifest = _snapshot(target, backup)
    # 模拟 apply 后的漂移：改一个、删一个、加一个
    (target / "docs" / "a.md").write_bytes(b"# A changed\n")
    (target / "docs" / "b.md").unlink()
    (target / "docs" / "c.md").write_bytes(b"# C\n")

    env = run_cli("--json", "pack", "rollback", "--backup", str(backup), "--target", str(target)).envelope()
    assert env["exit"] == 0, env
    assert (target / "docs" / "a.md").read_bytes() == b"# A\n"
    assert (target / "docs" / "b.md").read_bytes() == b"# B\n"
    assert not (target / "docs" / "c.md").exists()
    assert env["result"]["restored"] == 2
    assert env["result"]["removed"] == 1
    assert env["result"]["tree"] == manifest["tree"]


def test_pack_rollback_target_mismatch(tmp_path: Path) -> None:
    from nf_app.commands.pack_cmd import _snapshot

    target = tmp_path / "data"
    target.mkdir()
    (target / "x.md").write_bytes(b"x")
    backup = tmp_path / "backup"
    _snapshot(target, backup)
    _assert_error(
        run_cli("--json", "pack", "rollback", "--backup", str(backup), "--target", str(tmp_path / "other")),
        "NF-PCK-007",
        2,
    )


def test_pack_rollback_corrupt_backup(tmp_path: Path) -> None:
    from nf_app.commands.pack_cmd import _snapshot

    target = tmp_path / "data"
    target.mkdir()
    (target / "x.md").write_bytes(b"x")
    backup = tmp_path / "backup"
    _snapshot(target, backup)
    (backup / "files" / "x.md").write_bytes(b"tampered")
    _assert_error(
        run_cli("--json", "pack", "rollback", "--backup", str(backup), "--target", str(target)),
        "NF-PCK-007",
        2,
    )


# ---------------------------------------------------------------- share 脱敏

def _share_project(tmp_path: Path) -> Path:
    ws = helpers.make_workspace(tmp_path)
    return helpers.write_project(ws, helpers.project_doc(ws, status="authoring"))


def test_share_prompt_no_sensitive_content(tmp_path: Path) -> None:
    pfile = _share_project(tmp_path)
    first = run_cli("--json", "share", "prompt", "--project", str(pfile))
    env = first.envelope()
    assert env["exit"] == 0
    content = env["result"]["content"]
    assert "执行面" in content and "demo-pack" in content
    assert "C:\\Users\\" not in content and "/home/" not in content
    second = run_cli("--json", "share", "prompt", "--project", str(pfile))
    assert second.stdout == first.stdout, "share 输出必须确定性（同输入同字节）"


def test_share_masks_paths_emails_secrets(tmp_path: Path) -> None:
    pfile = _share_project(tmp_path)
    text = (
        "补充：路径 C:\\Users\\alice\\ws\\x.md 与 /home/bob/y；"
        "邮箱 a@b.com；token sk-abcdefghijklmnopqrstuvwxyz012345"
    )
    env = run_cli("--json", "share", "markdown", "--project", str(pfile), "--text", text).envelope()
    assert env["exit"] == 0, env
    content = env["result"]["content"]
    assert "alice" not in content and "bob" not in content
    assert "a@b.com" not in content
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in content
    assert set(env["result"]["masks"]) >= {"home", "email", "openai_key"}, env["result"]["masks"]


def test_share_json_kind(tmp_path: Path) -> None:
    pfile = _share_project(tmp_path)
    env = run_cli("--json", "share", "json", "--project", str(pfile)).envelope()
    assert env["exit"] == 0
    payload = env["result"]["content"]
    assert payload["schema"] == "nf-share/1"
    assert payload["project"]["id"] == "demo-project"
    assert payload["project"]["status"] == "authoring"


def test_share_requires_source() -> None:
    _assert_error(run_cli("--json", "share", "prompt"), "NF-E-003", 2)


def test_share_out_file(tmp_path: Path) -> None:
    pfile = _share_project(tmp_path)
    out = tmp_path / "share.md"
    env = run_cli("--json", "share", "markdown", "--project", str(pfile), "--out", str(out)).envelope()
    assert env["exit"] == 0
    assert out.is_file()
    assert out.read_text(encoding="utf-8").startswith("# 分享")


# ---------------------------------------------------------------- --json 全子命令

@pytest.mark.parametrize(
    "prefix",
    [
        ["import"],
        ["map"],
        ["project", "init"],
        ["project", "status"],
        ["project", "set"],
        ["author", "protocol"],
        ["author", "graph"],
        ["author", "spec"],
        ["assemble"],
        ["validate"],
        ["export"],
        ["share", "prompt"],
        ["share", "markdown"],
        ["share", "json"],
        ["pack", "update"],
        ["pack", "apply"],
        ["pack", "rollback"],
        ["ccos", "task"],
        ["ccos", "import-result"],
        ["ccos", "review"],
        ["selftest"],
    ],
)
def test_json_flag_accepted_everywhere(prefix: list[str]) -> None:
    for args in (["--json", *prefix], [*prefix, "--json"]):
        result = run_cli(*args)
        assert result.returncode in (0, 1, 2, 3, 4), result.stderr
        env = json.loads(result.stdout.strip())
        assert set(env) == {"ok", "exit", "result", "error"}
        assert env["exit"] == result.returncode
        if result.returncode != 0 and env["error"] is not None:
            assert env["error"]["code"].startswith("NF-")
        if result.returncode != 0 and env["error"] is None:
            # exit 1 的校验失败允许 result=report、error=null（CLI.md §2）
            assert env["result"] is not None, env

# ---------------------------------------------------------------- 核心 CLI 协议（每 op 请求/响应/退出码）

def _core_protocol_cases(core: Path, root: Path) -> dict[str, dict]:
    """构造 CLI.md op 表里每个 op 的合法请求（只构造一次，session 级）。"""
    import hashlib
    import shutil as _shutil

    import helpers as _helpers

    root.mkdir(parents=True, exist_ok=True)
    pack = FIXTURES / "sample-pack"
    pack_v2 = FIXTURES / "sample-pack-v2"
    graph = json.loads((pack / "pipeline" / "main.nfg.json").read_text(encoding="utf-8"))
    spec = json.loads((pack / "spec" / "main.nfspec.json").read_text(encoding="utf-8"))
    protocol = json.loads((pack / "protocol" / "nf-protocol-pack.json").read_text(encoding="utf-8"))

    def envelope(op: str, request: dict) -> dict:
        code, stdout, stderr = run_core_raw(core, op, request)
        assert stdout.strip(), f"{op} 无输出（exit={code}, stderr={stderr[:300]!r}）"
        payload = json.loads(stdout.decode("utf-8"))
        assert payload["exit"] == code
        assert payload["ok"] is (code == 0)
        return payload

    cases: dict[str, dict] = {}
    cases["canonical"] = {"value": {"b": 1, "a": [True, None, "ü"], "z": {"k": "v"}}}
    cases["pack-hash"] = {"root": str(pack)}
    cases["pack-verify"] = {"root": str(pack)}
    imported = envelope("import", {"file": str(pack / "docs" / "sample.md"), "source": {"kind": "file", "name": "sample.md"}})["result"]
    cases["import"] = {"file": str(pack / "docs" / "sample.md"), "source": {"kind": "file", "name": "sample.md"}}
    cases["map-suggest"] = {"import": imported, "spec": spec}
    cases["protocol-validate"] = {"pack": protocol}
    cases["protocol-render"] = {"pack": protocol, "values": {"F-001": "灯灭之前别回头", "F-002": "冷静"}}
    cases["graph-validate"] = {"graph": graph}
    cases["graph-compile"] = {"graph": graph, "spec": spec}
    cases["spec-validate"] = {"spec": spec}
    plan = envelope("graph-compile", cases["graph-compile"])["result"]
    out_dir = root / "out"
    out_dir.mkdir(exist_ok=True)
    cases["assemble"] = {
        "plan": plan,
        "spec": spec,
        "inputs": {
            "SLT-01": "灯灭之前，别回头。",
            "SLT-02": "面向喜欢西幻生存的读者。",
            "SLT-03": "雨夜的边境小镇。",
        },
        "out_dir": str(out_dir),
    }
    assembled = envelope("assemble", cases["assemble"])["result"]
    markdown = assembled["markdown"]
    cases["validate"] = {"markdown": markdown, "spec": spec, "plan": plan, "level": "L0"}
    export_dir = root / "export"
    export_dir.mkdir(exist_ok=True)
    cases["export"] = {"markdown": markdown, "format": "zip", "out_dir": str(export_dir), "manifest": True}
    cases["pack-diff"] = {"old_root": str(pack), "new_root": str(pack_v2)}
    update = envelope("pack-diff", cases["pack-diff"])["result"]
    ws = _helpers.make_workspace(root / "ws-root")
    overlay = _helpers.overlay_doc(ws)
    merge_dir = root / "merge"
    merge_dir.mkdir(exist_ok=True)
    cases["pack-merge"] = {
        "update": update,
        "base_root": str(pack),
        "new_root": str(pack_v2),
        "overlay": overlay,
        "decisions": {"CFL-01": "keep_mine"},
        "out_dir": str(merge_dir),
    }
    overlay_dir = root / "overlay-out"
    overlay_dir.mkdir(exist_ok=True)
    cases["overlay-apply"] = {"base_root": str(pack), "overlay": overlay, "out_dir": str(overlay_dir)}
    cases["project-validate"] = {"project": _helpers.project_doc(ws, status="authoring")}
    plan_path = ws / "out" / "plan.nfplan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(_helpers.canonical_text(plan).encode("utf-8"))
    validated = _helpers.project_doc(ws, status="validated")
    validated["refs"]["assembly"] = {
        "id": plan["pipeline"]["id"],
        "version": plan["pipeline"]["version"],
        "digest": plan["digest"],
        "path": "out/plan.nfplan.json",
        "sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
    }
    validated["history"] = [
        {"op": "assemble", "at": "2026-11-15T00:00:00Z", "digest": "a" * 64},
        {"op": "validate:L0", "at": "2026-11-15T00:00:00Z", "digest": "b" * 64},
    ]
    cases["ccos-build-task"] = {
        "project": validated,
        "task_id": "protocol-task-0001",
        "created_at": "2026-11-15T00:00:00Z",
        "budget": {"max_tokens": 1000, "max_chars": 4000, "max_seconds": 600},
    }
    task = envelope("ccos-build-task", cases["ccos-build-task"])["result"]
    cases["ccos-import-result"] = {"task": task, "result": _helpers.ccos_result_doc(task)}
    return cases


@pytest.fixture(scope="session")
def core_protocol_cases(core: Path, tmp_path_factory) -> dict[str, dict]:
    return _core_protocol_cases(core, tmp_path_factory.mktemp("core-ops"))


def test_core_abi_version(core: Path) -> None:
    import subprocess as _sp

    proc = _sp.run([str(core), "--abi-version"], capture_output=True, timeout=60, check=False)
    info = json.loads(proc.stdout.decode("utf-8"))
    assert info["abi"] == "nf-app-core/1"
    assert re_semver(info["version"])


def re_semver(text: str) -> bool:
    import re as _re

    return bool(_re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", text))


def test_every_core_op_envelope(core: Path, core_protocol_cases: dict) -> None:
    """CLI.md op 表逐 op：请求可被接受、信封字段齐全、exit 与 ok 一致。"""
    expected_ops = {
        "canonical",
        "pack-hash",
        "pack-verify",
        "import",
        "map-suggest",
        "protocol-validate",
        "protocol-render",
        "graph-validate",
        "graph-compile",
        "spec-validate",
        "assemble",
        "validate",
        "export",
        "pack-diff",
        "pack-merge",
        "overlay-apply",
        "project-validate",
        "ccos-build-task",
        "ccos-import-result",
    }
    assert set(core_protocol_cases) == expected_ops
    for op, request in core_protocol_cases.items():
        code, stdout, stderr = run_core_raw(core, op, request)
        assert stdout.strip(), f"{op} 无输出（exit={code}, stderr={stderr[:300]!r}）"
        envelope = json.loads(stdout.decode("utf-8"))
        assert set(envelope) == {"ok", "exit", "result", "error"}, op
        assert envelope["exit"] == code, op
        assert envelope["ok"] is (code == 0), op
        if code == 0:
            assert envelope["error"] is None, op
        else:  # pragma: no cover - 合法请求不应失败
            pytest.fail(f"{op} 合法请求失败: exit={code}, error={envelope['error']}")
    # validate/assemble/export 走 exit0 校验通过
    assert core_protocol_cases["validate"]["level"] == "L0"


def test_core_unknown_op_rejected(core: Path) -> None:
    code, stdout, _ = run_core_raw(core, "bogus-op", {})
    assert code == 2
    envelope = json.loads(stdout.decode("utf-8"))
    assert envelope["error"]["code"] == "NF-E-003"
    assert envelope["result"] is None


def test_core_bad_json_rejected(core: Path) -> None:
    import subprocess as _sp

    for payload in (b"{oops", b"", b"[1,2]"):
        proc = _sp.run([str(core), "canonical", "--in", "-"], input=payload, capture_output=True, timeout=60, check=False)
        assert proc.returncode == 2, payload
        envelope = json.loads(proc.stdout.decode("utf-8"))
        assert envelope["error"]["code"] == "NF-E-003", payload
        assert envelope["ok"] is False


def test_core_missing_request_field_rejected(core: Path) -> None:
    for op, request in (("canonical", {}), ("pack-hash", {}), ("graph-validate", {})):
        code, stdout, _ = run_core_raw(core, op, request)
        assert code == 2, op
        envelope = json.loads(stdout.decode("utf-8"))
        assert envelope["error"]["code"] == "NF-E-003", op
        assert envelope["error"]["message"] and envelope["error"]["fix"]
