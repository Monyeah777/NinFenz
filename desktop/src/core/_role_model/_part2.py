"""core.role_model 私有实现分片 2/2（对外只经 core.role_model 门面导入）：_projection_drift 等"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import atomic_write, json_doc

from ._part1 import (
    KERNEL_ROLES,
    PROJECTION_REL,
    ROLES,
    _rule_hits,
    _text_of,
    _text_scope,
    coordinate,
    files_of,
    load,
    projection,
    writes_disk,
)


def _projection_drift(root: str) -> List[str]:
    """② 投影件 == 实时重算；缺失/过期 → FAIL。"""
    p = Path(root) / PROJECTION_REL
    live = projection(root)
    if not p.is_file():
        return ["② 缺职能坐标投影 %s（修复指引：nf layers --write）" % PROJECTION_REL]
    try:
        rec = json_doc.load(p, dict, what=PROJECTION_REL)
    except (OSError, ValueError) as exc:
        return ["② %s 不可读：%s（修复指引：nf layers --write）" % (PROJECTION_REL, exc)]
    if rec.get("root_digest") != live.get("root_digest"):
        return ["② %s 与实时重算不一致（记录 %s / 实测 %s）（修复指引：nf layers --write）"
                % (PROJECTION_REL, str(rec.get("root_digest"))[:12], str(live.get("root_digest"))[:12])]
    return []


def write(root: str = ".") -> str:
    """落盘投影（`nf layers --write` 调用；在仓产物，原子写）。"""
    atomic_write.write_text(Path(root) / PROJECTION_REL,
                            json.dumps(projection(root), ensure_ascii=False,
                                       indent=2, sort_keys=True) + "\n")
    return PROJECTION_REL


def _write_channel_issues(root: str, writers: List[str], exc: Dict[str, Any]) -> List[str]:
    """③b 写通道契约化（D3）：写入口必须声明落点件，且该件已在 data_contracts 登记（owner 点名模块）。

    「自带写入口」一直是本仓的**成本中心**（实测 10 个）。只登记「有例外」不够——例外要能回答
    「写到哪个件、谁判它、坏了怎么重建」；答不出来就是没人管的写通道。
    """
    reg: Dict[str, str] = {}
    p = Path(root) / "protocol/data_contracts.json"
    if p.is_file():
        try:
            doc = json_doc.load(p, dict, what="protocol/data_contracts.json")
            for c in doc.get("contracts") or []:
                if isinstance(c, dict):
                    reg[str(c.get("artifact"))] = str(c.get("owner") or "")
        except (OSError, ValueError):
            reg = {}
    issues: List[str] = []
    for rel in writers:
        entry = exc.get(rel)
        artifact = str(entry.get("artifact") or "") if isinstance(entry, dict) else ""
        if not artifact:
            issues.append("③ 写入口 %s 未声明落点件（修复指引：roles.write_exceptions 的值写成 "
                          "{why, artifact}——写通道必须有契约）" % rel)
            continue
        if not (Path(root) / artifact).is_file():
            issues.append("③ 写入口 %s 的落点件不在场：%s（修复指引：改名/补件）" % (rel, artifact))
            continue
        owner = reg.get(artifact)
        if owner is None:
            issues.append("③ 写入口 %s 的落点件 %s 未在 protocol/data_contracts.json 登记"
                          "（修复指引：补一条契约，owner 点名该模块）" % (rel, artifact))
        elif Path(rel).name not in owner:
            issues.append("③ 写入口 %s 的落点件 %s 已登记，但 owner 未点名该模块（实为 %r）"
                          "（修复指引：owner 写清维护模块）" % (rel, artifact, owner[:40]))
    return issues


def _vocab_issues(roles: Dict[str, Any]) -> List[str]:
    """roles.vocabulary 与实现封闭集一致（声明与实现不许两套词表）。"""
    vocab = [str(v) for v in roles.get("vocabulary") or []]
    if set(vocab) != set(ROLES):
        return ["roles.vocabulary 与实现封闭集不一致（修复指引：与 core/role_model.ROLES 对齐）：%s"
                % sorted(set(ROLES) ^ set(vocab))]
    return []


def _coverage_issues(root: str, files: List[str], rules: List[Dict[str, Any]],
                     overrides: Dict[str, Any]) -> List[str]:
    """① 全覆盖 + 核内逐件：未归类 / 落兜底 / 核内实现面无自述。"""
    issues, uncovered, fallback, no_self = [], [], [], []
    for rel in files:
        c = coordinate(root, rel, rules, overrides)
        if not c["role"]:
            uncovered.append(rel)
            continue
        if c["role"] in KERNEL_ROLES:
            if c["rule"] == "R-catch":
                fallback.append(rel)
            if not c["function"]:
                no_self.append(rel)
    if uncovered:
        issues.append("① 覆盖缺口：%d 件未命中任何坐标（例：%s）（修复指引：补规则或 override）"
                      % (len(uncovered), "、".join(uncovered[:3])))
    if fallback:
        issues.append("① 核内件落兜底规则：%s（修复指引：为核内面补专属规则——兜底不许盖核）"
                      % "、".join(fallback[:3]))
    # 自述要求**按面分档**：核内**实现面**（desktop/src/core）无自述 = FAIL（职能句无处可推）；
    # 测试件与第二实现线（engine/**）无自述 = 计入 stats 的可减缺口（不给测试件灌样板 docstring）。
    core_missing = [x for x in no_self if x.startswith("desktop/src/core/") and x.endswith(".py")]
    if core_missing:
        issues.append("① 核内实现面 .py 无自述（职能句无处可推）：%s（修复指引：补模块 docstring 首句）"
                      % "、".join(core_missing[:3]))
    return issues


def _kernel_issues(root: str, kernel: List[str], rules: List[Dict[str, Any]],
                   overrides: Dict[str, Any], exc: Dict[str, str]
                   ) -> Tuple[List[str], List[str]]:
    """③ 核内一致：verify 是只读判据——自带写盘入口须逐条登记理由（→ issues, writers）。"""
    issues, writers = [], []
    for rel in kernel:
        if not rel.endswith(".py"):
            continue
        if coordinate(root, rel, rules, overrides)["role"] != "verify":
            continue
        text = _text_of(root, rel)
        if text is None:
            # 可吞：该件读不到 → 本判据跳过；「件不在场」另有 ① 覆盖判据兜着，不重复报。
            continue
        if writes_disk(text):
            writers.append(rel)
            if rel not in exc:
                issues.append("③ verify 件自带写盘入口未登记：%s（修复指引：在 roles.write_exceptions "
                              "写明理由，或把写入口移出判据面）" % rel)
    stale = sorted(k for k in exc if k not in writers)
    if stale:
        issues.append("③ 写例外已失效：%s（修复指引：从 roles.write_exceptions 删除——例外表只许缩小）"
                      % "、".join(stale[:3]))
    return issues, writers


def _scan_impl(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    roles = load(root)
    if not roles:
        return ["protocol/LAYERS.json 缺 roles 段（修复指引：补 vocabulary/rules/overrides）"], {}
    files = files_of(root)
    rules = _rule_hits(roles, files)
    overrides = roles.get("overrides") or {}
    coords = {rel: coordinate(root, rel, rules, overrides) for rel in files}
    kernel = [rel for rel in files if coords[rel]["role"] in KERNEL_ROLES]
    issues = _vocab_issues(roles) + _coverage_issues(root, files, rules, overrides)
    empty = [x["id"] for x in rules if not x["hits"] and x["id"] != "R-catch"]
    if empty:
        issues.append("② 规则空转：%s（修复指引：删规则或改 glob——空规则是腐烂）" % "、".join(empty))
    issues += _projection_drift(root)
    exc = dict(roles.get("write_exceptions") or {})
    kernel_issues, writers = _kernel_issues(root, kernel, rules, overrides, exc)
    issues += kernel_issues
    issues += _write_channel_issues(root, writers, exc)
    stats = {"files": len(files), "kernel": len(kernel), "rules": len(rules),
             "uncovered": sum(1 for c in coords.values() if not c["role"]),
             "kernel_no_self": sum(1 for r in kernel if not coords[r]["function"]),
             "verify_writers": len(writers), "write_exceptions": len(exc)}
    return issues, stats


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """三条可判定性 → (issues, stats)；并入 check27 的阶梯面（R7）。"""
    with _text_scope():
        return _scan_impl(root)
