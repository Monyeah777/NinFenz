"""core.layer_model 私有实现分片 3/3（对外只经 core.layer_model 门面导入）：write_region 等"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import atomic_write
from core import conformance_scan as csc
from core import face_key as _fk
from core import role_model as _roles

from ._part1 import DOC_REL, MARK_BEGIN, MARK_END, load
from ._part2 import _rule_issues, render_markdown


def write_region(root: str = ".") -> str:
    """把渲染结果写回 `docs/layers.md` 生成区（LF 落盘，避免 Windows CRLF 漂移）。"""
    doc = load(root)
    path = Path(root) / DOC_REL
    if not path.is_file():
        raise ValueError("缺阶梯文档 %s（修复指引：先建文件并放 %s / %s 标记）"
                         % (DOC_REL, MARK_BEGIN, MARK_END))
    text = path.read_text(encoding="utf-8")
    if MARK_BEGIN not in text or MARK_END not in text:
        raise ValueError("%s 缺生成区标记（修复指引：先补 %s 与 %s 再写）"
                         % (DOC_REL, MARK_BEGIN, MARK_END))
    head, rest = text.split(MARK_BEGIN, 1)
    _old, tail = rest.split(MARK_END, 1)
    new = head + MARK_BEGIN + "\n" + render_markdown(doc) + "\n" + MARK_END + tail
    # 原子写（2026-09-30 收口）：`docs/layers.md` 是**活文档**，且 `layer_model` 自己会把
    # 它当常驻语料读（L8/L10）——裸 `open(w)` 下并发读者可能读到半截正文。
    atomic_write.write_text(path, new)
    # 第二轴（职能坐标，ADR-0006）的冻结投影同命令刷新：`nf layers --write` = 两轴投影一起重生成。
    # 注意：**不**把职能判据折进本模块 issues——本面是跨语言对照面（engine/rust 的 layers.rs 同步实现
    # L1-L10），折进来会让第二实现线当场不同步；职能判据走 verify_report 判据表（同 redos 先例）。
    _roles.write(root)
    return DOC_REL


#: 规则**真读**的件（实测 130 件）；其余申报件只做**枚举级**判断（「存在且非空」）⇒ 键分两段取
#: （内容 + 成员，见 `core.face_key`）：L6 的 core/*.py + 声明 + 断言集 + 判据脚本 + 渲染投影。
_READ_FACE = ("desktop/src/core/*.py", "protocol/LAYERS.json", "protocol/assertions.json",
              "verify.sh", "docs/layers.md")


def patterns(root: str = ".") -> Tuple[str, ...]:
    """`scan()` 的输入面：**由阶梯声明动态给出**（各阶真源面 + 资产子级 + 纵切件 + 派生物），
    外加声明件本身与判据脚本。

    动态取是安全的：声明件（`protocol/LAYERS.json`）本身就在面内 ⇒ 声明一变指纹必变；声明新列的
    根即使一台空，结果也会变（「真源面须存在且非空」）——而「声明变了」这一点同样已经在指纹里。
    """
    pats = list(_READ_FACE)          # 真读面先入面（含 L6 的 core/*.py 与断言集——后者此前漏申报）
    try:
        doc = load(root)
    except ValueError:
        return tuple(pats)
    for tier in doc.get("tiers") or []:
        pats += [str(g) for g in ((tier.get("source") or {}).get("globs") or [])]
    for level in doc.get("asset_levels") or []:
        pats += [str(g) for g in (level.get("globs") or [])]
    for comp in ((doc.get("crosscut") or {}).get("components") or []):
        if comp.get("artifact"):
            pats.append(str(comp["artifact"]))
    pats += [str(p) for p in (doc.get("derived") or [])]
    out = []
    for pat in pats:
        pat = pat.strip()
        if not pat:
            continue
        # 声明里的「目录」写成不带通配的路径（如 `results/audit`）：按**它下面的件**入面，
        # 否则 `iter_files` 会把它当成一个叫 audit 的**文件**、什么都匹配不到（面会缺口）。
        if not any(ch in pat for ch in "*?[" ) and os.path.isdir(os.path.join(str(root), pat)):
            pat = pat.rstrip("/") + "/**/*"
        out.append(pat)
    return tuple(dict.fromkeys(out))


def face_fingerprint(root: str = ".") -> str:
    """`scan()` 的缓存键：**真读面内容 + 申报面成员集**（实测依据与两段语义见 `core.face_key`）。

    `purity_scan` 拿它组合「自有面 + 本面」的键并把值传给 `scan(_fp=...)`：同一张面只枚举一次。
    """
    return _fk.fingerprint(root, _READ_FACE, patterns(root))


def _scan_impl(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """真算（未命中缓存时走这里）。"""
    try:
        doc = load(root)
    except ValueError as exc:
        return [str(exc)], {"tiers": 0, "asset_levels": 0, "surfaces": 0}
    issues = _rule_issues(root, doc)
    stats = {
        "tiers": len(doc.get("tiers") or []),
        "asset_levels": len(doc.get("asset_levels") or []),
        "surfaces": len(doc.get("surfaces") or []),
        "crosscut": len((doc.get("crosscut") or {}).get("components") or []),
        "rules": len(doc.get("rules") or []),
        "derived": len(doc.get("derived") or []),
    }
    return issues, stats


def scan(root: str = ".", _fp: Optional[str] = None) -> Tuple[List[str], Dict[str, Any]]:
    """阶梯体检 → (issues, stats)；issues 空 = 阶梯自洽（并入 check27 纯度面）。

    派生结果按**输入内容指纹**缓存（输入面见 `patterns()`：声明列了整棵语料，面很宽）。
    **冷进程也走这层**（2026-09-29 改）：过去写「只在常驻语料层在位时才缓存」，理由是「冷进程里取
    指纹比直接算更贵」——实测不成立（冷进程本来就要为别的站点读整棵语料，摘要共享 ⇒ 指纹近乎白拿）；
    实测数字见 `quality_depth_scan.scan`。
    """
    return csc.memo_pair(
        'layer-model',
        patterns(root),
        _scan_impl,
        root,
        code_modules=('core.layer_model',),
        opts=csc.MemoOptions(fp=_fp),
    )
