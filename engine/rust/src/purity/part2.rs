use super::*;

/// R5 面：第三方 import 逐条核对（未软导入 / 未登记 / 端壳残留）。
pub(crate) fn check_imports(
    rel: &str,
    facts: &pyast::PurityFacts,
    root: &Path,
    residue: Option<&str>,
    out: &mut Vec<String>,
    imports: &mut i64,
) {
    for (mod_, lineno) in &facts.modules {
        if crate::py_stdlib::STDLIB.contains(&mod_.as_str()) || is_local(mod_, root) {
            continue;
        }
        *imports += 1;
        if HARD_ALLOW.contains(&mod_.as_str()) {
            continue;
        }
        if let Some((_, why)) = SOFT_IMPORTS.iter().find(|(m, _)| m == mod_) {
            if !facts.guarded.contains(lineno) {
                let msg = format!(
                    "{}:{} 第三方 {} 未软导入（须 try/except ImportError 守卫；登记理由：{}）",
                    rel, lineno, mod_, why
                );
                out.push(match residue {
                    Some(r) => format!("{}（{}）", msg, r),
                    None => msg,
                });
            }
            continue;
        }
        let msg = format!(
            "{}:{} 第三方 import 未登记：{}（修复指引：改为软导入并在 purity_scan.SOFT_IMPORTS 登记理由，或加入 HARD_ALLOW；端壳残留则登记 IMPORT_RESIDUE）",
            rel, lineno, mod_
        );
        out.push(match residue {
            Some(r) => format!("{}（{}）", msg, r),
            None => msg,
        });
    }
}

/// 真源 `scan` → `(issues, stats)`。
pub(crate) fn scan(root: &Path) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let mut raises = 0i64;
    let mut imports = 0i64;
    let mut sinks: Option<i64> = None;
    let mut residue: Vec<Json> = Vec::new();

    // R1/R2/R3：协议层文档
    let (proto_issues, docs) = proto_doc_issues(root);
    issues.extend(proto_issues);

    // R4：core/*.py（按文件名排序）——Rayon 按文件并行解析（`par_iter().map()` 是
    // IndexedParallelIterator，collect 保序）；聚合仍按原顺序串行执行，issues/residue 的
    // 次序与真源逐项一致。
    for d in core_findings(root).into_iter().flatten() {
        issues.extend(d.issues);
        raises += d.raises;
        imports += d.imports;
        *sinks.get_or_insert(0) += d.sinks;
        residue.extend(d.residue.into_iter().map(Json::Str));
    }
    // R5：IMPORT_SCAN 面（跳过 core/*，R4 已算过）
    for d in import_scan_findings(root).into_iter().flatten() {
        issues.extend(d.issues);
        imports += d.imports; // raises 只在 R4 那一段计
        *sinks.get_or_insert(0) += d.sinks;
        residue.extend(d.residue.into_iter().map(Json::Str));
    }

    // R6 自洽面 + R7 抽象阶梯 + R8 核心文面去叙述
    check_sink_registry(&mut issues);
    let layers = scan_layers(root, &mut issues);
    let (dn_files, dn_hits) = scan_domain_neutral(root, &mut issues);

    let stats = Json::Object(vec![
        ("docs".to_string(), Json::Int(docs)),
        ("raises".to_string(), Json::Int(raises)),
        ("imports".to_string(), Json::Int(imports)),
        ("import_residue".to_string(), Json::Array(residue)),
        ("sinks".to_string(), Json::Int(sinks.unwrap_or(0))),
        ("layers".to_string(), layers),
        (
            "domain_neutral".to_string(),
            Json::Object(vec![
                ("files".to_string(), Json::Int(dn_files)),
                ("hits".to_string(), Json::Int(dn_hits)),
            ]),
        ),
    ]);
    (issues, stats)
}

/// R1–R3：协议层文档的端壳残留 / 私货 / 重复标题；返回 issues 与已扫文档数。
pub(crate) fn proto_doc_issues(root: &Path) -> (Vec<String>, i64) {
    let mut issues: Vec<String> = Vec::new();
    let mut docs = 0i64;
    for name in PROTO_DOCS {
        let p = root.join(name);
        if !p.exists() {
            continue;
        }
        let Ok(text) = std::fs::read_to_string(&p) else {
            continue;
        };
        docs += 1;
        let f = doc_facts(&text);
        // 端壳残留**只在前两份**判
        if name == "01_核心协议.md" || name == "02_联动注册表.md" {
            for (i, ln) in &f.shell {
                issues.push(format!("{}:{} 端壳/APK 残留：{}", name, i, ln));
            }
        }
        for (i, ln) in &f.private {
            issues.push(format!("{}:{} 私货/可变物：{}", name, i, ln));
        }
        for (title, lines) in &f.dup_titles {
            let ls: Vec<String> = lines.iter().map(|x| x.to_string()).collect();
            issues.push(format!(
                "{} 重复标题「{}」：行 {}",
                name,
                title,
                ls.join(",")
            ));
        }
    }
    (issues, docs)
}

/// R4 的取件面：`desktop/src/core/*.py` 按文件名排序后并行取 findings（保序）。
pub(crate) fn core_findings(root: &Path) -> Vec<Option<FileFindings>> {
    // R4：core/*.py（按文件名排序）
    let core_rel = "desktop/src/core";
    let mut core_files: Vec<String> = Vec::new();
    if root.join(core_rel).is_dir() {
        if let Ok(rd) = std::fs::read_dir(root.join(core_rel)) {
            for e in rd.flatten() {
                let n = e.file_name().to_string_lossy().to_string();
                if n.ends_with(".py") {
                    core_files.push(n);
                }
            }
        }
    }
    core_files.sort();
    // Rayon 按文件并行解析（`par_iter().map()` 是 IndexedParallelIterator，collect 保序）；
    // 聚合仍按原顺序串行执行，issues/residue 的次序与真源逐项一致。
    use rayon::prelude::*;
    let r4: Vec<Option<FileFindings>> = core_files
        .par_iter()
        .map(|fname| {
            let rel = format!("{}/{}", core_rel, fname);
            let text = std::fs::read_to_string(root.join(&rel)).ok()?;
            file_findings(&rel, &text, root)
        })
        .collect();
    r4
}

/// R5 的取件面：`IMPORT_SCAN` 展开、排序去重，跳过 core/*（R4 已算过）。
pub(crate) fn import_scan_findings(root: &Path) -> Vec<Option<FileFindings>> {
    // R5：IMPORT_SCAN 面（跳过 core/*，R4 已算过）
    let mut rels: Vec<String> = Vec::new();
    for pat in IMPORT_SCAN {
        rels.extend(crate::glob::expand(root, pat));
    }
    rels.sort();
    rels.dedup();
    use rayon::prelude::*;
    let r5: Vec<Option<FileFindings>> = rels
        .par_iter()
        .map(|rel| {
            if rel.starts_with("desktop/src/core/") {
                return None;
            }
            let text = std::fs::read_to_string(root.join(rel)).ok()?;
            file_findings(rel, &text, root)
        })
        .collect();
    r5
}

/// R6 自洽面：登记表自身的判据（CWE 对齐 / 放行键指向已登记 sink）。
pub(crate) fn check_sink_registry(issues: &mut Vec<String>) {
    // R6 自洽面：登记表自身的判据
    let mut all_sinks: Vec<(&str, &str)> = DANGEROUS_CALLS.to_vec();
    all_sinks.extend(METHOD_SINKS.iter().copied());
    all_sinks.sort_by(|a, b| a.0.cmp(b.0));
    for (call, desc) in all_sinks {
        if !cwe_re().is_match(desc) {
            issues.push(format!(
                "危险 sink 类目缺 CWE 对齐：{}（修复指引：在 purity_scan.DANGEROUS_CALLS 的说明前加 `CWE-<nnn> `，便于外部扫描器按缺陷类型对账）",
                call
            ));
        }
    }
    let mut allow_keys: Vec<&str> = SINK_ALLOW.iter().map(|(k, _)| *k).collect();
    allow_keys.sort();
    for key in allow_keys {
        let sink = key.rsplit(':').next().unwrap_or(key);
        if !DANGEROUS_CALLS.iter().any(|(c, _)| *c == sink)
            && !METHOD_SINKS.iter().any(|(m, _)| *m == sink)
            && sink != "subprocess"
        {
            issues.push(format!(
                "SINK_ALLOW 放行键指向未登记 sink：{}（修复指引：删除放行，或先在 DANGEROUS_CALLS 登记该 sink 类目）",
                key
            ));
        }
    }
}

/// R7：抽象阶梯（真源 `layer_model`）；缺件时给出 skipped 结构。
pub(crate) fn scan_layers(root: &Path, issues: &mut Vec<String>) -> Json {
    // R7：抽象阶梯（真源 layer_model）
    let layers: Json = if root.join(crate::layers::DECL_REL).is_file() {
        let (li, ls) = crate::layers::scan(root);
        issues.extend(li);
        ls
    } else {
        Json::Object(vec![(
            "skipped".to_string(),
            Json::Str(format!(
                "缺 {}（另由断言表与规范性名单判）",
                crate::layers::DECL_REL
            )),
        )])
    };
    layers
}

/// R8：核心文面去叙述（域中立）——判定序 = 最左优先、同位置按表序取首个。
pub(crate) fn scan_domain_neutral(root: &Path, issues: &mut Vec<String>) -> (i64, i64) {
    let mut dn_files = 0i64;
    let mut dn_hits = 0i64;
    for pat in DOMAIN_FACE {
        for rel in crate::glob::expand(root, pat) {
            let Ok(text) = std::fs::read_to_string(root.join(&rel)) else {
                continue;
            };
            dn_files += 1;
            for (i, line) in text.lines().enumerate() {
                let chars: Vec<char> = line.chars().collect();
                let mut pos = 0usize;
                while pos < chars.len() {
                    let mut hit: Option<&str> = None;
                    for term in DOMAIN_TERMS {
                        let t: Vec<char> = term.chars().collect();
                        if pos + t.len() <= chars.len() && chars[pos..pos + t.len()] == t[..] {
                            hit = Some(term);
                            break;
                        }
                    }
                    let Some(term) = hit else {
                        pos += 1;
                        continue;
                    };
                    let exempt = pos > 0 && matches!(chars[pos - 1], '非' | '跨' | '反' | '去');
                    if !exempt {
                        dn_hits += 1;
                        let head: String = line.trim().chars().take(80).collect();
                        issues.push(format!(
                            "{}:{} 核心文面含叙述/题材词「{}」：{}（修复指引：改域中立表述；确属必要改在 core/domain_neutral.DOMAIN_ALLOW 登记理由）",
                            rel,
                            i + 1,
                            term,
                            head
                        ));
                    }
                    pos += term.chars().count();
                }
            }
        }
    }
    (dn_files, dn_hits)
}
