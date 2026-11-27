"""pack_combo 私有子模块 _readme：组合包说明面：README / 资产 README / 派生管线 / 证书登记。

门面 core.pack_combo 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core import conformance_scan as csc


def combo_readme(name: str, packs: Sequence[str], cert: Dict[str, Any],
                 refs: Sequence[Tuple[str, List[str]]], layers: Dict[str, List[str]],
                 pid: str) -> str:
    lines = [
        "# %s（组合包 · 由组合引擎产物化）" % name,
        "> 定位：**自由组合包**——由 `nf combine materialize` 从 %d 个域包组合而成；" % len(packs),
        "> 组合包**不新增内容资产**，全部模块经 `references` **只读借阅**（源包模块不改号、资产不复"
            "制）。",
        "> 唯一机读真相 = `protocol.yaml`；本 README 为人读速览（双源一致由 check14 ⑥ 断言）。",
        "> 管线：**%s** %s装配流（派生自 P00 九层骨架）｜借阅模块 **%d** 个｜产出面 8 件（含 T4 证"
            "书）"
        % (pid, name, cert["module_count"]),
        "",
        "## 1. 组合构成",
        "",
        "| 源包 | 借阅模块 |",
        "|---|---|",
    ]
    for sp, ms in refs:
        lines.append("| %s | %s |" % (sp, "、".join("`%s`" % m for m in ms)))
    lines += ["", "## 2. 层位堆叠（available 槽）", "", "| 层 | 模块（堆叠序） |", "|---|---|"]
    for lay, ms in sorted(layers.items()):
        lines.append("| %s | %s |" % (lay, "、".join("`%s`" % m for m in ms)))
    lines += [
        "",
        "## 3. 复现与验收",
        "",
        "```",
        "python scripts/nf.py combine plan --packs \"%s\"" % ",".join(packs),
        "python scripts/nf.py combine verify",
        "python scripts/nf.py output verify",
        "```",
        "",
        "## 4. 边界",
        "",
        "- 组合包**不改源包**：借阅只读；组合不产生新内容资产。",
        "- 合法性与可复算性由组合证书（`outputs/COMBO_CERT.json`）与五不变量保证；",
        "  内容质量仍由各源包口径与 T4 面承担。",
    ]
    return "\n".join(lines) + "\n"



def combo_assets_readme(refs: Sequence[Tuple[str, List[str]]],
                        _layers: Dict[str, List[str]]) -> str:
    lines = ["<!-- ai-index: borrow-only -->",
             "# 借阅索引（本包无自有内容资产）",
             "",
             "> 本组合包 `assets.count = 0`：不复制任何源包资产；下表是**借阅来源**清单，"
             "运行时经 `asset_get` 只读访问源包资产（`asset_readonly: true`）。",
             "",
             "| 源包 | 借阅模块 | 源包资产键 |",
             "|---|---|---|"]
    for sp, ms in refs:
        lines.append("| %s | %s | 见源包 `assets/provenance.json` |" % (sp, "、".join(ms)))
    return "\n".join(lines) + "\n"



def combo_pipeline(name: str, pid: str, layers: Dict[str, List[str]],
                   cert: Dict[str, Any]) -> str:
    order = ["P00", "P10", "P20", "P30", "P40", "P50", "P60", "P70", "P80"]
    lname = {"P00": "数据基座", "P10": "世界推进", "P20": "角色状态", "P30": "事件生产",
             "P40": "行为决策", "P50": "交互执行", "P60": "长期演变", "P70": "叙事素材",
             "P80": "输出呈现"}
    core_allow = {"P00": ["M00"],
 "P10": ["通用:M10"],
 "P20": ["M23"],
 "P30": ["事件:M22",
 "M06",
 "M13"],
                  "P50": ["M12"], "P70": ["M20", "M24"], "P80": ["M80"]}
    lines = [
        "# 管线 %s · %s装配流（组合包派生）" % (pid, name),
        "",
        "> 由组合引擎产物化：九层位名沿用 P00 骨架；`allowed_modules` = 官方核心承载件 ∪ "
        "本组合**借阅**模块（写在各层 `available`）；组合包不新增模块。",
        "> 组合合法性、层栈与闭包结果见 `outputs/COMBO_CERT.json`（T4：由 `nf combine verify` 重算"
            "）。",
        "```yaml",
        "Pipeline:",
        "  id: %s" % pid,
        "  name: %s装配流" % name,
        "  structure:",
        "    type: linear",
        "    flow:",
    ]
    for i, lay in enumerate(order):
        nxt = order[i + 1] if i + 1 < len(order) else "P00"
        lines += ["      - from: %s" % lay, "        to: %s" % nxt]
    lines.append("  layers:")
    for lay in order:
        borrow = layers.get(lay) or []
        allow = sorted(set(core_allow.get(lay, [])) | set(borrow))
        lines += [
            "    - id: %s" % lay,
            "      name: %s" % lname[lay],
            "      description: %s" % (("借阅模块堆叠：" + "、".join(borrow)) if borrow
                                      else "由官方核心承载（%s）" % "/".join(core_allow.get(lay,
 []))),
            "      optional: false",
            "      default_modules: []",
            "      allowed_modules: [%s]" % ", ".join(allow),
        ]
    lines += ["```", "",
              "## 说明",
              "",
              "- 本管线是**组合实例**：层位 default 全空，借阅模块入 available（不改源包挂载）。",
              "- 生成命令：`nf combine materialize --packs \"%s\" --write`。"
                  "" % "、".join(cert["packs"])]
    return "\n".join(lines) + "\n"



@dataclass(frozen=True)
class ComboSpec:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    name: str
    category: str
    pipeline: str
    packages: Sequence[str]
    refs: int
    cert: Dict[str, Any]


def combo_register(root: str, opts: ComboSpec) -> Dict[str, Any]:
    """登记组合包（三要件）：02 §8 段（**模块（0）**）+ verify.sh DOMAIN + registry protocols[]。

    组合包不走 `domain_pack._append_section02`（那条路径假设自有 2 模块 → 空 module_ids 会 IndexError，
    实测 2026-09-23），这里给组合专用段。
    """

    name = opts.name
    category = opts.category
    pipeline = opts.pipeline
    packages = opts.packages
    refs = opts.refs
    cert = opts.cert
    from core import domain_pack as dpk

    doc_path = Path(root) / dpk.DOC02_REL
    text = csc.read_text_cached(doc_path)
    did02 = False
    if "%s（community/%s/）" % (name, name) not in text:
        m = re.search(r"(?m)^## 9\.", text)
        nums = [int(x) for x in re.findall(r"(?m)^### 8\.(\d+) ", text)]
        nxt = (max(nums) + 1) if nums else 1
        seg = "\n".join([
            "### 8.%d %s（community/%s/）" % (nxt, name, name),
            "> **定位**：**组合包**（组合引擎产物化）——由 %d 个域包组合而成；"
            "**不新增模块、不新增内容资产**，全部模块经 `references` 只读借阅"
            "（源包模块不改号、资产不复制）。独占类别：%s（R2）。" % (len(packages), category),
            "- 管线：%s %s装配流（pipelines/%s_%s装配流管线.md；九层位骨架同 P00，"
            "层位 default 全空、借阅模块入 available——规避 check15 ③ 同层 default 冲突）"
            % (pipeline, name, pipeline, name),
            "- 模块（0）：组合包不新增模块；借阅模块 %d 个（%d 条 references，asset_readonly）"
            % (cert["module_count"], refs),
            "- 资产（0 内容文件 + README.md）：assets/README.md 为**借阅索引**（非内容资产，"
            "count = 0，与既有无资产包同为合法形态）",
            "- 产出面（8 机验件）：outputs/ 下 schema 3 / 数据 2 / 图表 1 / 图示 2，"
            "含 **T4 组合证书**（`outputs/COMBO_CERT.json`，由 `nf combine verify` 重算比对）",
            "- 合法性：组合五不变量（模块可定位 / 依赖闭合 / 事件闭合 / 层位堆叠确定 / 资产可寻址）"
            "＋ 广度证明（全部两两 + 定种子抽样）——见 docs/combos.md 与 AUD-0020",
            "",
        ])
        pos = m.start() if m else len(text)
        text = text[:pos] + seg + text[pos:]
        dpk._write_text_retry(doc_path, text)
        did02 = True
    spec_like = {"code": "COMBO", "name": name, "pack_name": name, "category": category}
    did_dom = dpk._append_domain_list(root, spec_like)
    reg_msg = dpk._register_protocols(root, spec_like,
                                      {"pipeline": pipeline, "module_ids": [],
                                       "exist": True})
    return {"section02": did02, "domain_list": did_dom, "protocols": reg_msg}
