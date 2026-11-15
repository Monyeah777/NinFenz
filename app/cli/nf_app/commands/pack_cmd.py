"""pack update|apply|rollback：diff → 冲突裁决 → 应用/备份/回滚（base 只读）。

- update：核心 pack-diff 产出 nf-pack-update/1（含 added/removed/modified + impact）。
- apply：核心 pack-merge 应用；冲突未裁决 = NF-PCK-006（exit 1，不应用）。
- 备份：apply --backup <dir> 先把 out_dir 现状快照到本地备份指针 nf-backup.json
  （时间戳/绝对路径只出现在本地备份指针，不进 canonical 产物）。
- rollback：校验备份摘要 → 还原 → 复算 tree，不一致 NF-PCK-007（exit 2）。
- base 只读：apply 前后用核心 pack-hash 复算 base tree，变了即 NF-PCK-004（exit 3）。
"""

from __future__ import annotations

import json
from pathlib import Path

from .. import core
from ..canonical import canonical_text, digest, sha256_hex
from ..errors import AppError
from ..io_utils import read_json, write_json_atomic
from ..schemas import validate as schema_validate
from ..pack import tree_digest
from ..security import safe_join
from .common import Outcome, format_human, load_doc, read_pack, require

DECISION_OPTIONS = ("keep_mine", "take_new", "defer")


def _load_decisions(path: str | None) -> dict | None:
    if not path:
        return None
    data = read_json(Path(path))
    if not isinstance(data, dict):
        raise AppError("NF-E-004", message="decisions 文件必须是 {冲突id: 选项} 对象", fix="例：{\"CFL-01\": \"take_new\"}")
    for key, value in data.items():
        if not isinstance(key, str):
            raise AppError("NF-E-002", message=f"decisions 键必须是冲突 id: {key!r}", fix="用 CFL-##")
        if value not in DECISION_OPTIONS:
            raise AppError(
                "NF-E-002",
                message=f"decisions[{key}] 选项非法: {value!r}",
                fix="选项只能是 keep_mine / take_new / defer",
            )
    return data


def cmd_pack_update(args) -> Outcome:
    base_root, _ = read_pack(args.base)
    new_root, _ = read_pack(args.new)
    request: dict = {"old_root": str(base_root), "new_root": str(new_root)}
    projects = []
    for path in args.projects or []:
        projects.append(load_doc(Path(path), "nf-project"))
    if projects:
        request["projects"] = projects
    update = core.call_ok("pack-diff", request)
    out = Path(args.out or "update.nfupdate.json")
    write_json_atomic(out, update, canonical=True)
    changes = update.get("changes", {})
    human = format_human(
        "Pack 更新计划已生成",
        [
            ("from", f"{update['from']['id']}@{update['from']['version']}"),
            ("to", f"{update['to']['id']}@{update['to']['version']}"),
            ("added", len(changes.get("added", []))),
            ("removed", len(changes.get("removed", []))),
            ("modified", len(changes.get("modified", []))),
            ("breaking", update["impact"]["breaking"]),
            ("冲突（需在 apply 里裁决）", len(update.get("conflicts", []))),
            ("输出", str(out)),
        ],
    )
    return Outcome({"update": update, "path": str(out), "digest": digest(update)}, human)


def _snapshot(out_dir: Path, backup_dir: Path) -> dict:
    """把 out_dir 现状快照到 backup_dir。

    nf-backup/1 只允许 {schema, tree, files:[{path,sha256}], created_at?}
    （schema additionalProperties=false），目标目录指针另存 sidecar 文件 nf-backup.target。
    """
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    files_root = backup_dir / "files"
    files_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    sized: list[dict] = []
    if out_dir.is_dir():
        for entry in sorted(out_dir.rglob("*")):
            if not entry.is_file():
                continue
            if entry.is_symlink():
                raise AppError("NF-SEC-002", message=f"输出目录含符号链接，拒绝备份: {entry}", fix="清理后重试")
            rel = entry.relative_to(out_dir).as_posix()
            data = entry.read_bytes()
            rows.append({"path": rel, "sha256": sha256_hex(data)})
            sized.append({"path": rel, "sha256": sha256_hex(data), "size": len(data)})
            target = files_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    manifest = {
        "schema": "nf-backup/1",
        "tree": tree_digest(sized),
        "files": rows,
    }
    errors = schema_validate("nf-backup", manifest)
    if errors:
        raise AppError("NF-PCK-007", message=f"备份清单不满足 nf-backup/1: {errors[0]['message']}", fix="按 schema 修")
    write_json_atomic(backup_dir / "nf-backup.json", manifest, canonical=True)
    # sidecar：本地目标指针（不属于 canonical 产物，可含绝对路径）
    (backup_dir / "nf-backup.target").write_bytes(str(Path(out_dir).resolve()).encode("utf-8"))
    return manifest


def _load_backup(backup_dir: Path) -> tuple[dict, Path]:
    path = Path(backup_dir) / "nf-backup.json"
    if not path.is_file():
        raise AppError("NF-PCK-007", message=f"备份缺失: {path}", fix="从别的备份恢复，或重跑 apply --backup")
    data = read_json(path)
    errors = schema_validate("nf-backup", data) if isinstance(data, dict) else [{"message": "不是对象", "path": "$"}]
    if errors:
        raise AppError("NF-PCK-007", message=f"备份清单非法（nf-backup/1）: {errors[0]['message']}", fix="从备份手工恢复并登记")
    pointer = Path(backup_dir) / "nf-backup.target"
    if not pointer.is_file():
        raise AppError("NF-PCK-007", message="备份缺少目标指针 nf-backup.target", fix="从备份手工恢复并登记")
    recorded = Path(pointer.read_text(encoding="utf-8").strip())
    return data, recorded


def cmd_pack_apply(args) -> Outcome:
    update = load_doc(Path(args.update), "nf-pack-update")
    base_root, _ = read_pack(args.base)
    new_root, _ = read_pack(args.new)
    decisions = _load_decisions(args.decisions)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)  # 核心不建用户目录树（CLI.md §1）
    base_before = core.call_ok("pack-hash", {"root": str(base_root)})["hashes"]["tree"]
    backup_manifest = None
    if args.backup:
        backup_manifest = _snapshot(out_dir, Path(args.backup))
    request: dict = {
        "update": update,
        "base_root": str(base_root),
        "new_root": str(new_root),
        "out_dir": str(out_dir),
    }
    if args.overlay:
        request["overlay"] = load_doc(Path(args.overlay), "nf-overlay")
    if decisions is not None:
        request["decisions"] = decisions
    result = core.call_ok("pack-merge", request)
    base_after = core.call_ok("pack-hash", {"root": str(base_root)})["hashes"]["tree"]
    require(
        base_before == base_after,
        "NF-PCK-004",
        "base 在 apply 期间被修改（base 只读，拒绝）",
        fix="恢复 base 原状后重试；只允许写 app 数据目录/输出目录",
    )
    human = format_human(
        "Pack 更新已应用",
        [
            ("输出目录", str(out_dir)),
            ("applied", result.get("applied")),
            ("result_tree", result.get("result_tree")),
            ("冲突", len(result.get("conflicts", []))),
            ("备份", str(args.backup) if args.backup else "未备份"),
        ],
    )
    return Outcome(
        {
            "merge": result,
            "out_dir": str(out_dir),
            "backup": str(args.backup) if args.backup else None,
            "backup_manifest": backup_manifest,
        },
        human,
    )


def cmd_pack_rollback(args) -> Outcome:
    backup_dir = Path(args.backup)
    target = Path(args.target).resolve()
    manifest, recorded_raw = _load_backup(backup_dir)
    recorded = Path(str(recorded_raw)).resolve()
    if recorded != target:
        raise AppError(
            "NF-PCK-007",
            message=f"回滚目标与备份记录不一致: {target} != {recorded}",
            fix="用备份清单里的 target，或换正确的备份目录",
        )
    files_root = backup_dir / "files"
    for row in manifest["files"]:
        source = safe_join(files_root, row["path"], code="NF-PCK-007")
        if not source.is_file():
            raise AppError("NF-PCK-007", message=f"备份文件缺失: {row['path']}", fix="从别处恢复")
        actual = sha256_hex(source.read_bytes())
        if actual != row["sha256"]:
            raise AppError("NF-PCK-007", message=f"备份文件摘要不符: {row['path']}", fix="备份已损坏，勿用")
    expected = {row["path"] for row in manifest["files"]}
    removed = 0
    for entry in sorted(target.rglob("*"), reverse=True) if target.is_dir() else []:
        if entry.is_symlink():
            raise AppError("NF-PCK-007", message=f"目标目录含符号链接: {entry}", fix="清理后重试")
        if entry.is_file():
            rel = entry.relative_to(target).as_posix()
            if rel not in expected:
                entry.unlink()
                removed += 1
    restored = 0
    for row in manifest["files"]:
        source = files_root / row["path"]
        destination = safe_join(target, row["path"], code="NF-PCK-007")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        restored += 1
    rows = []
    for entry in sorted(target.rglob("*")):
        if entry.is_file():
            data = entry.read_bytes()
            rows.append({"path": entry.relative_to(target).as_posix(), "sha256": sha256_hex(data), "size": len(data)})
    tree = tree_digest(rows)
    if tree != manifest["tree"]:
        raise AppError("NF-PCK-007", message="回滚后 tree 与备份记录不符", fix="从备份手工恢复并登记")
    human = format_human(
        "回滚完成",
        [("目标", str(target)), ("还原文件", restored), ("删除多余文件", removed), ("tree", tree)],
    )
    return Outcome(
        {"target": str(target), "restored": restored, "removed": removed, "tree": tree},
        human,
    )
