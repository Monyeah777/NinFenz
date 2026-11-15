"""project init|status|set：nf-project/1（只存引用 + 状态机 + 评审）。

- init：首次创建 status=draft；带 --force 对已存在项目 = 刷新引用（保留状态/评审/history，
  追加 history op=refs:refresh，前像 digest）。作者改过 graph/spec 后用它刷新引用。
- set：前进无需 --force；回退必须 --force 且写 history；前进跑核心 project-validate，失败不落盘。
"""

from __future__ import annotations

from pathlib import Path

from .. import core
from ..canonical import digest
from ..errors import AppError
from ..io_utils import rel_posix, sha256_file, write_json_atomic
from ..schemas import validate as schema_validate
from .common import (
    STATE_ORDER,
    Outcome,
    append_history,
    doc_digest,
    format_human,
    load_doc,
    project_digest,
    read_pack,
    ref_for_file,
)


def _write_project(path: Path, project: dict) -> None:
    write_json_atomic(Path(path), project, canonical=True)


def _build_refs(args, base: Path) -> dict:
    refs: dict = {}
    if args.base_pack:
        _root, manifest = read_pack(args.base_pack)
        refs["base_pack"] = {
            "id": manifest["id"],
            "version": manifest["version"],
            "tree": manifest["hashes"]["tree"],
        }
    if args.overlay:
        overlay_path = Path(args.overlay)
        load_doc(overlay_path, "nf-overlay")
        refs["overlay"] = {"path": rel_posix(overlay_path, base), "sha256": sha256_file(overlay_path)}
    if args.protocol:
        protocol_doc = load_doc(args.protocol, "nf-protocol-pack")
        refs["protocol"] = {
            "id": protocol_doc["id"],
            "version": protocol_doc["version"],
            "digest": doc_digest(protocol_doc),
        }
    if args.graph:
        refs["graph"] = ref_for_file(args.graph, base=base, stem="nf-pipeline-graph")
    if args.spec:
        refs["spec"] = ref_for_file(args.spec, base=base, stem="nf-md-spec")
    for key, flag in (("base_pack", "--base-pack"), ("graph", "--graph"), ("spec", "--spec")):
        if key not in refs:
            raise AppError(
                "NF-E-003",
                message=f"project init 缺 {flag}：refs.{key} 是必填引用",
                fix=f"补 {flag}（pack 清单位置 / 图文件 / spec 文件）",
            )
    return refs


def cmd_project_init(args) -> Outcome:
    target = Path(args.project_file)
    existing = None
    if target.exists():
        if not args.force:
            raise AppError(
                "NF-E-003",
                message=f"项目文件已存在: {target}",
                fix="换一个文件名，或加 --force 刷新引用（保留状态/history）",
            )
        try:
            existing = load_doc(target, "nf-project")
        except AppError:
            existing = None  # 坏文件按新建处理（--force 已显式同意覆盖）
    base = target.resolve().parent
    refs = _build_refs(args, base)
    if existing is not None:
        pre_digest = project_digest(existing)
        existing["refs"] = refs
        if args.id:
            existing["id"] = args.id
        if args.title:
            existing["title"] = args.title
        append_history(existing, "refs:refresh", at=getattr(args, "at", None), pre_digest=pre_digest)
        project = existing
        refreshed = True
    else:
        project_default_id = target.stem.lower().replace("_", "-").replace(".", "-")
        project = {
            "schema": "nf-project/1",
            "id": args.id or project_default_id,
            "title": getattr(args, "title", None) or target.stem,
            "refs": refs,
            "status": "draft",
            "review": {"state": "none"},
            "history": [],
        }
        refreshed = False
    errors = schema_validate("nf-project", project)
    if errors:
        raise AppError(
            "NF-VAL-001",
            message=f"项目结构非法: {errors[0]['message']}",
            fix="检查 --id 命名（小写字母开头）与引用字段",
            path=errors[0]["path"],
        )
    report = core.call_ok("project-validate", {"project": project})
    _write_project(target, project)
    human = format_human(
        ("项目已刷新引用: " if refreshed else "项目已初始化: ") + project["id"],
        [
            ("文件", str(target)),
            ("状态", project["status"]),
            ("base_pack", f"{refs['base_pack']['id']}@{refs['base_pack']['version']}"),
            ("graph", refs["graph"]["path"]),
            ("spec", refs["spec"]["path"]),
            ("project digest", project_digest(project)),
        ],
    )
    return Outcome(
        {
            "project": project,
            "path": str(target),
            "digest": project_digest(project),
            "report": report,
            "refreshed": refreshed,
        },
        human,
    )


def cmd_project_status(args) -> Outcome:
    target = Path(args.project_file)
    project = load_doc(target, "nf-project")
    report = core.call_ok("project-validate", {"project": project})
    human = format_human(
        f"项目 {project['id']}",
        [
            ("标题", project["title"]),
            ("状态", project["status"]),
            ("评审", project["review"]["state"]),
            ("history 条数", len(project["history"])),
            ("project digest", project_digest(project)),
            ("校验", report.get("verdict")),
        ],
    )
    return Outcome(
        {
            "project": project,
            "path": str(target),
            "digest": project_digest(project),
            "status": project["status"],
            "review": project["review"],
            "report": report,
        },
        human,
    )


def cmd_project_set(args) -> Outcome:
    target = Path(args.project_file)
    project = load_doc(target, "nf-project")
    new_status = args.status
    if new_status not in STATE_ORDER:
        raise AppError(
            "NF-E-002",
            message=f"未知项目状态: {new_status}",
            fix="状态只能是 " + " / ".join(STATE_ORDER),
        )
    old_status = project["status"]
    if new_status == old_status:
        human = format_human("状态未变", [("状态", old_status), ("文件", str(target))])
        return Outcome(
            {"project": project, "path": str(target), "status": old_status, "changed": False},
            human,
        )
    forward = STATE_ORDER.index(new_status) > STATE_ORDER.index(old_status)
    if not forward and not args.force:
        raise AppError(
            "NF-E-003",
            message=f"状态回退需要 --force：{old_status} → {new_status}",
            fix="确认要回退后加 --force（回退会写 history）",
        )
    pre_digest = project_digest(project)
    project["status"] = new_status
    if forward:
        report = core.call_ok("project-validate", {"project": project})
        op = f"status:{old_status}->{new_status}"
        human_rows = [("状态", f"{old_status} → {new_status}"), ("文件", str(target)), ("前像 digest", pre_digest)]
        skipped = None
    else:
        errors = schema_validate("nf-project", project)
        if errors:
            raise AppError(
                "NF-VAL-001",
                message=f"项目结构非法: {errors[0]['message']}",
                fix="修 refs/status 后重试",
                path=errors[0]["path"],
            )
        report = None
        op = f"status:force-retreat:{old_status}->{new_status}"
        human_rows = [
            ("状态（强制回退）", f"{old_status} → {new_status}"),
            ("文件", str(target)),
            ("前像 digest", pre_digest),
        ]
        skipped = "force-retreat 只做结构校验，不跑核心语义校验"
    append_history(project, op, at=args.at, pre_digest=pre_digest)
    _write_project(target, project)
    result = {
        "project": project,
        "path": str(target),
        "status": new_status,
        "changed": True,
        "force_retreat": not forward,
        "report": report,
    }
    if skipped:
        result["skipped"] = skipped
    return Outcome(result, format_human("项目状态已更新", human_rows))
