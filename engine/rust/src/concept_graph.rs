//! 概念图资产体检 —— 与真源 `desktop/src/core/concept_graph.py` 的 `scan` 对账。
//!
//! **移植面按消费者界定**：只移植门禁判据面（`graph_assets` / `load_graph` / `prereqs_of` /
//! `problems` 及其依赖）。真源里 `resolve` / `closure` / `missing` / `frontier` / `violations`
//! / `node_meta` 是给**求值器工具**（`scripts/ai_domain_closure.py`）用的，不是判据面 ⇒ 不移植
//! （不写没人核的代码）。
//!
//! 判据：结构（id 唯一 / 层位 ∈ P00–P80 / 必备 `name` / 边带 provenance 且键在图例中）+
//! 图论（无环 / 前置无悬空 / 无自环）+ 别名唯一 + 分支完备 + 证据强度声明与**覆盖实况**自洽。
//!
//! **一处口径说明**：真源别名键用 `str.casefold()`，本线用 `to_lowercase()`。二者在 ASCII 与
//! CJK 上一致，差异只在 `ß`/终结 sigma 这类特殊折叠（本仓资产无此）——若将来出现，对账会红。

use crate::pyjson::Json;
use crate::pyval;
use std::path::Path;

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
#[path = "generated/concept_graph_gen.rs"]
mod concept_graph_gen;
