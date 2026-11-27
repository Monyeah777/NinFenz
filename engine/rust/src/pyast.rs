//! Python 解析桥（内置 `rustpython-parser`）—— 供 AST 类判据使用。
//!
//! ## 为什么需要它
//!
//! `purity_scan` / `code_metrics` / `asset_contract` 三条真源判据建立在 **Python 语法树**之上
//! （调用图、控制流、规模统计）。手写子集解析器复刻不了 CPython 的 AST 语义，故内置成熟 crate。
//! 实测（2026-10-04）：本机 `x86_64-pc-windows-gnu` 可构建可运行；依赖树**无** `windows-sys` /
//! `windows-link` / `iana-time` / `chrono` / `winapi` ⇒ 不触发 dlltool 陷阱。
//!
//! ## 一处必须小心的地方：**遍历顺序**
//!
//! CPython 的 `ast.walk` 是 **BFS**（`deque` + `extend(iter_child_nodes)`），而 `rustpython-ast`
//! 的 `Visitor` 是 **DFS**。真源把 `raises` / `modules` / `sinks` 的**列表顺序写进消息**，
//! 故顺序可观察、必须复刻。
//!
//! 本线的做法：用 `Visitor` 在**进入节点时**记录 `(深度, 前序序号)`，再按 `(深度, 前序序号)`
//! 排序——**对树而言，这与 BFS 序等价**（同层内按前序即左到右；各层按深度先后）。
//! 深度由「调用 `generic_visit_*` 前后自己压/弹」得到，故 `Visitor` 的 12 个顶层钩子都要覆盖，
//! 漏一个深度就会错。

use rustpython_ast as past;
use rustpython_ast::Ranged;
use rustpython_ast::Visitor as _;
use rustpython_parser::{parse, Mode};
use std::collections::BTreeSet;

mod part1;
mod part2;
mod part3;

pub(crate) use part1::*;
pub(crate) use part3::*;
