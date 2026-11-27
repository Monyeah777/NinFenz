//! 域功能引擎：12 个确定性评测口径 —— 与真源 `desktop/src/core/domain_metrics.py` 对账。
//!
//! 用途：域包的 **T4 面**（可复算产出）。门禁用本模块按声明的族与样例重算报告，再与在盘产物
//! 逐字段比对（见 `output_forms._recompute_entry` / `_gen_domain_report`）。
//!
//! **移植面**：闭包（`evaluate` 起）19 个函数 / 约 280 行 + `load_rows`（生成器要用）。
//! **不移植**：`synthesize` / `rows_to_csv` / `_Rng` —— 那是**确定性夹具生成器**（写面：
//! 造样例 CSV 入库），本线只读，没有任何已移植面会用到它。
//!
//! 口径纪律照搬真源：**确定性**（纯函数 / 无墙钟 / 无随机 / 固定位数四舍五入）+ **不夸口**
//! （算的是样例集上的口径值，不是模型能力声明）。四舍五入走 `pyfloat::round_to`（Python 的
//! 银行家舍入）——用 Rust 的 `round()` 会在正中平局处差一位。
use crate::pyjson::Json;
use crate::pyval;
use std::collections::BTreeMap;
mod part1;
mod part2;
mod part3;
pub(crate) use part1::*;
pub(crate) use part2::*;
pub(crate) use part3::*;

#[cfg(test)]
#[path = "generated/domain_metrics_gen.rs"]
mod domain_metrics_gen;
