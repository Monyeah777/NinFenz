"""domain_pack · _plan（自 domain_pack.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import conformance_scan as csc

from ._alloc import (
    allocate,
)
from ._const import (
    DOC02_REL,
    REGISTRY_REL,
    SYSTEM_CARD_SCHEMA_JSON,
    VERIFY_REL,
)
from ._doc_concept import (
    concept_graph_md,
)
from ._doc_domain import (
    domain_spec_md,
    standards_md,
)
from ._doc_module import (
    module_md,
    pipeline_md,
)
from ._doc_pack import (
    protocol_yaml,
    provenance_json,
    readme_md,
)
from ._io import (
    _read_json,
    _write_text_retry,
)
from ._json_faces import (
    domain_spec_json,
    domain_spec_schema,
    output_index,
    report_schema,
    system_card,
)
from ._manifest import (
    update_manifest,
)

# ---------------------------------------------------------------- 组装

def plan(root: str, spec: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """产出「写什么」的计划：返回 (alloc, {仓库相对路径: 内容})。不落盘、不改登记。"""
    alloc = allocate(root, spec)
    pkg = "community/%s" % spec["pack_name"]
    code = spec["code"]
    from core import domain_metrics as dm
    cases = dm.rows_to_csv(dm.synthesize(spec["metric_family"], code))
    files = {
        "%s/protocol.yaml" % pkg: protocol_yaml(spec, alloc),
        "%s/README.md" % pkg: readme_md(spec, alloc),
        "%s/modules/%sa_%s.md" % (pkg, code, spec["module_titles"][0]): module_md(spec, 1, alloc),
        "%s/modules/%sb_%s.md" % (pkg, code, spec["module_titles"][1]): module_md(spec, 2, alloc),
        "%s/pipelines/%s_%s装配流管线.md" % (pkg, alloc["pipeline"], spec["name"]):
            pipeline_md(spec, alloc),
        "%s/assets/CONCEPT_GRAPH.md" % pkg: concept_graph_md(spec, root),
        "%s/assets/DOMAIN_SPEC.md" % pkg: domain_spec_md(spec, root),
        "%s/assets/STANDARDS_ANCHORS.md" % pkg: standards_md(spec, root),
        "%s/assets/provenance.json" % pkg: provenance_json(spec, alloc),
        "%s/outputs/INDEX.json" % pkg: output_index(spec),
        "%s/outputs/schemas/DOMAIN_SPEC.schema.json" % pkg: domain_spec_schema(spec),
        "%s/outputs/schemas/DOMAIN_REPORT.schema.json" % pkg: report_schema(spec),
        "%s/outputs/schemas/SYSTEM_CARD.schema.json" % pkg:
            json.dumps(SYSTEM_CARD_SCHEMA_JSON, ensure_ascii=False, indent=2) + "\n",
        "%s/outputs/DOMAIN_SPEC.json" % pkg: domain_spec_json(spec, root),
        "%s/outputs/SYSTEM_CARD.json" % pkg: system_card(spec, alloc),
        "%s/outputs/samples/CASES.csv" % pkg: cases,
    }
    return alloc, files




def _append_section02(root: str, spec: Dict[str, Any], alloc: Dict[str, Any]) -> bool:
    """在 02 §8 末尾追加登记段（幂等）。返回是否改动。"""
    doc_path = Path(root) / DOC02_REL
    text = csc.read_text_cached(doc_path)
    if "### 8." in text and spec["pack_name"] + "（community/" in text:
        return False
    m = re.search(r"^## 9\.", text, re.M)
    if not m:
        raise ValueError("02 文档缺 §9 锚点，无法安全插入 §8 登记段")
    nums = [int(x) for x in re.findall(r"^### 8\.(\d+) ", text, re.M)]
    nxt = (max(nums) + 1) if nums else 1
    ids = alloc["module_ids"]
    seg = "\n".join([
        "### 8.%d %s（community/%s/）" % (nxt, spec["pack_name"], spec["pack_name"]),
        "> **定位**：AI 品类域包（清单 %s · %s）——把「%s」这一域的 %d 条细分协议化："
        "口径可判定、判据可机检、锚可复核，并产出可复算域报告与机验形态面。"
        "独占类别：%s（R2，与既有 [情感]/[生存]/[世界]/[事件]/[轻混]/[通用]/[技术文档]/[AI系统]/"
        "[量化金融] 及各 AI 品类域包类别无交集）。"
        % (spec["code"],
 spec["section"],
 spec["name"],
 len(spec["subdivisions"]),
 spec["category"]),
        "- 管线：%s %s装配流（pipelines/%s_%s装配流管线.md；九层位 linear flow P00→P80→P00 回卷，"
        "P40/P60 两驻留层各挂 %s / %s，官方核心 M00·通用:M10·M50·M80 core 依赖引用不搬移）"
        % (alloc["pipeline"], spec["name"], alloc["pipeline"], spec["name"], ids[0], ids[1]),
        "- 模块（2）：%s %s（P40 行为决策，%d 条细分口径登记与冲突上报）、%s %s（P60 长期演变，"
        "度量复算 + 概念图派生收口）（modules/；编号落类内段 `<独占类别>:Mxx`，01 §1.6.11 通道②）"
        % (ids[0], spec["module_titles"][0], len(spec["subdivisions"]),
           ids[1], spec["module_titles"][1]),
        "- 资产（3 内容文件 + README.md）：assets/CONCEPT_GRAPH.md（%d 概念前置图）· "
        "assets/DOMAIN_SPEC.md（%d 条细分口径）· assets/STANDARDS_ANCHORS.md（逐条权威锚 + "
        "可达性实测）——经包内供应链台账 `provenance.json` 托管（check23 自证）"
        % (len(spec["subdivisions"]), len(spec["subdivisions"])),
        "- 产出面（9 机验件）：outputs/ 下 schema 3 / 数据 3 / 可复算 1（T4 域报告）/ 图表 1 / "
        "图结构 2；可机验占比 100%（≥95% 门槛），见 outputs/INDEX.json 与 docs/domain-packs.md",
        "- 依赖（R1）：core_only true + core_modules 4 件官方核心配合（M00 / 通用:M10 / M50 / M80）"
            "；"
        "cross_package [] 恒空、references [] 零跨包引用",
        "- 挂载层：P40 default [%s]、P60 default [%s]——类内段编号唯一，与既有包同层 default 无交集"
        % (ids[0], ids[1]),
        "",
    ])
    text = text[:m.start()] + seg + text[m.start():]
    _write_text_retry(doc_path, text)
    return True




def _append_domain_list(root: str, spec: Dict[str, Any]) -> bool:
    """把包目录加进 verify.sh check14 的 DOMAIN 列表（幂等）。"""
    p = Path(root) / VERIFY_REL
    text = csc.read_text_cached(p)
    entry = "'community/%s'" % spec["pack_name"]
    m = re.search(r"(?m)^(DOMAIN = \[)([^\]]*)(\])", text)
    if not m:
        raise ValueError("verify.sh 未找到 DOMAIN 列表锚点")
    if entry in m.group(2):
        return False
    inner = m.group(2)
    if not inner.rstrip().endswith(","):
        inner = inner.rstrip() + ","
    new = m.group(1) + inner + " " + entry + m.group(3)
    _write_text_retry(p, text[:m.start()] + new + text[m.end():])
    return True




def _register_protocols(root: str, spec: Dict[str, Any], _alloc: Dict[str, Any]) -> str:
    """把包投影进 registry protocols[]（与 `nf register --apply` 同一套纯函数）。"""
    from core import protocol_projection as pp
    from core import registry_sync as rsync

    pkg_dir = str(Path(root) / "community" / spec["pack_name"])
    path = Path(root) / REGISTRY_REL
    reg = _read_json(path) or {}
    cur = reg.get("protocols")
    if not isinstance(cur, list):
        return "registry protocols[] 缺失（跳过投影）"
    try:
        entry = pp.project_entry(pkg_dir)
    except Exception as exc:  # 投影失败必须可见
        return "投影失败：%s" % exc
    merged = rsync.merge_protocols(cur, [entry])
    if [json.dumps(p, sort_keys=True, ensure_ascii=False) for p in merged] == \
            [json.dumps(p, sort_keys=True, ensure_ascii=False) for p in cur]:
        return "已登记（幂等，无变化）"
    reg["protocols"] = merged
    _write_text_retry(path, json.dumps(reg, ensure_ascii=False, indent=2) + "\n")
    return "已写入（protocols[] %d → %d）" % (len(cur), len(merged))




def build(root: str, spec: Dict[str, Any], write: bool = False,
          render: bool = True, renderer=None) -> Dict[str, Any]:
    """生成整包：文件 + 登记三处（02 §8 / verify.sh DOMAIN / registry protocols[]）+ 渲染产出面。

    登记三处**一次做完**（2026-09-23 实测教训：漏跑 `nf register --apply` 会让
    check14 ⑦ / check15 ⑤ / check29 虚标 / check32 名录四处红——工厂把这一步收进来，
    从构造上消除「建了包没登记」这一类）。

    渲染产出面改由**调用方注入**（`renderer(root, package=…, write=…)`，见
    `output_forms.render_outputs`）：工厂不再反向 import 产出面——`domain_pack → output_forms
    → pack_combo → domain_pack` 那条模块级环由此断掉（2026-09-29；环由 `coupling_metrics`
    机检，零环是硬判据）。不注入 renderer 即不渲染，工厂自身的职责不变。
    """
    alloc, files = plan(root, spec)
    changed, written = [], []
    _prune_stale(pkg_dir=Path(root) / "community" / spec["pack_name"],
                 code=spec["code"], planned=set(files))
    for rel, content in sorted(files.items()):
        p = Path(root) / rel
        cur = p.read_bytes() if p.is_file() else b""
        if cur != content.encode("utf-8"):
            changed.append(rel)
            if write:
                p.parent.mkdir(parents=True, exist_ok=True)
                _write_text_retry(p, content)
                written.append(rel)
    reg = {"section02": False, "domain_list": False, "render": []}
    if write:
        reg["section02"] = _append_section02(root, spec, alloc)
        reg["domain_list"] = _append_domain_list(root, spec)
        reg["protocols"] = _register_protocols(root, spec, alloc)
        update_manifest(root, spec, write=True)
        if render and renderer is not None:
            issues, rows = renderer(root, package=spec["pack_name"], write=True)
            reg["render"] = rows
            reg["render_issues"] = issues
    return {"spec": spec["code"], "pipeline": alloc["pipeline"],
            "module_ids": alloc["module_ids"], "files": len(files),
            "changed": len(changed), "written": len(written), "registry": reg}




def _prune_stale(pkg_dir: Path, code: str, planned: set) -> List[str]:
    """删同前缀陈旧生成物（改名残留）：模块 `<码>a_/b_*`、管线 `P*/<域名>*`、资产同名计划外件。

    实测教训（2026-09-23）：模块标题或管线 id 变更后重建会**新增**文件而旧文件留存，
    check14 ⑤（裸号同包重复）与 check28（管线 schema）随即红。生成物可复算，删旧即安全。
    """
    removed: List[str] = []
    root_rel = pkg_dir.parents[1]
    for sub in ("modules", "pipelines"):
        d = pkg_dir / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            rel = f.relative_to(root_rel).as_posix()
            if rel in planned:
                continue
            tok = f.name.split("_")[0]
            keep = (sub == "modules" and tok in ("%sa" % code, "%sb" % code)) or \
                   (sub == "pipelines" and re.fullmatch(r"P\d{2,3}", tok) is not None)
            if keep:
                f.unlink()
                removed.append(rel)
    return removed




def verify(root: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """工厂自检：生成物是否与计划逐字节一致 + 登记是否到位 + 产出面机检。"""
    issues: List[str] = []
    _, files = plan(root, spec)
    missing, drift = _plan_drift_issues(root, files)
    issues += ["缺件：%s" % r for r in sorted(missing)]
    issues += ["与生成器漂移：%s" % r for r in sorted(drift)]
    _plan_doc_issues(root, spec, issues)
    _plan_verify_sh_issues(root, spec, issues)
    _plan_registry_issues(root, spec, issues)
    stats = {"files": len(files), "missing": len(missing), "drift": len(drift)}
    return issues, stats


def _plan_drift_issues(root, files):
    missing = [r for r, c in files.items()
               if not (Path(root) / r).is_file()]
    drift = [r for r, c in files.items()
             if (Path(root) / r).is_file()
             and (Path(root) / r).read_bytes() != c.encode("utf-8")]
    return missing, drift


def _plan_doc_issues(root, spec, issues):
    doc02 = csc.read_text_cached(Path(root) / DOC02_REL)
    if spec["pack_name"] + "（community/" not in doc02:
        issues.append("02 §8 未登记本包")
    else:
        segm = re.search(r"(?ms)^### 8\.\d+ %s\b.*?(?=^### 8\.|^## 9\.)"
                         % re.escape(spec["pack_name"]), doc02)
        if not segm or "模块（2）" not in segm.group(0):
            issues.append("02 §8 段缺 `模块（2）` 在册行")


def _plan_verify_sh_issues(root, spec, issues):
    vs = csc.read_text_cached(Path(root) / VERIFY_REL)
    if "'community/%s'" % spec["pack_name"] not in vs:
        issues.append("verify.sh DOMAIN 列表未登记本包")


def _plan_registry_issues(root, spec, issues):
    reg = _read_json(Path(root) / REGISTRY_REL) or {}
    pids, cats = _plan_registry_lists(reg, spec)
    if spec["pack_name"] not in pids:
        issues.append("registry protocols[] 未登记本包（修复指引：nf register --apply）")
    if spec["category"] in cats:
        issues.append("R2 类别冲突：%s 已被他包占用" % spec["category"])


def _plan_registry_lists(reg, spec):
    """registry → (protocols id 列表, 他包已占类别列表)。"""
    pids = [p.get("id") for p in reg.get("protocols") or []]
    cats = [c for p in reg.get("protocols") or []
            if p.get("id") != spec["pack_name"] for c in (p.get("categories") or [])]
    return pids, cats
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
