"""ccos task|import-result|review：CCOS 交接 + 人审状态机（APP 不直连 API）。"""

from __future__ import annotations

from pathlib import Path

from .. import core
from ..canonical import digest, digest_excluding
from ..errors import AppError
from ..io_utils import write_json_atomic
from ..schemas import validate as schema_validate
from .common import Outcome, append_history, format_human, load_doc, now_iso, project_digest, require


def _budget(args) -> dict:
    budget = {
        "max_tokens": args.max_tokens,
        "max_chars": args.max_chars,
        "max_seconds": args.max_seconds,
    }
    for key, value in budget.items():
        if value < 1:
            raise AppError("NF-E-003", message=f"预算 {key} 必须是正整数: {value}", fix="给 >=1 的整数")
    return budget


def cmd_ccos_task(args) -> Outcome:
    project_path = Path(args.project)
    project = load_doc(project_path, "nf-project")
    base = project_path.resolve().parent
    request: dict = {
        "project": project,
        "task_id": args.task_id,
        "created_at": args.created_at or now_iso(),
        "budget": _budget(args),
    }
    if args.variables:
        from ..io_utils import read_json

        variables = read_json(Path(args.variables))
        if not isinstance(variables, dict):
            raise AppError("NF-E-004", message="variables 文件必须是对象", fix="给 {键: 值}")
        request["variables"] = variables
    task = core.call_ok("ccos-build-task", request)
    errors = schema_validate("ccos-task", task)
    if errors:
        raise AppError(
            "NF-CCOS-001",
            message=f"核心产出的 ccos-task 结构非法: {errors[0]['message']}",
            fix="按 app/schema/ccos-task.schema.json 修核心实现",
            path=errors[0]["path"],
        )
    out = Path(args.out) if args.out else base / f"{args.task_id}.ccos-task.json"
    write_json_atomic(out, task, canonical=True)
    human = format_human(
        "CCOS 任务已生成",
        [
            ("任务 id", task["id"]),
            ("项目", project["id"]),
            ("状态要求", project["status"]),
            ("文件", str(out)),
            ("digest", digest(task)),
        ],
    )
    return Outcome({"task": task, "path": str(out), "digest": digest(task)}, human)


def _write_project_review(project_path: Path, project: dict, review: dict) -> None:
    project["review"] = review
    write_json_atomic(project_path, project, canonical=True)


def cmd_ccos_import_result(args) -> Outcome:
    task = load_doc(Path(args.task), "ccos-task")
    result = load_doc(Path(args.result), "ccos-result")
    imported = core.call_ok("ccos-import-result", {"task": task, "result": result})
    out = Path(args.out) if args.out else Path(args.task).resolve().parent / f"{task['id']}.ccos-result.json"
    write_json_atomic(out, result, canonical=True)
    project_doc = None
    if args.project:
        project_path = Path(args.project)
        project = load_doc(project_path, "nf-project")
        pre_digest = project_digest(project)
        review = {
            "state": "pending",
            "subject_digest": digest_excluding(result, ["human_review"]),
        }
        append_history(project, "ccos:import-result", pre_digest=pre_digest)
        _write_project_review(project_path, project, review)
        project_doc = project
    issues = imported.get("issues") or []
    human = format_human(
        "CCOS 结果已导入",
        [
            ("状态", imported.get("status")),
            ("人审", imported.get("review", {}).get("state")),
            ("问题数", len(issues)),
            ("文件", str(out)),
        ],
    )
    return Outcome(
        {
            "status": imported.get("status"),
            "review": imported.get("review"),
            "issues": issues,
            "result": result,
            "path": str(out),
            "project": project_doc,
        },
        human,
    )


def cmd_ccos_review(args) -> Outcome:
    result_path = Path(args.result)
    result = load_doc(result_path, "ccos-result")
    if bool(args.approve) == bool(args.reject):
        raise AppError("NF-E-003", message="必须且只能给 --approve 或 --reject 之一", fix="二选一")
    if not args.reviewer:
        raise AppError("NF-E-003", message="人审必须给 --reviewer", fix="--reviewer <名字>")
    if not args.note:
        raise AppError("NF-E-003", message="人审必须给 --note（说明依据）", fix="--note <说明>")
    target_state = "approved" if args.approve else "rejected"
    current = result["human_review"]["state"]
    if current != "pending" and current != target_state and not args.force:
        raise AppError(
            "NF-E-003",
            message=f"人审状态已经 {current}，改为 {target_state} 需要 --force",
            fix="确认后加 --force（会重写人审记录）",
        )
    if args.task:
        task = load_doc(Path(args.task), "ccos-task")
        require(
            digest(task) == result["task_digest"],
            "NF-CCOS-002",
            "task_digest 回钉不一致（结果不是这份任务的产物）",
            fix="核对任务/结果文件，或重新生成任务",
        )
    result["human_review"] = {
        "required": True,
        "state": target_state,
        "reviewer": args.reviewer,
        "note": args.note,
    }
    errors = schema_validate("ccos-result", result)
    if errors:
        raise AppError(
            "NF-CCOS-001",
            message=f"人审后的 ccos-result 结构非法: {errors[0]['message']}",
            fix="按 schema 修复",
            path=errors[0]["path"],
        )
    write_json_atomic(result_path, result, canonical=True)
    project_doc = None
    status = None
    if args.project:
        project_path = Path(args.project)
        project = load_doc(project_path, "nf-project")
        pre_digest = project_digest(project)
        review = {
            "state": target_state,
            "reviewer": args.reviewer,
            "note": args.note,
            "subject_digest": digest_excluding(result, ["human_review"]),
        }
        changed = False
        if args.approve:
            from .common import STATE_ORDER

            if STATE_ORDER.index(project["status"]) < STATE_ORDER.index("reviewed"):
                project["status"] = "reviewed"
                changed = True
        if changed:
            append_history(project, "review", pre_digest=pre_digest)
        _write_project_review(project_path, project, review)
        status = project["status"]
        project_doc = project
    human = format_human(
        f"人审完成: {target_state}",
        [
            ("结果文件", str(result_path)),
            ("reviewer", args.reviewer),
            ("项目状态", status or "(未给 --project)"),
        ],
    )
    return Outcome(
        {
            "state": target_state,
            "result": result,
            "path": str(result_path),
            "project": project_doc,
            "status": status,
        },
        human,
    )
