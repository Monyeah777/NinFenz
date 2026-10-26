#!/usr/bin/env python3
# nf-io: inputs=community/技术文档域包/gate_profiles/techdoc-strict.json,community/合规与监管域包/gate_profiles/regulatory-strict.json,desktop/tests/fixtures/gate_defects outputs=results/bench/gate_defect_report.json
"""Gate profile 缺陷注入测量台（T5.3）：把「profile 质量」变成可复现的检出率/误报率数字。

要回答的问题
------------
`techdoc-strict` / `regulatory-strict` 两个 profile 号称严格质量门——但它们到底能抓住
多少类缺陷、会不会把干净件判红？本台架对每个 profile 做 **10 类 × 10 例**注入实验：
每类 8 个负例（注入该类缺陷）+ 2 个正例（清洁件），逐例跑 `core.gate_profile.report`，
统计每 profile × 每类的 cases / detected / missed / false_positives / detection_rate / fp_rate。

判据口径（避免自欺）
--------------------
- **detected**：注入后 profile 报告里，**该类声明的 target clause** 出现 `ok=False`
  （fail 或 warn 都算——warn 级判据（如弱表达/安全提示）同样属于"门看见了"，在报告里
  按 target 的 level 可分辨）。
- **false_positive**：清洁件命中 target clause（该类判据对干净件误报）。
- **scope 三态**（profile 判据面不同，必须如实区分，不能拿"没这条规则"当"漏检"）：
  `native` = profile 本身有该类的判据；`compensated` = profile 无该类原生规则，但把缺陷
  注入到必填 token 后由既有条款检出（**代偿路径，明示**）；`out_of_scope` = profile 无
  任何能检出的判据（本轮只有 regulatory-strict 的「标题标点」——它全 profile 无标题风格
  条款），该类的负例**不进检出率分母**，只作信息面记录。
- 阈值：负例检出率 ≥90%，清洁件误报率 ≤10%（阈值写进报告，`--check` 式可机读）。
- 确定性：同输入同字节（无时间戳；报告 `sort_keys=True`）；两次跑必须完全一致。

不做什么
--------
不改 `core.gate_profile` 任何行为（本件只调用 `load`/`report`）；不跑全量 verify；
不改 README/站点/scripts/nf.py。若发现引擎 bug：先报告，最小修需单列 diff。

用法
----
    python scripts/gate_defect_bench.py                 # 跑台架 + 写报告 + 终端摘要
    python scripts/gate_defect_bench.py --json          # 只打机器面（仍写报告）
    python scripts/gate_defect_bench.py --no-write      # 只算不写
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, gate_profile as gp  # noqa: E402

SCHEMA = "nf-gate-defect-bench/1"
REPORT_REL = "results/bench/gate_defect_report.json"
MIN_DETECTION_RATE = 0.9
MAX_FP_RATE = 0.1
NEGATIVES_PER_CLASS = 8
CLEANS_PER_CLASS = 2
CLEAN_SUFFIX = "\n\n控制组：本段为台架正例控制文本，未注入任何缺陷。\n"

PROFILES = {
    "techdoc-strict": "community/技术文档域包/gate_profiles/techdoc-strict.json",
    "regulatory-strict": "community/合规与监管域包/gate_profiles/regulatory-strict.json",
}
FIXTURES = {
    "techdoc-strict": "desktop/tests/fixtures/gate_defects/techdoc_base.md",
    "regulatory-strict": "desktop/tests/fixtures/gate_defects/regulatory_base.md",
}


# ---------------------------------------------------------------- 注入算子
def _r(old: str, new: str) -> list:
    return [("replace", old, new)]


def _ra(old: str, new: str) -> list:
    return [("replace_all", old, new)]


def _rm(pairs: list) -> list:
    return [("replace_map", list(pairs))]


def _drop(marker: str) -> list:
    return [("drop_line", marker)]


def _drop_all(marker: str) -> list:
    return [("drop_lines_all", marker)]


def _droptab(marker: str) -> list:
    return [("drop_table", marker)]


def _droprow(marker: str, row: str) -> list:
    return [("drop_table_row", marker, row)]


def _droprows(marker: str) -> list:
    return [("drop_table_rows", marker)]


def _approw(marker: str, row: str) -> list:
    return [("append_table_row", marker, row)]


def _app(suffix: str) -> list:
    return [("append", suffix)]


class BenchError(RuntimeError):
    """注入算子前提不成立（锚点没找到/没产生变化）——台架必须报错，不许静默空转。"""


def _lines(text: str) -> list:
    return text.splitlines()


def _join(lines: list, had_trailing_newline: bool) -> str:
    out = "\n".join(lines)
    return out + "\n" if had_trailing_newline else out


def _table_span(lines: list, marker: str) -> tuple:
    """→ (header_idx, end_idx)；表格块 = 连续以 `|` 开头的行，end 为开区间。"""
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("|") and marker in ln:
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            return i, j
    raise BenchError("找不到表格：%r" % marker)


def _apply(text: str, ops: list) -> str:
    """按算子序列注入 → 新文本；任一算子没生效即抛 BenchError（fail-closed）。"""
    had_nl = text.endswith("\n")
    for op in ops:
        kind = op[0]
        before = text
        if kind == "append":
            text = text + op[1]
        elif kind in ("replace", "replace_all"):
            old, new = op[1], op[2]
            if old not in text:
                raise BenchError("replace 锚点不存在：%r" % old)
            text = text.replace(old, new) if kind == "replace_all" \
                else text.replace(old, new, 1)
        elif kind == "replace_map":
            for old, new in op[1]:
                if old not in text:
                    raise BenchError("replace_map 锚点不存在：%r" % old)
                text = text.replace(old, new)
        else:
            lines = _lines(text)
            if kind == "drop_line":
                hit = next((i for i, ln in enumerate(lines) if op[1] in ln), None)
                if hit is None:
                    raise BenchError("drop_line 锚点不存在：%r" % op[1])
                del lines[hit]
            elif kind == "drop_lines_all":
                kept = [ln for ln in lines if op[1] not in ln]
                if len(kept) == len(lines):
                    raise BenchError("drop_lines_all 锚点不存在：%r" % op[1])
                lines = kept
            elif kind == "drop_table":
                i, j = _table_span(lines, op[1])
                del lines[i:j]
            elif kind in ("drop_table_row", "append_table_row",
                          "drop_table_rows"):
                i, j = _table_span(lines, op[1])
                if kind == "drop_table_rows":
                    # 保留表头与分隔行，删掉全部数据行（判 min_rows 下限）
                    if j - i <= 2:
                        raise BenchError("表格没有数据行可删：%r" % op[1])
                    del lines[i + 2:j]
                elif kind == "drop_table_row":
                    hit = next((k for k in range(i + 2, j) if op[2] in lines[k]), None)
                    if hit is None:
                        raise BenchError("表格行不存在：%r" % op[2])
                    del lines[hit]
                else:  # append_table_row
                    lines.insert(j, op[2])
            else:
                raise BenchError("未知算子：%r" % (kind,))
            text = _join(lines, had_nl)
        if text == before:
            raise BenchError("算子未产生变化：%r" % (kind,))
    return text


# ---------------------------------------------------------------- 缺陷类目（10 类 × 8 负例）
#: 每类在每 profile 下声明：mode / targets（该类判据的 clause_id）/ cases（8 个注入算子序列）。
#: targets 是"该 profile 上该类缺陷应当被哪条 clause 看见"的**声明面**——检出不靠猜。
CLASSES: list[dict[str, Any]] = [
    {
        "id": "cross_domain", "label": "跨域",
        "profiles": {
            "techdoc-strict": {
                "mode": "native",
                "targets": ["DITA-1.3-DOCTYPE-01"],
                "note": "把技术文档声明成其他域的类型（合规/财报告等）——doc_type 白名单应拒收。",
                "cases": [_r("> 文档类型：guide", "> 文档类型：compliance_statement"),
                          _r("> 文档类型：guide", "> 文档类型：marketing_claim"),
                          _r("> 文档类型：guide", "> 文档类型：risk_register"),
                          _r("> 文档类型：guide", "> 文档类型：audit_log_schema"),
                          _r("> 文档类型：guide", "> 文档类型：safety_case"),
                          _r("> 文档类型：guide", "> 文档类型：medical_claim"),
                          _r("> 文档类型：guide", "> 文档类型：finance_report"),
                          _r("> 文档类型：guide", "> 文档类型：privacy_notice")],
            },
            "regulatory-strict": {
                "mode": "native",
                "targets": ["STRUCT-DOCTYPE"],
                "note": "把合规证据包声明成技术文档类型——doc_type 白名单应拒收。",
                "cases": [_r("> 文档类型：compliance_statement", "> 文档类型：guide"),
                          _r("> 文档类型：compliance_statement", "> 文档类型：safety"),
                          _r("> 文档类型：compliance_statement", "> 文档类型：installation"),
                          _r("> 文档类型：compliance_statement", "> 文档类型：operation"),
                          _r("> 文档类型：compliance_statement", "> 文档类型：troubleshooting"),
                          _r("> 文档类型：compliance_statement", "> 文档类型：specification"),
                          _r("> 文档类型：compliance_statement", "> 文档类型：reference"),
                          _r("> 文档类型：compliance_statement", "> 文档类型：unboxing")],
            },
        },
    },
    {
        "id": "missing_section", "label": "缺章节",
        "profiles": {
            "techdoc-strict": {
                "mode": "native",
                "targets": ["GB-19678-STRUCT-01", "GB-19678-GLOSSARY-01",
                            "DITA-1.3-TASK-STEPS-01"],
                "note": "必备章节改名（保留正文）或把操作步骤改成非编号段落。",
                "cases": [_r("## 2. 安全", "## 2. 防护须知"),
                          _r("## 3. 开箱", "## 3. 拆包流程"),
                          _r("## 4. 安装", "## 4. 装配"),
                          _r("## 5. 操作", "## 5. 运行"),
                          _r("## 6. 故障", "## 6. 异常"),
                          _r("## 7. 规格", "## 7. 参数"),
                          _r("## 1. 术语表", "## 1. 名词对照"),
                          _r("1. 确认设备处于停止状态且面板无报警后，切换运行模式。\n"
                             "2. 将目标温度设为 25 ℃，等待读数稳定在 ±1 ℃ 后进入下一步。",
                             "确认设备处于停止状态且面板无报警后，切换运行模式。\n"
                             "将目标温度设为 25 ℃，等待读数稳定在 ±1 ℃ 后进入下一步。")],
            },
            "regulatory-strict": {
                "mode": "native",
                "targets": ["EU-AIA-50-TRANSPARENCY-SECTION", "ISO-42001-STATEMENT",
                            "DATA-SOURCE-SECTION", "NIST-AIRMF-RISK-SECTION",
                            "OVERSIGHT-SECTION", "AUDIT-SECTION",
                            "RETENTION-SECTION", "PRIVACY-SECTION"],
                "note": "逐条去掉 8 个必备章节标题里的关键词（正文保留）。",
                "cases": [_r("## 2. AI 披露与标识", "## 2. 人工智能披露与标识"),
                          _rm([("## 1. 合规声明", "## 1. 合规承诺"),
                               ("（样例：内容合规声明）", "（样例：内容合规）")]),
                          _r("## 3. 数据来源与授权", "## 3. 数据出处与授权"),
                          _r("## 4. 风险分级与人类监督", "## 4. 风险档位与人类监督"),
                          _r("## 4. 风险分级与人类监督", "## 4. 风险分级与监督主体"),
                          _r("## 5. 审计日志与保留期", "## 5. 日志与保留期"),
                          _r("## 5. 审计日志与保留期", "## 5. 审计日志与档案期"),
                          _r("## 6. 敏感信息", "## 6. 个人信息")],
            },
        },
    },
    {
        "id": "term_inconsistency", "label": "术语不一致",
        "profiles": {
            "techdoc-strict": {
                "mode": "native",
                "targets": ["GB-19678-TERM-01", "GB-19678-TERM-02"],
                "note": "正文首次使用术语表外的术语（未就地定义），或规范术语与别名并存。",
                "cases": [_app("\n\n本设备的校准周期由年度维护计划确定。\n"),
                          _app("\n\n本设备的老化工序在出厂前完成。\n"),
                          _app("\n\n涉及设计调整时须填写变更单。\n"),
                          _app("\n\n设备对外提供 API 调用面，供集成方使用。\n"),
                          _app("\n\n本设备的装置清单随包装附件登记。\n"),
                          _app("\n\n故障件返厂前由服务台开具返修号。\n"),
                          _app("\n\n器件贴装以电路板为基板。\n"),
                          _app("\n\n包装取出步骤见拆箱章节。\n")],
            },
            "regulatory-strict": {
                "mode": "native",
                "targets": ["EU-AIA-50-GEN-STATEMENT"],
                "note": "把必填术语「人工智能生成/AI 生成」整体换成模糊同义词。",
                "cases": [_rm([("人工智能生成", "智能生成"), ("AI 生成", "智能生成")]),
                          _rm([("人工智能生成", "机器生成"), ("AI 生成", "机器生成")]),
                          _rm([("人工智能生成", "自动生成"), ("AI 生成", "自动生成")]),
                          _rm([("人工智能生成", "模型输出"), ("AI 生成", "模型输出")]),
                          _rm([("人工智能生成", "算法生成"), ("AI 生成", "算法生成")]),
                          _rm([("人工智能生成", "系统生成"), ("AI 生成", "系统生成")]),
                          _rm([("人工智能生成", "程序生成"), ("AI 生成", "程序生成")]),
                          _rm([("人工智能生成", "自动合成"), ("AI 生成", "自动合成")])],
            },
        },
    },
    {
        "id": "heading_punct", "label": "标题标点",
        "profiles": {
            "techdoc-strict": {
                "mode": "native",
                "targets": ["MS-STYLE-HEADING-PUNCT"],
                "note": "8 个二级标题逐条加句末句号（MS Style：标题不带句末标点）。",
                "cases": [_r("## 1. 术语表", "## 1. 术语表。"),
                          _r("## 2. 安全", "## 2. 安全。"),
                          _r("## 3. 开箱", "## 3. 开箱。"),
                          _r("## 4. 安装", "## 4. 安装。"),
                          _r("## 5. 操作", "## 5. 操作。"),
                          _r("## 6. 故障", "## 6. 故障。"),
                          _r("## 7. 规格", "## 7. 规格。"),
                          _r("## 8. 修订记录", "## 8. 修订记录。")],
            },
            "regulatory-strict": {
                "mode": "out_of_scope",
                "targets": [],
                "note": "regulatory-strict 全 profile 无标题风格条款（无 text_rule）——"
                        "该类在本 profile 上无判据面，检出率不计入分母（如实报覆盖缺口）。",
                "cases": [_r("## 1. 合规声明", "## 1. 合规声明。"),
                          _r("## 2. AI 披露与标识", "## 2. AI 披露与标识。"),
                          _r("## 3. 数据来源与授权", "## 3. 数据来源与授权。"),
                          _r("## 4. 风险分级与人类监督", "## 4. 风险分级与人类监督。"),
                          _r("## 5. 审计日志与保留期", "## 5. 审计日志与保留期。"),
                          _r("## 6. 敏感信息", "## 6. 敏感信息。"),
                          _r("## 7. 文档台账", "## 7. 文档台账。"),
                          _r("## 8. 版本变更", "## 8. 版本变更。")],
            },
        },
    },
    {
        "id": "single_space", "label": "单空格",
        "profiles": {
            "techdoc-strict": {
                "mode": "native",
                "targets": ["MS-STYLE-SPACE-01"],
                "note": "正文词间双空格 / 标点前空格（8 处不同位置）。",
                "cases": [_r("本手册给出", "本手册  给出"),
                          _r("断电并等待指示灯熄灭后", "断电  并等待指示灯熄灭后"),
                          _r("检查外包装有无破损", "检查  外包装有无破损"),
                          _r("将设备就位于水平台面", "将设备  就位于水平台面"),
                          _r("不大于 4 Ω", "不大于  4 Ω"),
                          _r("受潮痕迹。", "受潮痕迹 。"),
                          _r("，切换运行模式。", " ，切换运行模式。"),
                          _r("读数稳定在 ±1 ℃ 后", "读数稳定在  ±1 ℃ 后")],
            },
            "regulatory-strict": {
                "mode": "compensated",
                "targets": ["GB-45438-EXPLICIT", "GB-45438-IMPLICIT",
                            "EU-AIA-50-GEN-STATEMENT", "EU-AIA-50-DEEPFAKE",
                            "AUDIT-TRACE-ID", "RETENTION-DURATION",
                            "NIST-AIRMF-RISK-LEVELS"],
                "note": "本 profile 无空格条款（compensated）：把双空格注入必填 token 内部，"
                        "由 token 正则缺席代偿检出——这是**代偿路径**，不是原生空格判据。",
                "cases": [_ra("显式标识", "显 式标识"),
                          _ra("显式标识", "显式标 识"),
                          _ra("隐式标识", "隐 式标识"),
                          _rm([("人工智能生成", "人工智能 生成"),
                               ("AI 生成", "AI  生成")]),
                          _ra("深度合成", "深度合 成"),
                          _ra("trace_id", "trace_ id"),
                          _ra("保留期", "保留 期"),
                          _rm([("不可接受风险", "不可接受 风险"),
                               ("高风险", "高 风险"), ("有限风险", "有限 风险"),
                               ("最小风险", "最小 风险")])],
            },
        },
    },
    {
        "id": "weak_expression", "label": "弱表达",
        "profiles": {
            "techdoc-strict": {
                "mode": "native",
                "targets": ["MS-STYLE-WEAK-01"],
                "note": "8 个不同弱化词注入 8 处正文（warn 级判据，同样计入「门看见了」）。",
                "cases": [_r("读数不大于 4 Ω", "读数大概不大于 4 Ω"),
                          _r("面板无报警后，切换运行模式。", "面板可能无报警后，切换运行模式。"),
                          _r("等待读数稳定在 ±1 ℃ 后", "等待读数也许稳定在 ±1 ℃ 后"),
                          _r("传感器回路异常", "传感器回路似乎异常"),
                          _r("检查外包装有无破损或受潮痕迹。",
                             "检查外包装有无破损，尽量核对随机附件。"),
                          _r("四周预留 100 mm 散热空间。",
                             "四周预留 100 mm 散热空间，较为稳妥。"),
                          _r("仍复发则申请 RMA", "仍复发则差不多申请 RMA"),
                          _r("连接保护接地", "连接保护接地，或许先确认紧固")],
            },
            "regulatory-strict": {
                "mode": "compensated",
                "targets": ["OVERSIGHT-ACTION", "PRIVACY-MINIMIZATION",
                            "RETENTION-CONTACT", "EU-AIA-50-GEN-STATEMENT"],
                "note": "本 profile 无弱表达条款（compensated）：弱化词替换必填动作 token，"
                        "由必填 token 缺席代偿检出（同样明示为代偿路径）。",
                "cases": [_rm([("人工复核", "尽量复核"), ("人工确认", "大概确认")]),
                          _rm([("人工复核", "可能复核"), ("人工确认", "或许确认")]),
                          _rm([("人工复核", "大概复核"), ("人工确认", "尽量确认")]),
                          _rm([("人工复核", "也许复核"), ("人工确认", "似乎确认")]),
                          _rm([("人工智能生成", "大概生成"), ("AI 生成", "可能生成")]),
                          _rm([("去标识化", "大概处理"), ("匿名化", "可能处理")]),
                          _rm([("联系人", "或许对接"), ("数据保护官", "似乎负责人")]),
                          _rm([("人工智能生成", "较为生成"), ("AI 生成", "似乎生成")])],
            },
        },
    },
    {
        "id": "disclosure_missing", "label": "披露缺失",
        "profiles": {
            "techdoc-strict": {
                "mode": "native",
                "targets": ["DITA-1.3-SHORTDESC-01", "DITA-1.3-DOCTYPE-01"],
                "note": "读者告知面缺失：短述（blockquote 简摘）/文档类型声明被删或降级为非引用段。",
                "cases": [_drop("> 文档类型：guide"),
                          _r("文档类型：", "类型："),
                          _r("> 文档类型：guide", "> guide"),
                          _r("文档类型：guide", "文档类型："),
                          _rm([("> 文档类型：guide", "文档类型：guide"),
                               ("> 本手册给出", "本手册给出")]),
                          _rm([("> 文档类型：guide", "文档类型：guide"),
                               ("> 本手册给出示例产品的验收、装配、使用与维护口径，"
                                "供安装与运维人员使用。", "> 简介")]),
                          _rm([("> 文档类型：guide", "- 文档类型：guide"),
                               ("> 本手册给出", "- 本手册给出")]),
                          _rm([("> 文档类型：guide\n", ""),
                               ("> 本手册给出示例产品的验收、装配、使用与维护口径，"
                                "供安装与运维人员使用。\n", "")])],
            },
            "regulatory-strict": {
                "mode": "native",
                "targets": ["EU-AIA-50-TRANSPARENCY-SECTION", "EU-AIA-50-GEN-STATEMENT",
                            "EU-AIA-50-DISCLOSURE-TABLE", "EU-AIA-50-DEEPFAKE",
                            "GB-45438-EXPLICIT", "GB-45438-IMPLICIT",
                            "GB-45438-LABEL-TABLE"],
                "note": "AI 披露/标识面缺失：章节、披露表、深度合成口径、显式/隐式标识逐类摘除。",
                "cases": [_r("## 2. AI 披露与标识", "## 2. 标识与披露"),
                          _droptab("| 披露对象 |"),
                          _droptab("| 标识类型 |"),
                          _drop("深度合成内容（人脸替换、声音克隆）另加显式声明"),
                          _drop_all("| 显式标识 |"),
                          _ra("隐式标识", "隐含标识"),
                          _rm([("人工智能生成", "系统输出"), ("AI 生成", "系统输出")]),
                          _r("| 披露对象 | 披露方式 | 披露文本 |",
                             "| 披露对象 | 披露方式 | 披露内容 |")],
            },
        },
    },
    {
        "id": "audit_fields_missing", "label": "审计字段缺失",
        "profiles": {
            "techdoc-strict": {
                "mode": "native",
                "targets": ["GB-19678-REVISION-01", "GB-19678-REVISION-02"],
                "note": "修订记录（审计追溯）表缺列/缺行/版本或日期格式坏。",
                "cases": [_r("| 版本 | 日期 | 变更 |", "| 修订号 | 日期 | 变更 |"),
                          _r("| 版本 | 日期 | 变更 |", "| 版本 | 日期 |"),
                          _r("| 版本 | 日期 | 变更 |", "| 版本 | 时间 | 变更 |"),
                          _r("| v1.0 | 2026-10-01 | 首版发布 |",
                             "| 初版 | 2026-10-01 | 首版发布 |"),
                          _r("| v1.1 | 2026-10-20 | 补充规格参数与故障处置表 |",
                             "| v1.0 | 2026-10-20 | 补充规格参数与故障处置表 |"),
                          _r("2026-10-20 | 补充规格参数", "2026/10/20 | 补充规格参数"),
                          _droprows("| 版本 | 日期 | 变更 |"),
                          _approw("| 版本 | 日期 | 变更 |", "| v1.0 | 2026-10-21 | 重复登记 |")],
            },
            "regulatory-strict": {
                "mode": "native",
                "targets": ["AUDIT-SECTION", "AUDIT-FIELD-TABLE", "AUDIT-TRACE-ID"],
                "note": "审计日志面缺失：章节/字段表/必填列/trace_id 逐类摘除。",
                "cases": [_r("## 5. 审计日志与保留期", "## 5. 日志与保留期"),
                          _droptab("| 字段 | 类型 | 必填 | 说明 |"),
                          [("drop_table_row", "| 字段 | 类型 | 必填 | 说明 |", "| actor_id |"),
                           ("drop_table_row", "| 字段 | 类型 | 必填 | 说明 |", "| content_ref |")],
                          _r("| 字段 | 类型 | 必填 | 说明 |", "| 名称 | 类型 | 必填 | 说明 |"),
                          _r("| 字段 | 类型 | 必填 | 说明 |", "| 字段 | 类型 | 说明 |"),
                          _ra("trace_id", "traceid"),
                          [("drop_table_row", "| 字段 | 类型 | 必填 | 说明 |", "| trace_id |"),
                           ("replace_all", "+ trace_id", "+ 链路编号")],
                          _drop("## 5. 审计日志与保留期")],
            },
        },
    },
    {
        "id": "risk_tier", "label": "风险档位",
        "profiles": {
            "techdoc-strict": {
                "mode": "native",
                "targets": ["GB-19678-SAFETY-01"],
                "note": "techdoc profile 无风险档位规则 ⇒ 映射到安全提示档位（warn）："
                        "逐例整体摘除 警告/注意/危险 三档提示词。",
                "cases": [_rm([("警告", "提醒"), ("注意", "留意"), ("危险", "风险")]),
                          _rm([("警告", "告知"), ("注意", "关注"), ("危险", "隐患")]),
                          _rm([("警告", "提示"), ("注意", "留神"), ("危险", "风险")]),
                          _rm([("警告", "告示"), ("注意", "留意"), ("危险", "隐患")]),
                          _rm([("警告", "提醒"), ("注意", "关注"), ("危险", "隐患")]),
                          _rm([("警告", "提示"), ("注意", "留意"), ("危险", "风险")]),
                          _rm([("警告", "告知"), ("注意", "留神"), ("危险", "隐患")]),
                          _rm([("警告", "告示"), ("注意", "关注"), ("危险", "风险")])],
            },
            "regulatory-strict": {
                "mode": "native",
                "targets": ["NIST-AIRMF-RISK-SECTION", "NIST-AIRMF-RISK-TABLE",
                            "NIST-AIRMF-RISK-LEVELS"],
                "note": "风险分级面：章节/四档词表/风险等级表逐类破坏。",
                "cases": [_r("## 4. 风险分级与人类监督", "## 4. 风险档位与人类监督"),
                          _droptab("| 风险等级 |"),
                          _droprow("| 风险等级 |", "| 有限风险 |"),
                          _r("| 风险等级 | 风险描述 | 处置措施 |",
                             "| 风险等级 | 风险描述 | 响应措施 |"),
                          _r("| 风险等级 | 风险描述 | 处置措施 |",
                             "| 风险类别 | 风险描述 | 处置措施 |"),
                          _rm([("不可接受风险", "不可接受影响"), ("高风险", "高影响"),
                               ("有限风险", "有限影响"), ("最小风险", "最小影响")]),
                          [("drop_line", "档位只用不可接受风险、高风险、有限风险、最小风险四档"),
                           ("replace_map", [("高风险", "高影响"), ("有限风险", "有限影响")])],
                          [("replace", "## 4. 风险分级与人类监督", "## 4. 风险划分与人类监督"),
                           ("replace", "| 风险等级 |", "| 风险划分等级 |")]],
            },
        },
    },
    {
        "id": "version_no_rollback", "label": "版本不回退",
        "profiles": {
            "techdoc-strict": {
                "mode": "native",
                "targets": ["GB-19678-REVISION-01"],
                "note": "修订记录版本列回退/相等/格式坏/缺列。",
                "cases": [_r("| v1.1 | 2026-10-20 | 补充规格参数与故障处置表 |",
                             "| v1.0 | 2026-10-20 | 补充规格参数与故障处置表 |"),
                          _r("| v1.0 | 2026-10-01 | 首版发布 |",
                             "| v1.1 | 2026-10-01 | 首版发布 |"),
                          _approw("| 版本 | 日期 | 变更 |", "| v0.9 | 2026-10-21 | 回退实验 |"),
                          _r("| v1.0 | 2026-10-01 | 首版发布 |",
                             "| v2.0 | 2026-10-01 | 首版发布 |"),
                          _r("| 版本 | 日期 | 变更 |", "| 修订号 | 日期 | 变更 |"),
                          _r("| 版本 | 日期 | 变更 |", "| 版本 | 时间 | 变更 |"),
                          _droptab("| 版本 | 日期 | 变更 |"),
                          _r("| v1.1 | 2026-10-20 |", "| 1.1版 | 2026-10-20 |")],
            },
            "regulatory-strict": {
                "mode": "native",
                "targets": ["VERSION-TRACE", "VERSION-CHANGE-TABLE"],
                "note": "版本变更表版本列回退/相等/格式坏/缺列。",
                "cases": [_r("| 1.1.0 | 2026-10-26 | 补审计日志字段、保留期与联系人、文档台账 |",
                             "| 1.0.0 | 2026-10-26 | 补审计日志字段、保留期与联系人、文档台账 |"),
                          _r("| 1.0.0 | 2026-10-20 | 初版：披露、标识、来源、风险四类证据 |",
                             "| 2.0.0 | 2026-10-20 | 初版：披露、标识、来源、风险四类证据 |"),
                          _approw("| 版本 | 日期 | 变更 |", "| 0.9.0 | 2026-10-27 | 回退实验 |"),
                          _r("| 版本 | 日期 | 变更 |", "| 修订号 | 日期 | 变更 |"),
                          _r("| 版本 | 日期 | 变更 |", "| 版本 | 日期 |"),
                          _droptab("| 版本 | 日期 | 变更 |"),
                          _r("| 1.1.0 | 2026-10-26 |", "| 1.1.0 | 2026/10/26 |"),
                          _approw("| 版本 | 日期 | 变更 |", "| 1.0.5 | 2026-10-27 | 回退补丁 |")],
            },
        },
    },
]


# ---------------------------------------------------------------- 执行/统计
def _sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def _report_hits(profile: dict, text: str, cache: dict) -> tuple:
    """→ (命中 clause_id 集合, report 摘要)；同文本缓存（清洁件/重复注入不重复跑）。"""
    key = (str(profile.get("profile_id")), text)
    if key not in cache:
        doc = gp.report(text, profile)
        hits = frozenset(str(row["clause_id"]) for row in doc["clauses"] if not row["ok"])
        cache[key] = (hits, {"ok": bool(doc["ok"]),
                             "fail": int(doc["summary"]["fail"]),
                             "warn": int(doc["summary"]["warn"])})
    return cache[key]


def run_bench() -> dict:
    """跑完整台架 → 报告 dict（纯函数；无时间戳，同输入同字节）。"""
    cache: dict = {}
    invalid: list = []
    profiles_out: dict = {}
    grand = {"negatives": 0, "detected": 0, "clean_cases": 0, "fail_flagged_clean": 0,
             "classes_in_scope": 0}
    for pid, rel in PROFILES.items():
        profile = gp.load(str(ROOT / rel))
        base = (ROOT / FIXTURES[pid]).read_text(encoding="utf-8")
        rows: list = []
        tot = {"cases": 0, "negatives": 0, "detected": 0, "missed": 0,
               "clean_cases": 0, "false_positives": 0, "fail_flagged_clean": 0,
               "classes_in_scope": 0, "classes_total": 0}
        for spec in CLASSES:
            cfg = spec["profiles"][pid]
            mode = cfg["mode"]
            targets = list(cfg["targets"])
            in_scope = mode != "out_of_scope"
            detected = missed = fp = fail_flagged = 0
            missed_ids: list = []
            fp_ids: list = []
            hit_counts: dict = {}
            for idx in range(NEGATIVES_PER_CLASS):
                cid = "%s-%02d" % (spec["id"], idx + 1)
                try:
                    text = _apply(base, cfg["cases"][idx])
                except BenchError as exc:
                    invalid.append({"profile": pid, "class": spec["id"],
                                    "case": cid, "error": str(exc)})
                    continue
                hits, _rep = _report_hits(profile, text, cache)
                seen = sorted(hits & set(targets))
                for c in seen:
                    hit_counts[c] = hit_counts.get(c, 0) + 1
                if seen:
                    detected += 1
                else:
                    missed += 1
                    missed_ids.append(cid)
            for idx in range(CLEANS_PER_CLASS):
                cid = "%s-clean-%02d" % (spec["id"], idx + 1)
                text = base if idx == 0 else base + CLEAN_SUFFIX
                hits, rep = _report_hits(profile, text, cache)
                if not rep["ok"]:
                    fail_flagged += 1
                if hits & set(targets):
                    fp += 1
                    fp_ids.append(cid)
            rows.append({
                "id": spec["id"], "label": spec["label"], "mode": mode,
                "in_scope": in_scope, "target_clauses": targets,
                "cases": NEGATIVES_PER_CLASS + CLEANS_PER_CLASS,
                "negatives": NEGATIVES_PER_CLASS, "cleans": CLEANS_PER_CLASS,
                "detected": detected, "missed": missed, "false_positives": fp,
                "detection_rate": _rate(detected, NEGATIVES_PER_CLASS) if in_scope else None,
                "fp_rate": _rate(fp, CLEANS_PER_CLASS) if in_scope else None,
                "missed_cases": missed_ids, "false_positive_cases": fp_ids,
                "hit_clauses": dict(sorted(hit_counts.items())),
                "note": cfg["note"],
            })
            tot["cases"] += NEGATIVES_PER_CLASS + CLEANS_PER_CLASS
            tot["clean_cases"] += CLEANS_PER_CLASS
            tot["classes_total"] += 1
            # 清洁件误报是 profile 级属性：out_of_scope 类的正例照样计入（干净件不该被任何类判红）
            tot["fail_flagged_clean"] += fail_flagged
            grand["clean_cases"] += CLEANS_PER_CLASS
            grand["fail_flagged_clean"] += fail_flagged
            if in_scope:
                tot["negatives"] += NEGATIVES_PER_CLASS
                tot["detected"] += detected
                tot["missed"] += missed
                tot["false_positives"] += fp
                tot["classes_in_scope"] += 1
                grand["negatives"] += NEGATIVES_PER_CLASS
                grand["detected"] += detected
                grand["classes_in_scope"] += 1
        tot["detection_rate"] = _rate(tot["detected"], tot["negatives"]) \
            if tot["classes_in_scope"] else None
        tot["fp_rate"] = _rate(tot["fail_flagged_clean"], tot["clean_cases"]) \
            if tot["classes_in_scope"] else None
        profiles_out[pid] = {
            "profile_id": pid,
            "profile_path": rel,
            "profile_sha256": _sha(ROOT / rel),
            "fixture_path": FIXTURES[pid],
            "fixture_sha256": _sha(ROOT / FIXTURES[pid]),
            "classes": rows,
            "totals": tot,
        }
    overall = {
        "negatives": grand["negatives"], "detected": grand["detected"],
        "detection_rate": _rate(grand["detected"], grand["negatives"]),
        "clean_cases": grand["clean_cases"],
        "fail_flagged_clean": grand["fail_flagged_clean"],
        "fp_rate": _rate(grand["fail_flagged_clean"], grand["clean_cases"]),
        "classes_in_scope": grand["classes_in_scope"],
        "classes_total": len(CLASSES) * len(PROFILES),
    }
    verdict_profiles = {}
    reasons: list = []
    for pid, doc in profiles_out.items():
        det = doc["totals"]["detection_rate"]
        fp = doc["totals"]["fp_rate"]
        ok = (det is not None and det >= MIN_DETECTION_RATE
              and fp is not None and fp <= MAX_FP_RATE)
        verdict_profiles[pid] = bool(ok)
        if det is None or det < MIN_DETECTION_RATE:
            reasons.append("%s 检出率不足：%r < %.2f" % (pid, det, MIN_DETECTION_RATE))
        if fp is None or fp > MAX_FP_RATE:
            reasons.append("%s 误报率超限：%r > %.2f" % (pid, fp, MAX_FP_RATE))
    verdict_ok = bool(all(verdict_profiles.values())) and not invalid
    if invalid:
        reasons.append("注入算子失效 %d 例（台架自身不可信）" % len(invalid))
    return {
        "schema": SCHEMA,
        "bench": "gate profile defect injection",
        "thresholds": {"min_detection_rate": MIN_DETECTION_RATE,
                       "max_fp_rate": MAX_FP_RATE},
        "defect_classes": [{"id": c["id"], "label": c["label"]} for c in CLASSES],
        "profiles": profiles_out,
        "overall": overall,
        "invalid_cases": invalid,
        "verdict": {"ok": verdict_ok, "profiles": verdict_profiles, "reasons": reasons},
    }


def dumps(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _summary(report: dict) -> str:
    lines = ["== gate profile 缺陷注入台 ==",
             "  10 类 × (8 负 + 2 正) × %d profile；阈值：检出率 ≥%.0f%% / 误报率 ≤%.0f%%"
             % (len(PROFILES), MIN_DETECTION_RATE * 100, MAX_FP_RATE * 100)]
    for pid, doc in report["profiles"].items():
        t = doc["totals"]
        lines.append("  [%s] 负例 %d/%d 检出（%.1f%%）· 清洁 %d 例误报 %d（%.1f%%）· "
                     "在册类 %d/%d"
                     % (pid, t["detected"], t["negatives"],
                        (t["detection_rate"] or 0) * 100, t["clean_cases"],
                        t["fail_flagged_clean"], (t["fp_rate"] or 0) * 100,
                        t["classes_in_scope"], t["classes_total"]))
        for row in doc["classes"]:
            if not row["in_scope"]:
                lines.append("      · %-16s out_of_scope（%d 负例未检出——覆盖缺口，不计分母）"
                             % (row["id"], row["missed"]))
            elif row["missed"] or row["false_positives"]:
                lines.append("      · %-16s 漏检=%s 误报=%s"
                             % (row["id"], row["missed_cases"], row["false_positive_cases"]))
    ov = report["overall"]
    lines.append("  合计：负例 %d/%d 检出（%.1f%%）· 清洁 %d 例误报 %d（%.1f%%）"
                 % (ov["detected"], ov["negatives"], (ov["detection_rate"] or 0) * 100,
                    ov["clean_cases"], ov["fail_flagged_clean"],
                    (ov["fp_rate"] or 0) * 100))
    lines.append("  判定：%s%s" % ("通过" if report["verdict"]["ok"] else "未通过",
                                 "" if report["verdict"]["ok"] else
                                 "（%s）" % "；".join(report["verdict"]["reasons"])))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="gate profile 缺陷注入测量台（只调用 core.gate_profile，不改其行为）")
    ap.add_argument("--out", default=REPORT_REL, help="报告落点（默认 %s）" % REPORT_REL)
    ap.add_argument("--json", action="store_true", help="打印机器面报告")
    ap.add_argument("--no-write", action="store_true", help="只计算，不写盘")
    args = ap.parse_args(argv)

    report = run_bench()
    text = dumps(report)
    if not args.no_write:
        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write.write_text(out, text)
    print(text if args.json else _summary(report))
    return 0 if report["verdict"]["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
