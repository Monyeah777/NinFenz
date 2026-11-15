"""assemble / validate / export：编译 plan → 装配 → 校验 → 导出（全部经核心）。"""

from __future__ import annotations

from pathlib import Path

from .. import core
from ..canonical import digest, sha256_hex
from ..errors import AppError, envelope_from_core
from ..io_utils import (
    ensure_dir,
    read_json,
    read_text,
    rel_posix,
    sha256_file,
    write_bytes_atomic,
    write_json_atomic,
)
from ..schemas import validate as schema_validate
from .common import (
    STATE_ORDER,
    Outcome,
    append_history,
    doc_digest,
    format_human,
    load_doc,
    plan_digest,
    project_digest,
    require,
)

VALID_LEVELS = ("L0", "L1", "L2")
EXPORT_FORMATS = ("md", "zip", "json", "docx", "skill", "pdf")


def _verify_file_ref(base: Path, ref: dict, *, what: str) -> Path:
    target = base / ref["path"]
    if not target.is_file():
        raise AppError("NF-E-004", message=f"项目引用文件不存在（{what}）: {target}", fix="重建项目引用或恢复文件")
    actual = sha256_file(target)
    if actual != ref["sha256"]:
        raise AppError(
            "NF-ASM-001",
            message=f"{what} 文件摘要与项目引用不一致（可能被并发修改）",
            fix="重新 init/set 项目引用，或恢复文件原状",
            path=f"$.refs.{what.replace(' ', '_')}.sha256",
        )
    return target


def _load_inputs(path: str | None) -> dict:
    if not path:
        return {}
    data = read_json(Path(path))
    if not isinstance(data, dict):
        raise AppError("NF-E-004", message="inputs 文件必须是 {slot: 值} 对象", fix="例：{\"SLT-01\": \"……\"}")
    for key, value in data.items():
        if not isinstance(key, str):
            raise AppError("NF-E-003", message="inputs 键必须是槽位 id", fix="用 SLT-##")
        if not isinstance(value, str):
            raise AppError("NF-E-003", message=f"inputs[{key}] 必须是字符串", fix="assemble 只接受字符串值")
    return data


def _set_status_forward(project: dict, target: str) -> bool:
    if STATE_ORDER.index(project["status"]) < STATE_ORDER.index(target):
        project["status"] = target
        return True
    return False


def _find_result_md(base: Path, explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = base / path
        if not path.is_file():
            raise AppError("NF-E-004", message=f"找不到装配结果: {path}", fix="先跑 nf-app assemble")
        return path
    for candidate in (base / "out" / "result.md", base / "result.md"):
        if candidate.is_file():
            return candidate
    raise AppError("NF-E-004", message=f"找不到 result.md（{base}）", fix="先跑 nf-app assemble，或用 --markdown 指定")


def cmd_assemble(args) -> Outcome:
    project_path = Path(args.project)
    project = load_doc(project_path, "nf-project")
    base = project_path.resolve().parent
    refs = project["refs"]
    graph_path = _verify_file_ref(base, refs["graph"], what="graph")
    spec_path = _verify_file_ref(base, refs["spec"], what="spec")
    graph = load_doc(graph_path, "nf-pipeline-graph")
    spec = load_doc(spec_path, "nf-md-spec")
    inputs = _load_inputs(args.inputs)
    out_dir = Path(args.out) if args.out else base / "out"
    ensure_dir(out_dir)

    plan: dict | None = None
    plan_path: Path | None = None
    assembly_ref = refs.get("assembly")
    if assembly_ref:
        candidate = base / assembly_ref["path"]
        if candidate.is_file():
            try:
                candidate_doc = load_doc(candidate, "nf-assembly-plan")
            except AppError:
                candidate_doc = None
            if candidate_doc is not None and plan_digest(candidate_doc) == assembly_ref["digest"]:
                plan, plan_path = candidate_doc, candidate
    if plan is None:
        plan = core.call_ok("graph-compile", {"graph": graph, "spec": spec})
        plan_path = write_json_atomic(out_dir / "plan.nfplan.json", plan, canonical=True)

    request: dict = {"plan": plan, "spec": spec, "inputs": inputs, "out_dir": str(out_dir)}
    if args.stage:
        request["stage"] = args.stage
    if args.block:
        base_md = out_dir / "result.md"
        if not base_md.is_file():
            raise AppError(
                "NF-ASM-004",
                message=f"块级编辑需要既有 result.md（base_markdown）: {base_md}",
                fix="先整篇 assemble，再用 --block 只替换该节（其余字节保留）",
            )
        request["block"] = args.block
        request["base_markdown"] = base_md.read_text(encoding="utf-8")
    assembled = core.call_ok("assemble", request)
    markdown = assembled.get("markdown", "")

    result_md = out_dir / "result.md"
    if args.block:
        # 块级编辑：核心返回整篇（只替换目标节，其余字节保留）→ 写回 result.md
        write_bytes_atomic(result_md, markdown.encode("utf-8"))
        meta_blocks = assembled.get("meta") or {}
        errors = schema_validate("nf-assemble-result", meta_blocks)
        require(not errors, "NF-ASM-003", f"assemble meta 不满足 nf-assemble-result/1: {errors[0]['message'] if errors else ''}", fix="按 schema 修元数据")
        write_json_atomic(out_dir / "result.meta.json", meta_blocks, canonical=True)
        return Outcome(
            {
                "meta": meta_blocks,
                "block": args.block,
                "result_md": str(result_md),
                "markdown_digest": sha256_hex(markdown.encode("utf-8")),
            },
            format_human("块级装配完成", [("节", args.block), ("result.md", str(result_md)), ("plan digest", plan["digest"])]),
        )

    core_meta = assembled.get("meta") or {}
    result_meta = out_dir / "result.meta.json"
    if not result_md.is_file():
        raise AppError("NF-E-004", message=f"核心未写出 result.md: {result_md}", fix="核对 assemble 的 out_dir 语义")

    # 以核心 meta 为准（核心已按 nf-assemble-result/1 输出）；不合 schema 时由 CLI 按
    # 同一 schema 归一兜底（chars=写入字符数近似），保证产物始终可校验。
    markdown_digest = sha256_hex(markdown.encode("utf-8"))
    errors = schema_validate("nf-assemble-result", core_meta)
    if errors:
        slot_rows = []
        missing = []
        for slot in spec["slots"]:
            value = inputs.get(slot["id"])
            if value is None:
                if slot.get("required"):
                    missing.append(slot["id"])
                chars = 0
            else:
                chars = len(value)
            slot_rows.append({"id": slot["id"], "section": slot["section"], "chars": chars})
        core_meta = {
            "schema": "nf-assemble-result/1",
            "plan_digest": plan_digest(plan),
            "spec_digest": doc_digest(spec),
            "markdown_digest": markdown_digest,
            "slots": slot_rows,
            "missing": missing,
        }
        errors = schema_validate("nf-assemble-result", core_meta)
    require(
        not errors,
        "NF-ASM-003",
        f"assemble meta 不满足 nf-assemble-result/1: {errors[0]['message'] if errors else ''}",
        fix="按 app/schema/nf-assemble-result.schema.json 修元数据",
    )
    meta = core_meta
    write_json_atomic(result_meta, meta, canonical=True)

    pre_digest = project_digest(project)
    refs["assembly"] = {
        "id": plan["pipeline"]["id"],
        "version": plan["pipeline"]["version"],
        "digest": plan["digest"],
        "path": rel_posix(plan_path, base),
        "sha256": sha256_file(plan_path),
    }
    _set_status_forward(project, "assembled")
    append_history(project, "assemble", at=args.at, pre_digest=pre_digest)
    core.call_ok("project-validate", {"project": project})
    write_json_atomic(project_path, project, canonical=True)

    human = format_human(
        "装配完成",
        [
            ("输出目录", str(out_dir)),
            ("result.md", f"{result_md.stat().st_size} 字节"),
            ("plan digest", plan["digest"]),
            ("项目状态", project["status"]),
        ],
    )
    return Outcome(
        {
            "meta": meta,
            "out_dir": str(out_dir),
            "result_md": str(result_md),
            "markdown_digest": markdown_digest,
            "plan": {"path": str(plan_path), "digest": plan["digest"]},
            "project": project,
            "status": project["status"],
        },
        human,
    )


def cmd_validate(args) -> Outcome:
    project_path = Path(args.project)
    project = load_doc(project_path, "nf-project")
    base = project_path.resolve().parent
    refs = project["refs"]
    markdown_path = _find_result_md(base, args.markdown)
    markdown = read_text(markdown_path)
    spec_path = _verify_file_ref(base, refs["spec"], what="spec")
    spec = load_doc(spec_path, "nf-md-spec")
    assembly_ref = refs.get("assembly")
    if not assembly_ref:
        raise AppError("NF-E-004", message="项目缺 assembly 引用", fix="先跑 nf-app assemble")
    plan_path = _verify_file_ref(base, assembly_ref, what="assembly")
    plan = load_doc(plan_path, "nf-assembly-plan")
    require(
        plan_digest(plan) == assembly_ref["digest"],
        "NF-ASM-001",
        "plan 内容 digest 与项目引用不一致",
        fix="重新编译 plan 或刷新项目引用",
    )
    envelope = core.call(
        "validate",
        {"markdown": markdown, "spec": spec, "plan": plan, "level": args.level},
    )
    report = envelope.get("result")
    report_path = Path(args.out) if args.out else base / f"report-{args.level}.nfreport.json"
    if isinstance(report, dict):
        write_json_atomic(report_path, report, canonical=True)
    err = envelope_from_core(envelope)
    if err is not None:
        err.result = report
        raise err
    if args.record and report["verdict"] != "fail" and args.level in ("L0", "L1"):
        pre_digest = project_digest(project)
        if _set_status_forward(project, "validated"):
            append_history(project, f"validate:{args.level}", pre_digest=pre_digest)
            core.call_ok("project-validate", {"project": project})
            write_json_atomic(project_path, project, canonical=True)
    human = format_human(
        f"校验 {args.level} 完成",
        [
            ("verdict", report["verdict"]),
            ("issues", f"error={report['summary']['error']} warn={report['summary']['warn']}"),
            ("报告", str(report_path)),
            ("项目状态", project["status"]),
        ],
    )
    return Outcome(
        {
            "report": report,
            "path": str(report_path),
            "level": args.level,
            "verdict": report["verdict"],
            "project": project,
        },
        human,
    )


def _export_sources(project: dict) -> list[dict]:
    refs = project["refs"]
    sources = []
    if refs.get("spec"):
        sources.append({"kind": "spec", "ref": refs["spec"]["path"], "digest": refs["spec"]["digest"]})
    if refs.get("assembly"):
        sources.append({"kind": "plan", "ref": refs["assembly"]["path"], "digest": refs["assembly"]["digest"]})
    sources.append({"kind": "project", "ref": project["id"], "digest": project_digest(project)})
    return sources


def cmd_export(args) -> Outcome:
    fmt = args.format
    if fmt == "pdf":
        raise AppError(
            "NF-EXP-004",
            message="PDF 导出未内置：用平台打印另存为 PDF（Android PrintManager / 桌面 javax.print）",
            fix="改用 --format md|zip|json|docx|skill；PDF 走平台打印（OPEN）",
        )
    require(fmt in EXPORT_FORMATS, "NF-E-002", f"未知导出格式: {fmt}", fix="md/zip/json/docx/skill（pdf 走平台打印）")
    project_path = Path(args.project)
    project = load_doc(project_path, "nf-project")
    base = project_path.resolve().parent
    markdown_path = _find_result_md(base, args.markdown)
    markdown = read_text(markdown_path)
    out_dir = Path(args.out) if args.out else base / "export"
    ensure_dir(out_dir)
    core_manifest = core.call_ok(
        "export",
        {
            "markdown": markdown,
            "format": fmt,
            "out_dir": str(out_dir),
            "manifest": True,
            "sources": _export_sources(project),
        },
    )
    # 以核心 manifest 为准；不合 schema 时由 CLI 按同一 schema 归一兜底
    errors = schema_validate("nf-export-manifest", core_manifest) if isinstance(core_manifest, dict) else [
        {"message": "核心 manifest 不是对象", "path": "$"}
    ]
    if errors:
        rows = core_manifest.get("files") if isinstance(core_manifest, dict) else None
        if not rows:
            rows = [
                {"name": Path(row.get("path", "")).name, "sha256": row["sha256"], "bytes": row.get("size", 0)}
                for row in ((core_manifest or {}).get("outputs") or [])
            ]
        manifest = {
            "schema": "nf-export-manifest/1",
            "format": fmt,
            "files": [
                {"name": row["name"], "sha256": row["sha256"], "bytes": int(row["bytes"])} for row in rows
            ],
            "source": {
                "plan_digest": project["refs"]["assembly"]["digest"],
                "spec_digest": project["refs"]["spec"]["digest"],
                "markdown_digest": sha256_hex(markdown.encode("utf-8")),
            },
        }
        errors = schema_validate("nf-export-manifest", manifest)
    else:
        manifest = core_manifest
    require(
        not errors,
        "NF-EXP-001",
        f"导出清单不满足 nf-export-manifest/1: {errors[0]['message'] if errors else ''}",
        fix="按 app/schema/nf-export-manifest.schema.json 修导出清单",
    )
    write_json_atomic(out_dir / "manifest.json", manifest, canonical=True)
    pre_digest = project_digest(project)
    if _set_status_forward(project, "exported"):
        append_history(project, "export", pre_digest=pre_digest)
        core.call_ok("project-validate", {"project": project})
        write_json_atomic(project_path, project, canonical=True)
    outputs = manifest["files"]
    human = format_human(
        f"导出完成: {fmt}",
        [
            ("输出目录", str(out_dir)),
            ("文件", ", ".join(row.get("name", "") for row in outputs) or "(见 manifest)"),
            ("项目状态", project["status"]),
        ],
    )
    return Outcome(
        {
            "manifest": manifest,
            "out_dir": str(out_dir),
            "files": outputs,
            "project": project,
            "markdown_digest": sha256_hex(markdown.encode("utf-8")),
        },
        human,
    )
