use super::*;

pub(crate) const DECL_REL: &str = "protocol/LAYERS.json";

pub(crate) const SCHEMA: &str = "nf-layers/1";

pub(crate) const DOC_REL: &str = "docs/layers.md";

pub(crate) const VERIFY_REL: &str = "verify.sh";

pub(crate) const ASSERTIONS_REL: &str = "protocol/assertions.json";

pub(crate) const MARK_BEGIN: &str = "<!-- nf:layers:begin -->";

pub(crate) const MARK_END: &str = "<!-- nf:layers:end -->";

// check 定义行正则。模式串含裸花括号，提为常量以免被朴素括号计数误判。
pub(crate) const CHECK_DEF_PAT: &str = r"(?m)^check(\d+)\(\)\{";

pub(crate) fn check_def_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(CHECK_DEF_PAT).expect("check 定义正则固定合法"))
}

pub(crate) fn judge_check_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^check(\d+)$").expect("判据引用正则固定合法"))
}

/// 真源 `layer_model.load`：缺件/schema 不符 → 带修复指引的错误（不静默降级）。
pub(crate) fn load(root: &Path) -> Result<Json, String> {
    let path = root.join(DECL_REL);
    if !path.is_file() {
        return Err(format!(
            "缺阶梯真源 {}（修复指引：先落该件再跑 nf layers --verify）",
            DECL_REL
        ));
    }
    let text = std::fs::read_to_string(&path)
        .map_err(|e| format!("阶梯真源 {} 读取失败：{}", DECL_REL, e))?;
    let raw: serde_json::Value = serde_json::from_str(&text).map_err(|e| {
        // 真源把 json.JSONDecodeError 的文本拼进消息——**该措辞不做逐字节承诺**
        format!(
            "阶梯真源 {} 不是合法 JSON：{}（修复指引：修 JSON 语法后重跑）",
            DECL_REL, e
        )
    })?;
    let doc = jsonread::convert(&raw).map_err(|e| {
        format!(
            "阶梯真源 {} 含不支持的值：{}（修复指引：修 JSON 语法后重跑）",
            DECL_REL, e
        )
    })?;
    if py_str(get(&doc, "schema")) != SCHEMA {
        return Err(format!(
            "阶梯真源 schema 不匹配（期望 {}；修复指引：核对 schema 字段）",
            SCHEMA
        ));
    }
    Ok(doc)
}

/// 一次扫描内的 glob 展开上下文（**两层缓存**，与真源 `_expand_many` 同构）：
/// ① 每个子树只枚举一次文件清单；② 每个 pattern 的匹配结果复用。
///
/// **实测依据**（2026-10-03）：无缓存时本面反而比 Python 慢 1.5×（1280 ms vs 857 ms）——
/// `layers` 会对同一批 glob 反复展开（L1/L2/L3 各阶 + L6 + L9），`community/**/*` 那类大树
/// 被整棵重走多次。加缓存后同机复测见 README。
pub(crate) struct GlobCtx {
    pub(crate) root: std::path::PathBuf,
    pub(crate) patterns: HashMap<String, BTreeSet<String>>,
    pub(crate) cache: glob::Cache,
}

impl GlobCtx {
    pub(crate) fn new(root: &Path) -> Self {
        Self {
            root: root.to_path_buf(),
            patterns: HashMap::new(),
            cache: glob::Cache::new(),
        }
    }

    pub(crate) fn one(&mut self, pattern: &str) -> BTreeSet<String> {
        if let Some(hit) = self.patterns.get(pattern) {
            return hit.clone();
        }
        let got: BTreeSet<String> = self.cache.expand(&self.root, pattern).into_iter().collect();
        self.patterns.insert(pattern.to_string(), got.clone());
        got
    }

    pub(crate) fn many(&mut self, globs: Option<&Json>) -> BTreeSet<String> {
        let mut out = BTreeSet::new();
        for g in arr_items(globs) {
            out.extend(self.one(&plain_str(g)));
        }
        out
    }
}

/// 真源 `_exists`：`(Path(root)/str(rel)).exists()`（目录也算存在）。
pub(crate) fn exists(root: &Path, rel: Option<&Json>) -> bool {
    root.join(plain_str_opt(rel)).exists()
}

pub(crate) fn ids_of(items: &[&Json]) -> Vec<String> {
    items.iter().map(|t| plain_str_opt(get(t, "id"))).collect()
}

// ---------------------------------------------------------------- L1–L10

pub(crate) fn rule_issues(root: &Path, doc: &Json) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    let mut ctx = GlobCtx::new(root);
    let tiers = arr_items(get(doc, "tiers"));
    let tier_ids = ids_of(&tiers);

    // ---- L1 真源在位
    l1_issues(root, doc, &tiers, &tier_ids, &mut ctx, &mut issues);

    // ---- 派生物（L2/L3 已扣除）
    l2l3_issues(doc, &tiers, &tier_ids, &mut ctx, &mut issues);

    // ---- L4 依赖向下无环
    l4_issues(&tiers, &tier_ids, &mut issues);

    // ---- L5 入口面只登记角色
    l5_issues(doc, &tier_ids, &mut issues);

    // ---- L6 引擎不反向 import 入口面
    l6_issues(root, &mut ctx, &mut issues);

    // ---- L7 退役阶不被依赖
    l7_issues(doc, &tiers, &mut issues);

    // ---- L8 judged_by 可解析
    l8_issues(root, doc, &tiers, &mut issues);

    // ---- L9 豁免诚实
    for pattern in arr_items(get(doc, "derived")) {
        if ctx.one(&plain_str(pattern)).is_empty() {
            issues.push(format!(
                "L9 derived 条目命中零文件：{}（修复指引：删掉该豁免或修正 glob）",
                plain_str(pattern)
            ));
        }
    }

    // ---- L10 生成区 == 实时渲染
    l10_issues(root, doc, &mut issues);

    issues
}

/// L1：真源面 / 资产子级 / 入口面 / 纵切件在位。
pub(crate) fn l1_issues(
    root: &Path,
    doc: &Json,
    tiers: &[&Json],
    tier_ids: &[String],
    ctx: &mut GlobCtx,
    issues: &mut Vec<String>,
) {
    for tier in tiers {
        let src = get(tier, "source");
        let globs = src.and_then(|s| get(s, "globs"));
        let face = ctx.many(globs);
        if arr_items(globs).is_empty() {
            issues.push(format!(
                "L1 阶 {} 未声明真源面（修复指引：在 source.globs 写明真源落点）",
                plain_str_opt(get(tier, "id"))
            ));
        } else if face.is_empty() {
            issues.push(format!(
                "L1 阶 {} 的真源面展开为空：{}（修复指引：核对 globs 与实况）",
                plain_str_opt(get(tier, "id")),
                plain_str_opt(globs)
            ));
        }
    }
    for lv in arr_items(get(doc, "asset_levels")) {
        if ctx.many(get(lv, "globs")).is_empty() {
            issues.push(format!(
                "L1 资产子级 {} 的真源面为空：{}（修复指引：核对 globs）",
                plain_str_opt(get(lv, "id")),
                plain_str_opt(get(lv, "globs"))
            ));
        }
        if !tier_ids.contains(&py_str(get(lv, "tier"))) {
            issues.push(format!(
                "L1 资产子级 {} 的 tier 不在阶名单：{}（修复指引：改成真实阶 id）",
                plain_str_opt(get(lv, "id")),
                plain_str_opt(get(lv, "tier"))
            ));
        }
    }
    for sf in arr_items(get(doc, "surfaces")) {
        for rel in arr_items(get(sf, "entries")) {
            if !exists(root, Some(rel)) {
                issues.push(format!(
                    "L1 入口面 {} 的入口件不存在：{}（修复指引：补件或改成真实路径）",
                    plain_str_opt(get(sf, "id")),
                    plain_str(rel)
                ));
            }
        }
    }
    for comp in arr_items(get(doc, "crosscut").and_then(|c| get(c, "components"))) {
        if !exists(root, get(comp, "artifact")) {
            issues.push(format!(
                "L1 纵切件 {} 不存在：{}（修复指引：补件或改成真实路径）",
                plain_str_opt(get(comp, "id")),
                plain_str_opt(get(comp, "artifact"))
            ));
        }
    }
}

/// L2 归属互斥（派生物已扣除）+ L3 接口面须为真源面子集。
pub(crate) fn l2l3_issues(
    doc: &Json,
    tiers: &[&Json],
    tier_ids: &[String],
    ctx: &mut GlobCtx,
    issues: &mut Vec<String>,
) {
    let derived = ctx.many(get(doc, "derived"));

    // ---- L2 归属互斥（派生物已扣除）
    let mut faces: HashMap<String, BTreeSet<String>> = HashMap::new();
    for tier in tiers {
        let tid = plain_str_opt(get(tier, "id"));
        let face = ctx.many(get(tier, "source").and_then(|s| get(s, "globs")));
        let diff: BTreeSet<String> = face.difference(&derived).cloned().collect();
        faces.insert(tid, diff);
    }
    for i in 0..tier_ids.len() {
        for b in tier_ids.iter().skip(i + 1) {
            let a = &tier_ids[i];
            let empty = BTreeSet::new();
            let fa = faces.get(a).unwrap_or(&empty);
            let fb = faces.get(b).unwrap_or(&empty);
            let overlap: Vec<&String> = fa.intersection(fb).collect();
            if !overlap.is_empty() {
                let head: Vec<String> = overlap.iter().take(3).map(|s| (*s).clone()).collect();
                issues.push(format!(
                    "L2 阶 {} 与阶 {} 真源面重叠：{}（修复指引：把件归给唯一一阶，或把派生物登记进 derived）",
                    a,
                    b,
                    head.join("、")
                ));
            }
        }
    }

    // ---- L3 接口面 ⊆ 真源面
    for tier in tiers {
        let tid = plain_str_opt(get(tier, "id"));
        let iface = ctx.many(get(tier, "interface").and_then(|s| get(s, "globs")));
        if iface.is_empty() {
            issues.push(format!(
                "L3 阶 {} 未声明接口面（修复指引：在 interface.globs 写明跨阶可依赖面）",
                tid
            ));
        }
        let empty = BTreeSet::new();
        let base = faces.get(&tid).unwrap_or(&empty);
        let stray: Vec<String> = iface
            .difference(base)
            .filter(|r| !derived.contains(*r))
            .take(3)
            .cloned()
            .collect();
        if !stray.is_empty() {
            issues.push(format!(
                "L3 阶 {} 接口面超出真源面：{}（修复指引：接口必须是真源面的子集）",
                tid,
                stray.join("、")
            ));
        }
    }
}

/// L4：依赖方向向下且无环。
pub(crate) fn l4_issues(tiers: &[&Json], tier_ids: &[String], issues: &mut Vec<String>) {
    let mut order: HashMap<String, i64> = HashMap::new();
    for t in tiers {
        let o = match get(t, "order") {
            Some(Json::Int(i)) => *i,
            _ => 99,
        };
        order.insert(plain_str_opt(get(t, "id")), o);
    }
    for tier in tiers {
        let tid = plain_str_opt(get(tier, "id"));
        for dep in arr_items(get(tier, "depends_on")) {
            let dep = plain_str(dep);
            match order.get(&dep) {
                None => issues.push(format!(
                    "L4 阶 {} 依赖了不存在的阶：{}（修复指引：改成真实阶 id）",
                    tid, dep
                )),
                Some(od) => {
                    let own = *order.get(&tid).unwrap_or(&99);
                    if *od >= own {
                        issues.push(format!(
                            "L4 阶 {} 依赖方向不向下：{}（order {} ≥ 自身 {}；修复指引：依赖只能指向更下位的阶）",
                            tid, dep, od, own
                        ));
                    }
                }
            }
        }
    }
    let mut graph: HashMap<String, Vec<String>> = HashMap::new();
    for t in tiers {
        graph.insert(
            plain_str_opt(get(t, "id")),
            arr_items(get(t, "depends_on"))
                .iter()
                .map(|d| plain_str(d))
                .collect(),
        );
    }
    let mut walker = CycleWalker {
        order: &order,
        graph: &graph,
        walked: HashSet::new(),
        reported: HashSet::new(),
        issues,
    };
    for tid in tier_ids {
        walker.walk(tid, &[]);
    }
}

/// L5：入口面只登记角色（is_source_of_truth 恒 false；serves 指向在册阶）。
pub(crate) fn l5_issues(doc: &Json, tier_ids: &[String], issues: &mut Vec<String>) {
    for sf in arr_items(get(doc, "surfaces")) {
        if !matches!(get(sf, "is_source_of_truth"), Some(Json::Bool(false))) {
            issues.push(format!(
                "L5 入口面 {} 的 is_source_of_truth 必须为 false（修复指引：入口是角色，真源只能是四阶）",
                plain_str_opt(get(sf, "id"))
            ));
        }
        for served in arr_items(get(sf, "serves")) {
            if !tier_ids.contains(&plain_str(served)) {
                issues.push(format!(
                    "L5 入口面 {} 的 serves 指向不存在的阶：{}（修复指引：改成真实阶 id）",
                    plain_str_opt(get(sf, "id")),
                    plain_str(served)
                ));
            }
        }
    }
}
