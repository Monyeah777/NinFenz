"""domain_pack · _doc_pack（自 domain_pack.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import json
from typing import Any, Dict


def readme_md(spec: Dict[str, Any], alloc: Dict[str, Any]) -> str:
    code, cat, name = spec["code"], spec["category"], spec["name"]
    pid = alloc["pipeline"]
    return "\n".join([
        "# %s（community 非叙事题材域包 · %s装配流）" % (spec["pack_name"], name),
        "> 定位：**AI 品类域包**（清单 %s · %s）——把「%s」这一域的 %d 条细分协议化："
        "口径可判定、判据可机检、锚可复核，并产出**可复算的域报告**与**可机验的形态面**。"
        % (code, spec["section"], name, len(spec["subdivisions"])),
        "> 协议声明：包根 `protocol.yaml`（01 §6.1 Schema，schema_version \"2\"）为机读真相，"
        "本 README 为人读速览，双源一致（check14 ⑥）。",
        "> 结构：modules/（2 域模块 %s:M01、%s:M02，类内段编号）｜assets/（**3 内容资产**："
        "概念图 CONCEPT_GRAPH、域口径表 DOMAIN_SPEC、权威锚表 STANDARDS_ANCHORS）｜"
        "outputs/（**9 机验产出面**）｜pipelines/%s_%s装配流管线.md" % (cat, cat, pid, name),
        "> 依赖边界（R1）：只依赖官方核心层（M00 / 通用:M10 / M50 / M80，core_only true），"
        "官方模块文件不复制进包。",
        "",
        "## 1. 包速览",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        "| 管线 | **%s** %s装配流（九层线性回卷，装配自 P00 通用骨架） |" % (pid, name),
        "| 自带模块（本包） | 2：%s:M01（P40 口径登记） / %s:M02（P60 收口与派生） |" % (cat, cat),
        "| 资产 | **3 文件**：`CONCEPT_GRAPH.md`（%d 概念前置图）· `DOMAIN_SPEC.md`（%d 条细分口径"
            "）"
        "· `STANDARDS_ANCHORS.md`（逐条权威锚 + 可达性实测）" % (len(spec["subdivisions"]),
                                                         len(spec["subdivisions"])),
        "| 机验产出面 | **9 件**：schema 2 / 数据 2 / 可复算 1（T4）/ 图表 1 / 图结构 2 / 系统卡 1 "
            "|",
        "| 度量族 | `%s`（口径公式见 `docs/domain-packs.md`） |" % spec["metric_family"],
        "",
        "## 2. 复现命令",
        "",
        "| 产物 | 命令（仓库根目录） |",
        "| --- | --- |",
        "| 前置闭包 / 装载序 | `python scripts/ai_domain_closure.py --asset community/%s/assets/CON"
            "CEPT_GRAPH.md --target %s-12` |"
        % (spec["pack_name"], code),
        "| 形态与档位机检 | `python scripts/nf.py output verify` |",
        "| 重渲染产出面 | `python scripts/nf.py output render --write --package %s` |"
            "" % spec["pack_name"],
        "| 重新生成整包 | `python scripts/nf.py domain build --spec %s --write` |" % code,
        "",
        "## 3. 边界与不宣称",
        "",
        "- 本包是**口径协议 + 机验产出**类域包：**不提供**模型、不执行推理、不做能力承诺。",
        "- 域报告是**样例集上的口径值**（合成夹具，非真实测量），不是模型评测结论。",
        "- 外部权威锚只作口径参照，**不作质量背书**；本包正文自撰。",
    ]) + "\n"




def protocol_yaml(spec: Dict[str, Any], alloc: Dict[str, Any]) -> str:
    cat, code = spec["category"], spec["code"]
    pid, ids = alloc["pipeline"], alloc["module_ids"]
    return "\n".join([
        "# protocol.yaml — 第三方协议声明（%s，清单 %s · %s）" % (spec["pack_name"],
 code,
 spec["section"]),
        "# 依据 01 §6.1 Schema 模板骨架 + 02 §8.3 第三方协议登记；机读真相 = 本文件，"
        "人读速览 = README.md（双源一致，check14 ⑥ 断言）",
        "protocol:",
        '  schema_version: "2"',
        "package:",
        '  conformance: "L2"',
        "  id: %s" % spec["pack_name"],
        "  name: %s" % spec["pack_name"],
        '  version: "1.0.0"',
        "  pipeline: %s" % pid,
        "  module_id_range:",
        '    - "%s"' % ids[0],
        '    - "%s"' % ids[1],
        "  categories:",
        "    - %s" % cat,
        "  dependencies:",
        "    core_only: true",
        "    core_modules: [M00, 通用:M10, M50, M80]",
        "    cross_package: []",
        "  references: []",
        "  modules:",
        "    - id: \"%s\"" % ids[0],
        "      desc: %s（%d 条细分的定义 / 可机检判据 / 失效模式登记与冲突上报）"
        % (spec["module_titles"][0], len(spec["subdivisions"])),
        "    - id: \"%s\"" % ids[1],
        "      desc: %s（度量复算 T4 + 概念图派生 + 与口径表同源收口）" % spec["module_titles"][1],
        "  assets:",
        "    count: 3",
        "    readme: README.md",
        "  outputs:",
        "    index: outputs/INDEX.json",
        "    count: 9",
        "    machine_verifiable: 9",
        "    functional: 1",
        "  mount_layers:",
        "    P40 行为决策: {default: [%s], available: []}" % ids[0],
        "    P60 长期演变: {default: [%s], available: []}" % ids[1],
    ]) + "\n"




def provenance_json(spec: Dict[str, Any], _alloc: Dict[str, Any]) -> str:
    cat = spec["category"]
    doc = {
        "schema_version": "1",
        "tier": "community",
        "assets": [
            {"file": "CONCEPT_GRAPH.md", "key": "CONCEPT_GRAPH", "version": "1.0",
             "status": "active", "module": "%s:M01" % cat, "added": "2026-09-22",
             "source": "%s自带概念前置图（域包工厂生成，2026-09-22）；%d 个概念的来源锚见 "
                       "STANDARDS_ANCHORS，逐条可达性实证" % (spec["pack_name"],
                                                       len(spec["subdivisions"]))},
            {"file": "DOMAIN_SPEC.md", "key": "DOMAIN_SPEC", "version": "1.0",
             "status": "active", "module": "%s:M01" % cat, "added": "2026-09-22",
             "source": "%s自带域口径表（2026-09-22 自撰）；域内通行口径的规范化表述，"
                       "不含外部文本" % spec["pack_name"]},
            {"file": "STANDARDS_ANCHORS.md", "key": "STANDARDS_ANCHORS", "version": "1.0",
             "status": "active", "module": "%s:M02" % cat, "added": "2026-09-22",
             "source": "%s自带权威锚表（2026-09-22 本机实测可达性）；锚只作口径参照，"
                       "不作品质背书" % spec["pack_name"]},
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
