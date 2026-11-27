use super::*;

pub const BUILD_SCHEMA: &str = "nf-build-graph/1";
pub(crate) const FIXED_MTIME: &str = "1980-01-01T00:00:00Z";
pub(crate) const FENCE: &str = "```";
pub(crate) const TINY_PNG: &[u8] = &[
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4,
    0x89, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63, 0x60, 0x00, 0x00, 0x00,
    0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc, 0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae,
    0x42, 0x60, 0x82,
];

pub(crate) fn collect_image_srcs(v: &Value, out: &mut BTreeSet<String>) {
    if type_of(v) == "figure" {
        if let Some(src) = v.get("attrs").and_then(|a| a.get("src")).and_then(|s| s.as_str()) {
            let s = src.trim();
            if !s.is_empty() && !s.starts_with("http://") && !s.starts_with("https://") && !s.starts_with("data:") && !s.contains("..") {
                out.insert(s.to_string());
            }
        }
    }
    for c in kids(v) { collect_image_srcs(c, out); }
}

pub(crate) fn is_hash64(s: &str) -> bool {
    s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit())
}

pub(crate) fn hash_of(v: &Value) -> String {
    digest_value(v).unwrap_or_else(|_| sha256_hex(b"invalid"))
}

pub(crate) fn environment(req: &Value) -> Value {
    let font_hashes = req.get("font_hashes").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    json!({
        "core_version": crate::CORE_VERSION,
        "schema_version": "nf-sdir/1+nf-build-graph/1",
        "font_hashes": font_hashes,
        "locale": opt_str(req, "locale").ok().flatten().unwrap_or("und"),
        "fixed_mtime": FIXED_MTIME
    })
}

pub(crate) fn output_specs(req: &Value) -> Result<Vec<Value>, CoreError> {
    let arr = req.get("outputs").and_then(|v| v.as_array()).ok_or_else(|| usage("build-plan 需要 outputs[{path,format}]"))?;
    if arr.is_empty() {
        return Err(usage("outputs 不能为空"));
    }
    let mut out = Vec::new();
    let mut paths: BTreeSet<String> = BTreeSet::new();
    for (i, o) in arr.iter().enumerate() {
        let path = o.get("path").and_then(|v| v.as_str()).ok_or_else(|| usage(format!("outputs[{i}].path 缺失")))?;
        fsutil::validate_rel_path(path).map_err(|_| CoreError::new("NF-EXP-002").with_message(format!("输出路径不安全：{path}")).with_exit(3))?;
        let format = o.get("format").and_then(|v| v.as_str()).ok_or_else(|| usage(format!("outputs[{i}].format 缺失")))?;
        if !matches!(format, "md" | "html" | "json" | "docx" | "epub") {
            return Err(CoreError::new("NF-PROF-001").with_message(format!("build 不支持的输出格式：{format}")).with_exit(1));
        }
        if !paths.insert(path.to_string()) {
            return Err(CoreError::new("NF-BLD-001").with_message(format!("输出路径重复：{path}")).with_exit(1));
        }
        out.push(json!({"path": path, "format": format, "profile": o.get("profile").and_then(|v| v.as_str()).unwrap_or("default")}));
    }
    Ok(out)
}

pub fn plan(req: &Value) -> OpOutcome {
    let sdir = req_value(req, "sdir")?;
    let report = sdir::validate_sdir_value(sdir);
    if report.has_error() {
        return Ok((1, report.to_value()));
    }
    let specs = output_specs(req)?;
    let sd_sha = digest_value(sdir)?;
    let env = environment(req);
    let source_hashes: Vec<Value> = sdir.get("sources").and_then(|v| v.as_array()).map(|a| a.iter().map(|s| s.get("bytes_sha").cloned().unwrap_or(Value::Null)).collect()).unwrap_or_default();
    let plan_sha = match req.get("plan_sha").and_then(|v| v.as_str()) {
        Some(s) if is_hash64(s) => s.to_string(),
        Some(s) => return Err(CoreError::new("NF-BLD-001").with_message(format!("plan_sha 不是 64 位十六进制：{s}")).with_exit(1)),
        None => sd_sha.clone(),
    };
    let input_hashes: Vec<Value> = std::iter::once(Value::String(sd_sha.clone())).chain(source_hashes.iter().cloned()).collect();
    let mut nodes = vec![json!({
        "id": "in:0", "kind": "input", "op": "sdir",
        "input_hashes": [sd_sha],
        "cache_key": hash_of(&json!({"kind": "input", "sdir": sd_sha, "sources": source_hashes}))
    })];
    let mut edges = Vec::new();
    let mut outputs = Vec::new();
    for (i, spec) in specs.iter().enumerate() {
        let format = spec["format"].as_str().unwrap_or("md");
        let path = spec["path"].as_str().unwrap_or("out");
        let profile = spec["profile"].as_str().unwrap_or("default");
        let params = json!({"format": format, "path": path, "profile": profile});
        let cache_key = hash_of(&json!({"op": format!("render:{format}"), "inputs": input_hashes, "params": params, "environment": env}));
        let tid = format!("t:{i}");
        nodes.push(json!({"id": tid, "kind": "transform", "op": format!("render:{format}"), "input_hashes": input_hashes, "cache_key": cache_key, "params": params}));
        edges.push(json!({"from": "in:0", "to": tid, "port": "sdir"}));
        let oid = format!("o:{i}");
        let out_key = hash_of(&json!({"transform": cache_key, "path": path}));
        nodes.push(json!({"id": oid, "kind": "output", "op": "write", "input_hashes": [cache_key], "cache_key": out_key}));
        edges.push(json!({"from": tid, "to": oid, "port": "artifact"}));
        outputs.push(json!({"node": oid, "path": path, "sha256": sha256_hex(b""), "bytes": 0, "format": format}));
    }
    Ok((0, json!({"schema": BUILD_SCHEMA, "plan_sha": plan_sha, "environment": env, "nodes": nodes, "edges": edges, "outputs": outputs})))
}

pub(crate) fn validate_graph(graph: &Value) -> Report {
    let mut report = Report::new("L1", graph, "build-graph", "graph");
    for i in validate("nf-build-graph", graph) {
        report.error("NF-BLD-001", &i.path, &i.message);
    }
    if report.has_error() {
        return report;
    }
    let nodes = graph.get("nodes").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let ids: BTreeSet<String> = nodes.iter().map(|n| n.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string()).collect();
    if ids.len() != nodes.len() {
        report.error("NF-BLD-001", "$.nodes", "节点 id 重复");
    }
    for e in graph.get("edges").and_then(|v| v.as_array()).into_iter().flatten() {
        let from = e.get("from").and_then(|v| v.as_str()).unwrap_or("");
        let to = e.get("to").and_then(|v| v.as_str()).unwrap_or("");
        if !ids.contains(from) || !ids.contains(to) {
            report.error("NF-BLD-001", "$.edges", "边端点不存在");
        }
    }
    let outs = graph.get("outputs").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let paths: BTreeSet<String> = outs.iter().map(|o| o.get("path").and_then(|v| v.as_str()).unwrap_or("").to_string()).collect();
    if paths.len() != outs.len() {
        report.error("NF-BLD-001", "$.outputs", "输出路径重复");
    }
    report
}

pub(crate) fn check_cache(graph: &Value, sdir: &Value) -> Result<(), CoreError> {
    let env = graph.get("environment").cloned().unwrap_or(Value::Null);
    let sd_sha = digest_value(sdir)?;
    let source_hashes: Vec<Value> = sdir.get("sources").and_then(|v| v.as_array()).map(|a| a.iter().map(|s| s.get("bytes_sha").cloned().unwrap_or(Value::Null)).collect()).unwrap_or_default();
    let input_hashes: Vec<Value> = std::iter::once(Value::String(sd_sha)).chain(source_hashes.into_iter()).collect();
    for n in graph.get("nodes").and_then(|v| v.as_array()).into_iter().flatten() {
        if n.get("kind").and_then(|v| v.as_str()) != Some("transform") {
            continue;
        }
        let op = n.get("op").and_then(|v| v.as_str()).unwrap_or("");
        let params = n.get("params").cloned().unwrap_or_else(|| json!({}));
        let calc = hash_of(&json!({"op": op, "inputs": input_hashes, "params": params, "environment": env}));
        if calc != n.get("cache_key").and_then(|v| v.as_str()).unwrap_or("") {
            return Err(CoreError::new("NF-BLD-002").with_message("构建图 cache_key 与当前 SDIR/环境不匹配（缓存污染或手改图）").with_exit(3));
        }
    }
    Ok(())
}

pub(crate) fn atomic_write(path: &Path, bytes: &[u8]) -> Result<(), CoreError> {
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent).map_err(|e| fsutil::io_error("建输出目录失败", parent, e))?;
        }
    }
    let tmp = path.with_file_name(format!(".{}.nf-tmp-{}", path.file_name().and_then(|s| s.to_str()).unwrap_or("out"), sha256_hex(bytes)));
    std::fs::write(&tmp, bytes).map_err(|e| fsutil::io_error("写临时产物失败", &tmp, e))?;
    if path.exists() {
        std::fs::remove_file(path).map_err(|e| fsutil::io_error("替换旧产物失败", path, e))?;
    }
    std::fs::rename(&tmp, path).map_err(|e| fsutil::io_error("提交产物失败", path, e))?;
    Ok(())
}

pub(crate) fn esc_html(s: &str) -> String {
    s.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;").replace('"', "&quot;")
}

pub(crate) fn esc_xml(s: &str) -> String {
    esc_html(s).replace('\'', "&apos;")
}

pub(crate) fn heading_level(b: &Value) -> usize {
    b.get("attrs").and_then(|a| a.get("level")).and_then(|v| v.as_u64()).unwrap_or(2) as usize
}
pub(crate) fn text_of(b: &Value) -> &str { b.get("text").and_then(|v| v.as_str()).unwrap_or("") }
pub(crate) fn id_of(b: &Value) -> &str { b.get("id").and_then(|v| v.as_str()).unwrap_or("") }
pub(crate) fn type_of(b: &Value) -> &str { b.get("type").and_then(|v| v.as_str()).unwrap_or("") }
pub(crate) fn kids(b: &Value) -> &[Value] { b.get("children").and_then(|v| v.as_array()).map(|a| a.as_slice()).unwrap_or(&[]) }

pub(crate) fn md_node(b: &Value, out: &mut String) {
    match type_of(b) {
        "document" => { for c in kids(b) { md_node(c, out); } }
        "heading" => {
            out.push_str(&"#".repeat(heading_level(b).clamp(1, 6)));
            out.push(' ');
            out.push_str(text_of(b));
            out.push_str("\n\n");
            for c in kids(b) { md_node(c, out); }
        }
        "paragraph" => { out.push_str(text_of(b)); out.push_str("\n\n"); }
        "list" => {
            let ordered = b.get("attrs").and_then(|a| a.get("ordered")).and_then(|v| v.as_bool()).unwrap_or(false);
            for (i, c) in kids(b).iter().enumerate() {
                if ordered { out.push_str(&format!("{}. ", i + 1)); } else { out.push_str("- "); }
                out.push_str(text_of(c));
                out.push('\n');
            }
            out.push('\n');
        }
        "table" => {
            let rows: Vec<&Value> = kids(b).iter().collect();
            if let Some(first) = rows.first() {
                let cells: Vec<String> = kids(first).iter().map(|c| text_of(c).replace('|', "\\|")).collect();
                out.push_str(&format!("| {} |\n", cells.join(" | ")));
                out.push_str(&format!("| {} |\n", vec!["---"; cells.len()].join(" | ")));
            }
            for row in rows.iter().skip(1) {
                let cells: Vec<String> = kids(row).iter().map(|c| text_of(c).replace('|', "\\|")).collect();
                out.push_str(&format!("| {} |\n", cells.join(" | ")));
            }
            out.push('\n');
        }
        "code" => {
            let lang = b.get("attrs").and_then(|a| a.get("lang")).and_then(|v| v.as_str()).unwrap_or("");
            out.push_str(FENCE); out.push_str(lang); out.push('\n');
            out.push_str(text_of(b)); out.push('\n'); out.push_str(FENCE); out.push_str("\n\n");
        }
        "quote" => {
            for line in text_of(b).split('\n') { out.push_str("> "); out.push_str(line); out.push('\n'); }
            out.push('\n');
        }
        "figure" => {
            let src = b.get("attrs").and_then(|a| a.get("src")).and_then(|v| v.as_str()).unwrap_or("");
            out.push_str(&format!("![{}]({})\n\n", text_of(b), src));
        }
        "footnote" => {
            let label = b.get("attrs").and_then(|a| a.get("label")).and_then(|v| v.as_str()).unwrap_or("1");
            out.push_str(&format!("[^{}]: {}\n\n", label, text_of(b)));
        }
        _ => {
            if !text_of(b).is_empty() { out.push_str(text_of(b)); out.push_str("\n\n"); }
            for c in kids(b) { md_node(c, out); }
        }
    }
}

pub fn render_markdown(sdir: &Value) -> String {
    let mut out = String::new();
    if let Some(root) = sdir.get("blocks").and_then(|b| b.get(0)) { md_node(root, &mut out); }
    out.trim_end().to_string() + "\n"
}

pub(crate) fn html_node(b: &Value, out: &mut String) {
    let id = esc_html(id_of(b));
    match type_of(b) {
        "document" => { for c in kids(b) { html_node(c, out); } }
        "heading" => {
            let n = heading_level(b).clamp(1, 6);
            out.push_str(&format!("<h{n} id=\"{id}\">{}</h{n}>\n", esc_html(text_of(b))));
            for c in kids(b) { html_node(c, out); }
        }
        "paragraph" => out.push_str(&format!("<p id=\"{id}\">{}</p>\n", esc_html(text_of(b)))),
        "list" => {
            let ordered = b.get("attrs").and_then(|a| a.get("ordered")).and_then(|v| v.as_bool()).unwrap_or(false);
            let tag = if ordered { "ol" } else { "ul" };
            out.push_str(&format!("<{tag}>\n"));
            for c in kids(b) { out.push_str(&format!("<li id=\"{}\">{}</li>\n", esc_html(id_of(c)), esc_html(text_of(c)))); }
            out.push_str(&format!("</{tag}>\n"));
        }
        "table" => {
            out.push_str("<table>\n");
            for (ri, row) in kids(b).iter().enumerate() {
                out.push_str("<tr>");
                for cell in kids(row) {
                    let tag = if ri == 0 { "th" } else { "td" };
                    out.push_str(&format!("<{tag}>{}</{tag}> ", esc_html(text_of(cell))));
                }
                out.push_str("</tr>\n");
            }
            out.push_str("</table>\n");
        }
        "code" => {
            let lang = b.get("attrs").and_then(|a| a.get("lang")).and_then(|v| v.as_str()).unwrap_or("");
            out.push_str(&format!("<pre id=\"{id}\"><code class=\"language-{}\">{}</code></pre>\n", esc_html(lang), esc_html(text_of(b))));
        }
        "quote" => out.push_str(&format!("<blockquote id=\"{id}\">{}</blockquote>\n", esc_html(text_of(b)))),
        "figure" => {
            let src = b.get("attrs").and_then(|a| a.get("src")).and_then(|v| v.as_str()).unwrap_or("");
            if src.trim().is_empty() {
                out.push_str(&format!("<figure id=\"{id}\"><figcaption>{}</figcaption></figure>\n", esc_html(text_of(b))));
            } else {
                out.push_str(&format!("<figure id=\"{id}\"><img src=\"{}\" alt=\"{}\"/><figcaption>{}</figcaption></figure>\n", esc_html(src), esc_html(text_of(b)), esc_html(text_of(b))));
            }
        }
        "caption" => out.push_str(&format!("<figcaption>{}</figcaption>\n", esc_html(text_of(b)))),
        "footnote" => out.push_str(&format!("<aside id=\"fn-{id}\" role=\"doc-footnote\">{}</aside>\n", esc_html(text_of(b)))),
        "crossref" => out.push_str(&format!("<a href=\"#{id}\">{}</a>\n", esc_html(text_of(b)))),
        "math" => out.push_str(&format!("<span class=\"math\">{}</span>\n", esc_html(text_of(b)))),
        _ => {
            if !text_of(b).is_empty() { out.push_str(&format!("<div id=\"{id}\">{}</div>\n", esc_html(text_of(b)))); }
            for c in kids(b) { html_node(c, out); }
        }
    }
}

pub(crate) fn html_document(sdir: &Value, profile: &str) -> String {
    let title = sdir.get("meta").and_then(|m| m.get("title")).and_then(|v| v.as_str()).unwrap_or("NF 文档");
    let lang = sdir.get("meta").and_then(|m| m.get("lang")).and_then(|v| v.as_str()).unwrap_or("und");
    let mut body = String::new();
    if let Some(root) = sdir.get("blocks").and_then(|b| b.get(0)) { html_node(root, &mut body); }
    let css = if profile == "accessible" || profile == "large-print" {
        "body{max-width:46rem;margin:2rem auto;line-height:1.6;font-family:serif}h1,h2,h3{line-height:1.2}table{border-collapse:collapse}th,td{border:1px solid #444;padding:.3rem .5rem}img{max-width:100%}"
    } else {
        "body{max-width:52rem;margin:2rem auto;line-height:1.5}"
    };
    format!("<!DOCTYPE html>\n<html lang=\"{}\">\n<head>\n<meta charset=\"utf-8\"/>\n<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>\n<title>{}</title>\n<style>{}</style>\n</head>\n<body>\n<main>\n{}</main>\n</body>\n</html>\n", esc_html(lang), esc_html(title), css, body)
}

pub(crate) fn epub_bytes(sdir: &Value, profile: &str) -> Result<Vec<u8>, CoreError> {
    let title = sdir.get("meta").and_then(|m| m.get("title")).and_then(|v| v.as_str()).unwrap_or("NF 文档");
    let lang = sdir.get("meta").and_then(|m| m.get("lang")).and_then(|v| v.as_str()).unwrap_or("und");
    let id = digest_value(sdir)?;
    let mut body = String::new();
    if let Some(root) = sdir.get("blocks").and_then(|b| b.get(0)) { html_node(root, &mut body); }
    let mut images: BTreeSet<String> = BTreeSet::new();
    if let Some(root) = sdir.get("blocks").and_then(|b| b.get(0)) { collect_image_srcs(root, &mut images); }
    let mut manifest_extra = String::new();
    let mut extra_entries: Vec<(String, Vec<u8>)> = Vec::new();
    for (i, src) in images.iter().enumerate() {
        manifest_extra.push_str(&format!("<item id=\"img{i}\" href=\"{}\" media-type=\"image/png\"/>", esc_xml(src)));
        extra_entries.push((format!("OEBPS/{src}"), TINY_PNG.to_vec()));
    }
    let css = if profile == "accessible" || profile == "large-print" { "body{font-family:serif;line-height:1.6}table{border-collapse:collapse}th,td{border:1px solid #444;padding:.25rem}" } else { "body{line-height:1.5}" };
    let chapter = format!("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<!DOCTYPE html>\n<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"{}\" lang=\"{}\">\n<head><meta charset=\"utf-8\"/><title>{}</title><link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\"/></head>\n<body>\n{}</body>\n</html>\n", esc_xml(lang), esc_xml(lang), esc_xml(title), body);
    let nav = format!("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<!DOCTYPE html>\n<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\" xml:lang=\"{}\" lang=\"{}\">\n<head><meta charset=\"utf-8\"/><title>{}</title></head>\n<body><nav epub:type=\"toc\" id=\"toc\"><h1>目录</h1><ol><li><a href=\"chapter.xhtml\">{}</a></li></ol></nav></body>\n</html>\n", esc_xml(lang), esc_xml(lang), esc_xml(title), esc_xml(title));
    let opf = format!("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"3.0\" unique-identifier=\"bookid\">\n<metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\"><dc:identifier id=\"bookid\">urn:sha256:{}</dc:identifier><dc:title>{}</dc:title><dc:language>{}</dc:language><meta property=\"dcterms:modified\">1980-01-01T00:00:00Z</meta></metadata>\n<manifest><item id=\"nav\" href=\"nav.xhtml\" media-type=\"application/xhtml+xml\" properties=\"nav\"/><item id=\"chapter\" href=\"chapter.xhtml\" media-type=\"application/xhtml+xml\"/><item id=\"css\" href=\"style.css\" media-type=\"text/css\"/>{} </manifest>\n<spine><itemref idref=\"chapter\"/></spine>\n</package>\n", id, esc_xml(title), esc_xml(lang), manifest_extra);
    let container = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\"><rootfiles><rootfile full-path=\"OEBPS/content.opf\" media-type=\"application/oebps-package+xml\"/></rootfiles></container>\n";
    let mut entries: Vec<(String, Vec<u8>)> = vec![
        ("mimetype".to_string(), b"application/epub+zip".to_vec()),
        ("META-INF/container.xml".to_string(), container.as_bytes().to_vec()),
        ("OEBPS/content.opf".to_string(), opf.into_bytes()),
        ("OEBPS/nav.xhtml".to_string(), nav.into_bytes()),
        ("OEBPS/chapter.xhtml".to_string(), chapter.into_bytes()),
        ("OEBPS/style.css".to_string(), css.as_bytes().to_vec()),
    ];
    entries.extend(extra_entries);
    entries.sort_by(|a, b| a.0.cmp(&b.0));
    if let Some(pos) = entries.iter().position(|e| e.0 == "mimetype") {
        let m = entries.remove(pos);
        entries.insert(0, m);
    }
    zipsec::zip_bytes(&entries)
}

pub(crate) fn render_one(sdir: &Value, format: &str, profile: &str) -> Result<Vec<u8>, CoreError> {
    match format {
        "md" => Ok(render_markdown(sdir).into_bytes()),
        "html" => Ok(html_document(sdir, profile).into_bytes()),
        "json" => {
            let mut v = sdir.clone();
            if let Some(m) = v.as_object_mut() { m.insert("profile".into(), Value::String(profile.to_string())); }
            let mut b = crate::canonical::canonical_bytes(&v)?;
            b.push(b'\n');
            Ok(b)
        }
        "docx" => {
            let md = render_markdown(sdir);
            let title = sdir.get("meta").and_then(|m| m.get("title")).and_then(|v| v.as_str()).unwrap_or("NF 文档");
            docx::build_docx(&md, title)
        }
        "epub" => epub_bytes(sdir, profile),
        other => Err(CoreError::new("NF-PROF-001").with_message(format!("未知构建格式：{other}")).with_exit(1)),
    }
}
