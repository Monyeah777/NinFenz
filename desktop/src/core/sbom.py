"""材料清单（SBOM 式，`nf-sbom/1`）：把「这次交付由哪些输入构成」变成可核的摘要表。

为什么（第 113 轮，来自供应链域的 `sc.materials_products`）：发布结论回答了「那棵树是绿的」，
自省摘要回答了「谁判的」，但没人回答「**这份交付由哪些输入构成**」。本模块补这一格：

- `collect(root, scopes)`：按显式范围列出文件的 (path, sha256, bytes)，并折叠出总摘要；
- `verify(manifest, root)`：逐条核对文件仍在、摘要仍符、总数与折叠摘要可复算；

边界：只覆盖**显式范围**（协议 / 判定面 / 核心代码 / 文档），不是全仓清单——
范围越窄越好核；全仓清单会把成本加到每次检查上。
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

SCHEMA = "nf-sbom/1"
GUIDE = "修复指引："

#: 显式范围（相对 glob）：协议件 / 判定脚本 / 核心代码 / 收入文档
SCOPES = (
    "protocol/**/*.json",
    "scripts/*.py",
    "desktop/src/core/**/*.py",
    "docs/ccos/*.md",
)


def _files(root: Path) -> list[Path]:
    out: set[Path] = set()
    for pattern in SCOPES:
        out.update(p for p in root.glob(pattern) if p.is_file())
    return sorted(out)


def _digest(rows: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for row in sorted(rows, key=lambda r: str(r["path"])):
        h.update(str(row["path"]).encode("utf-8"))
        h.update(b"\x00")
        h.update(str(row["sha256"]).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def collect(root: str | Path = ".") -> dict[str, Any]:
    """按 `SCOPES` 收集材料清单（确定性：路径排序、摘要折叠）。"""
    base = Path(root)
    if not base.is_dir():
        raise ValueError("仓库根不存在：" + str(base) + "（" + GUIDE + "给正确的 --root）")
    rows: list[dict[str, Any]] = []
    for path in _files(base):
        data = path.read_bytes()
        rel = path.relative_to(base).as_posix()
        rows.append({"path": rel, "sha256": hashlib.sha256(data).hexdigest(),
                     "bytes": len(data)})
    if not rows:
        raise ValueError("材料清单为空（" + GUIDE + "确认 SCOPES 与仓库根是否匹配）")
    return {"schema": SCHEMA, "count": len(rows),
            "bytes": sum(int(r["bytes"]) for r in rows),
            "digest": _digest(rows), "materials": rows,
            "note": "只覆盖显式范围；不是全仓清单"}


def verify(manifest: Any, root: str | Path = ".") -> list[str]:
    """核对材料清单：结构、逐条文件与摘要、总数与折叠摘要。"""
    issues: list[str] = []
    if not isinstance(manifest, dict) or str(manifest.get("schema")) != SCHEMA:
        return ["材料清单 schema 不符（" + GUIDE + "需要 " + SCHEMA + "）"]
    rows = manifest.get("materials")
    if not isinstance(rows, list) or not rows:
        return ["材料清单为空（" + GUIDE + "用 collect 重新生成）"]
    base = Path(root)
    for row in rows:
        rel = str(row.get("path") or "")
        if not rel:
            issues.append("有条目缺 path")
            continue
        path = base / rel
        if not path.is_file():
            issues.append("材料不在场：" + rel + "（" + GUIDE + "删掉该条或恢复文件）")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != str(row.get("sha256") or ""):
            issues.append("材料摘要不符：" + rel + "（" + GUIDE + "重新生成清单）")
    if int(manifest.get("count") or -1) != len(rows):
        issues.append("count 与条目数不符（" + GUIDE + "手改过清单）")
    if str(manifest.get("digest") or "") != _digest(rows):
        issues.append("折叠摘要不可复算（" + GUIDE + "手改过清单）")
    return issues
