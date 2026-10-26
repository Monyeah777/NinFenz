"""T1.2 W1 · 层序闭包扫描（先 WARN + 例外登记，不直接升 FAIL）。

判据（契约语义核心报告 §2 W1）：
  rank(layer) = 装配管线 layers[] 下标（P00=0 … P80=8）；
  模块消费的前置模块（inputs 的 producer）其层位 rank 必须 ≤ consumer 层位 rank。
  倒挂 = 层序闭包违例：已登记于 protocol/layer_exceptions.json 的 → WARN；
  未登记 → FAIL 并给修复指引。

基线（origin/main v1.1.0）实测 4 条倒挂：M06←M20 / M12←M20 / M13←M12 / M13←M20，
故本轮只 WARN；例外表清空后才允许把本规则升 FAIL（升档前须跑全量 verify 确认零倒挂）。

边界：只扫官方核心 `04_模块库/`（社区包 id 命名空间不同，跨包契约由 check16 仲裁）；
调度器（M50，layer=调度器）与 P90 专线（M90，layer=P90）不在 P01 层序内，跳过。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from core import json_doc, pipeline_loader

SCHEMA = "nf-layer-exceptions/1"
EXCEPTIONS_REL = "protocol/layer_exceptions.json"
PIPELINE_REL = "03_管线库/P01_标准管线.md"


def _base(mid: Any) -> str:
    """模块 id 归一为裸号（事件:M22 → M22）；层序比较同一命名空间。"""
    return str(mid or "").strip().split(":")[-1]


def load_exceptions(root: str | Path = ".") -> Dict[Tuple[str, str], Dict[str, Any]]:
    """读例外表 → {(consumer, producer): 条目}；不可读/不合 schema → ValueError（带修复指引）。"""
    path = Path(root) / EXCEPTIONS_REL
    try:
        data = json_doc.load(path, dict, what=EXCEPTIONS_REL)
    except ValueError as exc:
        raise ValueError("层序例外表不可读：%s（修复指引：确认 %s 是合法 JSON 对象）"
                         % (exc, EXCEPTIONS_REL)) from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("层序例外表 schema 须为 %r（修复指引：核对 %s 顶层 schema 键）"
                         % (SCHEMA, EXCEPTIONS_REL))
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for i, entry in enumerate(data.get("exceptions") or []):
        if not isinstance(entry, dict):
            raise ValueError("层序例外表第 %d 条不是对象（修复指引：每条给 consumer/producer/reason）" % i)
        cons, prod = _base(entry.get("consumer")), _base(entry.get("producer"))
        if not cons or not prod:
            raise ValueError("层序例外表第 %d 条缺 consumer/producer（修复指引：填模块裸号如 M06/M20）" % i)
        if not str(entry.get("reason") or "").strip():
            raise ValueError("层序例外表第 %d 条缺 reason（修复指引：写清为何允许倒挂）" % i)
        out[(cons, prod)] = entry
    return out


def _contracts(root: Path) -> Dict[str, Dict[str, Any]]:
    """官方核心 13 件 machine_contract（裸号 → 机读块）。"""
    from core import conformance_scan as csc

    out: Dict[str, Dict[str, Any]] = {}
    for doc in csc._module_docs(str(root)):
        rel = Path(doc).relative_to(root).as_posix()
        if not rel.startswith("04_模块库/"):
            continue
        parsed = csc._fence_yaml(Path(doc).read_text(encoding="utf-8"), "machine_contract")
        mc = parsed.get("machine_contract") if isinstance(parsed, dict) else None
        if isinstance(mc, dict) and mc.get("id"):
            out[_base(mc["id"])] = mc
    return out


def scan(root: str | Path = ".",
         exceptions: Optional[Mapping[Tuple[str, str], Dict[str, Any]]] = None
         ) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """→ (fails, warns, stats)。未登记倒挂进 fails；已登记倒挂进 warns。"""
    root = Path(root)
    stats: Dict[str, Any] = {
        "pipeline": "", "layers": 0, "modules": 0, "edges": 0,
        "backward": 0, "warned": 0, "fails": 0, "exceptions": 0, "unused": [],
    }
    pipeline = pipeline_loader.load_pipeline_file(root / PIPELINE_REL)
    if pipeline is None or not pipeline.layers:
        return (["层序闭包不可判定：%s 不可解析（修复指引：核对管线件 yaml 围栏）"
                 % PIPELINE_REL], [], stats)
    rank = {str(lay.id): i for i, lay in enumerate(pipeline.layers)}
    stats["pipeline"] = pipeline.id
    stats["layers"] = len(rank)
    contracts = _contracts(root)
    stats["modules"] = len(contracts)
    exs = load_exceptions(root) if exceptions is None else dict(exceptions)
    stats["exceptions"] = len(exs)
    warns: List[str] = []
    fails: List[str] = []
    if len(contracts) < 13:
        warns.append("层序闭包覆盖面不足：官方核心机读块仅 %d/13 件（修复指引：补齐 machine_contract）"
                     % len(contracts))
    used = set()
    for cons, mc in sorted(contracts.items()):
        clay = str(mc.get("layer") or "")
        if clay not in rank:
            continue                      # 调度器 / P90 专线：不在 P01 层序内
        for dep in mc.get("inputs") or []:
            prod = _base(dep)
            pmc = contracts.get(prod)
            if not pmc:
                continue
            play = str(pmc.get("layer") or "")
            if play not in rank:
                continue
            stats["edges"] += 1
            if rank[play] <= rank[clay]:
                continue
            stats["backward"] += 1
            key = (cons, prod)
            entry = exs.get(key)
            if entry is not None:
                used.add(key)
                warns.append("层序闭包例外 WARN：%s(%s) ← %s(%s)（已登记：%s）"
                             % (cons, clay, prod, play, str(entry.get("reason") or "")))
            else:
                fails.append(
                    "层序闭包违例：%s(%s) ← %s(%s) 生产者在更后的层"
                    "（修复指引：调整层位/挂载，或按 %s 登记例外并写明 reason）"
                    % (cons, clay, prod, play, EXCEPTIONS_REL))
    stats["warned"] = len(warns)
    stats["fails"] = len(fails)
    stats["unused"] = ["%s←%s" % k for k in sorted(exs) if k not in used]
    return fails, warns, stats
