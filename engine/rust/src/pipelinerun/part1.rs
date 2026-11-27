use super::*;

/// 真源 `_MODULE_GLOBS`。
pub(crate) const MODULE_GLOBS: [&str; 2] = ["04_模块库/*/*.md", "community/*/modules/*.md"];

/// 真源 `core.models.fid_key`：把 full_id 归一为协议比较键（类别段去「类」字）。
pub(crate) fn fid_key(fid: &str) -> String {
    match fid.split_once(':') {
        Some((c, i)) => format!("{}:{}", c.trim_end_matches('类'), i),
        None => fid.to_string(),
    }
}

/// Python `str.split(":")[-1]`。
pub(crate) fn bare(s: &str) -> &str {
    s.rsplit(':').next().unwrap_or("")
}

/// 真源 `_module_files` 的一条记录。
#[derive(Clone)]
pub(crate) struct Rec {
    pub(crate) id: String,
    pub(crate) cat_id: String,
    pub(crate) has_contract: bool,
    pub(crate) inputs: Vec<String>,
    pub(crate) outputs: Vec<String>,
    pub(crate) publish: Vec<String>,
    pub(crate) subscribe: Vec<String>,
    pub(crate) io_types: Option<Json>,
}

/// 真源 `_module_files`：仓库模块索引（文件名即 id，机读契约在场则挂上）。
pub(crate) fn module_files(root: &Path) -> BTreeMap<String, Rec> {
    let mut out: BTreeMap<String, Rec> = BTreeMap::new();
    let mut seen: BTreeSet<String> = BTreeSet::new();
    for pat in MODULE_GLOBS {
        for rel in crate::glob::expand(root, pat) {
            if seen.contains(&rel) || rel.rsplit('/').next() == Some("README.md") {
                continue;
            }
            seen.insert(rel.clone());
            let name = rel.rsplit('/').next().unwrap_or("").to_string();
            let stem = name.split('_').next().unwrap_or("").to_string();
            let parent = rel.rsplit_once('/').map(|(p, _)| p).unwrap_or("");
            let cat = parent.rsplit('/').next().unwrap_or("").replace('类', "");
            let mut rec = Rec {
                id: stem.clone(),
                cat_id: format!("{}:{}", cat, stem),
                has_contract: false,
                inputs: Vec::new(),
                outputs: Vec::new(),
                publish: Vec::new(),
                subscribe: Vec::new(),
                io_types: None,
            };
            // 真源 `except OSError: pass`——件不可读 ⇒ 该模块无契约摘要（跳过，不伪造）
            if let Ok(text) = std::fs::read_to_string(root.join(&rel)) {
                let parsed = miniyaml::fence_yaml(&text, "machine_contract");
                let mc = parsed
                    .as_ref()
                    .and_then(|p| get(p, "machine_contract").cloned())
                    .unwrap_or(Json::Null);
                if matches!(mc, Json::Object(_)) {
                    rec.has_contract = true;
                    rec.inputs = str_list(get(&mc, "inputs"));
                    rec.outputs = str_list(get(&mc, "outputs"));
                    let ev = get(&mc, "events").cloned().unwrap_or(Json::Null);
                    rec.publish = str_list(get(&ev, "publish"));
                    rec.subscribe = str_list(get(&ev, "subscribe"));
                    if py_truthy(get(&mc, "id").unwrap_or(&Json::Null)) {
                        rec.cat_id = py_str(get(&mc, "id"));
                    }
                    rec.io_types = crate::io_types::parse_io_types(&text);
                }
            }
            for key in [stem, rec.cat_id.clone(), fid_key(&rec.cat_id)] {
                out.entry(key).or_insert_with(|| rec.clone());
            }
        }
    }
    out
}

/// 真源 `_core_ids`：官方核心基座 id（`registry.json` `modules[]`）。
pub(crate) fn core_ids(root: &Path) -> Vec<String> {
    let Some(reg) = jsonread::read_file(root, "desktop/src/core/registry.json") else {
        return Vec::new();
    };
    let mut out = Vec::new();
    if let Some(Json::Array(mods)) = get(&reg, "modules") {
        for m in mods {
            if py_truthy(get(m, "id").unwrap_or(&Json::Null)) {
                out.push(py_str(get(m, "id")));
            }
        }
    }
    out
}

/// 真源 `_resolve`。
pub(crate) fn resolve<'a>(r: &str, index: &'a BTreeMap<String, Rec>) -> Option<&'a Rec> {
    index
        .get(r)
        .or_else(|| index.get(&fid_key(r)))
        .or_else(|| index.get(bare(r)))
}

/// 真源 `published.setdefault(ev, mid)` —— **首个**发布方胜出。
pub(crate) fn set_default(published: &mut Vec<(String, String)>, ev: &str, mid: &str) {
    if !published.iter().any(|(e, _)| e == ev) {
        published.push((ev.to_string(), mid.to_string()));
    }
}

/// 真源 `subscribed.setdefault(ev, []).append(mid)`。
pub(crate) fn append_sub(subscribed: &mut Vec<(String, Vec<String>)>, ev: &str, mid: &str) {
    match subscribed.iter_mut().find(|(e, _)| e == ev) {
        Some((_, v)) => v.push(mid.to_string()),
        None => subscribed.push((ev.to_string(), vec![mid.to_string()])),
    }
}

/// `graph` 里 `sweep` **真正消费**的那几项。
///
/// 真源 `graph` 的 advisory 明细带 `category` / `detail`，但那两样只进 `sweep` 的
/// `advisory_buckets` / `advisory_items` —— 而契约 `_c_pipeline_dryrun` **只读**
/// `tot["pipelines"]` 与 `tot["notes"]`。故本线只留**计数**（分支结构一字未改，
/// 只是不再拼没人读的字符串）。同理 `steps` / `edges` / `tokens` 明细与
/// `stats.{missing,layers,typed_tokens}` 均不落结构。
pub(crate) struct Graph {
    pub pipeline_id: String,
    pub issues: Vec<String>,
    pub notes: usize,
}

// 真源的公开 `graph(pipeline_path, root, ...)` 单条入口不在契约消费面上（`sweep` 用
// `graph_with` 并复用同一份 index/core），故不移植——收了就是没人核的代码。

pub(crate) fn graph_with(
    pipeline_path: &str,
    root: &Path,
    index: &BTreeMap<String, Rec>,
    core: &[String],
) -> Result<Graph, String> {
    let pl = load_graph_pipeline(root, pipeline_path)?;
    let mut st = PipeState {
        issues: Vec::new(),
        notes: 0,
        modules_count: 0,
        tokens: Vec::new(),
        done: BTreeSet::new(),
        published: Vec::new(),
        subscribed: Vec::new(),
        layer_of: BTreeMap::new(),
        executed: Vec::new(),
    };
    seed_core(core, index, &mut st);
    run_layers(&pl, index, &mut st);
    check_event_closure(&mut st);
    check_types(index, &st.executed, &mut st.issues);

    let _ = st.modules_count; // 真源 stats.modules 只进 advisory 汇总，契约不读
    Ok(Graph {
        pipeline_id: pl.id.clone(),
        issues: st.issues,
        notes: st.notes,
    })
}

/// graph_with 的累积状态（token 池 / 已执行集 / 发布订阅表 / 层位表）。
pub(crate) struct PipeState {
    pub(crate) issues: Vec<String>,
    pub(crate) notes: usize,
    pub(crate) modules_count: usize,
    pub(crate) tokens: Vec<String>,
    pub(crate) done: BTreeSet<String>,
    pub(crate) published: Vec<(String, String)>,
    pub(crate) subscribed: Vec<(String, Vec<String>)>,
    pub(crate) layer_of: BTreeMap<String, usize>,
    pub(crate) executed: Vec<String>,
}

/// 载入管线文档；解析失败给带指路的错误。
pub(crate) fn load_graph_pipeline(root: &Path, pipeline_path: &str) -> Result<Pipeline, String> {
    let pl: Pipeline = match load_pipeline_file(&root.join(pipeline_path)) {
        Some(p) => p,
        None => {
            return Err(format!(
                "管线解析失败：{}（修复指引：检查 frontmatter 与代码围栏闭合）",
                pipeline_path
            ))
        }
    };
    Ok(pl)
}

/// 基座先跑：官方核心的产出/事件进入池。
pub(crate) fn seed_core(core: &[String], index: &BTreeMap<String, Rec>, st: &mut PipeState) {
    for x in core {
        st.done.insert(x.clone());
        st.done.insert(fid_key(x));
        st.done.insert(bare(x).to_string());
    }
    for r in core {
        if let Some(rec) = resolve(r, index) {
            for tok in &rec.outputs {
                if !st.tokens.contains(tok) {
                    st.tokens.push(tok.clone());
                }
            }
            for ev in &rec.publish {
                set_default(&mut st.published, ev, &rec.cat_id);
            }
            for ev in &rec.subscribe {
                append_sub(&mut st.subscribed, ev, &rec.cat_id);
            }
        }
    }
}
