//! 仓库可见件集合 —— 镜像真源 `core.repo_face.walk_repo_paths`。
//!
//! 为什么需要（2026-10-22 基线修复的 Rust 侧补齐）：`Path.glob` / 本线 `glob::expand`
//! 会把**构建产物**（`engine/dotnet/**/obj/*.cs`、`engine/rust/target/**`）也算进 `files`
//! 统计，于是同一个提交在「build 过」的树上得到不同计数。真源已用 `walk_repo_paths`
//! 收窄（跳过工具缓存目录 + `.gitignore` 覆盖面）；本模块把同一口径搬到 Rust，
//! 让 `asset_contract.resolve` 的命中面与真源一致。
//!
//! 口径（与真源逐条同源）：
//!   1. 跳过 `SKIP_DIR_NAMES`（VCS / 工具缓存 / 依赖树）；
//!   2. 跳过 `.gitignore` 覆盖面（由 `git ls-files -o -i --exclude-standard` 判定）；
//!   3. 链接工作树里的 `.git` **文件**也不算仓库件。
//!
//! 缓存：**只在一次 `scan` 的作用域内**复用（`begin_scope` / `end_scope`）；直接调用
//! `check_*`（单测夹具）时**现算不缓存**——夹具会在同一路径继续加件，跨调用缓存会把新件吞掉。

use std::collections::HashSet;
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::time::UNIX_EPOCH;

/// 与 `desktop/src/core/repo_face.py::SKIP_DIR_NAMES` **逐项一致**。
const SKIP_DIR_NAMES: &[&str] = &[
    ".git",
    ".rivet",
    "__pycache__",
    ".ruff_cache",
    ".mypy_cache",
    ".pylint.d",
    ".pytest_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
];

static SCOPE: Mutex<Option<(String, Arc<HashSet<String>>)>> = Mutex::new(None);
static IGNORED_CACHE: Mutex<Option<(String, String, Arc<HashSet<String>>)>> = Mutex::new(None);
static ROOT_IGNORED_CACHE: Mutex<Option<(String, String, bool)>> = Mutex::new(None);

fn stat_stamp(path: &Path) -> String {
    match std::fs::metadata(path) {
        Ok(meta) => {
            let nanos = meta
                .modified()
                .ok()
                .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                .map(|d| d.as_nanos())
                .unwrap_or(0);
            format!("{}:{}", nanos, meta.len())
        }
        Err(_) => "0:0".to_string(),
    }
}

fn repo_stamp(root: &Path) -> String {
    format!(
        "{}|{}|{}",
        stat_stamp(&root.join(".gitignore")),
        stat_stamp(&root.join(".git/info/exclude")),
        stat_stamp(&root.join(".git/index"))
    )
}

/// 开始一次判据面：构造并缓存该 root 的可见件集合（`scan` 起始调用）。
pub fn begin_scope(root: &Path) {
    let key = root.to_string_lossy().to_string();
    // 仓内夹具/合成面（root 自身被 gitignore 覆盖，如 `target/test-fixtures/...`）不做收窄：
    // 那里就是「临时树」语义，与真源对非 git 目录的处理一致。
    let set = if root_itself_ignored(root) {
        None
    } else {
        walk(root).map(Arc::new)
    };
    let mut g = SCOPE.lock().unwrap_or_else(|e| e.into_inner());
    *g = set.map(|s| (key, s));
}

/// 结束判据面：清空作用域缓存（`scan` 结束时调用）。
pub fn end_scope() {
    *SCOPE.lock().unwrap_or_else(|e| e.into_inner()) = None;
}

/// 仓库件集合（根相对 posix 路径）；根不可读 → `None`（调用方退回未过滤 glob，与真源一致）。
pub fn visible(root: &Path) -> Option<Arc<HashSet<String>>> {
    if root_itself_ignored(root) {
        return None;
    }
    let key = root.to_string_lossy().to_string();
    {
        let g = SCOPE.lock().unwrap_or_else(|e| e.into_inner());
        if let Some((k, v)) = g.as_ref() {
            if *k == key {
                return Some(Arc::clone(v));
            }
        }
    }
    // 无作用域（直接 check_* 调用）：现算不缓存。
    walk(root).map(Arc::new)
}

/// root 自身是否被 `.gitignore` 覆盖（`git check-ignore -q .`）。
///
/// 用于区分「真实仓库扫描」与「仓内临时夹具」：后者（如 `target/test-fixtures/...`）
/// 必须按临时树语义全量收件，否则夹具件会被自己的构建产物规则滤掉。
fn root_itself_ignored(root: &Path) -> bool {
    let key = root.to_string_lossy().to_string();
    let stamp = repo_stamp(root);
    {
        let g = ROOT_IGNORED_CACHE.lock().unwrap_or_else(|e| e.into_inner());
        if let Some((k, s, v)) = g.as_ref() {
            if k == &key && s == &stamp {
                return *v;
            }
        }
    }
    let got = std::process::Command::new("git")
        .arg("-C")
        .arg(root)
        .args(["check-ignore", "-q", "--", "."])
        .status()
        .map(|s| s.success())
        .unwrap_or(false);
    let mut g = ROOT_IGNORED_CACHE.lock().unwrap_or_else(|e| e.into_inner());
    *g = Some((key, stamp, got));
    got
}

/// `.gitignore` 覆盖面（posix 相对、去尾斜杠）；git 缺席/非 git 检出 → 空集（同真源）。
fn ignored_paths(root: &Path) -> Arc<HashSet<String>> {
    let key = root.to_string_lossy().to_string();
    let stamp = repo_stamp(root);
    {
        let g = IGNORED_CACHE.lock().unwrap_or_else(|e| e.into_inner());
        if let Some((k, s, v)) = g.as_ref() {
            if k == &key && s == &stamp {
                return Arc::clone(v);
            }
        }
    }
    let mut out = HashSet::new();
    let Ok(o) = std::process::Command::new("git")
        .arg("-C")
        .arg(root)
        .args(["ls-files", "-o", "-i", "--exclude-standard"])
        .output()
    else {
        let set = Arc::new(out);
        let mut g = IGNORED_CACHE.lock().unwrap_or_else(|e| e.into_inner());
        *g = Some((key, stamp, Arc::clone(&set)));
        return set;
    };
    if !o.status.success() {
        let set = Arc::new(out);
        let mut g = IGNORED_CACHE.lock().unwrap_or_else(|e| e.into_inner());
        *g = Some((key, stamp, Arc::clone(&set)));
        return set;
    }
    for line in String::from_utf8_lossy(&o.stdout).lines() {
        let s = line.trim().trim_end_matches('/');
        if !s.is_empty() {
            out.insert(s.replace('\\', "/"));
        }
    }
    let set = Arc::new(out);
    let mut g = IGNORED_CACHE.lock().unwrap_or_else(|e| e.into_inner());
    *g = Some((key, stamp, Arc::clone(&set)));
    set
}

/// `rel` 本身或其任一父目录被忽略。
fn is_ignored(rel: &str, ignored: &HashSet<String>) -> bool {
    if ignored.contains(rel) {
        return true;
    }
    let mut p = rel;
    while let Some(i) = p.rfind('/') {
        p = &p[..i];
        if ignored.contains(p) {
            return true;
        }
    }
    false
}

fn walk(root: &Path) -> Option<HashSet<String>> {
    std::fs::read_dir(root).ok()?;
    let ignored = ignored_paths(root);
    let mut out = HashSet::new();
    let mut stack: Vec<(std::path::PathBuf, String)> = vec![(root.to_path_buf(), String::new())];
    while let Some((dir, rel_dir)) = stack.pop() {
        let Ok(rd) = std::fs::read_dir(&dir) else {
            continue;
        };
        for entry in rd.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            let rel = if rel_dir.is_empty() {
                name.clone()
            } else {
                format!("{}/{}", rel_dir, name)
            };
            let Ok(ft) = entry.file_type() else { continue };
            if ft.is_dir() {
                if SKIP_DIR_NAMES.contains(&name.as_str()) || is_ignored(&rel, &ignored) {
                    continue;
                }
                stack.push((entry.path(), rel));
            } else if ft.is_file() {
                // 链接工作树：`.git` 是指针文件，不是仓库件（同真源）。
                if name == ".git" || is_ignored(&rel, &ignored) {
                    continue;
                }
                out.insert(rel);
            }
        }
    }
    Some(out)
}
