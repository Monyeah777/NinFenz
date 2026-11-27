use super::*;

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
