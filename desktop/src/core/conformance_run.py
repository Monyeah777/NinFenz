"""一致性套件自起服务编排（机制借鉴 smartsheet-rm check_conformance.sh）。

NF 有判据探针，但无「自起服务」编排纪律：启动 → 就绪轮询 → 收尸 trap → 钉版本。
本模块只产出**计划**（不真起进程），由调用方执行，保持 core 零外部进程约束。
"""
from __future__ import annotations

from typing import Any, Dict, List


def plan(service_id: str, command: str, port: int, ready_path: str,
         pinned_version: str) -> Dict[str, Any]:
    """构造编排计划（确定性；不执行）。"""
    return {"service": service_id, "command": command, "port": int(port),
            "ready_path": ready_path, "pinned_version": pinned_version,
            "steps": ["start", "poll-ready", "run-suite", "teardown"]}


def validate(pl: Dict[str, Any]) -> List[str]:
    """必填：启动命令 / 端口 / 就绪探针 / **收尸**（teardown）/ 钉版本。"""
    issues: List[str] = []
    for k in ("command", "port", "ready_path", "pinned_version"):
        if not pl.get(k):
            issues.append("编排计划缺 %s（修复指引：补该字段）" % k)
    if "teardown" not in (pl.get("steps") or []):
        issues.append("编排计划缺 teardown（修复指引：套件结束必须收尸，防残留进程）")
    if "poll-ready" not in (pl.get("steps") or []):
        issues.append("编排计划缺就绪轮询（修复指引：先轮询就绪再跑套件）")
    return issues
