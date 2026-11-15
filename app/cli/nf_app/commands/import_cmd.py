"""import / map：剪贴板或文件 → nf-import/1 → 映射建议。"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from .. import core
from ..canonical import digest, sha256_hex
from ..errors import AppError
from ..io_utils import read_bytes, write_json_atomic
from .common import Outcome, format_human, load_doc

SOURCE_KINDS = ("share", "view", "process_text", "saf", "clipboard", "file", "inbox")


def cmd_import(args) -> Outcome:
    if args.file == "-":
        data = sys.stdin.buffer.read()
        kind = args.source_kind or "clipboard"
        name = args.name or "clipboard.md"
    else:
        path = Path(args.file)
        data = read_bytes(path)
        kind = args.source_kind or "file"
        name = args.name or path.name
    if not data:
        raise AppError("NF-E-004", message="输入为空（文件/stdin 没有内容）", fix="检查输入后重试")
    if "\\" in name or name.startswith("/"):
        name = Path(name.replace("\\", "/")).name  # 只保留文件名，避免绝对路径进产物
    sha = sha256_hex(data)
    with tempfile.TemporaryDirectory(prefix="nf-import-") as tmpdir:
        staging = Path(tmpdir) / "input.bin"
        staging.write_bytes(data)
        result = core.call_ok(
            "import",
            {
                "file": str(staging),
                "source": {"kind": kind, "name": name, "size": len(data), "sha256": sha},
            },
        )
    if not isinstance(result, dict):
        raise AppError("NF-E-005", message="核心 import 返回不是对象", fix="核对核心实现与 app/docs/CLI.md")
    if args.out:
        write_json_atomic(Path(args.out), result)
    warnings = result.get("warnings") or []
    human = format_human(
        f"导入完成: {name}",
        [
            ("格式", result.get("detected", {}).get("format")),
            ("置信度", result.get("detected", {}).get("confidence")),
            ("标题数", len(result.get("structure", {}).get("headings", []))),
            ("映射建议", len(result.get("suggested", {}).get("mappings", []))),
            ("警告", ", ".join(w.get("code", "") for w in warnings) or "无"),
            ("输出", args.out or "(仅 stdout)"),
        ],
    )
    return Outcome({"import": result, "path": args.out, "digest": digest(result)}, human)


def cmd_map(args) -> Outcome:
    import_doc = load_doc(args.import_path, "nf-import")
    request: dict = {"import": import_doc}
    if args.spec:
        request["spec"] = load_doc(args.spec, "nf-md-spec")
    result = core.call_ok("map-suggest", request)
    if args.out:
        write_json_atomic(Path(args.out), result)
    mappings = result.get("suggested", {}).get("mappings", [])
    unmapped = result.get("suggested", {}).get("unmapped", [])
    human = format_human(
        "映射建议完成",
        [
            ("映射条目", len(mappings)),
            ("未映射", len(unmapped)),
            ("警告", ", ".join(w.get("code", "") for w in result.get("warnings", [])) or "无"),
            ("输出", args.out or "(仅 stdout)"),
        ],
    )
    return Outcome({"import": result, "path": args.out, "digest": digest(result)}, human)
