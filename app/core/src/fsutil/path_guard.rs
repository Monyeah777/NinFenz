use super::*;

pub(crate) const WIN_FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
pub(crate) const WIN_FILE_ATTRIBUTE_DEVICE: u32 = 0x40;

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

pub(crate) fn is_reserved_device(comp: &str) -> bool {
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

pub(crate) fn is_link_like(md: &fs::Metadata) -> bool {
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

pub(crate) fn is_special_device(md: &fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if md.file_attributes() & WIN_FILE_ATTRIBUTE_DEVICE != 0 {
            return true;
        }
    }
    false
}

pub(crate) fn join_rel(root: &Path, p: &Path) -> String {
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
pub(crate) struct ByHandleFileInformation {
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

pub(crate) fn hard_link_count(path: &Path) -> u64 {
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
