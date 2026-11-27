//! `asset_contract` 的**代码面**：AST 规范符合性 + **可证**空指针 + 测试件在场。
//!
//! 口径见真源 `asset_contract.py` 代码面那段。三处要点：
//!
//! 1. **`_walk_scope` 不进入嵌套函数/lambda/类**（各自另算，避免跨作用域误判）——本线用
//!    Visitor 在这几类节点上**提前返回**实现同一语义。
//! 2. `_derefs` 的行号顺序：真源用 `ast.iter_child_nodes` + 栈（LIFO）⇒ 子节点**逆序**；
//!    但其结果最终进 `sorted(out, key=lineno)` + 去重，故**文档序与 LIFO 序等价**。
//!    本线用文档序，理由写在这里而不是"反正一样"。
//! 3. `_none_deref` 与 `_denied_calls` 的结果顺序**可观察**（前者稳定排序 + 去重，
//!    后者直接进 issues）⇒ 前者取 BFS 序函数种子、后者取 BFS 序调用序列。

use crate::pyast::{d_arguments, d_comprehension, d_keyword, d_match_case, d_withitem};
use rustpython_ast as past;
use rustpython_ast::Ranged;
use rustpython_ast::Visitor as _;
use std::collections::BTreeSet;

mod part1;
mod part2;
mod part3;

pub(crate) use part1::*;
pub(crate) use part2::*;
pub(crate) use part3::*;
