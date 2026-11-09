"""验证器版本（自省层的对象）：**判定工具的摘要**，不是日期也不是 commit。

为什么要它（第 96 轮）：发布结论证明「某个 SHA 的树是绿的」，但没回答「**是哪套验证逻辑**证明的」。
工具本身改了而结论没重跑，结论就不再可信——这正是自省层缺的那个对象。

本模块只做一件事：对「判定面脚本」的内容算一个稳定摘要（`nf-verifier-version/1`）。
口径：按相对路径排序后逐个取内容 sha256，再整体折叠一次；任何脚本内容变化都会改变摘要。
边界：摘要只覆盖**判定面**（门禁脚本），不覆盖被测代码——后者由结论绑定的 HEAD 负责。
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

SCHEMA = "nf-verifier-version/1"
GUIDE = "修复指引："

#: 判定面脚本（**显式名单**：新门禁进名单要显式评审，不漏算也不多算）
JUDGE_FILES = (
    "scripts/verify_tests.py",
    "scripts/release_conclusion.py",
    "scripts/precheck.py",
    "scripts/precheck_gates.py",
    "scripts/style_check.py",
    "scripts/code_metrics.py",
    "scripts/coupling_metrics.py",
    "scripts/sast_check.py",
    "scripts/freshness_check.py",
    "scripts/verify_report.py",
)


def file_digests(root: str | Path = ".") -> dict[str, str]:
    """→ {相对路径: sha256}（文件缺失即抛错：判定面不完整不能算版本）。"""
    base = Path(root)
    out: dict[str, str] = {}
    missing: list[str] = []
    for rel in JUDGE_FILES:
        path = base / rel
        if not path.is_file():
            missing.append(rel)
            continue
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    if missing:
        raise ValueError("判定面脚本缺失：" + "、".join(missing) + "（" + GUIDE
                         + "恢复文件或更新 JUDGE_FILES 名单）")
    return out


def digest(root: str | Path = ".") -> dict[str, Any]:
    """→ {schema, files: n, verifier_digest}；同一棵树同一结果（确定性）。"""
    per_file = file_digests(root)
    h = hashlib.sha256()
    for rel in sorted(per_file):
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(per_file[rel].encode("ascii"))
        h.update(b"\n")
    return {"schema": SCHEMA, "files": len(per_file),
            "verifier_digest": h.hexdigest(),
            "note": "判定面脚本的内容摘要；脚本变了摘要就变，旧结论须重跑"}
