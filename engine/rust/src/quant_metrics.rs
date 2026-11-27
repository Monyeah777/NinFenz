//! 量化金融域功能面：绩效报告与指标口径 —— 与真源 `desktop/src/core/quant_metrics.py` 对账。
//!
//! 用途：`量化金融域包` 的 **T4 面**（`performance-report`）。门禁用本模块按净值样例重算报告，
//! 与在盘报告逐字段比对（见 `output_forms._gen_performance_report`）。
//!
//! **移植面**：`performance_report` 闭包 16 个函数 / 约 125 行 + `load_equity_curve`（生成器要用）
//! + 同族的 `information_coefficient` / `turnover` / `drawdown_series` 与图表规格
//! （`vega_equity_curve` / `vega_drawdown` / `mermaid_declaration_flow`）。
//! 后几项虽不在**真语料**的判据路径上，但属同一族公开口径面，**一次移植完整**，不留"可达但缺席"。
//!
//! 口径纪律照搬真源：年化因子显式（252/52/12，**不得默认 365**）、样本标准差 ddof=1、
//! 最大回撤按净值历史峰值、卡尔玛分子分母同区间、换手按单边声明、IC 用截面秩相关。
//! 确定性：纯函数 / 无墙钟 / 无随机 / 固定位数四舍五入（走 `pyfloat::round_to`，银行家舍入）。

use crate::pyjson::Json;
use std::path::Path;

mod part1;
mod part2;
pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
#[path = "generated/quant_metrics_gen.rs"]
mod quant_metrics_gen;
