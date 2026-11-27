//! CLI 命令实现模块：按命令族拆文件，`main.rs::run_inner` 统一分派。

mod commands_a;
mod commands_b;
mod commands_c;

pub(crate) use commands_a::*;
pub(crate) use commands_b::*;
pub(crate) use commands_c::*;

use crate::require_dir;
use std::path::PathBuf;

/// --root/--json/--out 三参数公共解析（stats / conformance run 共用）。
///
/// 错误文案与被抽出的两处**逐字一致**；root 必填，并就地校验是目录。
pub(crate) struct RootJsonOut {
    pub(crate) root: PathBuf,
    pub(crate) json: bool,
    pub(crate) out: Option<PathBuf>,
}

pub(crate) fn parse_root_json_out(args: &[String]) -> Result<RootJsonOut, String> {
    let mut root: Option<PathBuf> = None;
    let mut json = false;
    let mut out: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            "--json" => json = true,
            "--out" => {
                i += 1;
                out = Some(PathBuf::from(args.get(i).ok_or("--out 后缺路径")?));
            }
            other => return Err(format!("未知参数：{}", other)),
        }
        i += 1;
    }
    let root = root.ok_or("缺 --root（修复指引：传仓库根目录）")?;
    require_dir(&root)?;
    Ok(RootJsonOut { root, json, out })
}

/// --in/--out 公共解析（从子命令后的参数开始：游标从 1 起）。
///
/// missing_in 由调用方传入（两条命令的修复指引不同，保持原文案逐字不变）。
pub(crate) fn parse_in_out(
    args: &[String],
    missing_in: &str,
) -> Result<(PathBuf, Option<PathBuf>), String> {
    let mut input: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--in" => {
                i += 1;
                input = Some(PathBuf::from(args.get(i).ok_or("--in 后缺路径")?));
            }
            "--out" => {
                i += 1;
                out = Some(PathBuf::from(args.get(i).ok_or("--out 后缺路径")?));
            }
            other => return Err(format!("未知参数：{}", other)),
        }
        i += 1;
    }
    let input = input.ok_or_else(|| missing_in.to_string())?;
    Ok((input, out))
}
