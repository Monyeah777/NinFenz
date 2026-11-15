//! 文件系统纪律：POSIX 相对路径、符号链接拒绝、确定性遍历、tree 摘要、pack items。
//! 路径安全判据（绝对路径 / .. / 盘符 / UNC / NUL / 保留设备名 / 控制字符 / 反斜杠）。

use crate::canonical::{canonical_bytes, sha256_hex};
use crate::error::CoreError;
use crate::limits::limits;
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};

const WIN_FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
const WIN_FILE_ATTRIBUTE_DEVICE: u32 = 0x40;

#[derive(Clone, Debug)]
pub struct FileEntry {
    pub rel: String,
    pub abs: PathBuf,
    pub size: u64,
}

pub fn io_error(ctx: &str, path: &Path, e: std::io::Error) -> CoreError {
    CoreError::new("NF-E-004")
        .with_message(format!("{ctx}: {} ({e})", path.display()))
        .with_exit(2)
}

pub fn path_unsafe(rel: &str, message: impl Into<String>) -> CoreError {
    CoreError::new("NF-PCK-003")
        .with_message(message.into())
        .at(rel.to_string())
}

fn is_reserved_device(comp: &str) -> bool {
    let base = comp.split('.').next().unwrap_or(comp).trim_end_matches(' ');
    let upper = base.to_ascii_uppercase();
    if matches!(upper.as_str(), "CON" | "PRN" | "AUX" | "NUL") {
        return true;
    }
    if upper.len() == 4 {
        let (a, b) = upper.split_at(3);
        if (a == "COM" || a == "LPT") && b.chars().all(|c| c.is_ascii_digit()) {
            return true;
        }
    }
    false
}

/// 校验 POSIX 相对路径（CONTRACT §3）。
pub fn validate_rel_path(rel: &str) -> Result<(), CoreError> {
    if rel.is_empty() {
        return Err(path_unsafe(rel, "路径为空"));
    }
    if rel.contains('\0') {
        return Err(path_unsafe(rel, "路径含 NUL"));
    }
    if rel.starts_with('/') {
        return Err(path_unsafe(rel, "禁止绝对路径"));
    }
    if rel.contains('\\') {
        return Err(path_unsafe(rel, "路径必须用 POSIX 分隔符 /（禁反斜杠）"));
    }
    if rel.ends_with('/') {
        return Err(path_unsafe(rel, "路径不得以 / 结尾"));
    }
    if rel.chars().any(|c| (c as u32) < 0x20 || (c as u32) == 0x7f) {
        return Err(path_unsafe(rel, "路径含控制字符"));
    }
    for comp in rel.split('/') {
        if comp.is_empty() {
            return Err(path_unsafe(rel, "路径含空段"));
        }
        if comp == "." || comp == ".." {
            return Err(path_unsafe(rel, "路径含 . 或 .."));
        }
        if comp.contains(':') {
            return Err(path_unsafe(rel, "路径含盘符/ADS 冒号"));
        }
        if is_reserved_device(comp) {
            return Err(path_unsafe(rel, format!("路径含保留设备名 {comp}")));
        }
    }
    Ok(())
}

fn is_link_like(md: &fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        let attr = md.file_attributes();
        if attr & WIN_FILE_ATTRIBUTE_REPARSE_POINT != 0 {
            return true;
        }
    }
    #[cfg(unix)]
    {
        if md.file_type().is_symlink() {
            return true;
        }
    }
    md.file_type().is_symlink()
}

fn is_special_device(md: &fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if md.file_attributes() & WIN_FILE_ATTRIBUTE_DEVICE != 0 {
            return true;
        }
    }
    false
}

fn join_rel(root: &Path, p: &Path) -> String {
    let rel = p.strip_prefix(root).unwrap_or(p);
    let mut out = String::new();
    for (i, comp) in rel.components().enumerate() {
        if i > 0 {
            out.push('/');
        }
        out.push_str(&comp.as_os_str().to_string_lossy());
    }
    out
}


#[cfg(windows)]
#[repr(C)]
struct ByHandleFileInformation {
    file_attributes: u32,
    creation_time: [u32; 2],
    last_access_time: [u32; 2],
    last_write_time: [u32; 2],
    volume_serial_number: u32,
    file_size_high: u32,
    file_size_low: u32,
    number_of_links: u32,
    file_index_high: u32,
    file_index_low: u32,
}

#[cfg(windows)]
extern "system" {
    fn GetFileInformationByHandle(
        handle: *mut std::ffi::c_void,
        info: *mut ByHandleFileInformation,
    ) -> i32;
}

fn hard_link_count(path: &Path) -> u64 {
    #[cfg(windows)]
    {
        use std::os::windows::io::AsRawHandle;
        let file = match fs::File::open(path) {
            Ok(f) => f,
            Err(_) => return 1,
        };
        let mut info = ByHandleFileInformation {
            file_attributes: 0,
            creation_time: [0; 2],
            last_access_time: [0; 2],
            last_write_time: [0; 2],
            volume_serial_number: 0,
            file_size_high: 0,
            file_size_low: 0,
            number_of_links: 1,
            file_index_high: 0,
            file_index_low: 0,
        };
        let ok = unsafe { GetFileInformationByHandle(file.as_raw_handle() as *mut _, &mut info) };
        if ok == 0 {
            return 1;
        }
        info.number_of_links as u64
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        match fs::metadata(path) {
            Ok(md) => md.nlink(),
            Err(_) => 1,
        }
    }
    #[cfg(not(any(windows, unix)))]
    {
        let _ = path;
        1
    }
}

/// 递归列出普通文件（拒绝 symlink/junction/设备），按 path 码点升序。
pub fn walk_files(root: &Path) -> Result<Vec<FileEntry>, CoreError> {
    let root_md = fs::symlink_metadata(root).map_err(|e| io_error("读取目录失败", root, e))?;
    if is_link_like(&root_md) {
        return Err(CoreError::new("NF-SEC-002")
            .with_message(format!("root 是符号链接：{}", root.display()))
            .with_exit(3));
    }
    if !root_md.is_dir() {
        return Err(CoreError::new("NF-E-004")
            .with_message(format!("root 不是目录：{}", root.display()))
            .with_exit(2));
    }
    let mut entries = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let dir_md = fs::symlink_metadata(&dir).map_err(|e| io_error("读取目录失败", &dir, e))?;
        if is_link_like(&dir_md) {
            return Err(CoreError::new("NF-SEC-002")
                .with_message(format!("拒绝符号链接/目录联接：{}", join_rel(root, &dir)))
                .with_exit(3));
        }
        let mut children: Vec<PathBuf> = Vec::new();
        for ent in fs::read_dir(&dir).map_err(|e| io_error("列目录失败", &dir, e))? {
            let ent = ent.map_err(|e| io_error("列目录失败", &dir, e))?;
            children.push(ent.path());
        }
        children.sort();
        for p in children {
            let md = fs::symlink_metadata(&p).map_err(|e| io_error("读取元数据失败", &p, e))?;
            if is_link_like(&md) {
                return Err(CoreError::new("NF-SEC-002")
                    .with_message(format!("拒绝符号链接/junction：{}", join_rel(root, &p)))
                    .with_exit(3));
            }
            if is_special_device(&md) {
                return Err(CoreError::new("NF-SEC-002")
                    .with_message(format!("拒绝设备文件：{}", join_rel(root, &p)))
                    .with_exit(3));
            }
            if md.is_file() && hard_link_count(&p) > 1 {
                return Err(CoreError::new("NF-SEC-002")
                    .with_message(format!("拒绝硬链：{}", join_rel(root, &p)))
                    .with_exit(3));
            }
            if is_special_device(&md) {
                return Err(CoreError::new("NF-SEC-002")
                    .with_message(format!("拒绝设备文件：{}", join_rel(root, &p)))
                    .with_exit(3));
            }
            if md.is_dir() {
                stack.push(p);
            } else if md.is_file() {
                let rel = join_rel(root, &p);
                validate_rel_path(&rel)?;
                entries.push(FileEntry {
                    rel,
                    abs: p,
                    size: md.len(),
                });
            } else {
                return Err(CoreError::new("NF-SEC-002")
                    .with_message(format!("拒绝特殊文件：{}", join_rel(root, &p)))
                    .with_exit(3));
            }
        }
    }
    entries.sort_by(|a, b| a.rel.cmp(&b.rel));
    Ok(entries)
}

pub fn is_manifest_or_sig(rel: &str) -> bool {
    rel == "nf-pack.json" || rel == "nf-pack.sig" || rel.ends_with(".sig")
}

pub fn infer_kind(rel: &str) -> &'static str {
    let top = rel.split('/').next().unwrap_or(rel);
    match top {
        "protocol" | "protocols" => "protocol",
        "pipeline" | "pipelines" => "pipeline",
        "spec" | "specs" => "md-spec",
        "assets" | "asset" => "assets",
        "template" | "templates" => "template",
        "overlay" | "overlays" => "overlay",
        "docs" | "doc" => "docs",
        _ => "meta",
    }
}

#[derive(Clone, Debug)]
pub struct PackItems {
    pub items: Vec<Value>,
    pub tree: String,
    pub count: u64,
    pub total_bytes: u64,
}

/// 计算 items + tree 摘要。manifest 提供时沿用其同名 item 的 kind。
pub fn pack_items(root: &Path, manifest: Option<&Value>) -> Result<PackItems, CoreError> {
    let entries = walk_files(root)?;
    let l = limits();
    let manifest_items: Vec<(String, String)> = manifest
        .and_then(|m| m.get("items"))
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|i| {
                    Some((
                        i.get("path")?.as_str()?.to_string(),
                        i.get("kind")?.as_str()?.to_string(),
                    ))
                })
                .collect()
        })
        .unwrap_or_default();
    let mut items = Vec::new();
    let mut tree_input = Vec::new();
    let mut total: u64 = 0;
    for e in &entries {
        if is_manifest_or_sig(&e.rel) {
            continue;
        }
        if e.size > l.pack_max_file_bytes {
            return Err(CoreError::new("NF-SEC-003")
                .with_message(format!(
                    "item {} 大小 {} 超过单文件上限 {}",
                    e.rel,
                    e.size,
                    l.pack_max_file_bytes
                ))
                .at(e.rel.clone())
                .with_exit(3));
        }
        total = total.saturating_add(e.size);
        if total > l.pack_max_total_bytes {
            return Err(CoreError::new("NF-SEC-003")
                .with_message(format!("pack 总字节超过上限 {}", l.pack_max_total_bytes))
                .with_exit(3));
        }
        let bytes = fs::read(&e.abs).map_err(|err| io_error("读取 item 失败", &e.abs, err))?;
        let sha = sha256_hex(&bytes);
        let kind = manifest_items
            .iter()
            .find(|(p, _)| p == &e.rel)
            .map(|(_, k)| k.as_str().to_string())
            .unwrap_or_else(|| infer_kind(&e.rel).to_string());
        items.push(json!({
            "path": e.rel,
            "kind": kind,
            "sha256": sha,
            "size": e.size,
        }));
        tree_input.push(json!({
            "path": e.rel,
            "sha256": sha,
            "size": e.size,
        }));
        if items.len() as u64 > l.pack_max_items {
            return Err(CoreError::new("NF-SEC-003")
                .with_message(format!("pack item 数超过上限 {}", l.pack_max_items))
                .with_exit(3));
        }
    }
    let tree = tree_digest(&tree_input)?;
    let count = items.len() as u64;
    Ok(PackItems {
        items,
        tree,
        count,
        total_bytes: total,
    })
}

pub fn tree_digest(tree_input: &[Value]) -> Result<String, CoreError> {
    let array = Value::Array(tree_input.to_vec());
    Ok(sha256_hex(&canonical_bytes(&array)?))
}

pub fn digest_file(path: &Path) -> Result<String, CoreError> {
    let bytes = fs::read(path).map_err(|e| io_error("读取文件失败", path, e))?;
    Ok(sha256_hex(&bytes))
}

pub fn read_bytes(path: &Path, max: u64) -> Result<Vec<u8>, CoreError> {
    let md = fs::metadata(path).map_err(|e| io_error("读取文件失败", path, e))?;
    if !md.is_file() {
        return Err(CoreError::new("NF-E-004")
            .with_message(format!("不是普通文件：{}", path.display()))
            .with_exit(2));
    }
    if md.len() > max {
        return Err(CoreError::new("NF-SEC-003")
            .with_message(format!(
                "文件 {} 大小 {} 超过上限 {max}",
                path.display(),
                md.len()
            ))
            .with_exit(3));
    }
    fs::read(path).map_err(|e| io_error("读取文件失败", path, e))
}

pub fn load_json_file(path: &Path) -> Result<Value, CoreError> {
    let bytes = read_bytes(path, limits().json_max_bytes)?;
    crate::canonical::parse_json_bytes(&bytes)
}

pub fn write_bytes(path: &Path, bytes: &[u8]) -> Result<(), CoreError> {
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).map_err(|e| io_error("创建目录失败", parent, e))?;
        }
    }
    fs::write(path, bytes).map_err(|e| io_error("写文件失败", path, e))
}

pub fn write_json_canonical(path: &Path, value: &Value) -> Result<(), CoreError> {
    let bytes = canonical_bytes(value)?;
    write_bytes(path, &bytes)
}

pub fn ensure_dir(path: &Path) -> Result<(), CoreError> {
    let md = fs::metadata(path).map_err(|e| io_error("out_dir 不存在", path, e))?;
    if !md.is_dir() {
        return Err(CoreError::new("NF-E-004")
            .with_message(format!("out_dir 不是目录：{}", path.display()))
            .with_exit(2));
    }
    Ok(())
}

/// 复制目录树到 dst（保持相对路径）；返回按码点排序的 rel 列表。
pub fn copy_tree(src_root: &Path, dst_root: &Path) -> Result<Vec<String>, CoreError> {
    let entries = walk_files(src_root)?;
    let mut rels = Vec::new();
    for e in &entries {
        let dst = dst_root.join(e.rel.replace('/', std::path::MAIN_SEPARATOR_STR));
        let bytes = fs::read(&e.abs).map_err(|err| io_error("读取文件失败", &e.abs, err))?;
        write_bytes(&dst, &bytes)?;
        rels.push(e.rel.clone());
    }
    Ok(rels)
}

pub fn is_under(root: &Path, child: &Path) -> bool {
    match (root.canonicalize(), child.canonicalize()) {
        (Ok(r), Ok(c)) => c.starts_with(&r),
        _ => false,
    }
}
