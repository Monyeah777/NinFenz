use super::*;

pub(crate) fn read_json_opt(root: &Path, rel: &str) -> Option<Json> {
    let text = std::fs::read_to_string(root.join(rel)).ok()?;
    crate::jsonmini::parse(&text).ok().map(|r| r.value)
}

/// 真源 `_core_ids()`。
pub(crate) fn core_ids() -> BTreeSet<String> {
    let mut out: BTreeSet<String> = crate::output_tables::CORE13
        .iter()
        .map(|s| s.to_string())
        .collect();
    for x in crate::output_tables::CORE13 {
        out.insert(x.rsplit(':').next().unwrap_or(x).to_string());
    }
    out
}

/// 真源 `_pack_dirs`：有 `community/<包>/protocol.yaml` 的包名（有序）。
pub(crate) fn pack_dirs(root: &Path) -> Vec<String> {
    let mut v = crate::glob::expand(root, "community/*/protocol.yaml");
    v.sort();
    let mut out: Vec<String> = Vec::new();
    for rel in v {
        if let Some(pkg) = rel.split('/').nth(1) {
            if !out.contains(&pkg.to_string()) {
                out.push(pkg.to_string());
            }
        }
    }
    out
}

/// 真源 `_parse_protocol` 的结果。
#[derive(Clone, Debug, Default)]
pub(crate) struct Proto {
    pub id: String,
    pub pipeline: String,
    pub module_ids: Vec<String>,
    pub mount_layers: BTreeMap<String, Vec<String>>,
    pub references: Vec<(String, String)>,
}

// 分层清单行正则。模式串含裸花括号，提为常量以免被朴素括号计数误判。
pub(crate) const LAYER_DECL_PAT: &str = r"(?m)^\s*(P\d{2})\s*[^:]*:\s*\{default:\s*\[([^\]]*)\]";

/// 真源 `_parse_protocol`。
pub(crate) fn parse_protocol(path: &Path) -> Proto {
    let text = std::fs::read(path)
        .map(|b| String::from_utf8_lossy(&b).into_owned())
        .unwrap_or_default();
    let dir = path
        .parent()
        .and_then(|p| p.file_name())
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_default();
    let mut out = Proto::default();
    let re_id = regex::Regex::new(r"(?m)^\s*id:\s*(\S+)\s*$").expect("固定合法");
    out.id = re_id
        .captures(&text)
        .map(|c| c[1].to_string())
        .unwrap_or_else(|| dir.clone());
    let re_pipe = regex::Regex::new(r"(?m)^\s*pipeline:\s*(P\d{2,3})\s*$").expect("固定合法");
    out.pipeline = re_pipe
        .captures(&text)
        .map(|c| c[1].to_string())
        .unwrap_or_default();
    // 行式清单：全限定与裸号两种写法并集（保持出现序、去重）
    let mut ids: Vec<String> = Vec::new();
    let re_full =
        regex::Regex::new(r#"(?m)^\s*-\s*"([^"]+:M\d{2,3})"\s*(?:#.*)?$"#).expect("固定合法");
    for c in re_full.captures_iter(&text) {
        let v = c[1].to_string();
        if !ids.contains(&v) {
            ids.push(v);
        }
    }
    let re_bare = regex::Regex::new(r#"(?m)^\s*-\s*"?(M\d{2,3})"?\s*(?:#.*)?$"#).expect("固定合法");
    for c in re_bare.captures_iter(&text) {
        let v = c[1].to_string();
        if !ids.contains(&v) {
            ids.push(v);
        }
    }
    if ids.is_empty() {
        let re_flow =
            regex::Regex::new(r"(?m)^\s*module_id_range\s*:\s*\[([^\]]*)\]").expect("固定合法");
        if let Some(c) = re_flow.captures(&text) {
            for x in c[1].split(',') {
                let v = x
                    .trim()
                    .trim_matches(|ch| ch == '\'' || ch == '"')
                    .to_string();
                if !v.is_empty() {
                    ids.push(v);
                }
            }
        }
    }
    out.module_ids = ids;
    let re_layer = regex::Regex::new(LAYER_DECL_PAT).expect("固定合法");
    for c in re_layer.captures_iter(&text) {
        let mods: Vec<String> = c[2]
            .split(',')
            .map(|x| {
                x.trim()
                    .trim_matches(|ch| ch == '\'' || ch == '"')
                    .to_string()
            })
            .filter(|x| !x.is_empty())
            .collect();
        if !mods.is_empty() {
            out.mount_layers.insert(c[1].to_string(), mods);
        }
    }
    let re_ref =
        regex::Regex::new(r"(?ms)^\s*-\s*source_package:\s*(\S+)\s*\n\s*module_id:\s*(\S+)")
            .expect("固定合法");
    for c in re_ref.captures_iter(&text) {
        out.references.push((
            c[1].trim_matches(|ch| ch == '\'' || ch == '"').to_string(),
            c[2].trim_matches(|ch| ch == '\'' || ch == '"').to_string(),
        ));
    }
    out
}

/// 真源 `_face_paths`：按模式枚举（**有序**）。
///
/// ⚠️ **必须排序**：真源走 `csc.iter_files`（已排序），而 `_module_contracts` 的
/// 「同一键**首次胜**」语义**依赖枚举序**——不排序时 `M01` 这类裸号会解析到**别的包**的模块。
/// 实测（2026-10-04）：`校园情感领域包 + 西幻生存领域包` 的 `modules` 因此从 23 条裸号
/// 变成 23 条跨包全限定号，整张证书对不上。
pub(crate) fn face_paths(root: &Path, pattern: &str) -> Vec<String> {
    let mut v = crate::glob::expand(root, pattern);
    v.sort();
    v
}

/// 真源 `_module_contracts`：`{可查键: 契约摘要}`（id / stem / id 末段三种键，首次胜）。
pub(crate) fn module_contracts(root: &Path) -> Vec<(String, Json)> {
    let mut out: Vec<(String, Json)> = Vec::new();
    for rel in face_paths(root, "community/*/modules/*.md") {
        let text = match std::fs::read(root.join(&rel)) {
            Ok(b) => String::from_utf8_lossy(&b).into_owned(),
            Err(_) => continue,
        };
        let parsed = match crate::miniyaml::fence_yaml(&text, "machine_contract") {
            Some(p) => p,
            None => continue,
        };
        let mc = obj_get(&parsed, "machine_contract")
            .cloned()
            .unwrap_or(Json::Object(vec![]));
        if !matches!(mc, Json::Object(_)) || matches!(&mc, Json::Object(o) if o.is_empty()) {
            continue;
        }
        let stem = rel
            .rsplit('/')
            .next()
            .unwrap_or("")
            .split('_')
            .next()
            .unwrap_or("")
            .to_string();
        let pack = rel.split('/').nth(1).unwrap_or("").to_string();
        let id = {
            let v = s_of(obj_get(&mc, "id"));
            if v.is_empty() {
                stem.clone()
            } else {
                v
            }
        };
        let events = obj_get(&mc, "events")
            .cloned()
            .unwrap_or(Json::Object(vec![]));
        let rec = Json::Object(vec![
            ("id".to_string(), Json::Str(id.clone())),
            ("stem".to_string(), Json::Str(stem.clone())),
            ("pack".to_string(), Json::Str(pack)),
            ("layer".to_string(), Json::Str(s_of(obj_get(&mc, "layer")))),
            (
                "inputs".to_string(),
                str_json(&str_list(obj_get(&mc, "inputs"))),
            ),
            (
                "outputs".to_string(),
                str_json(&str_list(obj_get(&mc, "outputs"))),
            ),
            (
                "publish".to_string(),
                str_json(&str_list(obj_get(&events, "publish"))),
            ),
            (
                "subscribe".to_string(),
                str_json(&str_list(obj_get(&events, "subscribe"))),
            ),
            ("path".to_string(), Json::Str(rel.clone())),
        ]);
        // ⚠️ 三个键的语义**不同**（真源是 `out[id] = rec` + 两次 `setdefault`）：
        //   · `id` 键 = **赋值（覆盖）**；`stem` / 末段 = **首次胜**。
        // 把 id 键也写成"首次胜"会**挡住后来者的赋值**：实测（2026-10-04）
        // `community/西幻生存领域包/modules/M01_职业成长.md` 的 `id` 恰是裸号 `M01`，而 AI 包
        // 那份记录（`id: AI人力资源与招聘:M01`）已先把**末段键** `M01` setdefault 掉了
        // ⇒ 真源里裸记录**覆盖**它（`M01 → M01`），本线却保留了 AI 记录
        // ⇒ `profiles` 里 111 个包的 `module_recs` 连带错位，组合证书整张对不上。
        match out.iter_mut().find(|(k, _)| *k == id) {
            Some(slot) => slot.1 = rec.clone(),
            None => out.push((id.clone(), rec.clone())),
        }
        if !out.iter().any(|(k, _)| *k == stem) {
            out.push((stem.clone(), rec.clone()));
        }
        let tail = id.rsplit(':').next().unwrap_or(&id).to_string();
        if !out.iter().any(|(k, _)| *k == tail) {
            out.push((tail, rec));
        }
    }
    out
}

/// 真源 `_core_contracts`。
pub(crate) fn core_contracts(root: &Path) -> Vec<(String, Json)> {
    let mut out: Vec<(String, Json)> = Vec::new();
    for rel in face_paths(root, "04_模块库/*/*.md") {
        let text = match std::fs::read(root.join(&rel)) {
            Ok(b) => String::from_utf8_lossy(&b).into_owned(),
            Err(_) => continue,
        };
        let parsed = match crate::miniyaml::fence_yaml(&text, "machine_contract") {
            Some(p) => p,
            None => continue,
        };
        let mc = obj_get(&parsed, "machine_contract")
            .cloned()
            .unwrap_or(Json::Object(vec![]));
        if !matches!(mc, Json::Object(_)) || matches!(&mc, Json::Object(o) if o.is_empty()) {
            continue;
        }
        let stem = rel
            .rsplit('/')
            .next()
            .unwrap_or("")
            .split('_')
            .next()
            .unwrap_or("")
            .to_string();
        let id = {
            let v = s_of(obj_get(&mc, "id"));
            if v.is_empty() {
                stem.clone()
            } else {
                v
            }
        };
        let events = obj_get(&mc, "events")
            .cloned()
            .unwrap_or(Json::Object(vec![]));
        let rec = Json::Object(vec![
            ("id".to_string(), Json::Str(id.clone())),
            ("stem".to_string(), Json::Str(stem.clone())),
            (
                "publish".to_string(),
                str_json(&str_list(obj_get(&events, "publish"))),
            ),
            (
                "subscribe".to_string(),
                str_json(&str_list(obj_get(&events, "subscribe"))),
            ),
            ("path".to_string(), Json::Str(rel.clone())),
        ]);
        if !out.iter().any(|(k, _)| *k == id) {
            out.push((id, rec.clone()));
        }
        if !out.iter().any(|(k, _)| *k == stem) {
            out.push((stem, rec));
        }
    }
    out
}
