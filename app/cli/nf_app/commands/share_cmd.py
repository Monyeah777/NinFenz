"""share prompt|markdown|json：生成脱敏分享文本/文件（绝对路径/用户名/邮箱/密钥模式全遮）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..canonical import digest
from ..errors import AppError
from ..io_utils import read_text, write_bytes_atomic
from ..paths import repo_root
from ..security import assert_share_safe, sanitize_obj, sanitize_text
from .common import Outcome, doc_digest, format_human, load_doc, project_digest

MAX_SHARE_TEXT = 20000


def _spec_summary(project: dict, base: Path) -> dict:
    ref = project["refs"].get("spec")
    if not ref:
        return {}
    path = base / ref["path"]
    if not path.is_file():
        return {}
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        "id": spec.get("id"),
        "version": spec.get("version"),
        "title": spec.get("title"),
        "heading_level": spec.get("heading_level"),
        "sections": [
            {"id": sec.get("id"), "title": sec.get("title"), "order": sec.get("order"), "slots": sec.get("slots", [])}
            for sec in spec.get("sections", [])
        ],
        "slots": [
            {"id": slot.get("id"), "name": slot.get("name"), "kind": slot.get("kind"), "required": slot.get("required")}
            for slot in spec.get("slots", [])
        ],
        "acceptance": [
            {"id": row.get("id"), "description": row.get("description"), "severity": row.get("severity")}
            for row in spec.get("acceptance", [])
        ],
    }


def _build_prompt(project: dict | None, base: Path | None, text: str | None) -> str:
    lines = [
        "你是执行面（CCOS）。请按下面约束产出 Markdown 正文；只输出正文，不要解释，不要联网。",
    ]
    if project:
        pack = project["refs"]["base_pack"]
        lines.append(f"项目：{project['title']}（id={project['id']}，status={project['status']}）")
        lines.append(f"Pack：{pack['id']}@{pack['version']} tree={pack['tree']}")
        if project["refs"].get("spec"):
            ref = project["refs"]["spec"]
            lines.append(f"规范引用：{ref['path']} digest={ref['digest']}")
        spec = _spec_summary(project, base) if base else {}
        if spec.get("sections"):
            order = " → ".join(
                f"{sec['order']}.{sec['title']}" for sec in sorted(spec["sections"], key=lambda s: s["order"])
            )
            lines.append(f"章节顺序：{order}")
        if spec.get("acceptance"):
            for row in spec["acceptance"]:
                lines.append(f"验收 {row['id']}（{row['severity']}）：{row['description']}")
        lines.append("纪律：不携带密钥/本机路径/用户名；不修改规范引用的对象；输出遵循 nf-md-spec。")
    if text:
        lines.append("")
        lines.append("补充要求：")
        lines.append(text)
    return "\n".join(lines) + "\n"


def _build_markdown(project: dict | None, base: Path | None, text: str | None, result: str | None) -> str:
    lines = []
    if project:
        pack = project["refs"]["base_pack"]
        lines.extend(
            [
                f"# 分享：{project['title']}",
                "",
                f"- 项目：{project['id']}（{project['status']}）",
                f"- Pack：{pack['id']}@{pack['version']}",
                f"- project digest：{project_digest(project)}",
            ]
        )
        spec = _spec_summary(project, base) if base else {}
        if spec.get("sections"):
            lines.extend(["", "## 章节", ""])
            for sec in sorted(spec["sections"], key=lambda s: s["order"]):
                lines.append(f"{sec['order']}. {sec['title']}（{sec['id']}）")
        if spec.get("acceptance"):
            lines.extend(["", "## 验收", ""])
            for row in spec["acceptance"]:
                lines.append(f"- {row['id']}（{row['severity']}）：{row['description']}")
        lines.append("")
    if result:
        lines.extend(["## 结果", "", result.rstrip(), ""])
    if text:
        lines.extend(["## 说明", "", text.rstrip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def _build_json(project: dict | None, base: Path | None, text: str | None, result: str | None) -> dict:
    payload: dict[str, Any] = {"schema": "nf-share/1", "kind": "json"}
    if project:
        pack = project["refs"]["base_pack"]
        payload["project"] = {
            "id": project["id"],
            "title": project["title"],
            "status": project["status"],
            "pack": {"id": pack["id"], "version": pack["version"], "tree": pack["tree"]},
            "digest": project_digest(project),
            "spec_digest": (project["refs"].get("spec") or {}).get("digest"),
        }
        spec = _spec_summary(project, base) if base else {}
        if spec:
            payload["spec"] = spec
    if result:
        payload["result"] = {"digest": digest({"text": result}), "text": result}
    if text:
        payload["notes"] = text
    return payload


def cmd_share(args) -> Outcome:
    kind = args.share_kind
    project = None
    base = None
    if args.project:
        project_path = Path(args.project)
        project = load_doc(project_path, "nf-project")
        base = project_path.resolve().parent
    if project is None and not args.text and not args.result:
        raise AppError("NF-E-003", message="share 需要至少一个内容来源", fix="给 --project，或 --text/--result")
    result_text = read_text(Path(args.result)) if args.result else None
    repo_paths = (repo_root(),)
    masks: list[dict] = []

    if kind == "json":
        payload = _build_json(project, base, args.text, result_text)
        clean, masks = sanitize_obj(payload, repo_paths=repo_paths)
        body = json.dumps(clean, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        assert_share_safe(body)
        content: Any = clean
    else:
        if kind == "prompt":
            raw = _build_prompt(project, base, args.text)
        elif kind == "markdown":
            raw = _build_markdown(project, base, args.text, result_text)
        else:  # pragma: no cover - argparse choices 会拦住
            raise AppError("NF-E-002", message=f"未知分享类型: {kind}", fix="prompt|markdown|json")
        if len(raw) > MAX_SHARE_TEXT:
            raise AppError("NF-E-003", message=f"分享文本超过 {MAX_SHARE_TEXT} 字符", fix="缩小 --result 或拆分分享")
        body, masks = sanitize_text(raw, repo_paths=repo_paths)
        assert_share_safe(body)
        content = body

    path = None
    if args.out:
        target = Path(args.out)
        payload_bytes = body.encode("utf-8") if kind != "json" else body.encode("utf-8")
        write_bytes_atomic(target, payload_bytes)
        path = str(target)

    human = format_human(
        f"分享文本已生成（{kind}）",
        [
            ("输出", path or "(stdout)"),
            ("脱敏", ", ".join(sorted({m["kind"] for m in masks})) or "无命中"),
        ],
    )
    return Outcome(
        {
            "kind": kind,
            "content": content,
            "path": path,
            "masks": sorted({m["kind"] for m in masks}),
        },
        human,
    )
