"""派生空壳台账（域口径表）：把「还剩多少待补条目」变成可数事实 + 只减不增棘轮。

背景（实测）：社区域包的 `assets/DOMAIN_SPEC.md` 里有一类**派生空壳**——12 条细分名取自品类
清单，判据/失效模式只到**段级工程口径框架**，以占位短语「领域细则待作者补全 / 领域专属判据待补 /
领域专属失效模式待补」如实标注（每包 36 处 = 12 条 × 3 处）。

本模块**不代写领域判据**（宁缺毋滥：领域口径须由作者/领域专家落笔），只负责两件事：

1. `survey()`：逐包清点空壳与已填包 → 缺口可数、可交付边界清晰；
2. `ratchet()`：与冻结基线比对——**空壳只许减少**，新增一律 FAIL（防「越生越多还没人发现」）。

统计面与判据：人读真源 = `community/*/assets/DOMAIN_SPEC.md`；机读投影 = 同包
`outputs/DOMAIN_SPEC.json`——两处的占位出现次数必须一致（双源口径，`survey` 顺带判）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import json

from core import atomic_write, json_doc

#: 占位短语（命中任一即计一条空壳）
SHELL_PHRASES = ("领域细则待作者补全", "领域专属判据待补", "领域专属失效模式待补")
#: 人读真源（每个已建域包一件）
PACKAGE_GLOB = "community/*/assets/DOMAIN_SPEC.md"
#: 机读投影（与真源逐条同源）
JSON_SUFFIX = "outputs/DOMAIN_SPEC.json"

#: 完备度报告（可提交工件；人读 + 机读双形态）。生成：`nf domain shells --write`。
REPORT_REL = "docs/domain-completeness.md"
JSON_REL = "protocol/domain_completeness.json"

#: 冻结基线（2026-09-30 实测）。**只减不增**：空壳数 > 基线即 FAIL（补全后请下调本表）。
BASELINE: Dict[str, int] = {"packs_total": 100, "packs_with_shell": 73,
                            "hits": 2628, "per_shell_pack": 36}


def _hits(text: str) -> int:
    return sum(text.count(phrase) for phrase in SHELL_PHRASES)


def survey(root: str = ".") -> Dict[str, Any]:
    """逐包清点 → `{packs_total, packs_with_shell, packs_filled, hits, per_package, mismatches}`。"""
    base = Path(root)
    per_package: Dict[str, int] = {}
    mismatches: List[str] = []
    total = 0
    for p in sorted(base.glob(PACKAGE_GLOB)):
        pkg = p.parent.parent.name
        total += 1
        n = _hits(p.read_text(encoding="utf-8", errors="replace"))
        if n:
            per_package[pkg] = n
        proj = p.parent.parent / JSON_SUFFIX
        if proj.is_file():
            m = _hits(proj.read_text(encoding="utf-8", errors="replace"))
            if m != n:
                mismatches.append("%s：md %d / json %d" % (pkg, n, m))
    with_shell = len(per_package)
    return {"packs_total": total, "packs_with_shell": with_shell,
            "packs_filled": total - with_shell, "hits": sum(per_package.values()),
            "per_package": per_package, "mismatches": mismatches,
            "tier_mismatches": tier_mismatches(base, per_package)}


#: 人读档位声明里表示「还是占位档」的记号（生成器 `domain_pack.domain_spec_md` 的原文）。
DERIVED_MARK = "derived 档"


def tier_mismatches(base: Path, per_package: Dict[str, int]) -> List[str]:
    """**档位如实**：三处必须同真——人读声明（`.md` 档位行）/ 机读投影（`.json` `content_tier`）/
    正文占位计数。→ 不一致清单（空 = 全一致）。

    为什么（2026-10-01 取证）：档位行只是**声明**，条目正文来自内部规格（`.rivet/private_archive/
    ai_packs/specs/<code>.json`）的 `definition/check/pitfall` 原文。于是有两条静默错误路径：
    ① **虚报完成度**：把 `content_tier` 改成 `authored`（或新包忘了标）而正文仍带占位 ⇒ 读者
       以为「这一域已逐条撰写」，实际是段级框架；
    ② **少报完成度**：真填了内容却忘翻档位 ⇒ 包继续自称「领域细则待作者补全」，缺口台账虚高。
    补全这件事此前**只按占位计数**记账，两条路径都不拦——现把三处钉在一起（缺失即报，见
    `ratchet` 与 `test_shell_ledger`）。
    """
    out: List[str] = []
    for p in sorted(base.glob(PACKAGE_GLOB)):
        pkg = p.parent.parent.name
        hits = per_package.get(pkg, 0)
        head = "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[:8])
        says_derived = DERIVED_MARK in head
        proj = p.parent.parent / JSON_SUFFIX
        proj_tier = None
        if proj.is_file():
            try:
                proj_tier = json_doc.load(proj, dict, what=str(proj)).get("content_tier")
            except ValueError:
                out.append("%s：机读投影不可解析（修复指引：重渲染 outputs/DOMAIN_SPEC.json）" % pkg)
                continue
        if says_derived != (hits > 0):
            out.append("%s：人读档位声明与正文占位%s（占位 %d 处）（修复指引：补全正文后把档位行改"
                "成 "
                       "authored，或按 derived 如实标注）"
                       % (pkg, "矛盾——声明 derived 却无占位" if says_derived else
                          "矛盾——声明 authored 却仍有占位", hits))
        if proj_tier is not None and (proj_tier == "derived") != says_derived:
            out.append("%s：档位与人读声明分叉（json=%s / 人读=%s）（修复指引：重渲染该包产物）"
                       % (pkg, proj_tier, "derived" if says_derived else "authored"))
    return out


def ratchet(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """→ (issues, stats)。空壳 / 双源不一致 / 包数缩水 任一超基线即报。"""
    s = survey(root)
    issues: List[str] = []
    if s["packs_total"] < BASELINE["packs_total"]:
        issues.append("域包总数 %d < 基线 %d（包被删了？修复指引：确认删除是有意为之并下调基线）"
                      % (s["packs_total"], BASELINE["packs_total"]))
    if s["hits"] > BASELINE["hits"]:
        issues.append("派生空壳 %d 处 > 基线 %d 处（修复指引：新条目不许再留占位——补领域判据，"
                      "或补全后下调 %s.BASELINE）" % (s["hits"], BASELINE["hits"], __name__))
    if s["packs_with_shell"] > BASELINE["packs_with_shell"]:
        issues.append("带空壳的域包 %d > 基线 %d（修复指引：新域包不得以占位条目出厂）"
                      % (s["packs_with_shell"], BASELINE["packs_with_shell"]))
    for m in s["mismatches"]:
        issues.append("域口径表双源不一致：%s（修复指引：重渲染 outputs/DOMAIN_SPEC.json 使其同源）" % m)
    for m in s["tier_mismatches"]:
        issues.append("档位声明与实况不符：%s" % m)
    return issues, s


# ---------------------------------------------------------------- 完备度报告
def report(root: str = ".") -> Dict[str, Any]:
    """完备度报告（确定性，无时间戳）→ 机读 dict + 人读渲染共用一份真源。"""
    s = survey(root)
    derived = sorted(s["per_package"])
    authored = sorted(
        p.parent.parent.name for p in Path(root).glob(PACKAGE_GLOB)
        if p.parent.parent.name not in s["per_package"])
    return {"schema": "nf-domain-completeness/1",
            "packs_total": s["packs_total"],
            "packs_authored": s["packs_filled"],
            "packs_derived": s["packs_with_shell"],
            "shell_hits": s["hits"],
            "per_shell_pack": BASELINE["per_shell_pack"],
            "per_package": s["per_package"],
            "authored": authored,
            "derived": derived,
            "mismatches": s["mismatches"],
            "tier_mismatches": s["tier_mismatches"],
            "boundary": ("本报告只统计缺口，不代写领域判据；补全须作者/领域专家落笔，"
                         "补完把 BASELINE 下调后重跑 `nf domain shells --write`。")}


def render_markdown(rep: Dict[str, Any]) -> str:
    lines = [
        "# 域包内容完备度（自动生成，禁止手改）",
        "",
        "> 生成命令：`python scripts/nf.py domain shells --write` ｜ 机读：`protocol/domain_completeness.json`",
        "> 口径：域包「内容资产」是否已由作者逐条补全；**统计缺口不等于质量结论**，也不代写领域内容。",
        "",
        "## 总览",
        "",
        "| 项 | 值 |",
        "|---|---|",
        "| 域包总数 | %d |" % rep["packs_total"],
        "| **已写实（authored）** | **%d** |" % rep["packs_authored"],
        "| **待补全（derived，段级框架）** | **%d** |" % rep["packs_derived"],
        "| 空壳命中（12 细分 × 3 处占位） | %d 处 |" % rep["shell_hits"],
        "",
        "## 待补全清单（每包 36 处占位：定义 / 可机验判据 / 失效模式）",
        "",
        "| 包 | 占位处 |",
        "|---|---|",
    ]
    for pkg in rep["derived"]:
        lines.append("| %s | %d |" % (pkg, rep["per_package"].get(pkg, 0)))
    lines += ["", "## 已写实清单", "", "、".join(rep["authored"]) or "（无）", "",
              "## 补全指引", "",
              "1. `python scripts/nf.py domain template <包名> --out <fill.json>` 生成 12 条待填骨架；",
              "   由作者/领域专家逐条填写 definition/check/pitfall（不代写、不编造）。",
              "   锚表同步 `STANDARDS_ANCHORS.md`；不代写、不编造（宁缺毋滥）。",
              "2. 写完把该包 `content_tier` 改为 `authored`（人读/机读两处），",
              "   并把 `core/shell_ledger.BASELINE` 的 `packs_with_shell`/`hits` 下调到新实测值。",
              "3. `python scripts/nf.py domain shells --write` 重生成本报告与机读件，",
              "   再走冻结链（code_metrics → audit rebind → conformance → approve → receipts）。",
              "", "---", "", "边界：%s" % rep["boundary"]]
    return "\n".join(lines) + "\n"


def write_report(root: str = ".") -> Dict[str, str]:
    rep = report(root)
    p_md = Path(root) / REPORT_REL
    p_json = Path(root) / JSON_REL
    atomic_write.write_text(p_md, render_markdown(rep))
    atomic_write.write_text(p_json,
                            json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {"report": REPORT_REL, "json": JSON_REL}


def report_issues(root: str = ".") -> List[str]:
    """报告新鲜度：缺件 / 与实时 survey 不一致 → issue（由 check12 的单测与 CLI 共同消费）。"""
    issues: List[str] = []
    p_md = Path(root) / REPORT_REL
    p_json = Path(root) / JSON_REL
    if not p_md.is_file() or not p_json.is_file():
        return ["缺域包完备度报告（修复指引：nf domain shells --write）"]
    live = report(root)
    try:
        got = json_doc.load(p_json, dict, what=JSON_REL)
    except ValueError as exc:
        return ["域包完备度机读件不可解析：%s（修复指引：nf domain shells --write）" % exc]
    for key in ("packs_total", "packs_authored", "packs_derived", "shell_hits"):
        if got.get(key) != live[key]:
            issues.append("完备度报告过期：%s 记录=%r 实测=%r（修复指引：nf domain shells "
                          "--write）" % (key, got.get(key), live[key]))
    if got.get("per_package") != live["per_package"]:
        issues.append("完备度报告 per_package 与实测不一致（修复指引：nf domain shells --write）")
    if p_md.read_text(encoding="utf-8", errors="replace") != render_markdown(live):
        issues.append("完备度人读件与生成器输出不一致（修复指引：nf domain shells --write）")
    return issues
