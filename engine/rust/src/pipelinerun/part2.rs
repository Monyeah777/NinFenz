use super::*;

/// 逐层执行：解析模块、记录依赖序 / 类型面所需状态。
pub(crate) fn run_layers(pl: &Pipeline, index: &BTreeMap<String, Rec>, st: &mut PipeState) {
    for (idx0, layer) in pl.layers.iter().enumerate() {
        let idx = idx0 + 1;
        // 真源 overrides 在 sweep 下恒为 None ⇒ 取 layer.default_modules
        let refs: Vec<String> = layer.default_modules.clone();
        let same_layer: BTreeSet<String> = refs.iter().cloned().collect();
        for r in &refs {
            run_module(r, &layer.id, idx, &same_layer, index, st);
        }
    }
}

/// 单模块执行：解析 / 依赖序核对 / done 与事件登记。
fn run_module(
    r: &str,
    layer_id: &str,
    idx: usize,
    same_layer: &BTreeSet<String>,
    index: &BTreeMap<String, Rec>,
    st: &mut PipeState,
) {
    let Some(rec) = resolve(r, index) else {
        st.issues.push(format!(
            "模块未在仓库找到：{}（层 {}）（修复指引：核对 04_模块库/community/*/modules 的文件名与类别限定）",
            r, layer_id
        ));
        return;
    };
    let mid = rec.cat_id.clone();
    st.executed.push(mid.clone());
    st.modules_count += 1;
    st.layer_of.insert(mid.clone(), idx);
    for dep in &rec.inputs {
        dep_order_issues(&mid, dep, idx, same_layer, index, st);
    }
    st.done.insert(mid.clone());
    st.done.insert(fid_key(&mid));
    st.done.insert(bare(&mid).to_string());
    st.done.insert(rec.id.clone());
    for tok in &rec.outputs {
        if !st.tokens.contains(tok) {
            st.tokens.push(tok.clone());
        }
    }
    for ev in &rec.publish {
        set_default(&mut st.published, ev, &mid);
    }
    for ev in &rec.subscribe {
        append_sub(&mut st.subscribed, ev, &mid);
    }
}

/// 单条输入的依赖序核对：已做 / 同层 / 越层。
fn dep_order_issues(
    mid: &str,
    dep: &str,
    idx: usize,
    same_layer: &BTreeSet<String>,
    index: &BTreeMap<String, Rec>,
    st: &mut PipeState,
) {
    let dep_id = match resolve(dep, index) {
        Some(d) => d.cat_id.clone(),
        None => dep.to_string(),
    };
    let bare_dep = bare(&dep_id).to_string();
    let dep_layer = st
        .layer_of
        .get(&dep_id)
        .or_else(|| st.layer_of.get(&bare_dep))
        .copied();
    if st.done.contains(&dep_id) || st.done.contains(dep) || st.done.contains(&bare_dep) {
        // 真源在此记一条 edge；sweep 不消费 edge ⇒ 本线不计
    } else if same_layer.contains(dep)
        || same_layer.contains(&dep_id)
        || same_layer.contains(&bare_dep)
    {
        st.notes += 1; // 真源：category=同层依赖序
    } else if dep_layer.is_some_and(|dl| dl > idx) {
        st.issues.push(format!(
            "依赖序违约：{} 依赖 {}，但 {} 未在其之前执行（修复指引：前移提供方层位，或把该模块移出本层 default）",
            mid, dep_id, dep_id
        ));
    } else {
        st.notes += 1; // 真源：category=跨包/外部依赖
    }
}

/// 事件面：订阅方在本执行集内无发布方 ⇒ advisory。
pub(crate) fn check_event_closure(st: &mut PipeState) {
    // 事件面：订阅方在本执行集内无发布方 ⇒ advisory
    let mut subs_sorted: Vec<&(String, Vec<String>)> = st.subscribed.iter().collect();
    subs_sorted.sort_by(|a, b| a.0.cmp(&b.0));
    for (ev, subs) in subs_sorted {
        if !st.published.iter().any(|(e, _)| e == ev) {
            let mut uniq: Vec<String> = subs.clone();
            uniq.sort();
            uniq.dedup();
            st.notes += 1; // 真源：category=跨包/外部事件
        }
    }
}

/// 类型面（io_types）：仅在本执行集内判可证事项。
pub(crate) fn check_types(index: &BTreeMap<String, Rec>, executed: &[String], issues: &mut Vec<String>) {
    // 类型面（io_types）：仅在本执行集内判可证事项（未收窄不判死）
    let mut kind_of_token: Vec<(String, String)> = Vec::new();
    for mid in executed {
        let Some(rec) = resolve(mid, index) else {
            continue;
        };
        let Some(Json::Object(outs)) = rec.io_types.as_ref().and_then(|io| get(io, "outputs"))
        else {
            continue;
        };
        for (tok, kind) in outs.clone() {
            record_output_kind(&tok, &py_str(Some(&kind)), &mut kind_of_token, issues);
        }
    }
    for mid in executed {
        check_input_types(mid, index, issues);
    }
}

/// 输出类型登记：untyped 跳过；冲突报错；首见登记。
fn record_output_kind(
    tok: &str,
    kind: &str,
    kind_of_token: &mut Vec<(String, String)>,
    issues: &mut Vec<String>,
) {
    if kind == "untyped" {
        return;
    }
    if let Some((_, prev)) = kind_of_token.iter().find(|(t, _)| t == tok) {
        if prev != kind {
            issues.push(format!(
                "类型冲突：token {} 同时被声明为 {} 与 {}（修复指引：对齐各模块 io_types.outputs）",
                tok, prev, kind
            ));
        }
    }
    if !kind_of_token.iter().any(|(t, _)| t == tok) {
        kind_of_token.push((tok.to_string(), kind.to_string()));
    }
}

/// 输入类型面：期望类型须在提供方输出类型集内。
fn check_input_types(mid: &str, index: &BTreeMap<String, Rec>, issues: &mut Vec<String>) {
    let Some(rec) = resolve(mid, index) else {
        return;
    };
    let Some(Json::Object(ins)) = rec.io_types.as_ref().and_then(|io| get(io, "inputs")) else {
        return;
    };
    for (dep, want) in ins.clone() {
        let want = py_str(Some(&want));
        if want == "untyped" || want == "state" {
            continue;
        }
        let Some(dep_rec) = resolve(&dep, index) else {
            continue;
        };
        let got = dep_output_types(dep_rec);
        if !got.is_empty() && !got.contains(&want) {
            issues.push(format!(
                "类型不匹配：{} 期望 {} 提供 {}，而 {} 声明输出类型 {}（修复指引：对齐 io_types 或调整依赖）",
                mid,
                dep,
                want,
                dep,
                py_list(&got)
            ));
        }
    }
}

/// 依赖方声明的输出类型（去重排序，untyped 不计）。
fn dep_output_types(dep_rec: &Rec) -> Vec<String> {
    let mut got: Vec<String> = Vec::new();
    if let Some(Json::Object(outs)) = dep_rec.io_types.as_ref().and_then(|io| get(io, "outputs")) {
        for (_, v) in outs {
            let v = py_str(Some(v));
            if v != "untyped" && !got.contains(&v) {
                got.push(v);
            }
        }
    }
    got.sort();
    got
}

/// Python `sorted(list)` 的 `%s` 形态：`['a', 'b']`。
pub(crate) fn py_list(v: &[String]) -> String {
    format!(
        "[{}]",
        v.iter()
            .map(|x| format!("'{}'", x))
            .collect::<Vec<_>>()
            .join(", ")
    )
}

/// 真源 `discover`：仓库内全部管线文件（03_管线库 + community/*/pipelines）。
///
/// ⚠️ **前缀语义必须对齐**：真源是 `[Path(p).as_posix() for p in sorted(Path(root).glob(pat))]`
/// ——`root` 不是 `.` 时结果**带 root 前缀**（绝对 root ⇒ 绝对路径）。`glob::expand` 恒返回
/// root 相对路径，故这里补前缀。真语料上看不出差别（该契约全绿、无路径进消息），
/// 但**解析失败**时那句 `管线解析失败：<path>` 会带上它——实测过该分歧，故照搬。
pub(crate) fn discover(root: &Path) -> Vec<String> {
    let prefix = root.to_string_lossy().replace('\\', "/");
    let prefix = prefix.trim_end_matches('/').to_string();
    let mut hits: Vec<String> = Vec::new();
    for pat in ["03_管线库/*.md", "community/*/pipelines/*.md"] {
        for rel in crate::glob::expand(root, pat) {
            if prefix.is_empty() || prefix == "." {
                hits.push(rel);
            } else {
                hits.push(format!("{}/{}", prefix, rel));
            }
        }
    }
    hits
}

/// 真源 `sweep` 的返回（只留契约消费的字段）。
pub(crate) struct Sweep {
    pub issues: Vec<String>,
    pub pipelines: usize,
    pub notes: usize,
}

/// 真源 `sweep`。任一条管线 `graph` 抛错即整体 `Err`（真源不接异常，见模块头）。
pub(crate) fn sweep(root: &Path) -> Result<Sweep, String> {
    let index = module_files(root);
    let core = core_ids(root);
    let mut issues: Vec<String> = Vec::new();
    let mut pipelines = 0usize;
    let mut notes = 0usize;
    for p in discover(root) {
        let g = graph_with(&p, root, &index, &core)?;
        pipelines += 1;
        notes += g.notes;
        for i in &g.issues {
            issues.push(format!("{}：{}", g.pipeline_id, i));
        }
    }
    Ok(Sweep {
        issues,
        pipelines,
        notes,
    })
}
