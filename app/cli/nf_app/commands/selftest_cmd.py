"""selftest：跑一遍核心 op 冒烟（覆盖 import/map/validate/compile/assemble/export/pack/ccos）。

输出 JSON（nf-app-selftest/1），exit 0 全通过 / 1 有失败；
核心缺失 → NF-E-005（exit 4），绝不把缺核心当通过。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .. import core
from ..canonical import digest
from ..errors import AppError
from ..io_utils import write_bytes_atomic
from ..paths import fixtures_dir
from ..schemas import validate as schema_validate
from .common import Outcome, format_human, load_doc, plan_digest

FIXED_AT = "2026-11-15T00:00:00Z"


def _canonical_request() -> dict:
    return {"value": {"b": 1, "a": [True, None, "ü"], "z": {"k": "v"}}}


def cmd_selftest(args) -> Outcome:
    core.resolve_core()  # 缺核心 → AppError NF-E-005（exit 4）
    fixtures = fixtures_dir()
    pack = fixtures / "sample-pack"
    pack_v2 = fixtures / "sample-pack-v2"
    steps: list[dict] = []

    def record(op: str, fn, *, expect_code: str | None = None) -> bool:
        entry: dict = {"op": op}
        try:
            value = fn()
            entry.update({"ok": True, "exit": 0})
            steps.append(entry)
            return True
        except AppError as exc:
            entry.update({"exit": int(exc.exit or 0), "code": exc.code})
            if expect_code is not None and exc.code == expect_code:
                entry.update({"ok": True, "expected": True})
                steps.append(entry)
                return True
            entry.update({"ok": False, "message": exc.message})
            steps.append(entry)
            return False
        except Exception as exc:  # noqa: BLE001 - 冒烟要把任何异常记成失败
            entry.update({"ok": False, "exit": 2, "message": repr(exc)})
            steps.append(entry)
            return False

    manifest = load_doc(pack / "nf-pack.json", "nf-pack")
    spec = load_doc(pack / "spec" / "main.nfspec.json", "nf-md-spec")
    graph = load_doc(pack / "pipeline" / "main.nfg.json", "nf-pipeline-graph")
    protocol = load_doc(pack / "protocol" / "nf-protocol-pack.json", "nf-protocol-pack")

    with tempfile.TemporaryDirectory(prefix="nf-selftest-") as tmp:
        tmpdir = Path(tmp)
        out_dir = tmpdir / "out"
        export_md = tmpdir / "export-md"
        export_zip = tmpdir / "export-zip"
        for directory in (out_dir, export_md, export_zip):
            directory.mkdir(parents=True, exist_ok=True)  # 核心不建用户目录树（CLI.md §1）

        def step_canonical():
            result = core.call_ok("canonical", _canonical_request())
            if result.get("digest") != digest(_canonical_request()["value"]):
                raise AppError("NF-E-005", message="canonical digest 与 Python 独立实现对不上")
            return result

        def step_pack_hash():
            result = core.call_ok("pack-hash", {"root": str(pack)})
            if result["hashes"]["tree"] != manifest["hashes"]["tree"]:
                raise AppError("NF-PCK-002", message="pack-hash tree 与清单 tree 不一致")
            return result

        def step_pack_verify():
            result = core.call_ok("pack-verify", {"root": str(pack)})
            if result.get("verdict") != "pass":
                raise AppError("NF-PCK-002", message=f"pack-verify verdict={result.get('verdict')}")
            return result

        def step_import():
            result = core.call_ok(
                "import",
                {
                    "file": str(pack / "docs" / "sample.md"),
                    "source": {"kind": "file", "name": "sample.md"},
                },
            )
            errors = schema_validate("nf-import", result)
            if errors:
                raise AppError("NF-IMP-001", message=f"import 产物结构非法: {errors[0]['message']}")
            return result

        imported: dict = {}

        def step_import_keep():
            imported["doc"] = step_import()
            return imported["doc"]

        def step_map():
            return core.call_ok("map-suggest", {"import": imported["doc"], "spec": spec})

        def step_protocol():
            return core.call_ok("protocol-validate", {"pack": protocol})

        def step_protocol_render():
            return core.call_ok(
                "protocol-render",
                {"pack": protocol, "values": {"F-001": "灯灭之前别回头", "F-002": "冷静"}},
            )

        def step_graph():
            return core.call_ok("graph-validate", {"graph": graph})

        def step_spec():
            return core.call_ok("spec-validate", {"spec": spec})

        plan_box: dict = {}

        def step_compile():
            plan_box["plan"] = core.call_ok("graph-compile", {"graph": graph, "spec": spec})
            if plan_digest(plan_box["plan"]) != plan_box["plan"]["digest"]:
                raise AppError("NF-ASM-001", message="plan.digest 与内容不符")
            return plan_box["plan"]

        def step_assemble():
            result = core.call_ok(
                "assemble",
                {
                    "plan": plan_box["plan"],
                    "spec": spec,
                    "inputs": {
                        "SLT-01": "灯灭之前，别回头。",
                        "SLT-02": "面向喜欢西幻生存的读者。",
                        "SLT-03": "雨夜的边境小镇，主角必须在一个时辰内找到落脚点。",
                    },
                    "out_dir": str(out_dir),
                },
            )
            errors = schema_validate("nf-assemble-result", result.get("meta") or {})
            if errors:
                raise AppError("NF-ASM-003", message=f"assemble meta 不满足 schema: {errors[0]['message']}")
            if not (out_dir / "result.md").is_file():
                raise AppError("NF-E-004", message="assemble 未写出 result.md")
            return result

        def _markdown() -> str:
            result_md = out_dir / "result.md"
            if not result_md.is_file():
                raise AppError("NF-E-004", message="assemble 未写出 result.md")
            return result_md.read_text(encoding="utf-8")

        def step_validate_l0():
            return core.call_ok(
                "validate",
                {"markdown": _markdown(), "spec": spec, "plan": plan_box["plan"], "level": "L0"},
            )

        def step_validate_l1():
            return core.call_ok(
                "validate",
                {"markdown": _markdown(), "spec": spec, "plan": plan_box["plan"], "level": "L1"},
            )

        def _check_manifest(result):
            errors = schema_validate("nf-export-manifest", result or {})
            if errors:
                raise AppError("NF-EXP-001", message=f"export manifest 不满足 schema: {errors[0]['message']}")
            return result

        def step_export_md():
            return _check_manifest(
                core.call_ok(
                    "export",
                    {"markdown": _markdown(), "format": "md", "out_dir": str(export_md), "manifest": True},
                )
            )

        def step_export_zip():
            first = _check_manifest(
                core.call_ok(
                    "export",
                    {"markdown": _markdown(), "format": "zip", "out_dir": str(export_zip), "manifest": True},
                )
            )
            zip_path = export_zip / "result.zip"
            first_bytes = zip_path.read_bytes()
            second = core.call_ok(
                "export",
                {"markdown": _markdown(), "format": "zip", "out_dir": str(export_zip), "manifest": True},
            )
            if zip_path.read_bytes() != first_bytes:
                raise AppError("NF-EXP-001", message="zip 导出不确定（两次字节不同）")
            if first.get("outputs") != second.get("outputs"):
                raise AppError("NF-EXP-001", message="export manifest 不确定")
            return first

        def step_pack_diff():
            return core.call_ok("pack-diff", {"old_root": str(pack), "new_root": str(pack_v2)})

        project_box: dict = {}

        def step_project():
            workspace = tmpdir / "ws"
            workspace.mkdir()
            import shutil

            shutil.copytree(pack, workspace / "pack")
            spec_ref = {
                "id": spec["id"],
                "version": spec["version"],
                "digest": digest(spec),
                "path": "pack/spec/main.nfspec.json",
                "sha256": __import__("hashlib").sha256((workspace / "pack/spec/main.nfspec.json").read_bytes()).hexdigest(),
            }
            graph_ref = {
                "id": graph["id"],
                "version": graph["version"],
                "digest": digest(graph),
                "path": "pack/pipeline/main.nfg.json",
                "sha256": __import__("hashlib").sha256((workspace / "pack/pipeline/main.nfg.json").read_bytes()).hexdigest(),
            }
            project = {
                "schema": "nf-project/1",
                "id": "selftest-project",
                "title": "selftest",
                "refs": {
                    "base_pack": {"id": manifest["id"], "version": manifest["version"], "tree": manifest["hashes"]["tree"]},
                    "graph": graph_ref,
                    "spec": spec_ref,
                },
                "status": "authoring",
                "review": {"state": "none"},
                "history": [],
            }
            project_box["doc"] = project
            return core.call_ok("project-validate", {"project": project})

        def step_ccos_task():
            # 项目未 validated → 核心必须拒绝（NF-CCOS-001）；这里把 op 可达性纳入冒烟
            if "doc" not in project_box:
                raise AppError("NF-E-005", message="project 冒烟未成功，ccos 冒烟不可达（这是失败不是通过）")
            return core.call_ok(
                "ccos-build-task",
                {
                    "project": project_box["doc"],
                    "task_id": "selftest-task-0001",
                    "created_at": FIXED_AT,
                    "budget": {"max_tokens": 1000, "max_chars": 4000, "max_seconds": 600},
                },
            )

        record("canonical", step_canonical)
        record("pack-hash", step_pack_hash)
        record("pack-verify", step_pack_verify)
        record("import", step_import_keep)
        record("map-suggest", step_map)
        record("protocol-validate", step_protocol)
        record("protocol-render", step_protocol_render)
        record("graph-validate", step_graph)
        record("spec-validate", step_spec)
        record("graph-compile", step_compile)
        record("assemble", step_assemble)
        record("validate:L0", step_validate_l0)
        record("validate:L1", step_validate_l1)
        record("export:md", step_export_md)
        record("export:zip", step_export_zip)
        record("pack-diff", step_pack_diff)
        record("project-validate", step_project)
        record("ccos-build-task(预期 NF-CCOS-001)", step_ccos_task, expect_code="NF-CCOS-001")
        record("export:docx(预期 NF-EXP-004)", lambda: core.call_ok("export", {"markdown": "x", "format": "docx", "out_dir": str(tmpdir)}), expect_code="NF-EXP-004")
        record("canonical:float(预期 NF-E-006)", lambda: core.call_ok("canonical", {"value": 1.5}), expect_code="NF-E-006")

    ok_count = sum(1 for step in steps if step.get("ok"))
    fail_count = len(steps) - ok_count
    result = {
        "schema": "nf-app-selftest/1",
        "ok": fail_count == 0,
        "ops": steps,
        "summary": {"total": len(steps), "ok": ok_count, "fail": fail_count},
    }
    human = format_human(
        f"核心冒烟: {'通过' if fail_count == 0 else '失败'}",
        [(step["op"], f"ok={step.get('ok')} exit={step.get('exit')}" + (f" code={step.get('code')}" if step.get("code") else "")) for step in steps],
    )
    return Outcome(result, human, 0 if fail_count == 0 else 1)
