//! 组合包（combo）**证书复算 + 广度证明** —— 与真源 `desktop/src/core/pack_combo.py` 的 `scan` 对账。
//!
//! ## 移植面按消费者界定（有工具）
//!
//! 真源 1,268 行；从入口 `scan` 算调用闭包得 **25 个函数 / 约 602 行**，其中还有三项是**纯缓存**
//! （`_cache_key` / `_inputs_fingerprint` / `_verdict_cached` 的缓存层）——缓存只决定"要不要重算"，
//! **不改结论** ⇒ 不移植。移植的是判据与它依赖的索引层。
//!
//! ## 两处必须对齐的语义
//!
//! 1. **抽样器**：`breadth` 用 `random.Random(seed).sample(...)` 抽三/四/五/六元样，样本**进判据与
//!    stats** ⇒ 逐位复刻 CPython（见 `pyrandom`，已单独判据钉住）。
//! 2. **组合判决的耦合面**：`combine` 会经 `by_id` 拉入**任意第三方包**的模块、经 `pub_index` 拉入
//!    **任意发布方**（事件闭包）⇒ 索引必须**全局**构建一次、全程共用（真源的 `_CACHE` 同理）。
//!    本线把它做成**显式参数**，避免 6,900 次组合各重解析 235 份契约（那会慢到不可用）。
//!
//! `write` 面（`materialize` / `_write_*`）与 `cache_clear` 不移植。

use crate::pyjson::Json;
use crate::jsonx::{obj_get, arr_of, str_list, s_of};
use crate::pyval;
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;
