"""错误模型：错误码单一真源 = app/schema/error_codes.json。

进程退出码：0 成功 / 1 校验失败 / 2 用法·IO / 3 拒绝（安全·未知·超限）/ 4 环境缺失。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .paths import schema_dir

_REGISTRY: dict[str, dict] | None = None


def registry() -> dict[str, dict]:
    global _REGISTRY
    if _REGISTRY is None:
        data = json.loads((schema_dir() / "error_codes.json").read_text(encoding="utf-8"))
        _REGISTRY = {row["code"]: row for row in data["codes"]}
    return _REGISTRY


def error_info(code: str) -> dict:
    try:
        return registry()[code]
    except KeyError as exc:  # 未登记错误码 = 实现缺陷，fail-closed
        raise RuntimeError(f"未在 error_codes.json 登记的错误码: {code}") from exc


def exit_for(code: str) -> int:
    return int(error_info(code)["exit"])


@dataclass
class AppError(Exception):
    """CLI 层错误；code 必须已登记。"""

    code: str
    message: str | None = None
    fix: str | None = None
    path: str | None = None
    exit: int | None = None
    result: Any = None

    def __post_init__(self) -> None:
        info = error_info(self.code)
        if self.message is None:
            self.message = str(info["message"])
        if self.fix is None:
            self.fix = str(info["fix"])
        if self.exit is None:
            self.exit = int(info["exit"])
        super().__init__(self.message)

    def to_error(self) -> dict:
        err: dict[str, Any] = {"code": self.code, "message": self.message, "fix": self.fix}
        if self.path is not None:
            err["path"] = self.path
        return err

    def to_envelope(self) -> dict:
        return {"ok": False, "exit": int(self.exit or 0), "result": self.result, "error": self.to_error()}


def ok_envelope(result: Any, exit_code: int = 0) -> dict:
    return {"ok": exit_code == 0, "exit": exit_code, "result": result, "error": None}


def envelope_from_core(env: dict) -> AppError | None:
    """核心信封 → AppError（ok=true 时返回 None）。保留核心的 report result 与 exit。"""
    if not isinstance(env, dict):
        raise AppError("NF-E-005", message="核心响应不是 JSON 对象", fix="检查 nf-app-core 版本与 ABI")
    if env.get("ok") is True:
        return None
    err = env.get("error") or {}
    code = err.get("code")
    if not isinstance(code, str) or code not in registry():
        raise AppError(
            "NF-E-005",
            message=f"核心返回未登记错误码: {code!r}",
            fix="升级 APP 或收紧核心实现；错误码必须先登记到 app/schema/error_codes.json",
        )
    return AppError(
        code=code,
        message=err.get("message"),
        fix=err.get("fix"),
        path=err.get("path"),
        exit=int(env.get("exit", exit_for(code))),
        result=env.get("result"),
    )
