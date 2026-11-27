"""报告模块公共骨架（WP-50/WP-51 同源样板）。

四个报告模块（crosscheck / docs_claims / self_scan / stability）此前各自复制了
render / write / check 前半段与 _json 读取函数；抽到此处后各模块只保留业务判据，
重复块由 D-003 口径（单文件重复 8 行块）收敛。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple


def render(report: Dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_report(root: str, report_rel: str, build: Callable[[str], Dict[str, Any]]) -> Path:
    from core import atomic_write
    path = Path(root) / report_rel
    atomic_write.write_text(path, render(build(root)))
    return path


def load_committed(root: str, report_rel: str) -> Tuple[List[str], Dict[str, Any]]:
    """读 committed 报告：返回 (问题列表, 报告)。问题非空时调用方应直接返回 issues。"""
    path = Path(root) / report_rel
    if not path.is_file():
        return ["缺 %s（修复指引：跑 write() 生成）" % report_rel], {}
    try:
        return [], json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["%s 不可解析：%s（修复指引：重生成）" % (report_rel, exc)], {}


def writer(report_rel: str, build: Callable[[str], Dict[str, Any]]) -> Callable[..., Path]:
    """返回绑定 build 的 write(root)（各报告模块一行接入，避免复制样板）。"""
    def _write(root: str = ".") -> Path:
        return write_report(root, report_rel, build)
    return _write


def start(root: str, report_rel: str, build: Callable[[str], Dict[str, Any]],
          mismatch: str) -> Tuple[List[str], Dict[str, Any], Dict[str, Any]]:
    """check() 公共前置：读 committed、实时重算、比对。返回 (issues, committed, live)。"""
    issues, committed = load_committed(root, report_rel)
    if issues:
        return issues, committed, {}
    live = build(root)
    if render(committed) != render(live):
        issues.append(mismatch)
    return issues, committed, live


def load_json(root: str, rel: str) -> Dict[str, Any]:
    path = Path(root) / rel
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
