"""判据接线覆盖（静态可核验 / 架构纯度面 · 顶层化补维）。

为什么需要：一次全量审计发现 core 有 **56 个模块暴露 `scan()`**，其中 **5 个没有任何调用点**
（`payload_evidence` / `payload_typing` 甚至全仓零引用）。这类「判据写好了但没接消费者」
是 **"全 check PASS" 的盲区**——门禁全绿并不代表每条判据都在跑；读者会以为它被守着。

本判据把该盲区变成机检：
- 候选集 = `desktop/src/core/*.py` 中定义 `def scan(` 的模块；
- 「被消费」= 该模块名出现在任一消费者里：`verify.sh`、`scripts/nf.py`、
  `core/verify_report.py`（机器可读报告的判据表）、`core/quality_depth_scan.py`、
  或**其它 core 模块**（间接消费）；
- **未被消费且未登记 = FAIL**（修复指引：接进上述任一消费者，或删除该死判据）；
- 登记在 `protocol/judgement_coverage.json` 的例外**放行但须写明理由**；例外若已重新被消费 → WARN
  （例外表不得虚挂）。

纪律：纯标准库；只读；错误消息带修复指引。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import json_doc

from . import scan_memo

DECL_REL = "protocol/judgement_coverage.json"
SCHEMA = "nf-judgement-coverage/1"
CORE_DIR = "desktop/src/core"
CONSUMERS = ("verify.sh", "scripts/nf.py",
             "desktop/src/core/verify_report.py",
             "desktop/src/core/quality_depth_scan.py")
SCAN_DEF = re.compile(r"^def scan\(", re.M)


def candidates(root: str = ".") -> List[str]:
    d = Path(root) / CORE_DIR
    return sorted(p.stem for p in d.glob("*.py")
                  if SCAN_DEF.search(scan_memo.read_text(p) or ""))


def consumers_of(name: str, root: str = ".", sigs: dict = None) -> List[str]:
    """该判据模块被谁消费。

    **精度纪律**（本模块自己踩过的坑）：只认「真消费」信号——`NAME.scan(...)` 之类的属性调用、
    `from core import NAME` 的导入，或注册表里的**带引号模块名**（`verify_report` 的判据表、
    `quality_depth_scan` 的子扫描表都是这种注册式引用）。
    不认「文件里提到过该名字」（注释、文档字符串、例外说明里出现模块名，都不算消费）——
    上一版按裸名字匹配，结果把例外表自己的说明文字当成了消费方，产生 5 条假「例外失效」。
    """
    r = Path(root)
    sigs = _signals_map(root) if sigs is None else sigs
    out: List[str] = []
    registry_files = ("desktop/src/core/verify_report.py",
                      "desktop/src/core/quality_depth_scan.py")
    for rel in CONSUMERS:
        p = r / rel
        if not p.is_file():
            continue
        sig = sigs.get(os.path.abspath(str(p))) or scan_memo.signals(p)
        hit = name in sig["calls"] or name in sig["imports"]
        if not hit and rel in registry_files:
            hit = name in sig["quoted"]
        if hit:
            out.append(rel)
    for p in sorted((r / CORE_DIR).glob("*.py")):
        if p.stem == name:
            continue
        sig = sigs.get(os.path.abspath(str(p))) or scan_memo.signals(p)
        if name in sig["calls"] or name in sig["imports"]:
            out.append("%s/%s" % (CORE_DIR, p.name))
    return sorted(set(out))

def declaration(root: str = ".") -> Tuple[Dict[str, Any], List[str]]:
    p = Path(root) / DECL_REL
    if not p.is_file():
        return {}, ["缺判据例外声明 %s（修复指引：新建并在 exceptions 写明未接线判据与理由）"
                    % DECL_REL]
    try:
        doc = json_doc.load(p, dict, what=DECL_REL)
    except ValueError as exc:
        return {}, ["%s 不是合法 JSON：%s（修复指引：修好 JSON 语法）" % (DECL_REL, exc)]
    if doc.get("schema") != SCHEMA:
        return {}, ["%s schema 不匹配（期望 %s）（修复指引：改为声明件当前形态）"
                    % (DECL_REL, SCHEMA)]
    return doc, []


def scan(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """→ (issues, warns, stats)：未接线且未登记 = FAIL；登记却已接线 = WARN。"""
    doc, issues = declaration(root)
    warns: List[str] = []
    if issues:
        return issues, warns, {"scanners": 0, "consumed": 0, "exceptions": 0, "orphans": 0}
    exc = doc.get("exceptions") or {}
    cands = candidates(root)
    orphans: List[str] = []
    for name in cands:
        who = consumers_of(name, root)
        if not who:
            orphans.append(name)
            if name not in exc:
                issues.append("判据未接线：core/%s.py 暴露 scan() 却没有任何消费者（修复指引："
                              "接进 verify.sh / nf.py / verify_report 判据表 / 其它 core 模块，"
                              "或删除该死判据；确属设计用途须在 %s 的 exceptions 写明理由）"
                              % (name, DECL_REL))
        elif name in exc:
            warns.append("例外已失效：core/%s.py 已被消费（%s）（修复指引：从 %s 的 exceptions 移除"
                "）"
                         % (name, who[0], DECL_REL))
    stats = {"scanners": len(cands), "consumed": len(cands) - len(orphans),
             "exceptions": len(exc), "orphans": len(orphans)}
    return issues, warns, stats


#: 公开入口自成扫描作用域（读面/AST/事实/stat 去重共享；退出即清）
scan = scan_memo.scoped(scan)


def _signals_map(root: str = ".") -> dict:
    """一次扫描内**全部核心文件的 signals 表**（键=绝对路径 → 信号 dict）。

    为什么：`consumers_of` 对 68 个判据名各查一遍 signals，而每次查都走 `facts`（各带一次
    stat）——实测单次扫描 18,490 次 stat，其中 17,600+ 是同一个文件的重复问。表化后每文件
    只 stat 一次。
    """
    from pathlib import Path as _P

    def _compute() -> dict:
        out = {}
        for p in sorted((_P(root) / CORE_DIR).glob("*.py")):
            out[os.path.abspath(str(p))] = scan_memo.token_signals(p)
        return out

    return scan_memo.facts("jc.signals_map", _P(root) / CORE_DIR, _compute)
