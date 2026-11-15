"""子命令公共件：Outcome、文档装载/校验、digest、项目状态机工具。"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..canonical import digest, digest_excluding, sha256_hex
from ..errors import AppError
from ..io_utils import read_bytes, read_json, rel_posix, sha256_file, write_json_atomic
from ..schemas import validate as schema_validate

# 结构校验失败 → 对应域错误码（单一真源仍是 error_codes.json）
SCHEMA_CODE = {
    "nf-pack": "NF-PCK-001",
    "nf-overlay": "NF-PCK-001",
    "nf-template": "NF-PCK-001",
    "nf-pack-update": "NF-PCK-001",
    "nf-protocol-pack": "NF-PRT-001",
    "nf-pipeline-graph": "NF-GRF-001",
    "nf-md-spec": "NF-SPC-001",
    "nf-import": "NF-IMP-001",
    "nf-assembly-plan": "NF-VAL-001",
    "nf-validate-report": "NF-VAL-001",
    "nf-project": "NF-VAL-001",
    "ccos-task": "NF-CCOS-001",
    "ccos-result": "NF-CCOS-001",
    "nf-assemble-result": "NF-ASM-003",
    "nf-export-manifest": "NF-EXP-001",
    "nf-backup": "NF-PCK-007",
}

STATE_ORDER = ["draft", "authoring", "assembled", "validated", "exported", "reviewed"]


@dataclass
class Outcome:
    result: Any
    human: str = ""
    exit: int = 0


def code_for(stem: str) -> str:
    try:
        return SCHEMA_CODE[stem]
    except KeyError as exc:  # pragma: no cover - 新 schema 必须先登记映射
        raise RuntimeError(f"schema 未登记错误码映射: {stem}") from exc


def load_doc(path: Path | str, stem: str) -> dict:
    """读 JSON + 本地结构校验（语义面交给核心）；失败给域错误码与 JSON Pointer。"""
    doc = read_json(Path(path))
    if not isinstance(doc, dict):
        raise AppError(code_for(stem), message=f"{stem} 顶层必须是对象", fix="按 app/schema 修复")
    errors = schema_validate(stem, doc)
    if errors:
        first = errors[0]
        raise AppError(
            code_for(stem),
            message=f"{stem} 结构校验失败: {first['message']}",
            fix="按 path 修复字段（见 app/schema）",
            path=first["path"],
        )
    return doc


def doc_digest(doc: dict) -> str:
    """graph/protocol/spec 等对象的 canonical digest（遵守 x-digest-exclude）。"""
    return digest_excluding(doc)


def plan_digest(plan: dict) -> str:
    """plan.digest = sha256(canonical(plan 去掉 digest))。"""
    return digest_excluding(plan, ["digest"])


def project_digest(project: dict) -> str:
    """项目 digest 剔除 history（CONTRACT §7）。"""
    return digest_excluding(project, ["history"])


def now_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def append_history(project: dict, op: str, *, at: str | None = None, pre_digest: str | None = None) -> None:
    """history append-only；digest = 变更前项目摘要（前像，用于证明链）。"""
    project.setdefault("history", []).append(
        {"op": op, "at": at or now_iso(), "digest": pre_digest or project_digest(project)}
    )


def require(cond: bool, code: str, message: str, *, fix: str | None = None, path: str | None = None) -> None:
    if not cond:
        raise AppError(code, message=message, fix=fix, path=path)


def read_pack(path: Path | str) -> tuple[Path, dict]:
    """path 可以是 pack 根目录或 nf-pack.json；返回 (根目录, 清单)。"""
    target = Path(path)
    if target.is_dir():
        manifest_path = target / "nf-pack.json"
        root = target
    else:
        manifest_path = target
        root = target.parent
    if not manifest_path.is_file():
        raise AppError("NF-E-004", message=f"找不到 pack 清单: {manifest_path}", fix="给出 pack 根目录或 nf-pack.json")
    return root, load_doc(manifest_path, "nf-pack")


def write_out(path: Path | str, doc: Any) -> Path:
    return write_json_atomic(Path(path), doc)


def ref_for_file(path: Path | str, *, base: Path, stem: str | None = None) -> dict:
    """项目引用（nf-project.schema.json $defs/artifactRef）：
    {id, version, digest, path, sha256} —— 对象身份 + 内容摘要 + 文件内容摘要。"""
    target = Path(path)
    doc = load_doc(target, stem) if stem else read_json(target)
    return {
        "id": doc["id"],
        "version": doc["version"],
        "digest": doc_digest(doc),
        "path": rel_posix(target, base),
        "sha256": sha256_file(target),
    }


def file_sha(path: Path | str) -> str:
    return sha256_hex(read_bytes(Path(path)))


def format_human(title: str, rows: list[tuple[str, Any]]) -> str:
    width = max((len(key) for key, _ in rows), default=0)
    lines = [title]
    for key, value in rows:
        lines.append(f"  {key.ljust(width)}  {value}")
    return "\n".join(lines)


def json_pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
