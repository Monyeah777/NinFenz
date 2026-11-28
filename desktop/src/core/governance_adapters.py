"""治理 verify 适配层（WP-31，G3）：in-toto/DSSE、Sigstore、RFC3161、透明日志。

为什么：存量 `core/trust/*` 已能验 bundle/签名/锚，但缺少「**本机到底能对接到哪个外部标准、
缺工具时降级到哪**」的登记面——容易把「不可判定」写成通过。本模块：
- 机读适配器注册表 `protocol/governance_adapters.json`（标准/本地实现/外部工具/可用性/降级）；
- `detect()` 现测外部工具是否在场（与 `results/cq/toolchain.json` 同口径）；
- `verify_plan(required_level)` 给出达到该等级所需适配器、缺失项与**可达最高等级**——
  缺工具/缺锚 → degraded + exit 2，绝不冒充 T3/T4；
- `check()` 自检注册表（available 必须有本地实现、blocked 必须写理由与降级策略）。
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-gov-adapters/1"
REL = "protocol/governance_adapters.json"
GUIDE = "修复指引："
LEVELS = ("T0", "T1", "T2", "T3", "T4")
KINDS = ("attestation", "signature", "timestamp", "transparency")
AVAILABILITY = ("available", "blocked", "external-open")


class AdapterError(Exception):
    """适配器拒绝（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "ADAPTER-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise AdapterError("缺 %s（修复指引：补治理适配器注册表）" % REL,
                           code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AdapterError("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise AdapterError("registry schema 必须 %s" % SCHEMA)
    return doc


def detect(root: str = ".") -> Dict[str, Dict[str, Any]]:
    """现测适配器可用性；工具不在场 → live=blocked（与 CQ toolchain 同口径）。"""
    reg = load_registry(root)
    out: Dict[str, Dict[str, Any]] = {}
    for adapter in reg.get("adapters") or []:
        aid = str(adapter.get("id"))
        tool = str(adapter.get("tool") or "")
        declared = str(adapter.get("availability"))
        live = declared
        if declared == "available" and tool:
            live = "available" if shutil.which(tool) else "blocked"
        elif declared == "blocked":
            live = "blocked"
        out[aid] = {"id": aid, "standard": str(adapter.get("standard")),
                    "kind": str(adapter.get("kind")),
                    "tool": tool, "declared": declared, "live": live,
                    "local_impl": str(adapter.get("local_impl")),
                    "degrade": str(adapter.get("degrade"))}
    return out


def _needs(reg: Dict[str, Any], level: str) -> List[str]:
    """某等级声明的适配器需求表（缺 → 空表）。"""
    return (reg.get("level_requirements") or {}).get(str(level)) or []


def _achievable_level(reg: Dict[str, Any], live: Dict[str, Dict[str, Any]]) -> str:
    """现测可达的最高等级（逐级须全 available，遇缺即停）。"""
    achievable = "T0"
    for level in LEVELS:
        level_needs = _needs(reg, level)
        if all(live.get(aid, {}).get("live") == "available" for aid in level_needs):
            achievable = level
        else:
            break
    return achievable


def verify_plan(required_level: str, root: str = ".") -> Dict[str, Any]:
    """给定 required 等级 → 需要哪些适配器、缺什么、可达最高等级。

    缺适配器 → ok=False、degraded=True、exit_code=2（不可判定），**不返回更高等级**。
    """
    reg = load_registry(root)
    if str(required_level) not in LEVELS:
        raise AdapterError("未知 required_level：%r（修复指引：T0…T4）" % required_level,
                           code="LEVEL-UNKNOWN")
    needs = _needs(reg, required_level)
    live = detect(root)
    missing = [aid for aid in needs if live.get(aid, {}).get("live") != "available"]
    achievable = _achievable_level(reg, live)
    ok = not missing
    return {"schema": "nf-gov-plan/1", "required_level": str(required_level),
            "needs": list(needs), "missing": missing,
            "achievable": achievable, "ok": ok, "degraded": not ok,
            "exit_code": 0 if ok else 2,
            "note": "缺适配器=不可判定（exit 2），不降级冒充更高等级" if not ok else "所需适配器在场"}


def _blocked_issues(adapter: Dict[str, Any], aid: str) -> List[str]:
    """blocked 适配器必须写理由与降级策略。"""
    issues: List[str] = []
    if not str(adapter.get("blocked_reason") or "").strip():
        issues.append("%s blocked 但缺理由（修复指引：写清缺什么工具/为何不可用）" % aid)
    if not str(adapter.get("degrade") or "").strip():
        issues.append("%s blocked 但缺降级策略（修复指引：写清最高可报等级）" % aid)
    return issues


def _adapter_row_issues(root: str, adapter: Dict[str, Any]) -> List[str]:
    """单适配器：kind/availability 词表 + local_impl 在场 + blocked 义务。"""
    aid = str(adapter.get("id"))
    issues: List[str] = []
    if str(adapter.get("kind")) not in KINDS:
        issues.append("%s kind 非法：%s" % (aid, adapter.get("kind")))
    if str(adapter.get("availability")) not in AVAILABILITY:
        issues.append("%s availability 非法" % aid)
    impl = str(adapter.get("local_impl") or "")
    if impl and not (Path(root) / impl).is_file():
        issues.append("%s local_impl 不在场：%s" % (aid, impl))
    if str(adapter.get("availability")) == "blocked":
        issues.extend(_blocked_issues(adapter, aid))
    return issues


def _level_issues(levels: Dict[str, Any], ids: List[str]) -> List[str]:
    """等级映射：四等级齐备且只引用已登记适配器。"""
    issues: List[str] = []
    for level in LEVELS:
        if level not in levels:
            issues.append("level_requirements 缺 %s" % level)
        for aid in levels.get(level) or []:
            if aid not in ids:
                issues.append("level_requirements[%s] 引用未登记适配器：%s" % (level, aid))
    return issues


def check(root: str = ".") -> List[str]:
    """注册表自检：available 有本地实现、blocked 有理由+降级、kind/availability 词表、等级映射覆盖。"""
    issues: List[str] = []
    reg = load_registry(root)
    adapters = reg.get("adapters") or []
    if len(adapters) < 3:
        issues.append("适配器少于 3（in-toto/Sigstore/TSA 至少覆盖）")
    ids = [str(a.get("id")) for a in adapters]
    if len(ids) != len(set(ids)):
        issues.append("适配器 id 重复")
    for adapter in adapters:
        issues.extend(_adapter_row_issues(root, adapter))
    issues.extend(_level_issues(reg.get("level_requirements") or {}, ids))
    boundary = " ".join(str(x) for x in reg.get("claims_boundary") or [])
    if "不作质量背书" not in boundary:
        issues.append("claims_boundary 必须写明外部标准不作质量背书")
    return issues
