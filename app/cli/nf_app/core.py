"""subprocess 桥：统一调用 Rust 参考实现 nf-app-core（CLI/JSON 面，见 app/docs/CLI.md）。

- 位置优先级：explicit / 环境变量 NF_APP_CORE / app/core/target/{release,debug}/ / PATH。
- 找不到时 fail-closed：NF-E-005（exit 4）+ 明确修复指引，绝不降级为 Python 自造结果。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .errors import AppError, envelope_from_core
from .paths import core_candidates

CORE_MISSING_FIX = (
    "构建或安装核心：在仓库根执行 (cd app/core && cargo build --release)，"
    "产物应为 app/core/target/release/nf-app-core.exe（Linux/macOS 无 .exe）；"
    "或用环境变量 NF_APP_CORE=/path/to/nf-app-core 显式指定"
)


def resolve_core(explicit: str | None = None) -> Path:
    declared = explicit or os.environ.get("NF_APP_CORE")
    candidates = core_candidates(explicit)
    for cand in candidates:
        if cand.is_file():
            return cand
    if declared:
        # 显式声明（--core / NF_APP_CORE）必须存在：不静默回落到仓库内二进制
        raise AppError(
            "NF-E-005",
            message=f"显式指定的核心可执行文件不存在: {declared}",
            fix=CORE_MISSING_FIX,
        )
    which = shutil.which("nf-app-core")
    if which:
        return Path(which)
    raise AppError(
        "NF-E-005",
        message="找不到 nf-app-core 可执行文件（核心不可用）",
        fix=CORE_MISSING_FIX,
    )


def _request_bytes(request: Any) -> bytes:
    if request is None:
        request = {}
    return json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def call(
    op: str,
    request: Any = None,
    *,
    explicit: str | None = None,
    timeout: float | None = None,
) -> dict:
    """调用核心 op，返回响应信封；进程/协议故障 → NF-E-005。"""
    exe = resolve_core(explicit)
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    budget = timeout or float(os.environ.get("NF_APP_CORE_TIMEOUT", "300"))
    try:
        proc = subprocess.run(
            [str(exe), op, "--in", "-"],
            input=_request_bytes(request),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=budget,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError(
            "NF-E-005",
            message=f"核心调用超时（op={op}, {budget}s）",
            fix="检查输入规模或提高 NF_APP_CORE_TIMEOUT",
        ) from exc
    except OSError as exc:
        raise AppError("NF-E-005", message=f"无法执行核心（op={op}）: {exc}", fix=CORE_MISSING_FIX) from exc

    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    stderr = proc.stderr.decode("utf-8", errors="replace").strip()
    if not stdout:
        raise AppError(
            "NF-E-005",
            message=f"核心无输出（op={op}, exit={proc.returncode}）{': ' + stderr[:500] if stderr else ''}",
            fix=CORE_MISSING_FIX,
        )
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AppError(
            "NF-E-005",
            message=f"核心输出不是单行 JSON（op={op}）: {stdout[:300]}",
            fix="核对 app/docs/CLI.md §2 响应信封；核心与消费面必须同版本",
        ) from exc
    if not isinstance(envelope, dict) or "ok" not in envelope or "exit" not in envelope:
        raise AppError(
            "NF-E-005",
            message=f"核心信封字段不全（op={op}）: {str(envelope)[:300]}",
            fix="按 app/docs/CLI.md §2 返回 {ok,exit,result,error}",
        )
    if int(envelope["exit"]) != proc.returncode:
        raise AppError(
            "NF-E-005",
            message=(
                f"核心信封 exit({envelope['exit']}) 与进程退出码({proc.returncode}) 不一致（op={op}）"
            ),
            fix="核心实现必须让信封 exit 等于进程退出码（CLI.md §2）",
        )
    return envelope


def call_ok(op: str, request: Any = None, **kwargs: Any) -> Any:
    """调用并断言成功；核心失败信封转 AppError（保留 report 与 exit）。"""
    envelope = call(op, request, **kwargs)
    err = envelope_from_core(envelope)
    if err is not None:
        raise err
    return envelope.get("result")


def abi_version(*, explicit: str | None = None) -> dict:
    exe = resolve_core(explicit)
    try:
        proc = subprocess.run(
            [str(exe), "--abi-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AppError("NF-E-005", message=f"无法读取核心 ABI 版本: {exc}", fix=CORE_MISSING_FIX) from exc
    try:
        return json.loads(proc.stdout.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError as exc:
        raise AppError("NF-E-005", message="核心 --abi-version 输出不是 JSON", fix=CORE_MISSING_FIX) from exc


def available(explicit: str | None = None) -> Path | None:
    try:
        return resolve_core(explicit)
    except AppError:
        return None
