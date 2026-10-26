#!/usr/bin/env python3
"""门禁的**原生结构面** check（check1 / check3）——纯文件在场与文本落点判定。

为什么单独成层（2026-10-15）
----------------------------
`core/gate_engine.py` 触及本仓 `code_metrics` 的**新文件模块行数上限 800** 与「既有件冻结值」
两道闸门。把这两条**纯结构、无外部依赖**的判定搬出来，既让引擎回到限内，也让
「结构面」与「编排面」职责分开：

- 本模块只做「逐条对照 verify.sh 的路径清单与不变式字样」；
- 文案/banner 仍从 `verify.sh` 现读（`gate_labels`），**不手抄**——手抄必然漂移
  （第一版手抄时 check27 等几条立刻与真源不符，被差分测试当场抓出）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


PASS, FAIL = "PASS", "FAIL"

#: 官方核心 13 件（`07 §1` 清单，与 verify.sh 的 core13 逐条对应）。
CORE13: tuple = (
    "04_模块库/世界类/M08_环境状态.md",
    "04_模块库/事件类/M06_流程状态机.md",
    "04_模块库/事件类/M12_模板检索库.md",
    "04_模块库/事件类/M13_实体交互.md",
    "04_模块库/事件类/M20_知识条目库.md",
    "04_模块库/事件类/M22_事件编排.md",
    "04_模块库/技术文档类/M90_结构装配.md",
    "04_模块库/通用类/M00_数据槽总线.md",
    "04_模块库/通用类/M10_节拍推进.md",
    "04_模块库/通用类/M23_可见性边界.md",
    "04_模块库/通用类/M24_规则组合.md",
    "04_模块库/通用类/M50_调度器.md",
    "04_模块库/通用类/M80_输出质检门.md",
)

def check1(verify_text: str, root: Path) -> list[Any]:
    """check1：官方核心目录结构。逐条对照 verify.sh:101-134 的路径清单与文案。"""
    out: list[Any] = []
    err = 0
    for f in ("01_核心协议.md", "02_联动注册表.md", "06_Agent执行协议.md",
              "07_官方核心出厂与社区预设导航.md", "README.md", "LICENSE"):
        if not (root / f).is_file():
            out.append((FAIL, "根级缺失: {}".format(f))); err = 1
    for p in ("P00_通用文档生成管线.md", "P01_标准管线.md", "P90_结构装配管线.md"):
        if not (root / "03_管线库" / p).is_file():
            out.append((FAIL, "03 缺官方管线文件: {}".format(p))); err = 1
    for f in CORE13:
        if not (root / f).is_file():
            out.append((FAIL, "04 缺核心模块: {}".format(f))); err = 1
    if not (root / "05_资产库" / "README.md").is_file():
        out.append((FAIL, "05_资产库缺总 README")); err = 1
    if not (root / "05_资产库" / "用户自定义").is_dir():
        out.append((FAIL, "05 缺 用户自定义 扩增槽目录")); err = 1
    if err == 0:
        out.append((PASS, "根级 6 件；03 官方三管线（P00/P01/P90）；"
                          "04 核心 13 件逐件在场；05=README+用户自定义"))
    return out


def check3(verify_text: str, root: Path) -> list[Any]:
    """check3：五条不变式落点。对照 verify.sh:161-173。"""
    out: list[Any] = []
    doc = (root / "01_核心协议.md").read_text(encoding="utf-8", errors="replace")
    err = 0
    for s in ("三正交分离", "核心固定", "通信契约", "数据隔离", "真相唯一"):
        if s not in doc:
            out.append((FAIL, "01 §5 缺不变式: {}".format(s))); err = 1
    for q in ("asset_get", "asset_query", "asset_match", "asset_roll", "asset_register"):
        if q not in doc:
            out.append((FAIL, "I4 五接口缺: {}".format(q))); err = 1
    if not ("M50" in doc and "M80" in doc):
        out.append((FAIL, "I2 核心固定缺 M50/M80 字样")); err = 1
    if err == 0:
        out.append((PASS, "I1-I5 五条不变式 + I4 五接口 + I2 核心锚点全部落于 01 §5"))
    return out


__all__ = ["CORE13", "check1", "check3"]

