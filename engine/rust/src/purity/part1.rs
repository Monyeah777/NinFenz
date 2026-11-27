use super::*;

pub(crate) const PROTO_DOCS: [&str; 4] = [
    "01_核心协议.md",
    "02_联动注册表.md",
    "06_Agent执行协议.md",
    "07_官方核心出厂与社区预设导航.md",
];

/// 真源 `IMPORT_SCAN`（R5 的取件面）。
pub(crate) const IMPORT_SCAN: [&str; 3] = [
    "desktop/src/core/*.py",
    "scripts/*.py",
    ".github/scripts/*.py",
];

/// 真源 `core/domain_neutral.FACE`（R8 的被扫面）。
pub(crate) const DOMAIN_FACE: [&str; 2] = ["03_管线库/**/*.md", "04_模块库/**/*.md"];

/// 真源 `core/domain_neutral.DOMAIN_TERMS`（顺序即判定序：最左优先、同位置按表序取首个）。
pub(crate) const DOMAIN_TERMS: [&str; 28] = [
    "叙事",
    "叙述",
    "故事",
    "剧情",
    "主角",
    "玩家",
    "NPC",
    "台词",
    "情感",
    "情绪",
    "好感",
    "冲动",
    "遗憾",
    "幽灵",
    "战斗",
    "魔法",
    "校园",
    "西幻",
    "文风",
    "白描",
    "恋爱",
    "悬疑",
    "恐怖",
    "情书",
    "情敌",
    "角色卡",
    "人物卡",
    "三冲动",
];

/// 真源 `HARD_ALLOW`：登记的第三方硬依赖（允许直接 import）。
pub(crate) const HARD_ALLOW: [&str; 1] = ["yaml"];

/// 真源 `SOFT_IMPORTS`：第三方可选依赖（须 try/except ImportError 守卫）。值只用于消息。
pub(crate) const SOFT_IMPORTS: [(&str, &str); 6] = [
    (
        "numpy",
        "水印鲁棒性基准（watermark_bench）里按像素构造噪声/亮度攻击；软导入 + 缺依赖给修复指引",
    ),
    (
        "PIL",
        "标注水印层（label_watermark）读写 PNG 位图；软导入 + 缺依赖给修复指引",
    ),
    (
        "jsonschema",
        "IDL 标准实现交叉验证（可选对照；缺依赖则跳过该面）",
    ),
    (
        "PySide6",
        "CCV3 卡面占位图写入（缺依赖须给明确修复指引，不得裸 ImportError）",
    ),
    (
        "nf_pyengine",
        "PyO3 扩展为可选进程内原语加速；缺扩展时 rust_pyext 回退 hashlib/repr",
    ),
    (
        "laya",
        "决策层本地服务（scripts/serve_decision_model.py）的模型运行时；软导入 + 缺依赖给修复指引",
    ),
];

/// 真源 `IMPORT_RESIDUE`（空表 = 零残留）。
pub(crate) const IMPORT_RESIDUE: [(&str, &str); 0] = [];

/// 真源 `DANGEROUS_CALLS`（键 = 规范化调用名；值 = CWE 对齐说明）。
pub(crate) const DANGEROUS_CALLS: [(&str, &str); 12] = [
    ("eval", "CWE-95 动态执行（输入可注入）"),
    ("exec", "CWE-95 动态执行（输入可注入）"),
    ("__import__", "CWE-470 动态导入（须证明模块名非用户输入）"),
    ("os.system", "CWE-78 shell 命令（改用 subprocess 列表参数）"),
    ("os.popen", "CWE-78 shell 管道（改用 subprocess 列表参数）"),
    ("pickle.load", "CWE-502 不安全反序列化（可执行任意代码）"),
    ("pickle.loads", "CWE-502 不安全反序列化（可执行任意代码）"),
    ("marshal.loads", "CWE-502 不安全反序列化"),
    (
        "yaml.load",
        "CWE-502 非安全 YAML 载入（改用 yaml.safe_load）",
    ),
    (
        "shutil.rmtree",
        "CWE-73 递归删除外部可控路径（须证明落点非主目录/仓库根/盘根）",
    ),
    (
        "os.remove",
        "CWE-73 删除外部可控路径（须证明来源不可被外部左右）",
    ),
    ("os.rmdir", "CWE-73 删除外部可控目录"),
];

/// 真源 `METHOD_SINKS`（按**方法名**匹配，避免随接收者变量名漂移）。
pub(crate) const METHOD_SINKS: [(&str, &str); 1] = [(
    "unlink",
    "CWE-73 删除外部可控文件（`Path.unlink` 等价 `os.remove`，同样须证明来源不可被外部左右）",
)];

/// 真源 `SINK_ALLOW`（键 = `<文件基名>:<调用名>`；放行须可审计）。值不参与判据，只作留档。
/// 顺序与真源 `purity_scan.SINK_ALLOW` 逐条同序（2026-10-19：补 `scratch.py` 的两条豁免，
/// 该模块是 2026-10-19 新增的临时区单一裁决点，Python 侧已登记「探针自清 / 整目录回收」）。
pub(crate) const SINK_ALLOW: [(&str, &str); 16] = [
    ("rust_engine.py:unlink", ""),
    // 快照互斥锁自清：只删 .worktrees/gate-snap/.snapshot.lock（本模块自己写的锁），
    // 落点由 snapshot_base 单源决定、删前核对 pid/年龄；与真源 `purity_scan.SINK_ALLOW` 同步。
    ("release_conclusion.py:unlink", ""),
    ("release_conclusion.py:shutil.rmtree", ""),
    ("regression_score.py:__import__", ""),
    ("e2e_desktop_headless.py:shutil.rmtree", ""),
    ("storage.py:shutil.rmtree", ""),
    ("watch.py:os.rmdir", ""),
    // 2026-10-15（门禁提速批）：`core/gate_inproc.py` 的进程内 heredoc 执行面——
    // 源码字符串由该模块自己从本仓 `verify.sh` 机械切出，不来自任何外部输入；
    // 理由是「省掉 heredoc 的解释器启动税」，等价性由 Python 侧
    // `tests/test_gate_engine_parity.py` 逐 check 差分守住。与真源同步见 `purity_scan.SINK_ALLOW`。
    ("gate_inproc.py:exec", ""),
    ("disk_cache.py:unlink", ""),
    ("scratch.py:unlink", ""),
    ("scratch.py:shutil.rmtree", ""),
    ("atomic_write.py:unlink", ""),
    ("domain_pack.py:unlink", ""),
    ("pack_combo.py:unlink", ""),
    ("storage.py:unlink", ""),
    ("watch.py:unlink", ""),
];

pub(crate) fn end_shell_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"(?i)(android|APK|src/ui|Kivy)").expect("固定合法"))
}

pub(crate) fn private_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"[A-Za-z]:\\|/tmp/|/Users/|/home/|TODO|FIXME|XXX|TBD").expect("固定合法")
    })
}

pub(crate) fn head_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^#{1,6}\s+(.*?)\s*$").expect("固定合法"))
}

pub(crate) fn action_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(
            r"(应|须|先|必填|必需|必须|请|建议|参考|查看|运行|执行|使用|改用|替换|修复|补齐|重新|重跑|更正|核对|检查|可选|选项|列表|注册|示例|格式|参见|见|按|需|选择|可用|如|缺少|缺|期望|修正|§|文档|帮助|重试|再)",
        )
        .expect("固定合法")
    })
}

/// 真源 `_NEEDS_AST` 的文本预筛：不命中即三类事实必然为空，连 parse 都不做。
pub(crate) fn needs_ast_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        let tails: Vec<String> = DANGEROUS_CALLS
            .iter()
            .map(|(c, _)| regex::escape(c.rsplit('.').next().unwrap_or(c)))
            .collect();
        regex::Regex::new(&format!(r"raise|import|try|shell|{}", tails.join("|")))
            .expect("固定合法")
    })
}

pub(crate) fn cwe_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^CWE-\d+ ").expect("固定合法"))
}

/// Python 的 `list[:n]`（**按字符**截断）。
pub(crate) fn head_chars(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

/// 真源 `_doc_facts` → `(端壳命中, 私货命中, 重复标题)`。
pub(crate) struct DocFacts {
    pub shell: Vec<(u32, String)>,
    pub private: Vec<(u32, String)>,
    /// **插入序**（首次出现顺序），值是该标题出现的行号。
    pub dup_titles: Vec<(String, Vec<u32>)>,
}

pub(crate) fn doc_facts(text: &str) -> DocFacts {
    let mut shell = Vec::new();
    let mut private = Vec::new();
    let mut seen: Vec<(String, Vec<u32>)> = Vec::new();
    for (i, ln) in text.lines().enumerate() {
        let i = i as u32 + 1;
        if end_shell_re().is_match(ln) {
            shell.push((i, head_chars(ln.trim(), 80)));
        }
        if private_re().is_match(ln) {
            private.push((i, head_chars(ln.trim(), 80)));
        }
        if let Some(c) = head_re().captures(ln) {
            let title = c[1].trim().to_string();
            match seen.iter_mut().find(|(t, _)| *t == title) {
                Some((_, v)) => v.push(i),
                None => seen.push((title, vec![i])),
            }
        }
    }
    let dup_titles = seen.into_iter().filter(|(_, v)| v.len() > 1).collect();
    DocFacts {
        shell,
        private,
        dup_titles,
    }
}

/// 真源 `_is_local`。
pub(crate) fn is_local(mod_: &str, root: &Path) -> bool {
    if mod_ == "core" {
        return true;
    }
    for base in ["desktop/src/core", "scripts", ".github/scripts"] {
        if root.join(base).join(format!("{}.py", mod_)).exists() {
            return true;
        }
    }
    false
}

/// 单份源码的 R4–R6 findings。
pub(crate) struct FileFindings {
    pub issues: Vec<String>,
    pub raises: i64,
    pub imports: i64,
    pub sinks: i64,
    pub residue: Vec<String>,
}

/// 真源 `_file_findings`。`None` 表示事实不可得（未命中预筛 / 解析失败）——与真源一致，
/// 此时该件贡献空结论。
pub(crate) fn file_findings(rel: &str, text: &str, root: &Path) -> Option<FileFindings> {
    if !needs_ast_re().is_match(text) {
        return None;
    }
    let facts = pyast::purity_facts(text)?;
    let fname = rel.rsplit('/').next().unwrap_or(rel);
    let residue: Option<&str> = IMPORT_RESIDUE
        .iter()
        .find(|(r, _)| *r == rel)
        .map(|(_, v)| *v);
    let mut out: Vec<String> = Vec::new();
    let mut delta = FileFindings {
        issues: Vec::new(),
        raises: 0,
        imports: 0,
        sinks: 0,
        residue: Vec::new(),
    };

    raise_findings(&facts, fname, &mut out, &mut delta.raises);
    check_imports(rel, &facts, root, residue, &mut out, &mut delta.imports);
    for s in &facts.sinks {
        sink_findings(s, rel, fname, &mut out, &mut delta.sinks);
    }
    delta.issues = out;
    Some(delta)
}

/// raise 面：消息必须带修复指引。
fn raise_findings(facts: &pyast::PurityFacts, fname: &str, out: &mut Vec<String>, raises: &mut i64) {
    for r in &facts.raises {
        *raises += 1;
        if !r.msg.is_empty() && !action_re().is_match(&r.msg) {
            out.push(format!(
                "{}:{} raise 消息缺修复指引：{}",
                fname,
                r.lineno,
                head_chars(&r.msg, 60)
            ));
        }
    }
}

/// 单条 sink：危险调用 / 方法 sink / shell=True；白名单登记可豁免。
fn sink_findings(s: &pyast::SinkFact, rel: &str, fname: &str, out: &mut Vec<String>, sinks: &mut i64) {
    {
        let mut flags: Vec<(String, String)> = Vec::new();
        if DANGEROUS_CALLS.iter().any(|(c, _)| *c == s.call) {
            flags.push((s.call.clone(), s.call.clone()));
        }
        let method = s.call.rsplit('.').next().unwrap_or(&s.call).to_string();
        if METHOD_SINKS.iter().any(|(m, _)| *m == method) {
            flags.push((method.clone(), method.clone()));
        }
        if s.shell_true {
            flags.push((
                "subprocess(shell=True)".to_string(),
                "subprocess".to_string(),
            ));
        }
        for (name, key_name) in flags {
            *sinks += 1;
            if SINK_ALLOW
                .iter()
                .any(|(k, _)| *k == format!("{}:{}", fname, key_name))
            {
                continue;
            }
            let why = DANGEROUS_CALLS
                .iter()
                .find(|(c, _)| *c == s.call)
                .map(|(_, d)| (*d).to_string())
                .or_else(|| {
                    METHOD_SINKS
                        .iter()
                        .find(|(m, _)| *m == method)
                        .map(|(_, d)| (*d).to_string())
                })
                .unwrap_or_else(|| "shell=True 命令注入面".to_string());
            out.push(format!(
                "{}:{} 危险 sink {}（{}）——确需使用须在 purity_scan.SINK_ALLOW 登记理由（修复指引：改用安全等价物，或登记后写明为何不可注入）",
                rel, s.lineno, name, why
            ));
        }
    }
}
