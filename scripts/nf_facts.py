#!/usr/bin/env python3
"""NF 事实真源（SSOT）：`protocol/facts.json` 的唯一生成器 + `--check` 断言。

背景（2026-10-26 SSOT 审计，Wave 2 T2.2）：版本/许可/质量/规模/npm 五类事实此前散落在
README ×3、llms.txt / llms-full.txt、site/facts.json、site 首页 meta/JSON-LD、CITATION.cff、
codemeta.json、packaging/npm/README.md 等 ≥20 个手写面；2026-10-26 实测漂移：机器面仍写 MIT
（真值是分层许可）、三语 README 仍写 1.0.5（真值 1.1.0）、CHANGELOG 两节仍标「未发布」。

本模块的地基是 `core/repo_stats.py` 的口径表（模块/管线/包/资产/标准/馆藏 ← 产物实算），
在其上补齐：版本（scripts/nf.py 为 L0）、许可（REUSE.toml 为 L0）、npm（package.json +
payload-manifest.json 为 L0）、历史 MIT 上限（LICENSING.md 为 L0）。

产物只有一个：`protocol/facts.json`（schema `nf-facts/2`）。对外事实面由**规则**渲染；
规则与产物同源，因此 `--check` 能对全量面做逐字节比对（不依赖 node，不跑 verify.sh）。

用法：
  python scripts/nf_facts.py --write    # 重写 facts.json 并修所有受管面
  python scripts/nf_facts.py --check    # 只校验（差异/不变量/字面量禁区）
  python scripts/nf_facts.py --json     # 附加机读摘要

设计约束（勿改）：
- 生成物**不含时间戳**，保证幂等与 diff 稳定；
- 许可分两层：`release.license.*` 为**当前**生效许可；`historical_mit_through` 单独承载
  「≤ 该版本曾按 MIT 发布」——历史句只能来自这里，渲染时不得覆盖成当前许可（反之亦然）；
- 无法在本仓实算的事实（npm registry 件数/体积）只作**声明**：payload-manifest.json 在场时
  以它为准，否则保留上次记录并在 facts 里标 `source`，不静默编新值。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

FACTS_REL = "protocol/facts.json"
SCHEMA = "nf-facts/2"

#: npm registry 外部事实的初始记录（2026-10-08 实测：2907 件 / 解包 23.13 MB）。
#: 打包时若 `packaging/npm/payload/payload-manifest.json` 在场，一律以清单为准。
NPM_SEED = {"files": 2907, "unpacked_bytes": 24253563, "measured_at": "2026-10-08"}

#: 当前许可的规范化短句（渲染进各事实面；来源 REUSE.toml / LICENSING.md）。
LIC_ZH = "AGPL-3.0-only 或商业（协议文本 CC BY 4.0）"
LIC_ZH_FULL = ("代码 AGPL-3.0-only 或商业许可；协议文本 CC BY 4.0；"
               "社区投稿 LicenseRef-Community-Submission")
LIC_EN = "code AGPL-3.0-only or commercial; protocol text CC BY 4.0"

#: 字面量禁区扫描面（公开事实面；历史/法务文件与内部档案不进扫描）。
SCAN_FACES = [
    "README.md", "README.en.md", "README.ja.md", "llms.txt", "llms-full.txt",
    "llms-install.md", "CITATION.cff", "codemeta.json", "GLAMA.md",
    "packaging/npm/README.md", "packaging/mcp/DIRECTORIES.md",
    "packaging/mcp/SUBMIT.md", "packaging/mcp/assets/README.md",
    "packaging/mcp/submissions/03-mcp-so.md", "packaging/mcp/submissions/04-glama.md",
    "packaging/mcp/submissions/05-pulsemcp.md", "packaging/mcp/submissions/06-modelscope.md",
    "packaging/mcp/submissions/07-mcpservers-org.md", "packaging/mcp/submissions/08-mcpmarket.md",
    "packaging/mcp/submissions/09-generic-en.md", "packaging/mcp/submissions/10-generic-zh.md",
    "packaging/hf-space/README.md",
    "site/index.html", "site/en/index.html", "site/use/index.html", "site/en/use/index.html",
    "site/llms.txt", "site/llms-full.txt", "site/nf.txt", "site/agent.txt",
    "site/facts.json", "site/run.sh", "site/robots.txt", "site/404.html",
    "site/sitemap.xml", "site/README.md", "protocol/facts.json",
    "skills/ninfenz/SKILL.md",
]
#: 允许出现历史 MIT / 历史版本的扫描行标记（历史句必须自带这些标记才放行）。
HIST_MARKS = ("historical_mit", "≤ v1.0.5", "≤ 1.0.5", "v1.0.5-mit-final",
              "历史版本", "MIT-NOTICE")


# ---------------------------------------------------------------- 采集 L0 → facts

def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _json(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                                        # noqa: BLE001 - 缺件按 issue 报
        return None


def _release(root: str, issues: List[str]) -> Tuple[str, str]:
    nf_py = _read(os.path.join(root, "scripts", "nf.py"))
    m = re.search(r'^NF_CLI_VERSION = "([^"]+)"', nf_py, re.M)
    if not m:
        issues.append("scripts/nf.py 缺 NF_CLI_VERSION（CLI 版本真源）")
        cli = ""
    else:
        cli = m.group(1)
    readme = _read(os.path.join(root, "README.md"))
    cm = re.search(r"^\|\s*\*\*内容与协议\*\*\s*\|\s*\*\*(v\d+\.\d+)\*\*\s*\|", readme, re.M)
    if not cm:
        issues.append("README.md 缺内容线版本行（`| **内容与协议** | **vX.Y** |`）")
        content = ""
    else:
        content = cm.group(1)
    return cli, content


def _license(root: str, issues: List[str]) -> Dict[str, Any]:
    """许可分层真源 = REUSE.toml（SPDX 映射）；历史 MIT 上限 = LICENSING.md。"""
    code = protocol = community = ""
    try:
        data = tomllib.loads(_read(os.path.join(root, "REUSE.toml")))
        for ann in data.get("annotations") or []:
            paths = ann.get("path") or []
            if isinstance(paths, str):
                paths = [paths]
            spdx = str(ann.get("SPDX-License-Identifier") or "")
            if ann.get("precedence") == "aggregate":
                code = spdx
            for p in paths:
                if p == "protocol/**":
                    protocol = spdx
                elif p == "community/**":
                    community = spdx
    except Exception as exc:                                 # noqa: BLE001
        issues.append("REUSE.toml 不可解析：%s（许可真源缺失）" % exc)
    if not (code and protocol and community):
        issues.append("REUSE.toml 缺分层 SPDX（aggregate / protocol/** / community/** 各一）")
    alt = "LicenseRef-Commercial"
    pyproj = _read(os.path.join(root, "pyproject.toml"))
    if alt not in pyproj:
        issues.append("pyproject.toml 未声明商业替代许可 %s" % alt)
    lic_md = _read(os.path.join(root, "LICENSING.md"))
    hm = re.search(r"≤ v(\d+\.\d+\.\d+)", lic_md)
    if not hm:
        issues.append("LICENSING.md 缺历史 MIT 上限（`≤ vX.Y.Z`）")
    return {
        "code": code,
        "code_alternative": alt,
        "protocol": protocol,
        "community": community,
        "historical_mit_through": hm.group(1) if hm else "",
    }


def _npm(root: str, old: Dict[str, Any], issues: List[str]) -> Dict[str, Any]:
    pkg = _json(os.path.join(root, "packaging", "npm", "package.json")) or {}
    version = str(pkg.get("version") or "")
    if not version:
        issues.append("packaging/npm/package.json 缺 version")
    old_npm = (old or {}).get("npm") or {}
    files = old_npm.get("files", NPM_SEED["files"])
    nbytes = old_npm.get("unpacked_bytes", NPM_SEED["unpacked_bytes"])
    measured = old_npm.get("measured_at", NPM_SEED["measured_at"])
    source = "registry.npmjs.org"
    man_path = os.path.join(root, "packaging", "npm", "payload", "payload-manifest.json")
    man = _json(man_path)
    if isinstance(man, dict) and isinstance(man.get("count"), int) \
            and isinstance(man.get("total_bytes"), int):
        files, nbytes = man["count"], man["total_bytes"]
        source, measured = "payload-manifest.json", ""
    try:
        files, nbytes = int(files), int(nbytes)
    except (TypeError, ValueError):
        issues.append("npm 件数/体积口径不是整数（facts.json 旧值被改坏？）")
    return {
        "version": version,
        "files": files,
        "unpacked_bytes": nbytes,
        "unpacked_mb": "%.2f" % (nbytes / 1048576.0),
        "provenance": bool((pkg.get("publishConfig") or {}).get("provenance")),
        "source": source,
        "measured_at": measured,
    }


def collect(root: str = ROOT) -> Tuple[Dict[str, Any], List[str]]:
    """采集全部事实。返回 (facts, issues)；issues 非空时调用方必须 fail。"""
    issues: List[str] = []
    from core import repo_stats as rs          # 承重口径：产物实算（repo_stats.py:6-19）
    stats, stat_issues = rs.compute(root)
    issues.extend(stat_issues)
    cli, content = _release(root, issues)
    old = _json(os.path.join(root, FACTS_REL)) or {}
    license_block = _license(root, issues)
    npm = _npm(root, old, issues)
    quality = {
        "verify_version": "v%s" % stats.get("verify_version", ""),
        "checks": int(stats.get("baseline_checks") or stats.get("verify_checks") or 0),
        "expected_pass": int(stats.get("baseline_pass") or 0),
    }
    if not quality["verify_version"].strip("v"):
        issues.append("取不到 verify.sh 版本头（质量凭证无法生成）")
    scale_keys = (
        "registered_packs", "pack_dirs", "pack_assets", "concept_graphs", "domain_packs",
        "subdivisions_total", "standards_total", "standards_reachable",
        "standards_unreachable", "standards_bodies", "standards_edges",
        "standards_by_layer", "standard_bindings", "library_items",
        "core_modules", "core_pipelines",
    )
    scale = {k: stats.get(k) for k in scale_keys}
    facts = {
        "schema": SCHEMA,
        "release": {"cli_version": cli, "content_version": content, "license": license_block},
        "quality": quality,
        "npm": npm,
        "scale": scale,
        "faces": {
            "quality_line": "verify v%s · check1-%d · PASS=%d"
                            % (quality["verify_version"].lstrip("v"),
                               quality["checks"], quality["expected_pass"]),
            "quality_line_zh": "质量凭证：verify v%s · check1-%d · PASS=%d"
                               % (quality["verify_version"].lstrip("v"),
                                  quality["checks"], quality["expected_pass"]),
            "license_line_zh": LIC_ZH,
            "license_line_en": LIC_EN,
        },
    }
    return facts, issues


def canonical(facts: Dict[str, Any]) -> str:
    """facts.json 的唯一字节形态（无时间戳 → 幂等、diff 稳定）。"""
    return json.dumps(facts, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------- 受管面规则

def _fmt(facts: Dict[str, Any]) -> Dict[str, Any]:
    lic = facts["release"]["license"]
    return {
        "cli": facts["release"]["cli_version"],
        "content": facts["release"]["content_version"],
        "mit": lic["historical_mit_through"],
        "quality": facts["faces"]["quality_line"],
        "npm_files": str(facts["npm"]["files"]),
        "npm_mb": facts["npm"]["unpacked_mb"],
        "cli_b": facts["release"]["cli_version"],
    }


def rules(facts: Dict[str, Any]) -> List[Tuple[str, str, str, str]]:
    """(note, relpath, pattern, replacement)；按声明顺序应用，替换文本必须幂等。"""
    f = _fmt(facts)
    R: List[Tuple[str, str, str, str]] = []

    def add(note: str, rel: str, pat: str, rep: str) -> None:
        R.append((note, rel, pat, rep))

    # ---- 许可：README 之外的公开事实面（历史 MIT 句只允许出现在法务/历史文件） ----
    lic_full_zh = "%s（≤ v%s 为 MIT）" % (LIC_ZH_FULL, f["mit"])
    for rel in ("llms.txt",):
        add("许可：LICENSE 行", rel,
            r"：MIT License · 原创开源", "：%s · 原创开源" % LIC_ZH_FULL)
        add("许可：引用形态", rel, r"，Monyeah777，MIT，", "，Monyeah777，%s，" % LIC_ZH)
    md_citation = "，Monyeah777，%s，" % LIC_ZH
    for rel in ("llms-full.txt", "site/llms-full.txt"):
        add("许可：一句话定义", rel, r"· 不是托管服务 · MIT · 可离线运行。",
            "· 不是托管服务 · %s · 可离线运行。" % LIC_ZH)
        add("许可：许可段", rel,
            r"本项目以 MIT 许可发布：欢迎转载与商用，但\*\*必须保留 LICENSE 与来源署名\*\*；"
            r"抹掉署名的转载不符合许可条件。",
            "本项目按分层许可发布：%s。转载与商用须保留 LICENSE 与来源署名；"
            "抹掉署名的转载不符合许可条件。" % lic_full_zh)
        add("许可：第 8 条", rel, r"许可与费用：MIT，无付费版、无托管服务。",
            "许可与费用：%s。无付费版、无托管服务。" % lic_full_zh)
        add("许可：FAQ", rel, r"答：MIT，无付费版、无托管服务。",
            "答：%s。无付费版、无托管服务。" % lic_full_zh)
        add("许可：引用形态", rel, r"，Monyeah777，MIT，", md_citation)
        add("许可：APA", rel, r"\[Computer software\]\. MIT\.",
            "[Computer software]. %s." % LIC_EN)
        add("许可：bibtex", rel, r"license = \{MIT\}",
            "license = {AGPL-3.0-only OR LicenseRef-Commercial; protocol text CC-BY-4.0}")
    add("许可：一句话定义", "site/llms.txt", r"不是某厂商 SDK。MIT。",
        "不是某厂商 SDK。%s。" % LIC_ZH)
    add("许可：转载句", "site/llms.txt", r"；MIT 允许转载，但必须保留 LICENSE 与来源署名",
        "；当前分层许可允许转载，但必须保留 LICENSE 与来源署名")
    add("许可：声明", "site/llms.txt", r"- 许可：MIT（CITATION\.cff）",
        "- 许可：%s（机读 protocol/facts.json · CITATION.cff）" % LIC_ZH_FULL)
    add("许可：声明", "site/llms.txt", r"许可 MIT。", "许可 %s。" % LIC_ZH)
    for rel in ("site/nf.txt",):
        add("许可：边界句", rel, r"许可 MIT，可离线运行。", "许可 %s，可离线运行。" % LIC_ZH)
        add("许可：引用形态", rel, r"，Monyeah777，MIT，", md_citation)
    add("许可：边界句", "site/use/index.html", r"仓库就是全部，MIT。", "仓库就是全部，%s。" % LIC_ZH)
    add("许可：边界句", "site/en/use/index.html", r"the repository is everything, MIT\.",
        "the repository is everything; %s." % LIC_EN)
    add("许可：meta", "site/index.html", r"；MIT、可离线。", "；%s、可离线。" % LIC_ZH)
    add("许可：og:meta", "site/index.html", r"不是厂商 SDK。MIT、离线可跑。",
        "不是厂商 SDK。%s、离线可跑。" % LIC_ZH)
    add("许可：not 行", "site/index.html", r"不是某厂商 SDK · MIT · 可离线",
        "不是某厂商 SDK · %s · 可离线" % LIC_ZH)
    add("许可：JSON-LD FAQ", "site/index.html", r'"text": "MIT，无付费版、无托管服务。"',
        '"text": "%s，无付费版、无托管服务。"' % LIC_ZH)
    add("许可：FAQ", "site/index.html", r"<p>MIT，无付费版、无托管服务。</p>",
        "<p>%s，无付费版、无托管服务。</p>" % LIC_ZH)
    add("许可：许可段", "site/index.html",
        r"本项目以 MIT 许可发布：欢迎转载与商用，但<strong>必须保留 LICENSE 与来源署名</strong>；"
        r"抹掉署名的转载不符合许可条件。",
        "本项目按分层许可发布：%s。转载与商用须保留 LICENSE 与来源署名；"
        "抹掉署名的转载不符合许可条件。" % lic_full_zh)
    add("许可：引用形态", "site/index.html", r"，Monyeah777，MIT，", md_citation)
    add("许可：APA", "site/index.html", r"\[Computer software\]\. MIT\.",
        "[Computer software]. %s." % LIC_EN)
    add("许可：bibtex", "site/index.html", r"license = \{MIT\}",
        "license = {AGPL-3.0-only OR LicenseRef-Commercial; protocol text CC-BY-4.0}")
    add("许可：badge", "site/index.html", r'<span class="badge">MIT</span>',
        '<span class="badge">AGPL-3.0-only 或商业</span>')
    add("许可：meta", "site/en/index.html",
        r"Merkle inclusion proofs, MIT, offline\.",
        "Merkle inclusion proofs, %s, offline." % LIC_EN)
    add("许可：og:meta", "site/en/index.html", r"not a vendor SDK\. MIT, offline\.",
        "not a vendor SDK. %s, offline." % LIC_EN)
    add("许可：not 行", "site/en/index.html", r"not a vendor SDK · MIT · runs offline",
        "not a vendor SDK · %s · runs offline" % LIC_EN)
    add("许可：JSON-LD FAQ", "site/en/index.html",
        r'"text": "MIT\. No paid tier and no hosted service\."',
        '"text": "%s. No paid tier and no hosted service."' % LIC_EN)
    add("许可：FAQ", "site/en/index.html", r"<p>MIT, no paid tier, no hosted service\.</p>",
        "<p>%s; no paid tier, no hosted service.</p>" % LIC_EN)
    add("许可：许可段", "site/en/index.html",
        r"Released under MIT: redistribution and commercial use are welcome",
        "Released under layered licences (%s): redistribution and commercial use are welcome"
        % LIC_EN)
    add("许可：引用形态", "site/en/index.html",
        r"Plain: NinFenz \(NF\) - content contract layer, Monyeah777, MIT, ",
        "Plain: NinFenz (NF) - content contract layer, Monyeah777, %s, " % LIC_EN)
    add("许可：APA", "site/en/index.html", r"\[Computer software\]\. MIT\.",
        "[Computer software]. %s." % LIC_EN)
    add("许可：bibtex", "site/en/index.html", r"license = \{MIT\}",
        "license = {AGPL-3.0-only OR LicenseRef-Commercial; protocol text CC-BY-4.0}")
    add("许可：badge", "site/en/index.html", r'<span class="badge">MIT</span>',
        '<span class="badge">AGPL-3.0-only / commercial</span>')
    add("许可：badge", "site/use/index.html", r'<span class="badge">MIT</span>',
        '<span class="badge">AGPL-3.0-only 或商业</span>')
    add("许可：badge", "site/en/use/index.html", r'<span class="badge">MIT</span>',
        '<span class="badge">AGPL-3.0-only / commercial</span>')
    add("许可：run.sh", "site/run.sh", r'许可：MIT · 全部内容可公开引用',
        "许可：%s · 全部内容可公开引用" % LIC_ZH)
    # site/facts.json：机读事实面（含 license/license_allows/citation 三处 + 历史上限字段）
    add("许可：SPDX", "site/facts.json", r'"license": "MIT"',
        '"license": "AGPL-3.0-only OR LicenseRef-Commercial"')
    add("许可：允许项", "site/facts.json",
        r'"license_allows": "MIT: redistribution and commercial use are allowed"',
        '"license_allows": "code: AGPL-3.0-only or commercial license; protocol text: '
        'CC-BY-4.0 (attribution); community: LicenseRef-Community-Submission"')
    add("许可：历史上限位", "site/facts.json",
        r'("license_requires": "keep LICENSE and attribution")'
        r'(?!,\n    "historical_mit_through")',
        r'\1,\n    "historical_mit_through": "%s"' % f["mit"])
    add("许可：引用形态", "site/facts.json", r"，Monyeah777，MIT，", md_citation)
    add("许可：APA", "site/facts.json", r"\[Computer software\]\. MIT\.",
        "[Computer software]. %s." % LIC_EN)
    add("许可：bibtex", "site/facts.json", r"license = \{MIT\}",
        "license = {AGPL-3.0-only OR LicenseRef-Commercial; protocol text CC-BY-4.0}")
    add("许可：CFF", "CITATION.cff", r"^license: MIT$",
        "license: AGPL-3.0-only OR LicenseRef-Commercial")
    add("许可：CFF 纪律注", "CITATION.cff",
        r"# 纪律：本件不钉版本号（版本真源在 README 版本块 / VERSION-MATRIX）",
        "# 纪律：本件不钉版本号（版本/许可真源 = protocol/facts.json，"
        "由 scripts/nf_facts.py --write 生成）")
    add("许可：npm 包自述", "packaging/npm/README.md", r"某厂商 SDK。MIT。",
        "某厂商 SDK。%s。" % lic_full_zh)
    add("许可：npm 包许可行", "packaging/npm/README.md",
        r"- 许可：MIT（见包内 `LICENSE`）",
        "- 许可：%s（包内 `LICENSE` = AGPL-3.0-only 全文）" % LIC_ZH_FULL)
    add("许可：llms-install", "llms-install.md", r"> 许可 MIT —— 使用请保留 LICENSE 与署名；",
        "> 许可：%s —— 使用请保留 LICENSE 与署名；" % LIC_ZH_FULL)
    for rel in ("GLAMA.md",):
        add("许可：能力表 1", rel, r"\| License \| 仓库许可证 \| A（MIT） \|",
            "| License | 仓库许可证 | A（AGPL-3.0-only 或商业） |")
        add("许可：能力表 2", rel, r"\| License \| MIT \|",
            "| License | AGPL-3.0-only 或商业（协议文本 CC BY 4.0） |")
    add("许可：渠道表", "packaging/mcp/DIRECTORIES.md", r"\| 许可 \| MIT \|",
        "| 许可 | AGPL-3.0-only 或商业（协议文本 CC BY 4.0） |")
    add("许可：提交模板", "packaging/mcp/SUBMIT.md", r"\| 许可 \| MIT \|",
        "| 许可 | AGPL-3.0-only 或商业（协议文本 CC BY 4.0） |")
    add("许可：图标表", "packaging/mcp/assets/README.md",
        r"MIT（见仓库 `LICENSE`）", "AGPL-3.0-only 或商业（见仓库 `LICENSE`）")
    add("许可：图标表", "packaging/mcp/assets/README.md", r"\| MIT \|",
        "| AGPL-3.0-only 或商业 |")
    for rel in ("packaging/mcp/submissions/03-mcp-so.md",
                "packaging/mcp/submissions/04-glama.md",
                "packaging/mcp/submissions/05-pulsemcp.md",
                "packaging/mcp/submissions/07-mcpservers-org.md",
                "packaging/mcp/submissions/08-mcpmarket.md"):
        add("许可：提交模板", rel, r"\*\*许可 / License\*\*：MIT",
            "**许可 / License**：AGPL-3.0-only 或商业（协议文本 CC BY 4.0）")
    add("许可：提交模板", "packaging/mcp/submissions/06-modelscope.md",
        r"\*\*许可\*\*：MIT", "**许可**：AGPL-3.0-only 或商业（协议文本 CC BY 4.0）")
    add("许可：提交模板", "packaging/mcp/submissions/09-generic-en.md",
        r"^License: MIT$", "License: AGPL-3.0-only or commercial (protocol text CC BY 4.0)")
    add("许可：提交模板", "packaging/mcp/submissions/10-generic-zh.md",
        r"^许可：MIT$", "许可：AGPL-3.0-only 或商业（协议文本 CC BY 4.0）")
    add("许可：HF Space 元数据", "packaging/hf-space/README.md", r"^license: mit$",
        "license: agpl-3.0")
    add("许可：HF Space 自述", "packaging/hf-space/README.md", r"^- 许可：MIT$",
        "- 许可：AGPL-3.0-only 或商业（协议文本 CC BY 4.0）")
    for rel in ("site/index.html", "site/en/index.html"):
        add("许可：rel=license / JSON-LD license URL", rel,
            r"https://opensource\.org/license/mit",
            "https://opensource.org/license/agpl-3.0")
    add("许可：Skill frontmatter", "skills/ninfenz/SKILL.md", r"^license: MIT$",
        "license: AGPL-3.0-only OR LicenseRef-Commercial")

    # ---- 版本：所有公开面统一到 facts.release.cli_version ----
    for rel in ("README.md", "README.en.md", "README.ja.md"):
        add("版本：安装句", rel, r"`ninfenz`\s+\d+\.\d+\.\d+", "`ninfenz` " + f["cli"])
        add("版本：版本表", rel,
            r"(\|\s*\*\*(?:命令行工具|Command-line tool|コマンドラインツール)\*\*\s*\|\s*\*\*)"
            r"\d+\.\d+\.\d+(\*\*)", r"\g<1>" + f["cli"] + r"\g<2>")
    for rel in ("GLAMA.md",):
        add("版本：发布步骤", rel, r"版本填 `\d+\.\d+\.\d+`", "版本填 `%s`" % f["cli"])
        add("版本：发布步骤", rel, r"版本填 \*\*`\d+\.\d+\.\d+`\*\*（与 `pyproject\.toml` 一致）",
            "版本填 **`%s`**（与 `protocol/facts.json` 一致）" % f["cli"])
        add("版本：验收句", rel, r"确认版本是 `\d+\.\d+\.\d+`", "确认版本是 `%s`" % f["cli"])
    for rel in ("packaging/mcp/DIRECTORIES.md",):
        add("版本：渠道表", rel, r"已满足（npm \d+\.\d+\.\d+ 带 `mcpName`）",
            "已满足（npm %s 带 `mcpName`）" % f["cli"])
        add("版本：当前版本", rel, r"当前仓库版本为 `\d+\.\d+\.\d+`",
            "当前仓库版本为 `%s`" % f["cli"])
        add("版本：发布项", rel, r"复核并发布 \d+\.\d+\.\d+", "复核并发布 %s" % f["cli"])
    npm_ver_faces = ("site/index.html", "site/en/index.html", "site/use/index.html",
                     "site/en/use/index.html", "site/llms.txt", "site/llms-full.txt",
                     "site/agent.txt", "site/nf.txt", "site/facts.json", "llms-full.txt")
    for rel in npm_ver_faces:
        add("版本：npm 面", rel, r"ninfenz v\d+\.\d+\.\d+", "ninfenz v" + f["cli"])
        add("版本：npm 面", rel, r"ninfenz@\d+\.\d+\.\d+", "ninfenz@" + f["cli"])
        add("版本：JSON-LD", rel, r'("softwareVersion":\s*")\d+\.\d+\.\d+(")',
            r"\g<1>" + f["cli"] + r"\g<2>")

    # ---- npm 件数/体积：口径唯一（声明源见 facts.npm） ----
    for rel in npm_ver_faces:
        add("npm：件数/体积", rel, r"ninfenz v\d+\.\d+\.\d+（\d+ 文件 / 解包 \d+\.\d+ MB",
            "ninfenz v%s（%s 文件 / 解包 %s MB" % (f["cli"], f["npm_files"], f["npm_mb"]))
        add("npm：件数/体积（en）", rel, r"ninfenz v\d+\.\d+\.\d+ \(\d+ files / \d+\.\d+ MB",
            "ninfenz v%s (%s files / %s MB" % (f["cli"], f["npm_files"], f["npm_mb"]))

    # ---- 质量凭证：站点手写面统一到 canonical 串（README/llms 由 nf stats 生成，不在此管） ----
    for rel in ("site/index.html", "site/en/index.html", "site/use/index.html",
                "site/en/use/index.html", "site/llms.txt", "site/llms-full.txt",
                "site/nf.txt", "site/agent.txt", "site/facts.json"):
        add("质量：凭证串", rel, r"verify v\d+\.\d+ · check1-\d+ · PASS=\d+", f["quality"])
    return R


def _render_files(facts: Dict[str, Any], root: str = ROOT) -> Dict[str, str]:
    """按文件归并规则：{rel: 新文本}（只含实际命中的文件）。"""
    out: Dict[str, str] = {}
    seen: set = set()

    def render_one(rel: str, text: str) -> str:
        for _note, frel, pat, rep in rules(facts):
            if frel == rel:
                text = re.sub(pat, rep, text, flags=re.M)
        return text

    for _note, rel, _pat, _rep in rules(facts):
        if rel in seen:
            continue
        seen.add(rel)
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new = render_one(rel, text)
        if new != text:
            out[rel] = new
    return out


# ---------------------------------------------------------------- CHANGELOG / 矩阵

def _changelog_rule(root: str, facts: Dict[str, Any]) -> str:
    """把两个「[未发布]」节收进 1.1.0 发布节（结构性一次性改写，幂等）。"""
    path = os.path.join(root, "CHANGELOG.md")
    text = _read(path)
    new = text
    if "## [1.1.0]" not in new:
        new = new.replace("# Changelog\n\n", "# Changelog\n\n## [1.1.0] - 2026-10-25\n\n", 1)
    new = new.replace(
        "## [未发布] · **License change（1.1.0 生效）** — 分层双许可",
        "### 许可变更（1.1.0 生效）— 分层双许可", 1)
    new = new.replace(
        "## [未发布] · **1.1.0 候选**（2026-10-25） · 职能坐标（ADR-0006）+ 项目改名："
        "NarrativeForge → NinFenz（宁封子）+ 全仓审计 V3 修复波",
        "### 职能坐标（ADR-0006）+ 项目改名：NarrativeForge → NinFenz（宁封子）+ "
        "全仓审计 V3 修复波", 1)
    return new


def _matrix_rule(root: str, facts: Dict[str, Any]) -> str:
    path = os.path.join(root, "docs/meta/VERSION-MATRIX.md")
    text = _read(path)
    if "| v1.1.0" in text:
        return text
    row = ("| v1.1.0（CLI / 分层许可） | 2026-10-25 ✅（tag 由作者执行） | "
           "protocol/facts.json · REUSE.toml | CLI/npm/MCP 版本统一 %s；分层许可生效"
           "（代码 AGPL-3.0-only 或商业 / 协议 CC BY 4.0 / 社区 LicenseRef-Community-Submission，"
           "≤ v%s 为 MIT）；verify %s · check1-%d · PASS=%d |\n"
           % (facts["release"]["cli_version"], facts["release"]["license"]["historical_mit_through"],
              facts["quality"]["verify_version"], facts["quality"]["checks"],
              facts["quality"]["expected_pass"]))
    if not text.endswith("\n"):
        text += "\n"
    return text + row


# ---------------------------------------------------------------- 断言

def _scan(facts: Dict[str, Any], issues: List[str]) -> None:
    """字面量禁区：旧许可（MIT 作为**当前**许可）、旧版本、旧发布状态。"""
    mit_re = re.compile(r"(?<![A-Za-z_])MIT(?![A-Za-z_])")
    mit_url_re = re.compile(r"opensource\.org/license/mit|^license:\s*mit\s*$", re.I | re.M)
    ver_re = re.compile(r"\b1\.0\.5\b")
    for rel in SCAN_FACES:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        try:
            lines = _read(path).splitlines()
        except UnicodeDecodeError:
            issues.append("%s 不是 UTF-8（事实面必须是 UTF-8）" % rel)
            continue
        for no, line in enumerate(lines, 1):
            hist = any(m in line for m in HIST_MARKS)
            if (mit_re.search(line) or mit_url_re.search(line)) and not hist:
                issues.append("%s:%d 仍把 MIT 写成当前许可：%s" % (rel, no, line.strip()[:100]))
            if ver_re.search(line) and not hist:
                issues.append("%s:%d 仍含旧版本 1.0.5：%s" % (rel, no, line.strip()[:100]))
    # CHANGELOG 发布节必须在场，且 1.1.0 不再是「未发布」。
    cl = _read(os.path.join(ROOT, "CHANGELOG.md"))
    if "## [1.1.0]" not in cl:
        issues.append("CHANGELOG.md 缺 `## [1.1.0]` 发布节")
    if "## [未发布]" in cl:
        issues.append("CHANGELOG.md 仍有 `## [未发布]` 节")
    mx = _read(os.path.join(ROOT, "docs/meta/VERSION-MATRIX.md"))
    if "| v1.1.0" not in mx:
        issues.append("docs/meta/VERSION-MATRIX.md 缺 v1.1.0 行")
    if "PASS=%d" % facts["quality"]["expected_pass"] not in mx:
        issues.append("docs/meta/VERSION-MATRIX.md 不含当前 PASS 基线")


def _invariants(facts: Dict[str, Any], issues: List[str]) -> None:
    """跨源不变量：同一事实在多个 L0 声明处必须同值。"""
    cli = facts["release"]["cli_version"]
    pyproj = _read(os.path.join(ROOT, "pyproject.toml"))
    npm_pkg = _json(os.path.join(ROOT, "packaging", "npm", "package.json")) or {}
    srv = _json(os.path.join(ROOT, "packaging", "mcp", "server.json")) or {}
    codemeta = _json(os.path.join(ROOT, "codemeta.json")) or {}
    integ = _json(os.path.join(ROOT, "integrations", "site", "integration.json")) or {}
    m = re.search(r'^version = "([^"]+)"', pyproj, re.M)
    pairs = [
        ("pyproject.toml:version", m.group(1) if m else None),
        ("packaging/npm/package.json:version", npm_pkg.get("version")),
        ("packaging/mcp/server.json:version", srv.get("version")),
        ("packaging/mcp/server.json:packages[0].version",
         ((srv.get("packages") or [{}])[0] or {}).get("version")),
        ("codemeta.json:version", codemeta.get("version")),
        ("integrations/site/integration.json:version", integ.get("version")),
    ]
    for name, val in pairs:
        if str(val) != cli:
            issues.append("跨源版本不一致：%s=%s ≠ facts.release.cli_version=%s"
                          % (name, val, cli))
    code_lic = facts["release"]["license"]["code"]
    if str(npm_pkg.get("license")) != code_lic:
        issues.append("npm package.json license=%s ≠ 真源 %s"
                      % (npm_pkg.get("license"), code_lic))
    if str(codemeta.get("license")) != code_lic:
        issues.append("codemeta.json license=%s ≠ 真源 %s"
                      % (codemeta.get("license"), code_lic))
    if "AGPL-3.0-only" not in pyproj:
        issues.append("pyproject.toml license 未声明 AGPL-3.0-only")
    q = facts["quality"]
    if not q["checks"] or not q["expected_pass"]:
        issues.append("质量凭证不完整（checks=%s expected_pass=%s）"
                      % (q["checks"], q["expected_pass"]))


# ---------------------------------------------------------------- 入口

def write(root: str = ROOT) -> Tuple[List[str], Dict[str, Any]]:
    issues: List[str] = []
    facts, collect_issues = collect(root)
    issues.extend(collect_issues)
    if collect_issues:
        return issues, facts
    from core import atomic_write
    path = os.path.join(root, FACTS_REL)
    atomic_write.write_text(path, canonical(facts))
    for rel, new in _render_files(facts, root).items():
        atomic_write.write_text(os.path.join(root, rel), new)
    cl_path = os.path.join(root, "CHANGELOG.md")
    cl_new = _changelog_rule(root, facts)
    if cl_new != _read(cl_path):
        atomic_write.write_text(cl_path, cl_new)
    mx_path = os.path.join(root, "docs", "meta", "VERSION-MATRIX.md")
    mx_new = _matrix_rule(root, facts)
    if mx_new != _read(mx_path):
        atomic_write.write_text(mx_path, mx_new)
    return issues, facts


def check(root: str = ROOT) -> Tuple[List[str], Dict[str, Any]]:
    issues: List[str] = []
    facts, collect_issues = collect(root)
    issues.extend(collect_issues)
    if collect_issues:
        return issues, facts
    path = os.path.join(root, FACTS_REL)
    if not os.path.isfile(path):
        issues.append("缺 %s（跑 `nf facts --write` 生成）" % FACTS_REL)
    else:
        with open(path, encoding="utf-8") as fh:
            recorded = fh.read()
        if recorded != canonical(facts):
            issues.append("%s 与实算不一致（跑 `nf facts --write` 重写）" % FACTS_REL)
    for rel in _render_files(facts, root):
        issues.append("%s 有陈旧事实面（跑 `nf facts --write` 重写）" % rel)
    if _changelog_rule(root, facts) != _read(os.path.join(root, "CHANGELOG.md")):
        issues.append("CHANGELOG.md 发布状态陈旧（跑 `nf facts --write`）")
    if _matrix_rule(root, facts) != _read(os.path.join(root, "docs", "meta",
                                                       "VERSION-MATRIX.md")):
        issues.append("docs/meta/VERSION-MATRIX.md 缺 v1.1.0 行（跑 `nf facts --write`）")
    _invariants(facts, issues)
    _scan(facts, issues)
    return issues, facts


def run(write_mode: bool = False, json_out: bool = False, root: str = ROOT) -> int:
    issues, facts = write(root) if write_mode else check(root)
    if json_out:
        print(json.dumps({"kind": "facts", "schema": SCHEMA, "issues": issues,
                          "facts": facts}, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        lic = facts["release"]["license"]
        print("== nf facts（真相源 %s · 唯一机读产物）==" % FACTS_REL)
        print("  版本：CLI %s · 内容 %s" % (facts["release"]["cli_version"],
                                       facts["release"]["content_version"]))
        print("  许可：代码 %s（或 %s）· 协议 %s · 社区 %s · ≤ v%s 为 MIT"
              % (lic["code"], lic["code_alternative"], lic["protocol"], lic["community"],
                 lic["historical_mit_through"]))
        print("  质量：verify %s · check1-%d · PASS=%d"
              % (facts["quality"]["verify_version"], facts["quality"]["checks"],
                 facts["quality"]["expected_pass"]))
        print("  npm：v%s · %d 件 · 解包 %s MB（源 %s）"
              % (facts["npm"]["version"], facts["npm"]["files"],
                 facts["npm"]["unpacked_mb"], facts["npm"]["source"]))
        print("  规模：%d 登记包 · %d 资产档 · 标准 %d（可达 %d / 不可达 %d）"
              % (facts["scale"]["registered_packs"], facts["scale"]["pack_assets"],
                 facts["scale"]["standards_total"], facts["scale"]["standards_reachable"],
                 facts["scale"]["standards_unreachable"]))
        print("  模式：%s" % ("write（已重写 facts.json 与受管面）" if write_mode
                             else "check（只校验）"))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
    return 1 if issues else 0


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nf_facts", description="NF 事实真源生成/校验")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="重写 facts.json 与受管事实面")
    g.add_argument("--check", action="store_true", help="只校验（默认）")
    ap.add_argument("--json", action="store_true", help="打印机读结果")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    return run(write_mode=bool(args.write), json_out=bool(args.json))


if __name__ == "__main__":
    raise SystemExit(main())
