"""守护请求 cwd 的规范化与包含性边界。"""
from __future__ import annotations

import os
import re
from pathlib import Path


def validated_cwd(root: Path, cwd: str | None, max_chars: int) -> str | None:
    """空值使用守护自身 cwd；非空值必须是仓库根内的现存目录。"""
    if cwd is None:
        return None
    if not isinstance(cwd, str) or not cwd:
        raise ValueError("cwd 必须是非空字符串（修复指引：客户端传绝对目录，或省略 cwd）")
    if len(cwd) > max_chars:
        raise ValueError(f"cwd 超过上限 {max_chars} 字符（修复指引：缩短路径或省略 cwd）")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in cwd):
        raise ValueError("cwd 含控制字符（修复指引：路径里不得含 \x00-\x1f）")
    if os.name == "nt":
        match = re.match(r"^/([A-Za-z])/(.*)$", cwd)
        if match:
            cwd = f"{match.group(1).upper()}:\\{match.group(2).replace('/', chr(92))}"
    safe = os.path.realpath(cwd)
    if not os.path.isdir(safe):
        raise ValueError(f"cwd 不是现存目录：{safe}（修复指引：传仓库根的绝对路径，或省略 cwd）")
    safe_root = os.path.realpath(str(root))
    try:
        inside_root = os.path.commonpath((safe_root, safe)) == safe_root
    except ValueError:
        inside_root = False
    if not inside_root:
        raise ValueError(
            f"cwd 越出仓库根：{safe}（修复指引：只传 {safe_root} 内的目录，或省略 cwd）"
        )
    return safe
