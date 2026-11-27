"""domain_pack · _io（自 domain_pack.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from core import atomic_write, json_doc
from core import conformance_scan as csc

from ._catalog import (
    spec_issues,
)
from ._const import (
    REGISTRY_REL,
    SPEC_DIR,
    STANDARDS_REL,
)


def load_spec(root: str, code: str) -> Dict[str, Any]:
    # 读进来之前先定形：`code` 来自命令行，`Path(root)/SPEC_DIR/("%s.json" % code)` 这种拼法
    # 在 `code = "../x"` 时会读到规格目录之外（实测形态）。规格**内容**的校验（`spec_issues`）
    # 发生在读盘之后，挡不住这一步——故形状判据前置（与 `pack_combo.materialize` 同名同规）。
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", str(code or "")):
        raise ValueError("域规格代码形态非法：%r（修复指引：代码取 <A-F><两位数>，如 A01；"
                         "只许字母/数字/-/_）" % code)
    p = Path(root) / SPEC_DIR / ("%s.json" % code)
    if not p.is_file():
        raise ValueError("域规格不存在：%s.json（修复指引：`nf domain specs` 列全量规格代码）"
                         % code)
    spec = json_doc.loads(csc.read_text_cached(p), dict, what=str(p))
    issues = spec_issues(spec)
    if issues:
        raise ValueError("域规格不合规：%s（修复指引：按 spec_issues 逐条补齐规格字段）"
                         % "；".join(issues))
    return spec




def standards_catalog(root: str = ".") -> Dict[str, Dict[str, Any]]:
    doc = _read_json(Path(root) / STANDARDS_REL) or {}
    return {str(s["id"]): s for s in (doc.get("standards") or [])}




def _read_json(path: Path) -> Any:
    """读 JSON；缺件/坏件返回 None（工厂在局部树上也要能工作——由调用方决定语义）。"""

    return _read_json_raw(path)




def _write_text_retry(path: Path, text: str, _tries: int = 5) -> None:
    """带重试的落盘（Windows 实测：杀软/句柄扫描会让 write_text 偶发 EINVAL(22)）。

    落点是**在仓产物**（`community/<包>/…`），并发读者（check32/33/39 各扫描）此前可能
    读到半截。**重试与原子性已收敛到唯一出处**（2026-09-30）：`atomic_write` 现在自带
    瞬时错短重试（EACCES/EBUSY/EINVAL）+ 同目录临时件 `os.replace`——本函数保留为
    **薄兼容壳**（调用方签名不变），不再自己写第二套重试循环。
    """
    atomic_write.write_text(path, text)




def _read_json_raw(path: Path) -> Any:
    """读 JSON；缺件/坏件返回 None（工厂在局部树上也要能工作——由调用方决定语义）。"""
    try:
        return json_doc.loads(csc.read_text_cached(path), None, what=str(path))
    except (OSError, ValueError):  # 缺件/坏件 ⇒ None（调用方决定语义；工厂在局部树上也要能跑）
        return None




# ---------------------------------------------------------------- 全局唯一性

def used_pipeline_ids(root: str = ".") -> List[str]:
    reg = _read_json(Path(root) / REGISTRY_REL) or {}
    out = [str(p.get("pipeline")) for p in (reg.get("protocols") or [])]
    for f in sorted((Path(root) / "03_管线库").glob("*.md")):
        m = re.search(r"(?m)^\s*id:\s*(P\d{2})\s*$", csc.read_text_cached(f))
        if m:
            out.append(m.group(1))
    return out




def module_stems(root: str = ".") -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for p in sorted(Path(root).glob("community/*/modules/*.md")) + \
            sorted(Path(root).glob("04_模块库/*/*.md")):
        stem = p.name.split("_")[0]
        out.setdefault(stem, []).append(p.as_posix())
    return out
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
