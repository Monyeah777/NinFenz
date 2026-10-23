"""45 #3 · trace → drill 自动比对器（遥测消费方）。

把 nf assemble --check --trace 落盘的 trace（含 source/requirement/ok）喂回 drill：
- 用 requirement 重建装配允许集；
- 对 source 转录重跑 round_drill；
- 断言「重跑判定 == trace.ok」——不一致 = 遥测与实现漂移（FAIL）。

判定口径分档（2026-09-30 统一）：`ok` 是**命令总判定**，只有加了 `--rounds` 才含回合级；
新写的 trace 逐字带 `rounds:{checked,ok}`。有该键时按它核（`checked=False` ⇒ 返回
`verdict_scope="none"`，即**不适用**，不做漂移断言）；老 trace（无该键）沿用总判定。
"""

from __future__ import annotations

import hashlib
import platform
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import json_doc

_ROOT = Path(__file__).resolve().parents[3]
MAX_TRACE_BYTES = 16 * 1024 * 1024
MAX_SOURCE_BYTES = 16 * 1024 * 1024
TRACE_FORMAT_VERSION = "1"


def _read_bounded(path: Path, limit: int) -> Tuple[str | None, str | None]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, "文件不存在或不可读：%s（%s）" % (path, exc)
    if size > limit:
        return None, "文件过大（%d > %d 字节）" % (size, limit)
    try:
        return path.read_text(encoding="utf-8-sig"), None
    except (OSError, UnicodeError) as exc:
        return None, "文件不可读：%s（%s）" % (path, exc)


def env_fingerprint(root: Path) -> str:
    raw = "%s|%s|%s" % (platform.python_version(), platform.system(), root.resolve())
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _fingerprint_issues(trace: Dict[str, Any], root: Path) -> List[str]:
    issues: List[str] = []
    version = trace.get("generator_version")
    if version and str(version) != TRACE_FORMAT_VERSION:
        issues.append("trace 生成器版本 %s ≠ 当前 %s（修复指引：用当前版本重跑 --trace）"
                      % (version, TRACE_FORMAT_VERSION))
    env = trace.get("env")
    if isinstance(env, dict):
        expect = {"python": platform.python_version(), "platform": platform.system()}
        for key, value in expect.items():
            if key in env and str(env[key]) != value:
                issues.append("trace 环境指纹 %s 不一致：记录 %s / 当前 %s"
                              % (key, env[key], value))
        if env.get("root_fingerprint") and str(env["root_fingerprint"]) != env_fingerprint(root):
            issues.append("trace 仓库根指纹不一致（修复指引：在同一检出上重跑 --trace）")
    return issues


def analyze(trace_path: str, root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    r = Path(root)
    issues: List[str] = []
    # utf-8-sig：容忍外来件开头 BOM（审计 N4）——否则带 BOM 的 trace 被误报成「不是 JSON」。
    raw, err = _read_bounded(Path(trace_path), MAX_TRACE_BYTES)
    if err is not None:
        return ([err], {})
    try:
        trace = json_doc.loads(raw or "", None, what=str(trace_path), strict_constants=True)
    except ValueError as exc:
        return (["trace 不是合法 JSON：%s（修复指引：用 nf assemble --check --trace 产物）" % exc], {})
    # 审计 N3（P2）：顶层非对象时此前会在 trace.get 抛 AttributeError，一路冒成「内部错误：
    # 'list' object has no attribute 'get'」——设计好的诊断分支因此不可达。这里先判形状。
    if not isinstance(trace, dict):
        return (["trace 顶层不是 JSON 对象（实为 %s）"
                 "（修复指引：喂 nf assemble --check --trace 落盘的 trace 件，"
                 "形如 {tool, phase, source, requirement, ok}）" % type(trace).__name__], {})
    source = trace.get("source")
    requirement = trace.get("requirement") or ""
    if not source:
        return ["trace 缺 source（须由 nf assemble --check --trace 生成）"], {}
    transcript = Path(source) if Path(source).is_absolute() else r / source
    if not transcript.is_file():
        return ["trace.source 文件不存在：%s" % source], {}
    text, err = _read_bounded(transcript, MAX_SOURCE_BYTES)
    if err is not None:
        return ([err], {})

    from core import assemble_plan as ap
    from core import round_drill as rd

    plan_ = ap.plan(requirement)
    allowed = plan_.get("allowed_module_ids") or []
    r_issues, r_stats = rd.scan(text or "", allowed)
    issues += _fingerprint_issues(trace, r)
    # 判定口径分档（2026-09-30）：`nf assemble --check --trace` 的总判定 `ok` 只在加了
    # `--rounds` 时才含回合级；新写法的 trace 逐字带 `rounds:{checked,ok}`。有它就用它
    # （checked=False ⇒ **不适用**，不做漂移断言，详见返回的 verdict_scope），
    # 老 trace（无该键）沿用总判定，保持向后兼容。
    scope = trace.get("rounds") if isinstance(trace.get("rounds"), dict) else None
    if scope is not None and scope.get("checked") is False:
        return (["trace 未含回合级判定（写时未加 --rounds）⇒ 不做漂移断言"],
                {"transcript_turns": r_stats["turns"], "expected_ok": None,
                 "actual_ok": not r_issues, "verdict_scope": "none"})
    if scope is not None and scope.get("checked") and scope.get("ok") is not None:
        expected_ok = bool(scope["ok"])
        verdict_scope = "rounds"
    else:
        expected_ok = bool(trace.get("ok"))
        verdict_scope = "overall"
    actual_ok = not r_issues
    if actual_ok != expected_ok:
        issues.append("verdict 漂移：trace 记录 %s（口径=%s）· 重跑判定 %s（issue=%s）"
                      % (expected_ok, verdict_scope, actual_ok, r_issues[:3]))
    return issues, {"transcript_turns": r_stats["turns"],
                    "expected_ok": expected_ok, "actual_ok": actual_ok,
                    "verdict_scope": verdict_scope,
                    "env_fingerprint": env_fingerprint(r),
                    "trace_version": trace.get("generator_version", "")}
