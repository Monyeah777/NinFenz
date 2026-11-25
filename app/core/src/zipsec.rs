//! zip 解包硬化（zip slip / bomb / symlink / 嵌套 / 重名）与确定性 zip 写入。
//! 固定 mtime 1980-01-01、权限 0644、不写 extra field、entry 按调用方给定顺序（须已按 path 码点升序）。

use crate::error::CoreError;
use crate::fsutil::validate_rel_path;
use crate::limits::limits;
use std::io::{Cursor, Read, Write};
use std::path::Path;
use zip::write::SimpleFileOptions;
use zip::{CompressionMethod, DateTime, ZipArchive, ZipWriter};

#[derive(Clone, Debug)]
pub struct ZipEntry {
    pub name: String,
    pub data: Vec<u8>,
}

fn zip_err(context: &str, e: impl std::fmt::Display) -> CoreError {
    CoreError::new("NF-E-002")
        .with_message(format!("{context}: {e}"))
        .with_exit(3)
}

fn sec(code: &str, message: impl Into<String>) -> CoreError {
    CoreError::new(code).with_message(message.into()).with_exit(3)
}

fn is_nested_zip(data: &[u8]) -> bool {
    data.len() >= 4 && &data[0..4] == b"PK\x03\x04"
}

/// 安全解包到内存。所有上限取自 limits.json。
pub fn read_zip(path: &Path) -> Result<Vec<ZipEntry>, CoreError> {
    let bytes = crate::fsutil::read_bytes(path, limits().zip_max_total_unpacked_bytes)?;
    read_zip_bytes(&bytes)
}

/// 手工扫描中央目录的名字列表（zip crate 打开时会对重名去重，因此重名要在 raw 层拦）。
fn central_dir_names(bytes: &[u8]) -> Option<Vec<String>> {
    let eocd_sig = [0x50, 0x4b, 0x05, 0x06];
    let start = bytes.len().saturating_sub(66_000);
    let eocd = (start..bytes.len().saturating_sub(21))
        .rev()
        .find(|i| bytes[*i..].starts_with(&eocd_sig))?;
    let u16_at = |off: usize| -> Option<u16> {
        bytes
            .get(off..off + 2)
            .map(|s| u16::from_le_bytes([s[0], s[1]]))
    };
    let u32_at = |off: usize| -> Option<u32> {
        bytes
            .get(off..off + 4)
            .map(|s| u32::from_le_bytes([s[0], s[1], s[2], s[3]]))
    };
    let count = u16_at(eocd + 10)? as usize;
    let mut off = u32_at(eocd + 16)? as usize;
    let mut names = Vec::with_capacity(count);
    for _ in 0..count {
        if bytes.get(off..off + 4) != Some(&[0x50, 0x4b, 0x01, 0x02]) {
            return None;
        }
        let name_len = u16_at(off + 28)? as usize;
        let extra_len = u16_at(off + 30)? as usize;
        let comment_len = u16_at(off + 32)? as usize;
        let name = bytes.get(off + 46..off + 46 + name_len)?;
        names.push(String::from_utf8_lossy(name).to_string());
        off = off + 46 + name_len + extra_len + comment_len;
    }
    Some(names)
}

pub fn read_zip_bytes(bytes: &[u8]) -> Result<Vec<ZipEntry>, CoreError> {
    read_zip_bytes_with(bytes, false)
}

/// 证据包专用：允许 artifact/ 下携带 zip 容器（EPUB/DOCX），但不解包、不递归。
pub fn read_zip_bytes_allow_artifact(bytes: &[u8]) -> Result<Vec<ZipEntry>, CoreError> {
    read_zip_bytes_with(bytes, true)
}

fn read_zip_bytes_with(bytes: &[u8], allow_artifact_nested: bool) -> Result<Vec<ZipEntry>, CoreError> {
    let l = limits();
    let cursor = Cursor::new(bytes.to_vec());
    let mut archive = ZipArchive::new(cursor).map_err(|e| zip_err("zip 解析失败", e))?;
    // 重名 entry 拒绝（NF-PCK-003）：zip crate 会静默去重，必须在 raw 中央目录层拦。
    if let Some(names) = central_dir_names(bytes) {
        let mut seen = std::collections::BTreeSet::new();
        for name in &names {
            if !seen.insert(name.clone()) {
                return Err(sec("NF-PCK-003", format!("zip 内 entry 路径重复：{name}")));
            }
        }
    }
    let count = archive.len() as u64;
    if count > l.zip_max_entries {
        return Err(sec(
            "NF-SEC-003",
            format!("zip entry 数 {count} 超过上限 {}", l.zip_max_entries),
        ));
    }
    let mut out: Vec<ZipEntry> = Vec::new();
    let mut total: u64 = 0;
    for i in 0..archive.len() {
        let mut f = archive
            .by_index(i)
            .map_err(|e| zip_err("读取 zip entry 失败", e))?;
        let raw_name = f.name().to_string();
        let enclosed = match f.enclosed_name() {
            Some(p) => p,
            None => {
                return Err(sec(
                    "NF-SEC-001",
                    format!("zip slip：entry 路径越界 {raw_name:?}"),
                ))
            }
        };
        let name = enclosed
            .components()
            .map(|c| c.as_os_str().to_string_lossy().to_string())
            .collect::<Vec<_>>()
            .join("/");
        if f.is_dir() || raw_name.ends_with('/') {
            validate_rel_path(&name).map_err(|_| sec("NF-SEC-001", format!("zip entry 路径不安全：{raw_name:?}")))?;
            continue;
        }
        validate_rel_path(&name).map_err(|_| sec("NF-SEC-001", format!("zip entry 路径不安全：{raw_name:?}")))?;
        if f.encrypted() {
            return Err(sec("NF-E-002", format!("zip entry 加密，拒绝解析：{name}")));
        }
        if let Some(mode) = f.unix_mode() {
            let ft = mode & 0o170000;
            if ft == 0o120000 {
                return Err(sec("NF-SEC-002", format!("zip 含 symlink，拒绝：{name}")));
            }
            if ft != 0 && ft != 0o100000 && ft != 0o040000 {
                return Err(sec(
                    "NF-SEC-002",
                    format!("zip entry 类型不支持（mode={mode:o}）：{name}"),
                ));
            }
        }
        let size = f.size();
        let compressed = f.compressed_size();
        if size > l.zip_max_file_bytes {
            return Err(sec(
                "NF-SEC-003",
                format!("zip entry {name} 解压后 {size} 字节，超过单文件上限 {}", l.zip_max_file_bytes),
            ));
        }
        total = total.saturating_add(size);
        if total > l.zip_max_total_unpacked_bytes {
            return Err(sec(
                "NF-SEC-003",
                format!("zip 解压总量超过上限 {}", l.zip_max_total_unpacked_bytes),
            ));
        }
        if size > 0 {
            if compressed == 0 {
                return Err(sec(
                    "NF-SEC-003",
                    format!("zip bomb：entry {name} 压缩后 0 字节但展开 {size} 字节"),
                ));
            }
            let ratio = (size as u128) / (compressed as u128);
            if ratio > l.zip_max_compression_ratio as u128 {
                return Err(sec(
                    "NF-SEC-003",
                    format!(
                        "zip bomb：entry {name} 压缩比 {ratio}:1 超过上限 {}:1",
                        l.zip_max_compression_ratio
                    ),
                ));
            }
        }
        let mut data = Vec::with_capacity(size.min(1 << 20) as usize);
        f.read_to_end(&mut data)
            .map_err(|e| zip_err(&format!("读取 entry {name} 失败"), e))?;
        if data.len() as u64 != size {
            return Err(sec(
                "NF-SEC-003",
                format!("zip entry {name} 实际字节 {} 与声明 {size} 不符", data.len()),
            ));
        }
        if is_nested_zip(&data) && !(allow_artifact_nested && name.starts_with("artifact/")) {
            // 嵌套层数上限 = 1：容器 zip 本身算第 1 层，里面再套 zip 即第 2 层 → 拒绝。
            return Err(sec(
                "NF-SEC-003",
                format!("zip 嵌套超过上限 {}（entry {name} 是 zip）", l.zip_max_nesting),
            ));
        }
        if out.iter().any(|e| e.name == name) {
            return Err(sec("NF-PCK-003", format!("zip 内 entry 路径重复：{name}")));
        }
        out.push(ZipEntry { name, data });
    }
    Ok(out)
}

fn fixed_options() -> SimpleFileOptions {
    SimpleFileOptions::default()
        .compression_method(CompressionMethod::Deflated)
        .compression_level(Some(6))
        .last_modified_time(DateTime::from_date_and_time(1980, 1, 1, 0, 0, 0).expect("固定 mtime"))
        .unix_permissions(0o644)
        .large_file(false)
}

fn stored_options() -> SimpleFileOptions {
    SimpleFileOptions::default()
        .compression_method(CompressionMethod::Stored)
        .last_modified_time(DateTime::from_date_and_time(1980, 1, 1, 0, 0, 0).expect("固定 mtime"))
        .unix_permissions(0o644)
        .large_file(false)
}

/// 确定性 zip 字节（entry 顺序由调用方按 path 升序给定；重名由调用方先查）。
pub fn zip_bytes(entries: &[(String, Vec<u8>)]) -> Result<Vec<u8>, CoreError> {
    let mut cursor = Cursor::new(Vec::new());
    {
        let mut writer = ZipWriter::new(&mut cursor);
        for (name, data) in entries {
            validate_rel_path(name).map_err(|e| sec("NF-EXP-002", e.message))?;
            let opts = if name == "mimetype" {
                stored_options()
            } else {
                fixed_options()
            };
            writer
                .start_file(name, opts)
                .map_err(|e| zip_err("写 zip entry 失败", e))?;
            writer
                .write_all(data)
                .map_err(|e| zip_err("写 zip entry 失败", e))?;
        }
        writer.finish().map_err(|e| zip_err("收尾 zip 失败", e))?;
    }
    Ok(cursor.into_inner())
}

pub fn write_zip_file(path: &Path, entries: &[(String, Vec<u8>)]) -> Result<Vec<u8>, CoreError> {
    let bytes = zip_bytes(entries)?;
    crate::fsutil::write_bytes(path, &bytes)?;
    Ok(bytes)
}

/// 复核写入结果的确定性属性（测试与自检用）：extra field 必须为空、mtime 固定、权限 0644。
pub fn inspect_zip(
    bytes: &[u8],
) -> Result<Vec<(String, String, Option<u32>, Option<Vec<u8>>)>, CoreError> {
    let cursor = Cursor::new(bytes.to_vec());
    let mut archive = ZipArchive::new(cursor).map_err(|e| zip_err("zip 解析失败", e))?;
    let mut out = Vec::new();
    for i in 0..archive.len() {
        let f = archive.by_index(i).map_err(|e| zip_err("zip 解析失败", e))?;
        let when = match f.last_modified() {
            Some(dt) => format!(
                "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}",
                dt.year(),
                dt.month(),
                dt.day(),
                dt.hour(),
                dt.minute(),
                dt.second()
            ),
            None => "none".to_string(),
        };
        out.push((
            f.name().to_string(),
            when,
            f.unix_mode(),
            f.extra_data().map(|d| d.to_vec()),
        ));
    }
    Ok(out)
}
