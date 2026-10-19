//! 演练保真度**量化**（`drill_fidelity`）—— 与真源逐字对账。
//!
//! 真源三个件（本模块一并移植，均在模块头注明）：
//! - `desktop/src/core/drill_fidelity.py` —— `measure` / `scan`（外层判据）
//! - `desktop/src/core/execution_drill.py` —— `run_case`（句子级硬断言 R1–R4）
//! - `desktop/src/core/round_drill.py` —— `scan`（回合级断言 R-R1–R-R4）
//!
//! 判据：逐个执行演练集跑 `run_case`，要求「捕获无漏报（`expect_captured ⊆ hits`）+
//! guard 无误报（无期望命中时不得有命中）」；逐个回合样本回放，要求实测 verdict 复现样本声明
//! （`good → conformant` / `bad → non-conformant`）；**找不到用例/样本 = FAIL**（标准不得无载体）。
//! 保真度 = 通过例数 / 总例数，`round(x, 4)`（CPython 半偶舍入，走 `pyfloat::round_to`）。
//!
//! 移植面：只做 `scan`。真源的 `write` 是**写面**（落 `protocol/drill_fidelity.json`），本线不碰；
//! `main()` 是 CLI 入口，无判据消费者。故 `measure` 只按 `scan` 要用的字段取材。
//!
//! ## 已知偏差（无法逐字比对，单列说明）
//!
//! 1. **坏 JSON 的异常文本**：真源 `except ValueError as exc` 把 CPython 的
//!    `JSONDecodeError` 原文（如 `Expecting value: line 1 column 1 (char 0)`）拼进 issue；
//!    本线措辞自拟（`…不是合法 JSON：（本线不复刻 CPython 解析器原文，见模块头）`）。
//!    **两侧都判 FAIL**，只是文本不同。真语料上所有夹具件均可解析；分支夹具里的坏 JSON 因此
//!    只断言 issue 前缀（`bad_json_*_needs_a_self_authored_prefix`），不伪造真源文本。
//! 2. **JSON 合法但非对象**（如顶层是 `[]`）：真源 `data.get(...)` 抛 `AttributeError` ⇒ 整条判据
//!    记 **ERROR**；本线把该件当作「无 cases / 无样本」继续 ⇒ 记 **FAIL**。两侧都是红的，
//!    但状态不同。这与 `modeling` 的未登记 `python_attr` 是同一类偏差。
//! 3. **`cases`/`allowed` 显式为 `null`**：真源 `for case in None` 抛 `TypeError` ⇒ ERROR；
//!    本线按空集处理 ⇒ FAIL。
//! 4. **Unicode 数字的回合号**：Python `int("٣")` 得 3；本线 `parse::<i64>()` 只吃 ASCII 数字，
//!    解析失败按 0 计。真语料为 ASCII。
//! 5. **真实语料命中裁定（2026-10-20 加，真源 `real_corpus`）**：真源把唯一真实战例
//!    `docs/完整版样本_西幻生存流P03.md` 逐非空行回放 `execution_drill`，并要求逐条 TP/FP 裁定
//!    （`real_corpus.adjudications`）；本线**只移植 `scan`**（写面/度量面不移植，见本模块头），
//!    故 `real_corpus` 的命中裁定门与 `metrics` 只在真源侧执行。两侧在真语料上的 `scan`
//!    （issues/stats）仍逐字一致；语料裁定漂移时只有真源报 FAIL——这是**有意的不对称**，
//!    不是静默：真源 `scan` 的 issues 里会多出「真实语料裁定：…」条目。
//! 6. **待裁定样本**（`verdict`/`label_status` = `pending`，2026-10-20 加）：两侧同口径——
//!    不参与「声明 vs 实测」分子分母，但必须解析出回合标记（`turns > 0`），否则 FAIL。

use crate::jsonread;
use crate::pyjson::Json;
use crate::pyval::{arr_items, get, plain_str_opt, py_str};
use std::collections::BTreeSet;
use std::path::Path;

pub const EXEC_GLOB: &str = "desktop/tests/fixtures/execution/p*_drill_cases.json";
pub const ROUND_GLOB: &str = "desktop/tests/fixtures/execution/rounds/*.json";


/// 真源 `VERDICT_MAP`：样本侧写 good/bad，drill 侧吐 conformant/non-conformant。
fn verdict_map(s: &str) -> Option<&'static str> {
    match s {
        "good" | "conformant" => Some("conformant"),
        "bad" | "non-conformant" => Some("non-conformant"),
        _ => None,
    }
}

// ============================================================ execution_drill（句子级）

/// 真源 `_MODULE_TOKEN`：`(?:[\u4e00-\u9fff]+:)?M\d{2,3}`。
/// Rust `regex` 的 `\d` 与 Python `re` 一样是 Unicode 十进制类（`\p{Nd}`），故不必改写。
fn module_token_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"(?:[\x{4e00}-\x{9fff}]+:)?M\d{2,3}").expect("模块号正则固定合法")
    })
}

/// 真源 `execution_drill._DECISION_WORDS`（缺省中文；用例可在 fixture 的 lexicon 里覆盖）。
const EXEC_DECISION: [&str; 8] = ["应", "应该", "必须", "禁止", "不得", "下一步", "输出", "结论"];

/// 真源 `execution_drill._DECISION_GLUE`：单字判定词的构词排除表（(词, (前字集, 后字集))）。
/// 真实语料实测：`元素反应`/`对应件`/`应用` 里的 `应` 不是「应当」义。
const EXEC_DECISION_GLUE: [(&str, (&str, &str)); 1] = [(
    "应",
    ("反对适响供效相顺答呼照策接报感", "用急对变聘邀酬届试运付缴纳计答战征招"),
)];

/// 真源 `execution_drill._ASSERT_ABSENT_CUES`：编号断言的否定语境谓词。
/// **只认显式谓词**（不做「句内有『不』就豁免」的粗口径，否则真失范会被误豁免）。
const ASSERT_ABSENT_CUES: [&str; 22] = [
    "不命中", "未命中", "不适用", "不含", "不包含", "未包含", "不参与", "未参与", "不涉及",
    "未涉及", "未采用", "未使用", "不使用", "不得使用", "禁止使用", "不挂载", "未挂载",
    "不纳入", "未纳入", "跳过", "已移除", "未生效",
];

/// 真源 `execution_drill._ASSERT_HISTORY_CUES`：编号断言的历史语境谓词。
const ASSERT_HISTORY_CUES: [&str; 13] = [
    "曾", "此前", "上一版", "旧版", "历史", "原编号", "旧编号", "残留", "遗留", "已废弃",
    "已下线", "已迁移", "旧名",
];

/// 真源 `_ASSERT_CTX_BEFORE` / `_ASSERT_CTX_AFTER`（单位：**码点**，与 Python 切片一致）。
const ASSERT_CTX_BEFORE: usize = 10;
const ASSERT_CTX_AFTER: usize = 14;

/// 真源 `execution_drill._CITATION`。
fn citation_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(
            r"(§\s*\d+(?:[.-]\d+)*|第\s*\d+\s*(?:节|步|章)|L\d+|行号|[0-9A-Za-z_]+:[MTP]\d{2,3}|/\d+|\b\d{1,3}\b\s*行)",
        )
        .expect("引用正则固定合法")
    })
}

/// 真源 `round_drill._CITE`（**与 `execution_drill._CITATION` 不同**：无 `行号`、无 `/数字`——不可合并）。
fn round_cite_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(
            r"(§\s*\d+(?:[.-]\d+)*|第\s*\d+\s*(?:节|步|章)|L\d+|[0-9A-Za-z_]+:[MTP]\d{2,3}|\b\d{1,3}\b\s*行)",
        )
        .expect("回合引用正则固定合法")
    })
}

fn split_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"[。！？；\n]+").expect("分句正则固定合法"))
}

fn ws_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"\s+").expect("空白正则固定合法"))
}

/// 真源 `execution_drill._PROGRESS`。
const EXEC_PROGRESS: [&str; 6] = [
    "回合推进",
    "进入回合",
    "已进入第",
    "时间推进",
    "推进至",
    "进入下一回合",
];

/// 真源 `round_drill._PROGRESS`（**与 `execution_drill` 不同**——不可合并）。
const ROUND_PROGRESS: [&str; 7] = ["推进", "进入", "写回", "快照", "存档", "状态", "回合"];

/// 真源 `_bigrams`：去空白后取**码点**二元组；不足两个码点时返回「整串」单元素集。
fn bigrams(text: &str) -> BTreeSet<String> {
    let flat: Vec<char> = ws_re().replace_all(text, "").chars().collect();
    let mut out: BTreeSet<String> = BTreeSet::new();
    if flat.len() >= 2 {
        for i in 0..flat.len() - 1 {
            out.insert(flat[i..i + 2].iter().collect());
        }
    }
    if out.is_empty() {
        out.insert(flat.iter().collect());
    }
    out
}

fn mention_tokens(output: &str) -> Vec<String> {
    module_token_re().find_iter(output).map(|m| m.as_str().to_string()).collect()
}

/// 真源 `execution_drill._id_tokens`：**可作编号断言的**模块号（排除路径/文件名前缀）。
///
/// 真实语料实测（2026-10-20）：唯一真实战例 P03 第 109 行
/// `- 出处：community/西幻生存领域包/modules/M10_死亡重生.md` —— `M10` 是**文件名**的前缀，
/// 旧线照抓并判 `fabricated_id`。Rust `regex` 无 lookaround，故按匹配尾后字符就地过滤：
/// 紧跟 ASCII 标识符字符（`M10_死亡重生`）或 `.<ASCII 扩展名>`（`M10.md`）者不算裸编号断言；
/// 中文紧邻（`M10的`）与列表分隔（`M02/M03`）照常算。
fn exec_id_token_spans(output: &str) -> Vec<(String, usize, usize)> {
    let mut out: Vec<(String, usize, usize)> = Vec::new();
    for m in module_token_re().find_iter(output) {
        let mut it = output[m.end()..].chars();
        if let Some(c) = it.next() {
            if c.is_ascii_alphanumeric() || c == '_' {
                continue;
            }
            if c == '.' {
                if matches!(it.next(), Some(d) if d.is_ascii_alphanumeric()) {
                    continue;
                }
            }
        }
        out.push((m.as_str().to_string(), m.start(), m.end()));
    }
    out
}

/// 真源 `_assertion_context`：取编号前后**同句内**的语境窗（不跨 。！？；换行）。
fn assertion_context(output: &str, start: usize, end: usize) -> (String, String) {
    let before_raw = tail_chars(&output[..start], ASSERT_CTX_BEFORE);
    let before = split_re().split(before_raw).last().unwrap_or("").to_string();
    let after_raw = head_chars(&output[end..], ASSERT_CTX_AFTER);
    let after = split_re().split(after_raw).next().unwrap_or("").to_string();
    (before, after)
}

/// `s` 末尾 `n` 个码点（`n` 超长时取全串）。
fn tail_chars(s: &str, n: usize) -> &str {
    let mut count = 0usize;
    for (i, _) in s.char_indices().rev() {
        count += 1;
        if count == n {
            return &s[i..];
        }
    }
    s
}

/// `s` 开头 `n` 个码点（`n` 超长时取全串）。
fn head_chars(s: &str, n: usize) -> &str {
    match s.char_indices().nth(n) {
        Some((i, _)) => &s[..i],
        None => s,
    }
}

/// 真源 `_is_contextual_mention`：否定/历史语境里的编号提及**不是当前断言**。
fn is_contextual_mention(before: &str, after: &str) -> bool {
    ASSERT_ABSENT_CUES
        .iter()
        .chain(ASSERT_HISTORY_CUES.iter())
        .any(|c| before.contains(c) || after.contains(c))
}

/// 真源 `_has_decision`：判定词命中（**带边界**）——多字词子串；单字词排除构词粘连。
fn has_decision(output: &str, decision: &[String]) -> bool {
    for word in decision {
        if word.chars().count() > 1 {
            if output.contains(word.as_str()) {
                return true;
            }
            continue;
        }
        let Some(first) = word.chars().next() else {
            continue;
        };
        let glue = EXEC_DECISION_GLUE.iter().find(|(w, _)| *w == word.as_str()).map(|(_, g)| *g);
        for (i, ch) in output.char_indices() {
            if ch != first {
                continue;
            }
            let prev = output[..i].chars().next_back();
            let next = output[i + ch.len_utf8()..].chars().next();
            let glued = match glue {
                Some((prev_set, next_set)) => {
                    prev.map(|c| prev_set.contains(c)).unwrap_or(false)
                        || next.map(|c| next_set.contains(c)).unwrap_or(false)
                }
                None => false,
            };
            if !glued {
                return true;
            }
        }
    }
    false
}

/// 真源「_ASSET_TOKEN」：大写下划线资产键（至少一个下划线）。
fn asset_token_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b").expect("资产键正则固定合法")
    })
}

/// 真源 `_clauses`：按 `[。！？；\n]+` 切分并 strip 掉空段。
fn clauses(output: &str) -> Vec<String> {
    split_re()
        .split(output)
        .map(|c| c.trim())
        .filter(|c| !c.is_empty())
        .map(|c| c.to_string())
        .collect()
}

/// 真源「_check_fabricated_id」：本管线真实编号放行；其它管线真实编号判跨管线串号；其余判编造。
///
/// **后缀归一**（2026-10-20 修）：装配真实集写 `通用:M10` / `生存:M10`（重号须类别前缀限定），
/// 执行正文里常写裸 `M10`——旧实现拿整串精确比较 ⇒ 同一模块被判「编造」。
/// 现与 `round_drill.scan`（R-R3）和 `assemble_plan`（决策句编号校验）**同口径**：尾段命中即放行。
fn check_fabricated_id(output: &str, real_ids: &[String], other_ids: &[String]) -> &'static str {
    let real_tails: Vec<String> = real_ids.iter().map(|r| tail_after_colon(r)).collect();
    let other_tails: Vec<String> = other_ids.iter().map(|r| tail_after_colon(r)).collect();
    for (tok, start, end) in exec_id_token_spans(output) {
        let tail = tail_after_colon(&tok);
        if real_ids.iter().any(|r| *r == tok) || real_tails.iter().any(|t| *t == tail) {
            continue;
        }
        let (before, after) = assertion_context(output, start, end);
        if is_contextual_mention(&before, &after) {
            continue;
        }
        if other_ids.iter().any(|r| *r == tok) || other_tails.iter().any(|t| *t == tail) {
            return "cross_pipeline_id";
        }
        return "fabricated_id";
    }
    ""
}

/// 真源「_check_fabricated_asset_key」：仅当给了允许集才判（无允许集不判，防误报）。
fn check_fabricated_asset_key(output: &str, asset_keys: &[String]) -> &'static str {
    if asset_keys.is_empty() {
        return "";
    }
    for m in asset_token_re().find_iter(output) {
        if !asset_keys.iter().any(|k| k == m.as_str()) {
            return "fabricated_asset_key";
        }
    }
    ""
}

/// 真源 `_check_browse_repeat`。
fn check_browse_repeat(output: &str, source_text: &str, progress: &[String]) -> &'static str {
    if source_text.is_empty() || output.chars().count() < 8 {
        return "";
    }
    let src = bigrams(source_text);
    let ob = bigrams(output);
    let inter = ob.intersection(&src).count();
    let overlap = inter as f64 / std::cmp::max(1, src.len()) as f64;
    if overlap >= 0.55 && !progress.iter().any(|p| output.contains(p.as_str())) {
        return "browse_repeat";
    }
    ""
}

/// 真源 `_check_no_citation`。
fn check_no_citation(output: &str, decision: &[String], citation: &regex::Regex) -> &'static str {
    if has_decision(output, decision) && !citation.is_match(output) {
        if mention_tokens(output).is_empty() {
            return "no_citation";
        }
    }
    ""
}

/// 真源 `_check_semantic_misalignment`。
fn check_semantic_misalignment(output: &str, semantics: Option<&Json>) -> &'static str {
    let Some(Json::Object(pairs)) = semantics else {
        return "";
    };
    if pairs.is_empty() {
        return "";
    }
    // `others` 逐 tok 重算（真源如此）；顺序不影响布尔结论。
    let words_of = |v: &Json| -> Vec<String> {
        match v {
            Json::Array(a) => a
                .iter()
                .map(|w| match w {
                    Json::Str(s) => s.clone(),
                    other => plain_str_opt(Some(other)),
                })
                .collect(),
            other => vec![plain_str_opt(Some(other))],
        }
    };
    for clause in clauses(output) {
        for tok in mention_tokens(&clause) {
            let own: Vec<String> = pairs
                .iter()
                .find(|(m, _)| *m == tok)
                .map(|(_, v)| words_of(v))
                .unwrap_or_default();
            if own.is_empty() {
                continue;
            }
            let others: Vec<String> = pairs
                .iter()
                .filter(|(m, _)| *m != tok)
                .flat_map(|(_, v)| words_of(v))
                .collect();
            let has_own = own.iter().any(|w| clause.contains(w.as_str()));
            let has_other = others.iter().any(|w| clause.contains(w.as_str()));
            if has_other && !has_own {
                return "semantic_misalignment";
            }
        }
    }
    ""
}

/// 真源 `execution_drill._compile_citation` + 词表取法 → `(decision, progress, citation)`。
/// 缺省用内置中文词表与单模式；fixture 里的 `lexicon` 按语言覆盖（多语协议执行）。
fn exec_lexicon(lexicon: Option<&Json>) -> (Vec<String>, Vec<String>, regex::Regex) {
    let decision_items = arr_items(lexicon.and_then(|l| get(l, "decision")));
    let progress_items = arr_items(lexicon.and_then(|l| get(l, "progress")));
    let citation_items = arr_items(lexicon.and_then(|l| get(l, "citation")));
    let decision: Vec<String> = if decision_items.is_empty() {
        EXEC_DECISION.iter().map(|s| s.to_string()).collect()
    } else {
        decision_items.iter().map(|v| py_str(Some(v))).collect()
    };
    let progress: Vec<String> = if progress_items.is_empty() {
        EXEC_PROGRESS.iter().map(|s| s.to_string()).collect()
    } else {
        progress_items.iter().map(|v| py_str(Some(v))).collect()
    };
    let citation = if citation_items.is_empty() {
        citation_re().clone()
    } else {
        let joined = citation_items
            .iter()
            .map(|v| format!("(?:{})", py_str(Some(v))))
            .collect::<Vec<String>>()
            .join("|");
        regex::Regex::new(&joined).expect("lexicon.citation 模式须为合法正则")
    };
    (decision, progress, citation)
}


/// 真源 `execution_drill.run_case` → 命中的失范规则名列表（**顺序即判据**）。
fn run_case(case: &Json, real_ids: &[String], semantics: Option<&Json>, source_text: &str,
            other_ids: &[String], asset_keys: &[String], lexicon: Option<&Json>) -> Vec<String> {
    let (decision, progress, citation) = exec_lexicon(lexicon);
    let output = py_str(get(case, "output"));
    let mut hits: Vec<String> = Vec::new();
    let hit = check_fabricated_id(&output, real_ids, other_ids);
    if !hit.is_empty() {
        hits.push(hit.to_string());
    }
    let hit = check_fabricated_asset_key(&output, asset_keys);
    if !hit.is_empty() {
        hits.push(hit.to_string());
    }
    // 真源：`source_text or case.get("source_text", "")`
    let case_src = match get(case, "source_text") {
        Some(v) => py_str(Some(v)),
        None => String::new(),
    };
    let src = if source_text.is_empty() { case_src } else { source_text.to_string() };
    let hit = check_browse_repeat(&output, &src, &progress);
    if !hit.is_empty() {
        hits.push(hit.to_string());
    }
    let hit = check_no_citation(&output, &decision, &citation);
    if !hit.is_empty() {
        hits.push(hit.to_string());
    }
    let hit = check_semantic_misalignment(&output, semantics);
    if !hit.is_empty() {
        hits.push(hit.to_string());
    }
    hits
}

// ============================================================ round_drill（回合级）

fn turn_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"(?m)^[#>\s]*(?:回合\s*(\d+)\s*[:：]|第\s*(\d+)\s*回合)")
            .expect("回合标记正则固定合法")
    })
}

/// 真源 `round_drill.scan` → `(issues, turns, warn_gaps)`。
/// `turns` 对应真源 `stats["turns"]`；`warn_gaps` 对应 `stats["warn_gaps"]`。
fn round_scan(transcript: &str, allowed: &[String]) -> (Vec<String>, i64, Vec<(i64, i64)>) {
    let mut issues: Vec<String> = Vec::new();
    let re = turn_re();

    // 真源按**码点**切片（`transcript[start:end]`），故先把字节偏移映成码点下标。
    let chars: Vec<char> = transcript.chars().collect();
    let mut char_byte: Vec<usize> = Vec::with_capacity(chars.len() + 1);
    let mut b = 0usize;
    for c in &chars {
        char_byte.push(b);
        b += c.len_utf8();
    }
    char_byte.push(b);
    let char_of = |byte: usize| -> usize {
        char_byte.binary_search(&byte).unwrap_or_else(|i| i.min(chars.len()))
    };

    let matches: Vec<(usize, usize, i64)> = re
        .captures_iter(transcript)
        .map(|c| {
            let m = c.get(0).expect("整个匹配必在");
            // 真源 `int(m.group(1) or m.group(2))`：第 1 组未参与则取第 2 组。
            let num = match c.get(1) {
                Some(g) => parse_uint(g.as_str()),
                None => c.get(2).map(|g| parse_uint(g.as_str())).unwrap_or(0),
            };
            (char_of(m.start()), char_of(m.end()), num)
        })
        .collect();

    let mut turns: Vec<(i64, String)> = Vec::new();
    for (i, (_, end, num)) in matches.iter().enumerate() {
        let stop = matches.get(i + 1).map(|(s, _, _)| *s).unwrap_or(chars.len());
        let body: String = chars[*end..stop].iter().collect();
        turns.push((*num, body));
    }

    if turns.is_empty() {
        issues.push("未检测到回合标记（转录需含 回合 N： / 第 N 回合）".to_string());
        return (issues, 0, Vec::new());
    }

    let allowed_set: BTreeSet<String> = allowed.iter().cloned().collect();
    let allowed_tails: BTreeSet<String> = allowed.iter().map(|a| tail_after_colon(a)).collect();
    let mut gaps: Vec<(i64, i64)> = Vec::new();
    for (i, (num, body)) in turns.iter().enumerate() {
        if !round_cite_re().is_match(body) {
            issues.push(format!("第 {} 回合缺引用（R-R1）", num));
        }
        if !ROUND_PROGRESS.iter().any(|k| body.contains(k)) {
            issues.push(format!("第 {} 回合无推进/状态留痕（R-R2）", num));
        }
        for tok in module_token_re().find_iter(body).map(|m| m.as_str().to_string()) {
            if !allowed_set.contains(&tok) && !allowed_tails.contains(&tail_after_colon(&tok)) {
                issues.push(format!("第 {} 回合出现允许集外编号 {}（R-R3）", num, tok));
            }
        }
        if i > 0 && *num != turns[i - 1].0 + 1 {
            gaps.push((turns[i - 1].0, *num));
        }
    }
    (issues, turns.len() as i64, gaps)
}

/// 真源 `s.split(":", 1)[-1]`：无冒号即整串。
fn tail_after_colon(s: &str) -> String {
    match s.split_once(':') {
        Some((_, tail)) => tail.to_string(),
        None => s.to_string(),
    }
}

fn parse_uint(s: &str) -> i64 {
    s.parse::<i64>().unwrap_or(0)
}

// ============================================================ drill_fidelity（外层判据）

struct ExecSet {
    set: String,
    cases: i64,
    passed: i64,
    error: Option<String>,
}

struct RoundSample {
    sample: String,
    declared: String,
    live: String,
    matched: bool,
    first_issue: String,
    /// 真源 `label_status == "pending"` 或 `verdict == "pending"`：未裁定样本。
    pending: bool,
    /// 回合数（parse 成功 ⇔ `turns > 0`；待裁定样本的 parse 是裁定前提）。
    turns: i64,
    /// 样本坏件（真源 `_round_sample` 的 `error` 键）：非空时 `scan` 直接报该条并跳过其余判定。
    error: Option<String>,
}

/// 真源 `_exec_sets`。返回 `(集合, issues)`——坏 JSON 记 issue（措辞自拟，见模块头偏差 1/2）。
fn exec_sets(root: &Path) -> Vec<ExecSet> {
    let mut out: Vec<ExecSet> = Vec::new();
    for rel in crate::glob::expand(root, EXEC_GLOB) {
        let name = rel.rsplit('/').next().unwrap_or(&rel).to_string();
        let Some(data) = jsonread::read_file(root, &rel) else {
            out.push(ExecSet {
                error: Some(format!("JSON 不可解析：（本线不复刻 CPython 解析器原文，见模块头）")),
                set: name,
                cases: 0,
                passed: 0,
            });
            continue;
        };
        if !matches!(data, Json::Object(_)) {
            out.push(ExecSet {
                error: Some("JSON 顶层非对象（真源在此记 ERROR，本线如实报出）".to_string()),
                set: name,
                cases: 0,
                passed: 0,
            });
            continue;
        }
        let real_ids: Vec<String> =
            arr_items(get(&data, "real_ids")).iter().map(|v| py_str(Some(v))).collect();
        let other_ids: Vec<String> =
            arr_items(get(&data, "other_ids")).iter().map(|v| py_str(Some(v))).collect();
        let asset_keys: Vec<String> =
            arr_items(get(&data, "asset_keys")).iter().map(|v| py_str(Some(v))).collect();
        let semantics = get(&data, "semantics");
        let lexicon = get(&data, "lexicon");
        // 真源 `data.get("source_text", "")`：**键不在场**才取默认；在场为 null 则传 None 下去
        let src_opt: Option<&Json> = get(&data, "source_text");
        let src = plain_str_opt(src_opt);
        let mut n = 0i64;
        let mut ok = 0i64;
        for case in arr_items(get(&data, "cases")) {
            if !matches!(case, Json::Object(_)) {
                // 真源 `case.get` 在此抛 AttributeError ⇒ ERROR；本线按「不通过」计，保守侧
                n += 1;
                continue;
            }
            let hits = run_case(case, &real_ids, semantics, &src, &other_ids, &asset_keys, lexicon);
            let expect: Vec<String> =
                arr_items(get(case, "expect_captured")).iter().map(|v| py_str(Some(v))).collect();
            let good = (expect.is_empty() && hits.is_empty())
                || expect.iter().all(|e| hits.iter().any(|h| h == e));
            n += 1;
            if good {
                ok += 1;
            }
        }
        out.push(ExecSet { set: name, cases: n, passed: ok, error: None });
    }
    out
}

/// 真源 `_round_samples`。返回 `(样本, issues)`。
fn round_samples(root: &Path) -> Vec<RoundSample> {
    let mut out: Vec<RoundSample> = Vec::new();
    for rel in crate::glob::expand(root, ROUND_GLOB) {
        let name = rel.rsplit('/').next().unwrap_or(&rel).to_string();
        let declared_of = |d: &Json| -> String {
            // 真源 `VERDICT_MAP.get(str(verdict or "").lower(), str(verdict))`
            let raw = plain_str_opt(get(d, "verdict"));
            let lowered = py_str(get(d, "verdict")).to_lowercase();
            verdict_map(&lowered).map(|s| s.to_string()).unwrap_or(raw)
        };
        let Some(d) = jsonread::read_file(root, &rel) else {
            out.push(RoundSample {
                error: Some(format!(
                    "JSON 不可解析：{} 不是合法 JSON：（本线不复刻 CPython 解析器原文，见模块头）",
                    name
                )),
                sample: name,
                declared: "?".to_string(),
                live: "error".to_string(),
                matched: false,
                pending: false,
                turns: 0,
                first_issue: String::new(),
            });
            continue;
        };
        if !matches!(d, Json::Object(_)) {
            out.push(RoundSample {
                error: Some(format!(
                    "JSON 不可解析：{} 顶层形状不对：（本线不复刻 CPython 解析器原文，见模块头）",
                    name
                )),
                sample: name,
                declared: "?".to_string(),
                live: "error".to_string(),
                matched: false,
                pending: false,
                turns: 0,
                first_issue: String::new(),
            });
            continue;
        }
        let transcript = py_str(get(&d, "transcript"));
        let allowed: Vec<String> =
            arr_items(get(&d, "allowed")).iter().map(|v| py_str(Some(v))).collect();
        let (issues, turns, _gaps) = round_scan(&transcript, &allowed);
        let live = if issues.is_empty() { "conformant" } else { "non-conformant" };
        let declared = declared_of(&d);
        // 真源：`label_status`/`verdict` 为 pending ⇒ 未裁定（不参与「声明 vs 实测」分子分母）。
        let pending = py_str(get(&d, "label_status")).to_lowercase() == "pending"
            || py_str(get(&d, "verdict")).to_lowercase() == "pending";
        out.push(RoundSample {
            sample: name,
            matched: !pending && declared == live,
            declared,
            live: live.to_string(),
            first_issue: issues.first().cloned().unwrap_or_default(),
            pending,
            turns,
            error: None,
        });
    }
    out
}

/// 真源 `round(x, 4) if y else 0.0`（CPython 半偶舍入）。
fn fidelity(pass: i64, total: i64) -> f64 {
    if total == 0 {
        0.0
    } else {
        crate::pyfloat::round_to(pass as f64 / total as f64, 4)
    }
}

/// 真源 `drill_fidelity.scan` → `(issues, warns, stats)`。
pub fn scan(root: &Path) -> (Vec<String>, Vec<String>, Json) {
    let sets = exec_sets(root);
    let samples = round_samples(root);

    let ex_cases: i64 = sets.iter().map(|s| s.cases).sum();
    let ex_pass: i64 = sets.iter().map(|s| s.passed).sum();
    // 待裁定样本（pending）不参与「声明 vs 实测」分子分母（未裁定就无声明可复现），
    // 但必须解析出回合标记——parse 是裁定前提。
    let adjudicated: Vec<&RoundSample> = samples.iter().filter(|s| !s.pending).collect();
    let rnd_total = adjudicated.len() as i64;
    let rnd_pass = adjudicated.iter().filter(|s| s.matched).count() as i64;
    let total = ex_cases + rnd_total;
    let passed = ex_pass + rnd_pass;

    let mut issues: Vec<String> = Vec::new();
    if ex_cases == 0 {
        issues.push(format!(
            "找不到执行演练用例（修复指引：{} 下须有 p*_drill_cases.json）",
            EXEC_GLOB
        ));
    }
    if rnd_total == 0 {
        issues.push(format!(
            "找不到回合级回放样本（修复指引：{} 下须有样本，含 transcript/allowed/verdict）",
            ROUND_GLOB
        ));
    }
    for s in &sets {
        if let Some(e) = &s.error {
            issues.push(format!("{} {}", s.set, e));
        } else if s.passed != s.cases {
            issues.push(format!(
                "执行演练保真度不足：{} {}/{}（修复指引：先修样本集自身或捕获逻辑，演练集不达标不得入库）",
                s.set, s.passed, s.cases
            ));
        }
    }
    for s in &samples {
        if let Some(err) = &s.error {
            issues.push(format!("{} {}", s.sample, err));
            continue;
        }
        if s.pending {
            if s.turns == 0 {
                issues.push(format!(
                    "待裁定回合样本未解析出回合标记：{}（parse 失败 ⇒ 裁定前提不成立；修复指引：转录须含「回合 N：」/「第 N 回合」）",
                    s.sample
                ));
            }
            continue;
        }
        if !s.matched {
            let head: String = s.first_issue.chars().take(60).collect();
            issues.push(format!(
                "回合级回放未复现声明：{} 声明={} 实测={}（{}）（修复指引：修样本或回合断言——回放须可复现声明结论）",
                s.sample, s.declared, s.live, head
            ));
        }
    }

    // 真源 `stats = m["overall"]` 再 update 两个键 ⇒ 键序为 cases/passed/fidelity/exec_sets/round_samples
    let stats = Json::Object(vec![
        ("cases".to_string(), Json::Int(total)),
        ("passed".to_string(), Json::Int(passed)),
        ("fidelity".to_string(), Json::Float(fidelity(passed, total))),
        ("exec_sets".to_string(), Json::Int(sets.len() as i64)),
        // 真源 `stats["round_samples"]` = 样本文件总数（含待裁定样本）；`cases` 只计已裁定样本。
        ("round_samples".to_string(), Json::Int(samples.len() as i64)),
    ]);
    (issues, Vec::new(), stats)
}

#[cfg(test)]
mod tests {
    use super::*;
    // >>> GENERATED by tools/gen_drill_fidelity_branches.py（勿手改；重跑生成器覆盖本段）

    /// ===== 分支级差分判据（期望值由 `tools/gen_drill_fidelity_branches.py` 从真源生成）=====
    ///
    /// 真语料上本面**全绿**（`issues=0`、保真度 1.0）⇒ 对账核不到任何错误分支。本夹具逐分支踩：
    /// 执行演练四条硬断言（`fabricated_id` / `browse_repeat` / `no_citation` /
    /// `semantic_misalignment`）各自的命中与不命中、`expect_captured` 未满足 ⇒ 保真度不足；
    /// 回合级 R-R1 缺引用 / R-R2 无推进 / R-R3 越集（含「带前缀 tok ↔ 无前缀 allowed」同尾豁免）/
    /// 跳号 / 无回合标记；样本声明与实测不一致 ⇒ 未复现声明；找不到用例 / 找不到样本 / 坏 JSON。
    ///
    /// ⚠️ **坏 JSON 的执行集**那条 issue 里含 CPython `JSONDecodeError` 原文，**无法逐字复刻**：
    /// 本判据只断言其前缀（见 `badexec_needs_a_self_authored_prefix`），其余场景逐条全比。
    const DF_EXEC: &str = r#"{"schema": "nf-execution-drill/1", "pipeline": "P01", "real_ids": ["M00", "通用:M10"], "semantics": {"M00": ["装配"], "通用:M10": ["节拍"]}, "source_text": "官方核心装配 P01：由 通用:M10 驱动节拍，事件候选经质量门后生成成品。", "cases": [{"id": "c-fab", "output": "由 M99 完成本条推进。", "expect_captured": ["fabricated_id"]}, {"id": "c-browse", "output": "官方核心装配 P01：由 通用:M10 驱动节拍，事件候选经质量门后生成成品。 就到这里。", "expect_captured": ["browse_repeat"]}, {"id": "c-cite", "output": "结论：应当输出。", "expect_captured": ["no_citation"]}, {"id": "c-sem", "output": "M00 负责节拍。", "expect_captured": ["semantic_misalignment"]}, {"id": "g-progress", "output": "官方核心装配 P01：由 通用:M10 驱动节拍，事件候选经质量门后生成成品。回合推进：已进入第 5 回合。", "expect_captured": []}, {"id": "c-unsat", "output": "干干净净一句话，没有任何失范。", "expect_captured": ["no_citation"]}]}"#;
    const DF_ROUND_GOOD: &str = r#"{"schema": "nf-round-transcript/1", "verdict": "good", "transcript": "回合 1：引用 06 §3 推进，M00 写回 状态快照。\n回合 2：引用 06 §3，通用:M10 输出并进入下一回合。\n", "allowed": ["M00", "通用:M10"]}"#;
    const DF_ROUND_BAD: &str = r#"{"schema": "nf-round-transcript/1", "verdict": "good", "transcript": "回合 1：无引用也无推进。\n回合 3：引用 06 §3 推进，M99 越集。\n", "allowed": ["M00"]}"#;
    const DF_ROUND_NOTURN: &str = r#"{"schema": "nf-round-transcript/1", "verdict": "bad", "transcript": "这里一个回合标记也没有。\n", "allowed": []}"#;
    const DF_ROUND_TAIL: &str = r#"{"schema": "nf-round-transcript/1", "verdict": "good", "transcript": "回合 1：引用 06 §3 推进，M10 写回状态。\n", "allowed": ["通用:M10"]}"#;

    fn build_df_fixture(scenario: &str, exec_doc: Option<&str>,
                        rounds: &[(&str, &str)]) -> std::path::PathBuf {
        let root = crate::testutil::fixture(&format!("drill-fidelity-branches-{}", scenario));
        let base = root.join("desktop/tests/fixtures/execution");
        std::fs::create_dir_all(base.join("rounds")).unwrap();
        if let Some(d) = exec_doc {
            std::fs::write(base.join("p01_drill_cases.json"), d).unwrap();
        }
        for (name, body) in rounds {
            std::fs::write(base.join("rounds").join(name), body).unwrap();
        }
        root
    }

    #[test]
    fn scan_matches_truth_source_branch_by_branch() {
        for (scenario, exec_doc, rounds, want_issues, want_cases, want_passed, want_fid, want_sets, want_rs) in [
            (
                "kitchen",
                Some(DF_EXEC),
                &[
                    ("good.json", DF_ROUND_GOOD),
                    ("bad.json", DF_ROUND_BAD),
                    ("noturn.json", DF_ROUND_NOTURN),
                    ("tail.json", DF_ROUND_TAIL),
                ][..],
                &["执行演练保真度不足：p01_drill_cases.json 5/6（修复指引：先修样本集自身或捕获逻辑，演练集不达标不得入库）", "回合级回放未复现声明：bad.json 声明=conformant 实测=non-conformant（第 1 回合缺引用（R-R1））（修复指引：修样本或回合断言——回放须可复现声明结论）"] as &[&str],
                10,
                8,
                0.8,
                1,
                4,
            ),
            ("empty", None, &[][..], &["找不到执行演练用例（修复指引：desktop/tests/fixtures/execution/p*_drill_cases.json 下须有 p*_drill_cases.json）", "找不到回合级回放样本（修复指引：desktop/tests/fixtures/execution/rounds/*.json 下须有样本，含 transcript/allowed/verdict）"] as &[&str], 0, 0, 0.0, 0, 0),
        ] {
            let root = build_df_fixture(scenario, exec_doc, rounds);
            let (issues, warns, stats) = scan(&root);
            assert_eq!(issues, want_issues, "场景 {} 的 issues", scenario);
            assert!(warns.is_empty(), "本面 warns 恒空");
            let want_stats = crate::jsonread::convert(&serde_json::json!({
                "cases": want_cases, "passed": want_passed,
                "fidelity": want_fid, "exec_sets": want_sets, "round_samples": want_rs
            }))
            .unwrap();
            assert!(
                crate::jsonread::json_eq(&stats, &want_stats),
                "场景 {} 的 stats：实得 {:?}，期望 {:?}",
                scenario,
                stats,
                want_stats
            );
        }
    }

    #[test]
    fn bad_json_round_sample_needs_a_self_authored_prefix() {
        // ⚠️ 已知偏差：真源 issue 尾部含 CPython `JSONDecodeError` 原文（如
        // `Expecting value: line 1 column 13 (char 12)`），本线不复刻 ⇒ 只断言前缀，
        // 与 `badexec_needs_a_self_authored_prefix` 同一口径。
        let root = build_df_fixture("badround", None, &[("bad.json", "{ \"broken\": ")]);
        let (issues, _w, stats) = scan(&root);
        assert_eq!(issues.len(), 2, "{:?}", issues);
        assert!(issues[0].starts_with("找不到执行演练用例"), "{}", issues[0]);
        assert!(issues[1].starts_with("bad.json JSON 不可解析："), "{}", issues[1]);
        assert!(crate::jsonread::json_eq(
            &stats,
            &crate::jsonread::convert(&serde_json::json!({
                "cases": 1, "passed": 0, "fidelity": 0.0, "exec_sets": 0, "round_samples": 1
            }))
            .unwrap()
        ));
    }

    #[test]
    fn badexec_needs_a_self_authored_prefix() {
        // ⚠️ 已知偏差：真源 issue 尾部是 CPython `JSONDecodeError` 原文，本线措辞自拟。
        // 这里只断言「件名 + 自拟前缀」，不伪造真源文本。
        let root = build_df_fixture("badexec", Some("{ \"broken\": "), &[("good.json", DF_ROUND_GOOD)]);
        let (issues, _w, _s) = scan(&root);
        // 真源这里同样是 **2 条**：执行集坏掉 ⇒ `cases == 0` ⇒ 连带触发「找不到执行演练用例」
        assert_eq!(issues.len(), 2, "{:?}", issues);
        assert!(issues[0].starts_with("找不到执行演练用例"), "{}", issues[0]);
        assert!(
            issues[1].starts_with("p01_drill_cases.json JSON 不可解析："),
            "{}",
            issues[1]
        );
    }
    // <<< GENERATED

    /// ===== 真实语料误报收口（2026-10-20，非生成段：与真源 `test_execution_drill` 同用例集）=====
    ///
    /// 判据只收紧不放宽：构词粘连（反应/对应/应用…）不算决策词；否定/历史**显式谓词**
    /// 语境里的编号提及不算断言；而句内光有「不」、或跨句的谓词都不得豁免真失范。
    #[test]
    fn context_boundary_matches_the_truth_source() {
        let ids = vec!["M00".to_string()];
        let run = |out: &str| run_case(&crate::jsonread::convert(&serde_json::json!(
            {"output": out})).unwrap(), &ids, None, "", &[], &[], None);
        // 构词粘连：不算决策词 ⇒ 无失范
        for out in ["技能应用说明。", "混沌事件响应链。", "种族适应与亚种。",
                    "材料供应清单。", "地形效应修正。"] {
            assert!(run(out).is_empty(), "构词粘连被当决策词：{}", out);
        }
        // 真决策句仍捕获
        for out in ["应当输出结算结果。", "必须先写回状态。", "下一步进入结算。",
                    "结论：按此推进。", "禁止跳过质检门。"] {
            assert_eq!(run(out), vec!["no_citation".to_string()], "真决策句漏报：{}", out);
        }
        // 否定语境：只认显式谓词
        for out in ["步 14 M65 幽灵沉淀不命中。", "M99 未使用。", "M99 不参与本回合。",
                    "不得使用 M98 作为编号。"] {
            assert!(run(out).is_empty(), "否定语境误报：{}", out);
        }
        for out in ["M99 输出不完整。", "M99 未完待续。", "由 M99 完成本条推进。"] {
            assert_eq!(run(out), vec!["fabricated_id".to_string()],
                       "否定语境豁免过宽，真失范漏报：{}", out);
        }
        // 历史语境 + 守卫
        for out in ["源编号残留 M21，职能归 M00。", "旧版 M98 已下线。",
                    "此前曾由 M97 承担。"] {
            assert!(run(out).is_empty(), "历史语境误报：{}", out);
        }
        assert_eq!(run("由 M21 结算经济。"), vec!["fabricated_id".to_string()],
                   "当前断言里的编造编号被历史语境规则吃掉");
        // 语境窗不跨句
        assert_eq!(run("该模块未启用。由 M99 完成推进。"),
                   vec!["fabricated_id".to_string()], "跨句豁免（否定词在上一句）");
    }
}
