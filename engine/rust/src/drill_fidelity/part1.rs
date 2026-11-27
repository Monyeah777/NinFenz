use super::*;

pub(crate) const EXEC_GLOB: &str = "desktop/tests/fixtures/execution/p*_drill_cases.json";

pub(crate) const ROUND_GLOB: &str = "desktop/tests/fixtures/execution/rounds/*.json";

/// 真源 `VERDICT_MAP`：样本侧写 good/bad，drill 侧吐 conformant/non-conformant。
pub(crate) fn verdict_map(s: &str) -> Option<&'static str> {
    match s {
        "good" | "conformant" => Some("conformant"),
        "bad" | "non-conformant" => Some("non-conformant"),
        _ => None,
    }
}

// ============================================================ execution_drill（句子级）

/// 真源 `_MODULE_TOKEN`：`(?:[\u4e00-\u9fff]+:)?M\d{2,3}`。
/// Rust `regex` 的 `\d` 与 Python `re` 一样是 Unicode 十进制类（`\p{Nd}`），故不必改写。
pub(crate) fn module_token_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"(?:[\x{4e00}-\x{9fff}]+:)?M\d{2,3}").expect("模块号正则固定合法")
    })
}

/// 真源 `execution_drill._DECISION_WORDS`（缺省中文；用例可在 fixture 的 lexicon 里覆盖）。
pub(crate) const EXEC_DECISION: [&str; 8] = [
    "应",
    "应该",
    "必须",
    "禁止",
    "不得",
    "下一步",
    "输出",
    "结论",
];

/// 真源 `execution_drill._DECISION_GLUE`：单字判定词的构词排除表（(词, (前字集, 后字集))）。
/// 真实语料实测：`元素反应`/`对应件`/`应用` 里的 `应` 不是「应当」义。
pub(crate) const EXEC_DECISION_GLUE: [(&str, (&str, &str)); 1] = [(
    "应",
    (
        "反对适响供效相顺答呼照策接报感",
        "用急对变聘邀酬届试运付缴纳计答战征招",
    ),
)];

/// 真源 `execution_drill._ASSERT_ABSENT_CUES`：编号断言的否定语境谓词。
/// **只认显式谓词**（不做「句内有『不』就豁免」的粗口径，否则真失范会被误豁免）。
pub(crate) const ASSERT_ABSENT_CUES: [&str; 22] = [
    "不命中",
    "未命中",
    "不适用",
    "不含",
    "不包含",
    "未包含",
    "不参与",
    "未参与",
    "不涉及",
    "未涉及",
    "未采用",
    "未使用",
    "不使用",
    "不得使用",
    "禁止使用",
    "不挂载",
    "未挂载",
    "不纳入",
    "未纳入",
    "跳过",
    "已移除",
    "未生效",
];

/// 真源 `execution_drill._ASSERT_HISTORY_CUES`：编号断言的历史语境谓词。
pub(crate) const ASSERT_HISTORY_CUES: [&str; 13] = [
    "曾",
    "此前",
    "上一版",
    "旧版",
    "历史",
    "原编号",
    "旧编号",
    "残留",
    "遗留",
    "已废弃",
    "已下线",
    "已迁移",
    "旧名",
];

/// 真源 `_ASSERT_CTX_BEFORE` / `_ASSERT_CTX_AFTER`（单位：**码点**，与 Python 切片一致）。
pub(crate) const ASSERT_CTX_BEFORE: usize = 10;

pub(crate) const ASSERT_CTX_AFTER: usize = 14;

/// 真源 `execution_drill._CITATION`。
pub(crate) fn citation_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(
            r"(§\s*\d+(?:[.-]\d+)*|第\s*\d+\s*(?:节|步|章)|L\d+|行号|[0-9A-Za-z_]+:[MTP]\d{2,3}|/\d+|\b\d{1,3}\b\s*行)",
        )
        .expect("引用正则固定合法")
    })
}

/// 真源 `round_drill._CITE`（**与 `execution_drill._CITATION` 不同**：无 `行号`、无 `/数字`——不可合并）。
pub(crate) fn round_cite_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(
            r"(§\s*\d+(?:[.-]\d+)*|第\s*\d+\s*(?:节|步|章)|L\d+|[0-9A-Za-z_]+:[MTP]\d{2,3}|\b\d{1,3}\b\s*行)",
        )
        .expect("回合引用正则固定合法")
    })
}

pub(crate) fn split_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"[。！？；\n]+").expect("分句正则固定合法"))
}

pub(crate) fn ws_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"\s+").expect("空白正则固定合法"))
}

/// 真源 `execution_drill._PROGRESS`。
pub(crate) const EXEC_PROGRESS: [&str; 6] = [
    "回合推进",
    "进入回合",
    "已进入第",
    "时间推进",
    "推进至",
    "进入下一回合",
];

/// 真源 `round_drill._PROGRESS`（**与 `execution_drill` 不同**——不可合并）。
pub(crate) const ROUND_PROGRESS: [&str; 7] = ["推进", "进入", "写回", "快照", "存档", "状态", "回合"];

/// 真源 `_bigrams`：去空白后取**码点**二元组；不足两个码点时返回「整串」单元素集。
pub(crate) fn bigrams(text: &str) -> BTreeSet<String> {
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

pub(crate) fn mention_tokens(output: &str) -> Vec<String> {
    module_token_re()
        .find_iter(output)
        .map(|m| m.as_str().to_string())
        .collect()
}

/// 真源 `execution_drill._id_tokens`：**可作编号断言的**模块号（排除路径/文件名前缀）。
///
/// 真实语料实测（2026-10-20）：唯一真实战例 P03 第 109 行
/// `- 出处：community/西幻生存领域包/modules/M10_死亡重生.md` —— `M10` 是**文件名**的前缀，
/// 旧线照抓并判 `fabricated_id`。Rust `regex` 无 lookaround，故按匹配尾后字符就地过滤：
/// 紧跟 ASCII 标识符字符（`M10_死亡重生`）或 `.<ASCII 扩展名>`（`M10.md`）者不算裸编号断言；
/// 中文紧邻（`M10的`）与列表分隔（`M02/M03`）照常算。
pub(crate) fn exec_id_token_spans(output: &str) -> Vec<(String, usize, usize)> {
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
pub(crate) fn assertion_context(output: &str, start: usize, end: usize) -> (String, String) {
    let before_raw = tail_chars(&output[..start], ASSERT_CTX_BEFORE);
    let before = split_re()
        .split(before_raw)
        .last()
        .unwrap_or("")
        .to_string();
    let after_raw = head_chars(&output[end..], ASSERT_CTX_AFTER);
    let after = split_re().split(after_raw).next().unwrap_or("").to_string();
    (before, after)
}

/// `s` 末尾 `n` 个码点（`n` 超长时取全串）。
pub(crate) fn tail_chars(s: &str, n: usize) -> &str {
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
pub(crate) fn head_chars(s: &str, n: usize) -> &str {
    match s.char_indices().nth(n) {
        Some((i, _)) => &s[..i],
        None => s,
    }
}

/// 真源 `_is_contextual_mention`：否定/历史语境里的编号提及**不是当前断言**。
pub(crate) fn is_contextual_mention(before: &str, after: &str) -> bool {
    ASSERT_ABSENT_CUES
        .iter()
        .chain(ASSERT_HISTORY_CUES.iter())
        .any(|c| before.contains(c) || after.contains(c))
}

/// 真源 `_has_decision`：判定词命中（**带边界**）——多字词子串；单字词排除构词粘连。
pub(crate) fn has_decision(output: &str, decision: &[String]) -> bool {
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
        let glue = EXEC_DECISION_GLUE
            .iter()
            .find(|(w, _)| *w == word.as_str())
            .map(|(_, g)| *g);
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
pub(crate) fn asset_token_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b").expect("资产键正则固定合法")
    })
}
