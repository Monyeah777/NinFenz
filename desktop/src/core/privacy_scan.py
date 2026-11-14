"""PII 扫描/脱敏叶子件（纯标准库；不 import 任何 core 模块）。

为什么单独成件（NF-Final WP-0B）：隐私判据要能**机检**「证据/日志/文档面里有没有 PII」，
以及「脱敏后原文不可复原」。凭据类（私钥/token）已有唯一实现
`core.meta_cockpit.secret_guard`（不重复造），本件只补 PII 类（邮箱/手机号）并做**脱敏**；
测试把两件拼起来用（`test_privacy_contract.py`），避免两套凭据规则分叉。

边界：只做**高置信、低误报**形态；命中即「需人工复核」，不是「已泄露」判定；
不扫描二进制/超大文本（上限 8 MiB），不可判定的件记 `skipped` 而不是当干净。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

MAX_BYTES = 8 << 20
TEXT_EXT = {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".py", ".toml", ".sh", ".csv"}
REDACTION = "[REDACTED]"

PATTERNS = (
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("cn-mobile", re.compile(r"(?<![0-9A-Za-z])1[3-9]\d{9}(?![0-9A-Za-z])")),
)


def scan_text(text: str) -> List[str]:
    """→ 命中的 PII 类别（去重、保持首次出现顺序）。"""
    kinds: List[str] = []
    for kind, pattern in PATTERNS:
        if pattern.search(text) and kind not in kinds:
            kinds.append(kind)
    return kinds


def redact(text: str) -> str:
    """把 PII 与凭据类值替换为 `[REDACTED]`（凭据类复用 secret_guard 的唯一实现）。"""
    result = text
    for _kind, pattern in PATTERNS:
        result = pattern.sub(REDACTION, result)
    try:
        from core.meta_cockpit import secret_guard  # 唯一凭据规则来源
    except Exception:  # pragma: no cover - 叶子件被裁剪时退回纯 PII 脱敏
        return result
    return secret_guard.redact(result)


def scan_paths(root: str, rels: Iterable[str]) -> Dict[str, Any]:
    """扫声明面 → {findings: [{path,kind}], skipped: [path...], scanned: n}。

    `rels` 可以是文件或目录（目录递归、只收文本后缀）；读不出/超限/二进制 → 记 skipped，
    **不得**当「扫描通过」（fail-closed：不可判定要显式呈报）。
    """
    findings: List[Dict[str, str]] = []
    skipped: List[str] = []
    scanned = 0
    base = Path(root)
    for rel in rels:
        target = base / rel
        paths = [target] if target.is_file() else sorted(target.rglob("*")) if target.is_dir() else []
        if not target.exists():
            skipped.append(str(rel) + "（不在场）")
            continue
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in TEXT_EXT:
                continue
            try:
                if path.stat().st_size > MAX_BYTES:
                    skipped.append(str(path.relative_to(base)) + "（超 1 MiB）")
                    continue
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                skipped.append(str(path.relative_to(base)) + "（不可读/非 UTF-8）")
                continue
            scanned += 1
            for kind in scan_text(text):
                findings.append({"path": str(path.relative_to(base)).replace(os.sep, "/"),
                                 "kind": kind})
    return {"findings": findings, "skipped": skipped, "scanned": scanned}
