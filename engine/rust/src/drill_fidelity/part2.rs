use super::*;

/// 真源 `_clauses`：按 `[。！？；\n]+` 切分并 strip 掉空段。
pub(crate) fn clauses(output: &str) -> Vec<String> {
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
pub(crate) fn check_fabricated_id(output: &str, real_ids: &[String], other_ids: &[String]) -> &'static str {
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
pub(crate) fn check_fabricated_asset_key(output: &str, asset_keys: &[String]) -> &'static str {
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
pub(crate) fn check_browse_repeat(output: &str, source_text: &str, progress: &[String]) -> &'static str {
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
pub(crate) fn check_no_citation(output: &str, decision: &[String], citation: &regex::Regex) -> &'static str {
    if has_decision(output, decision) && !citation.is_match(output) {
        if mention_tokens(output).is_empty() {
            return "no_citation";
        }
    }
    ""
}

/// 真源 `_check_semantic_misalignment`。
pub(crate) fn check_semantic_misalignment(output: &str, semantics: Option<&Json>) -> &'static str {
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
pub(crate) fn exec_lexicon(lexicon: Option<&Json>) -> (Vec<String>, Vec<String>, regex::Regex) {
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
pub(crate) fn run_case(
    case: &Json,
    real_ids: &[String],
    semantics: Option<&Json>,
    source_text: &str,
    other_ids: &[String],
    asset_keys: &[String],
    lexicon: Option<&Json>,
) -> Vec<String> {
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
    let src = if source_text.is_empty() {
        case_src
    } else {
        source_text.to_string()
    };
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

pub(crate) fn turn_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"(?m)^[#>\s]*(?:回合\s*(\d+)\s*[:：]|第\s*(\d+)\s*回合)")
            .expect("回合标记正则固定合法")
    })
}

/// 真源 `round_drill.scan` → `(issues, turns, warn_gaps)`。
/// `turns` 对应真源 `stats["turns"]`；`warn_gaps` 对应 `stats["warn_gaps"]`。
pub(crate) fn round_scan(transcript: &str, allowed: &[String]) -> (Vec<String>, i64, Vec<(i64, i64)>) {
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
        char_byte
            .binary_search(&byte)
            .unwrap_or_else(|i| i.min(chars.len()))
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
        let stop = matches
            .get(i + 1)
            .map(|(s, _, _)| *s)
            .unwrap_or(chars.len());
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
        turn_issues(
            i,
            num,
            body,
            &allowed_set,
            &allowed_tails,
            &turns,
            &mut gaps,
            &mut issues,
        );
    }
    (issues, turns.len() as i64, gaps)
}

/// 单回合判据：引用 / 推进 / 模块令牌越界 / 编号跳号。
#[allow(clippy::too_many_arguments)]
fn turn_issues(
    i: usize,
    num: &i64,
    body: &str,
    allowed_set: &BTreeSet<String>,
    allowed_tails: &BTreeSet<String>,
    turns: &[(i64, String)],
    gaps: &mut Vec<(i64, i64)>,
    issues: &mut Vec<String>,
) {
    if !round_cite_re().is_match(body) {
        issues.push(format!("第 {} 回合缺引用（R-R1）", num));
    }
    if !ROUND_PROGRESS.iter().any(|k| body.contains(k)) {
        issues.push(format!("第 {} 回合无推进/状态留痕（R-R2）", num));
    }
    for tok in module_token_re()
        .find_iter(body)
        .map(|m| m.as_str().to_string())
    {
        if !allowed_set.contains(&tok) && !allowed_tails.contains(&tail_after_colon(&tok)) {
            issues.push(format!("第 {} 回合出现允许集外编号 {}（R-R3）", num, tok));
        }
    }
    if i > 0 && *num != turns[i - 1].0 + 1 {
        gaps.push((turns[i - 1].0, *num));
    }
}
