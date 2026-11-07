"""Reconstruct a contract-level timeline from Git history."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess  # nosec B404 - local Git argv calls only
import sys
from pathlib import Path
from typing import Any

from core import json_doc, knowledge_sig, paths

SCHEMA = "nf-contract-history/1"
FIELD = "\x1f"
ROOT_CONTRACTS = {
    "01_核心协议.md",
    "02_联动注册表.md",
    "06_Agent执行协议.md",
    "07_官方核心出厂与社区预设导航.md",
}
PROTOCOL_CONTRACTS = {"protocol/CONFORMANCE.md", "protocol/EXTENSION.md"}


def _git(root: Path, *args: str) -> tuple[int, bytes]:
    git = shutil.which("git")
    if not git:
        return 127, b"git unavailable"
    proc = subprocess.run(  # noqa: S603,RUF100  # nosec B603/B607 - argv list, no shell
        [git, *args],
        cwd=str(root),
        capture_output=True,
        check=False,
    )
    return proc.returncode, proc.stdout


def _contract_path(root: Path, rel: str) -> str:
    rel = paths.validate_path(str(root), rel, allow_absolute=True).replace("\\", "/")
    candidate = Path(rel)
    try:
        repo_rel = candidate.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(
            f"契约路径不在当前仓库：{rel}（修复指引：给仓库根内相对路径）"
        ) from exc
    if repo_rel in ROOT_CONTRACTS or repo_rel in PROTOCOL_CONTRACTS:
        return repo_rel
    if repo_rel.startswith("protocol/schema/") and repo_rel.endswith(".json"):
        return repo_rel
    raise ValueError(
        f"不属于受支持的契约面：{repo_rel}（修复指引：收 01/02/06/07 协议文档、"
        "protocol/CONFORMANCE.md、protocol/EXTENSION.md 或 protocol/schema/*.json）"
    )


def _revisions(root: Path, rel: str, limit: int) -> list[dict[str, str]]:
    fmt = f"%H{FIELD}%ad{FIELD}%s"
    code, out = _git(
        root,
        "log",
        "--follow",
        "-n",
        str(limit),
        f"--format={fmt}",
        "--date=short",
        "--",
        rel,
    )
    if code != 0:
        raise ValueError(
            "读取 Git 历史失败（修复指引：确认当前目录在 Git 工作树内且 git 可用）"
        )
    rows = []
    for line in out.decode("utf-8", errors="replace").splitlines():
        parts = line.split(FIELD, 2)
        if len(parts) == 3:
            rows.append({"commit": parts[0], "date": parts[1], "subject": parts[2]})
    return rows


def _json_shape(value: Any, pointer: str = "$") -> dict[str, str]:
    shape: dict[str, str] = {}
    if isinstance(value, dict):
        shape[pointer] = "object"
        for key in sorted(value):
            shape.update(_json_shape(value[key], f"{pointer}.{key}"))
    elif isinstance(value, list):
        shape[pointer] = "array"
        for index, item in enumerate(value):
            shape.update(_json_shape(item, f"{pointer}[{index}]"))
    elif isinstance(value, bool):
        shape[pointer] = f"bool:{str(value).lower()}"
    elif value is None:
        shape[pointer] = "null"
    else:
        shape[pointer] = f"{type(value).__name__}:{json.dumps(value, ensure_ascii=False)}"
    return shape


def _json_signature(rel: str, text: str) -> dict[str, Any]:
    value = json_doc.loads(text, None, what=f"契约 {rel}", strict_constants=True)
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "kind": "contract-json",
        "path": rel,
        "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "shape": _json_shape(value),
    }


def _is_version_pointer(pointer: str) -> bool:
    tail = pointer.rsplit(".", 1)[-1]
    return tail in {"$id", "$schema", "schema", "version", "schema_version"}


def _json_diff(before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    changes = []
    for pointer in sorted(set(before) - set(after)):
        changes.append({"pointer": pointer, "from": before[pointer], "to": None, "kind": "移除"})
    for pointer in sorted(set(after) - set(before)):
        changes.append({"pointer": pointer, "from": None, "to": after[pointer], "kind": "新增"})
    for pointer in sorted(set(before) & set(after)):
        if before[pointer] != after[pointer]:
            changes.append(
                {"pointer": pointer, "from": before[pointer], "to": after[pointer],
                 "kind": "变更"}
            )
    removed = [change for change in changes if change["kind"] == "移除"]
    added = [change for change in changes if change["kind"] == "新增"]
    changed = [change for change in changes if change["kind"] == "变更"]
    type_changed = any(
        change["from"].split(":", 1)[0] != change["to"].split(":", 1)[0]
        for change in changed
    )
    required_added = any(".required[" in change["pointer"] for change in added)
    version_changed = any(_is_version_pointer(change["pointer"]) for change in changed)
    if removed or type_changed or required_added or version_changed:
        impact = "bump"
    elif added:
        impact = "additive"
    else:
        impact = "editorial"
    verdict = {
        "bump": "破坏（结构移除、类型/版本变化或必填项增加）",
        "additive": "兼容（字段级新增）",
        "editorial": "兼容（编辑性变更）",
    }[impact]
    return {"verdict": verdict, "impact": impact, "changes": changes}


def _signature(rel: str, text: str) -> dict[str, Any]:
    if rel.endswith(".json"):
        return _json_signature(rel, text)
    sig = knowledge_sig.build_signature_text(rel, text)
    return {"kind": "contract-markdown", "path": rel,
            "digest": knowledge_sig.signature_digest(sig), "signature": sig}


def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    if before["kind"] == "contract-json":
        return _json_diff(before["shape"], after["shape"])
    diff = knowledge_sig.diff_signatures(before["signature"], after["signature"])
    return {"verdict": diff["verdict"], "impact": diff["impact"], "changes": diff["changes"]}


def history(root: str = ".", rel: str = "", limit: int = 20) -> dict[str, Any]:
    """Return a deterministic, chronological contract signature timeline."""
    if limit < 1 or limit > 200:
        raise ValueError("--history 须在 1..200（修复指引：给合理的提交数上限）")
    repo = Path(root).resolve()
    contract = _contract_path(repo, rel)
    rows = list(reversed(_revisions(repo, contract, limit)))
    if not rows:
        raise ValueError(f"契约没有 Git 历史：{contract}（修复指引：确认路径已被 Git 跟踪）")
    events = []
    previous = None
    totals = {"baseline": 0, "editorial": 0, "additive": 0, "bump": 0}
    for row in rows:
        code, content = _git(repo, "show", f"{row['commit']}:{contract}")
        if code != 0:
            raise ValueError(
                f"无法读取契约历史版本：{contract}@{row['commit'][:12]}"
                "（修复指引：确认路径未改名；改名前历史暂不推断）"
            )
        current = _signature(contract, content.decode("utf-8"))
        if previous is None:
            delta = {"verdict": "基线", "impact": "baseline", "changes": []}
        else:
            delta = _diff(previous, current)
        totals[delta["impact"]] += 1
        events.append(
            {
                "commit": row["commit"],
                "date": row["date"],
                "subject": row["subject"],
                "digest": current["digest"],
                **delta,
            }
        )
        previous = current
    return {
        "schema": SCHEMA,
        "path": contract,
        "revisions": events,
        "summary": {"count": len(events), **totals},
    }


def _run_fail(args: Any, message: str, code: int = 1) -> int:
    if getattr(args, "json", False):
        print(json.dumps({"ok": False, "error": message, "exit": code},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"  ✗ {message}", file=sys.stderr)
    return code


def _rel_to_root(root: str, target: str) -> str:
    full = os.path.abspath(target if os.path.isabs(target) else os.path.join(root, target))
    if not os.path.isfile(full):
        raise ValueError(
            f"签名目标不是文件：{target}（修复指引：`nf diff a b` 各收一份文件；"
            "契约历史用 `nf diff --history N <契约路径>`）"
        )
    return Path(os.path.relpath(full, root)).as_posix()


def run(args: Any, root: str = ".") -> int:
    """Run the existing diff face plus its optional contract-history mode."""
    try:
        if args.history is not None:
            if not args.a or args.b is not None:
                return _run_fail(
                    args,
                    "nf diff --history 只收一个契约路径（修复指引："
                    "`nf diff --history 20 01_核心协议.md`；双文件比较请去掉 --history）",
                    2,
                )
            result = history(root, args.a, args.history)
            if args.json:
                print(json.dumps({"kind": "contract-history", **result},
                                 ensure_ascii=False, indent=2, sort_keys=True))
                return 0
            print("== nf diff --history ==")
            print(f"  契约：{result['path']}")
            for event in result["revisions"]:
                print(f"  {event['date']} {event['commit'][:12]} [{event['impact']}] "
                      f"{event['subject']}")
                if event["changes"]:
                    print(f"    变更 {len(event['changes'])} 项 · {event['verdict']}")
            summary = result["summary"]
            print(f"  提交 {summary['count']} · bump {summary['bump']} · "
                  f"additive {summary['additive']} · editorial {summary['editorial']}")
            return 0
        if not args.a or not args.b:
            return _run_fail(
                args,
                "nf diff 需要两份文件（修复指引：`nf diff OLD NEW`；"
                "看单个契约历史用 `nf diff --history 20 <契约路径>`）",
                2,
            )
        rel_a = _rel_to_root(root, args.a)
        rel_b = _rel_to_root(root, args.b)
        diff = knowledge_sig.diff_signatures(
            knowledge_sig.build_signature(rel_a, root),
            knowledge_sig.build_signature(rel_b, root),
        )
        if args.json:
            print(json.dumps({"kind": "diff", **diff},
                             ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        print("== nf diff ==")
        print(f"  {diff['from']}  →  {diff['to']}")
        if not diff["changes"]:
            print("  无字段差异（两份签名一致）")
        for change in diff["changes"]:
            print(f"  [{change['kind']}] {change['field']}  "
                  f"{change['from']!r} → {change['to']!r}")
        print(f"  判定：{diff['verdict']}")
        impact = diff.get("impact", "editorial")
        label = {
            "bump": "结构性（须 bump + 迁移记录）",
            "additive": "字段级新增（V1 只增不删）",
            "editorial": "措辞/编辑（无契约影响）",
        }.get(impact, impact)
        print(f"  影响度：{impact}（{label}）")
        return 0
    except (OSError, ValueError) as exc:
        return _run_fail(args, str(exc))
