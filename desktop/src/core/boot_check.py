"""启动自检与安全模式（K8 最小实现）：坏配置**拒绝启动**，不带病运行。

为什么（2026-11-08，方案 §2.4 K8）：没有它，「失败可恢复」是空话——
现在的 CLI 遇到坏 protocol JSON 会冒成内部错误或静默降级。本模块把「启动前必须成立的事」
写成清单：关键件在场且可解析 → normal；任一不成立 → safe（拒绝执行写面，并给修复指引）。

panic 转储：异常时产出结构化 dump（类型/消息/上下文/版本），落盘由调用方决定。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "nf-boot-check/1"
DUMP_SCHEMA = "nf-panic-dump/1"
GUIDE = "修复指引："
#: 启动关键件（缺一即 safe）：门禁与裁决数据、方法包索引、判据注册表
CRITICAL = (
    "protocol/adr/registry.json",
    "protocol/docs_ledger.json",
    "protocol/criteria/registry.json",
    "protocol/method_packs/index.json",
)


def check(root: str = ".") -> dict[str, Any]:
    """启动自检 → {schema, mode, issues[], loaded{}}；任一关键件坏 → mode=safe。"""
    issues: list[dict[str, Any]] = []
    loaded: dict[str, Any] = {}
    for rel in CRITICAL:
        path = Path(root) / rel
        if not path.is_file():
            issues.append({"file": rel, "code": "missing",
                           "detail": "关键件不在场（" + GUIDE + "恢复该文件）"})
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            issues.append({"file": rel, "code": "bad-json",
                           "detail": str(exc) + "（" + GUIDE + "修语法）"})
            continue
        if not str(doc.get("schema") or "").startswith("nf"):
            issues.append({"file": rel, "code": "bad-schema",
                           "detail": "缺 nf 前缀 schema（" + GUIDE + "补 schema 字段）"})
            continue
        loaded[rel] = doc.get("schema")
    return {"schema": SCHEMA, "mode": "normal" if not issues else "safe",
            "issues": issues, "loaded": loaded,
            "note": "safe 模式下写面必须拒绝执行（fail-closed），只允许只读体检与修复指引"}


def panic_dump(exc: BaseException, context: dict[str, Any] | None = None,
               version: str = "") -> dict[str, Any]:
    """异常转储（结构化，不含堆栈源码以免泄漏路径；带类型/消息/上下文/版本）。"""
    dump = {"schema": DUMP_SCHEMA, "exc_type": type(exc).__name__,
            "message": str(exc), "context": context or {}, "version": str(version)}
    raw = json.dumps(dump, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    import hashlib
    dump["digest"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return dump


def safe_mode_write_gate(verdict: dict[str, Any]) -> list[str]:
    """safe 模式下写操作应被拒的理由列表（空 = 可写）。"""
    if str(verdict.get("mode")) != "safe":
        return []
    return ["启动自检未通过（safe mode）：" + str(item.get("file")) + " / "
            + str(item.get("detail")) for item in verdict.get("issues") or []]
