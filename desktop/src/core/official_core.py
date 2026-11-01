#!/usr/bin/env python3
"""官方核心件清单的**唯一实现**（审计 Z1 F6：「官方核心 13 件」曾 4 处硬编码、1 处写成 12）。

事实：官方核心 = **13 件**（04_模块库 保留件；含技术文档件 M90）。
此前三处代码各自硬编码：
- pack_combo.CORE13 = 13（对）
- market_analyzer.OFFICIAL13 = 13（对）
- protocol_wizard.DEFAULT_CORE_MODULES = **12（缺 M90）** ← 唯一错处

现在都从这里取，并由 desktop/tests/test_official_core.py 钉住三件事：
① 本清单 == desktop/src/core/registry.json 的 modules[]（机读真源）；
② 三个消费方逐项一致；
③ 与 Rust 端 output_tables.rs 的 CORE13 转录一致（跨语言夹具，审计修订建议 2）。

顺序口径：沿用消费方既有顺序（M90 置末）——顺序参与了 Rust 转录与快照，改序会无谓地动
生成件；集合语义由测试保证。
"""
from typing import Tuple

#: 官方核心 13 件（顺序与 pack_combo/market_analyzer 既有清单一致；M90 置末）。
CORE_MODULES: Tuple[str, ...] = (
    "M00", "通用:M10", "M08", "M23", "M24", "M50", "M80",
    "事件:M22", "M06", "M12", "M13", "M20", "M90",
)
