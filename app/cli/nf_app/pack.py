"""Pack 目录 → nf-pack/1 items/tree（口径与核心一致，见 CLI.md / CONTRACT §2）。

tree = sha256(canonical([{path,sha256,size}] 按 path 码点升序))；
排除 root 下 nf-pack.json、nf-pack.json.sig、root 下 *.sig 文件；不跟随 symlink。
"""

from __future__ import annotations

from pathlib import Path

from .canonical import canonical_text, sha256_hex
from .errors import AppError

KIND_BY_DIR = {
    "protocol": "protocol",
    "pipeline": "pipeline",
    "pipelines": "pipeline",
    "spec": "md-spec",
    "assets": "assets",
    "template": "template",
    "overlay": "overlay",
    "docs": "docs",
}


def classify(path: str) -> str:
    head = path.split("/", 1)[0] if "/" in path else ""
    return KIND_BY_DIR.get(head, "meta")


def is_excluded(rel: str) -> bool:
    if rel == "nf-pack.json" or rel == "nf-pack.json.sig":
        return True
    return "/" not in rel and rel.endswith(".sig")


def iter_pack_files(root: Path) -> list[tuple[str, Path]]:
    root = Path(root)
    if not root.is_dir():
        raise AppError("NF-E-004", message=f"目录不存在: {root}", fix="给出 pack 根目录")
    out: list[tuple[str, Path]] = []

    def walk(directory: Path, prefix: str) -> None:
        for entry in sorted(directory.iterdir(), key=lambda p: p.name):
            rel = f"{prefix}{entry.name}"
            if entry.is_symlink():
                raise AppError(
                    "NF-SEC-002",
                    message=f"pack 目录含符号链接/junction: {rel}",
                    fix="重打包为普通文件",
                )
            if entry.is_dir():
                walk(entry, rel + "/")
            else:
                if is_excluded(rel):
                    continue
                out.append((rel, entry))

    walk(root, "")
    out.sort(key=lambda pair: pair[0])
    return out


def compute_items(root: Path, *, kinds: dict[str, str] | None = None) -> list[dict]:
    items = []
    for rel, path in iter_pack_files(root):
        data = path.read_bytes()
        items.append(
            {
                "path": rel,
                "kind": (kinds or {}).get(rel) or classify(rel),
                "sha256": sha256_hex(data),
                "size": len(data),
            }
        )
    return items


def tree_digest(items: list[dict]) -> str:
    rows = [{"path": it["path"], "sha256": it["sha256"], "size": it["size"]} for it in items]
    rows.sort(key=lambda row: row["path"])
    return sha256_hex(canonical_text(rows).encode("utf-8"))
