"""路径过滤触发：改了 applies_to 内路径 ⇒ 对应 check 必须有运行证据（机制借鉴 lumio pre-commit 路径过滤）。

patterns 的 applies_to 与 LAYERS 的 judged_by 已存在，但无「改了就必跑」联动；
本模块给出触发与证据缺口的机读判据。
"""
from __future__ import annotations

import fnmatch
from typing import Any, Dict, Iterable, List


def triggered(mapping: Dict[str, str], changed: Iterable[str]) -> Dict[str, List[str]]:
    """mapping: {通配路径: check_id} → {check_id: [触发的改动文件]}。"""
    out: Dict[str, List[str]] = {}
    for path in changed:
        for pattern, check in mapping.items():
            if fnmatch.fnmatch(path, pattern):
                out.setdefault(str(check), []).append(path)
    return out


def missing_evidence(hit: Dict[str, List[str]], evidence: Iterable[str]) -> List[str]:
    """哪些被触发的 check 没有运行证据。"""
    have = set(evidence)
    return ["触发但无运行证据：%s（改动 %s）（修复指引：跑该 check 并留证据）"
            % (check, ", ".join(files[:3])) for check, files in hit.items() if check not in have]
