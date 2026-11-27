//! 评分 / 分层 / 契约封缄（score · layers · conformance run/seal）。
//!
//! 自 `main.rs` 按命令族拆出：实现逐字搬运，逻辑与文案未改；分派仍在 `main.rs::run_inner`。

use crate::{conformance, contracts, emit, jsonread, layers, pyjson, pyval, require_dir, score};
use super::commands_a::run_conformance_contract;
use super::{parse_root_json_out, RootJsonOut};
use std::path::PathBuf;
use std::process::ExitCode;

/// `nf-rs score --root <仓库根> --signals <json> [--baseline <rel>] [--tolerance <f>]
/// [--exceptions <json>] [--json] [--out <文件>]`。
///
/// `--signals` 提供**尚未移植**的 4 个扫描器计数；缺键 = 扫描器不可用（真源 `_count` 的哨兵语义）。
pub(crate) fn run_score(args: &[String]) -> Result<ExitCode, String> {
    let ScoreArgs {
        root,
        signals,
        baseline_rel,
        exceptions_path,
        tolerance,
        out,
    } = parse_score_args(args)?;
    let root = root.ok_or("缺 --root（修复指引：传仓库根目录）")?;
    require_dir(&root)?;

    let sup = match &signals {
        Some(p) => {
            let text = std::fs::read_to_string(p)
                .map_err(|e| format!("读 {} 失败：{}", p.display(), e))?;
            let v: serde_json::Value = serde_json::from_str(&text)
                .map_err(|e| format!("{} 不是合法 JSON：{}", p.display(), e))?;
            let n = |k: &str| v.get(k).and_then(|x| x.as_i64());
            score::Supplied {
                depth_clean: n("depth_clean"),
            }
        }
        None => score::Supplied::default(),
    };

    let current = score::evaluate(&root, &sup);

    let base_rel = baseline_rel.unwrap_or_else(|| score::DEFAULT_BASELINE.to_string());
    let base_path = if PathBuf::from(&base_rel).is_absolute() {
        PathBuf::from(&base_rel)
    } else {
        root.join(&base_rel)
    };
    let baseline = if base_path.is_file() {
        let text = std::fs::read_to_string(&base_path)
            .map_err(|e| format!("读 {} 失败：{}", base_path.display(), e))?;
        let raw: serde_json::Value =
            serde_json::from_str(&text).map_err(|e| format!("基线不是合法 JSON：{}", e))?;
        jsonread::convert(&raw).map_err(|e| format!("基线含不支持的值：{}", e))?
    } else {
        pyjson::Json::Object(vec![(
            "schema".to_string(),
            pyjson::Json::Str(score::SCHEMA.to_string()),
        )])
    };

    let exceptions: Vec<(String, String)> = match &exceptions_path {
        Some(p) => {
            let text = std::fs::read_to_string(p)
                .map_err(|e| format!("读 {} 失败：{}", p.display(), e))?;
            let v: serde_json::Value =
                serde_json::from_str(&text).map_err(|e| format!("例外表不是合法 JSON：{}", e))?;
            v.as_array()
                .map(|a| {
                    a.iter()
                        .filter_map(|e| {
                            let s = e.get("signal").and_then(|x| x.as_str())?;
                            let r = e.get("reason").and_then(|x| x.as_str()).unwrap_or("");
                            Some((s.to_string(), r.to_string()))
                        })
                        .collect()
                })
                .unwrap_or_default()
        }
        None => Vec::new(),
    };

    emit(
        &score::render_bytes(&current, &baseline, tolerance, &exceptions),
        &out,
    )?;
    if score::is_ok(&current, &baseline, tolerance, &exceptions) {
        Ok(ExitCode::SUCCESS)
    } else {
        Ok(ExitCode::from(1))
    }
}

/// `run_score` 的参数面（缺省即 `None` / `0.0`）。
struct ScoreArgs {
    root: Option<PathBuf>,
    signals: Option<PathBuf>,
    baseline_rel: Option<String>,
    exceptions_path: Option<PathBuf>,
    tolerance: f64,
    out: Option<PathBuf>,
}

/// 解析 `run_score` 参数（`--json` 只影响输出面，此处忽略）。
fn parse_score_args(args: &[String]) -> Result<ScoreArgs, String> {
    let mut root: Option<PathBuf> = None;
    let mut signals: Option<PathBuf> = None;
    let mut baseline_rel: Option<String> = None;
    let mut exceptions_path: Option<PathBuf> = None;
    let mut tolerance = 0.0f64;
    let mut out: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            "--signals" => {
                i += 1;
                signals = Some(PathBuf::from(args.get(i).ok_or("--signals 后缺路径")?));
            }
            "--baseline" => {
                i += 1;
                baseline_rel = Some(args.get(i).ok_or("--baseline 后缺值")?.clone());
            }
            "--exceptions" => {
                i += 1;
                exceptions_path =
                    Some(PathBuf::from(args.get(i).ok_or("--exceptions 后缺路径")?));
            }
            "--tolerance" => {
                i += 1;
                tolerance = args
                    .get(i)
                    .ok_or("--tolerance 后缺值")?
                    .parse::<f64>()
                    .map_err(|e| format!("--tolerance 不是数字：{}", e))?;
            }
            "--json" => {}
            "--write-baseline" => {
                return Err("本线不实现 --write-baseline（写面仍在 Python 侧；修复指引：`python scripts/nf.py score --write-baseline`）".into())
            }
            "--out" => {
                i += 1;
                out = Some(PathBuf::from(args.get(i).ok_or("--out 后缺路径")?));
            }
            other => return Err(format!("未知参数：{}", other)),
        }
        i += 1;
    }
    Ok(ScoreArgs {
        root,
        signals,
        baseline_rel,
        exceptions_path,
        tolerance,
        out,
    })
}

// ---------------------------------------------------------------- layers 面

/// `nf layers --verify`（阶梯体检）。**只读**：`--write`（刷新 docs/layers.md 生成区）不实现。
pub(crate) fn run_layers(args: &[String]) -> Result<ExitCode, String> {
    let mut root: Option<PathBuf> = None;
    let mut verify = false;
    let mut json = false;
    let mut out: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                root = Some(PathBuf::from(args.get(i).ok_or("--root 后缺路径")?));
            }
            "--verify" => verify = true,
            "--json" => json = true,
            "--write" => {
                return Err(
                    "本线不实现 --write（写面仍在 Python 侧；修复指引：`python scripts/nf.py layers --write`）"
                        .into(),
                )
            }
            "--out" => {
                i += 1;
                out = Some(PathBuf::from(args.get(i).ok_or("--out 后缺路径")?));
            }
            other => return Err(format!("未知参数：{}", other)),
        }
        i += 1;
    }
    let root = root.ok_or("缺 --root（修复指引：传仓库根目录）")?;
    require_dir(&root)?;
    if !verify {
        return Err(
            "本线只实现 --verify（修复指引：nf-rs layers --root <仓库根> --verify）".into(),
        );
    }

    let (issues, stats) = layers::scan(&root);
    if json {
        // 与真源同一条合成路径：这里直接复用 verify_bytes 的构造，避免两份输出口径
        emit(&layers::verify_bytes(&root), &out)?;
    } else {
        let mut s = String::new();
        s.push_str("== nf layers --verify（阶梯体检 · 与 verify check27 R7 同源）==\n");
        for i in &issues {
            s.push_str(&format!("  [FAIL] {}\n", i));
        }
        s.push_str(&format!(
            "  阶 {} · 资产子级 {} · 入口面 {} · 纵切件 {} · 规则 {} → {}\n",
            int_field(&stats, "tiers"),
            int_field(&stats, "asset_levels"),
            int_field(&stats, "surfaces"),
            int_field(&stats, "crosscut"),
            int_field(&stats, "rules"),
            if issues.is_empty() {
                "通过".to_string()
            } else {
                format!("FAIL {}", issues.len())
            }
        ));
        emit(s.as_bytes(), &out)?;
    }
    if issues.is_empty() {
        Ok(ExitCode::SUCCESS)
    } else {
        Ok(ExitCode::from(1))
    }
}

pub(crate) fn int_field(j: &pyjson::Json, k: &str) -> i64 {
    match pyval::get(j, k) {
        Some(pyjson::Json::Int(i)) => *i,
        _ => 0,
    }
}

// ---------------------------------------------------------------- conformance 封缄内核

/// 裁决行 → 封缄报告。输入可以是**契约行数组**，也可以是含 `contracts` 的真源报告对象；
/// 行内若自带 `digest` 则顺带做差分核对（**不信任输入摘要**）。
/// `nf-rs conformance run --root <仓库根> --json [--out <文件>]`：
/// 全量实时重算 27 条契约 → 封缄报告 + 与在盘报告比对（真源 `nf conformance --json` 的同形物）。
/// 人类可读面留在 Python 真源；本线只服务机器面（`--json`）。
pub(crate) fn run_conformance_run(args: &[String]) -> Result<ExitCode, String> {
    let RootJsonOut { root, json, out } = parse_root_json_out(args)?;
    if !json {
        return Err(
            "本线只实现 --json（修复指引：nf-rs conformance run --root <根> --json）".into(),
        );
    }
    let live = conformance::run_live(&root);
    let (issues, _stats) = conformance::verify_committed_with(&root, &live);
    let ok_verdict = match pyval::get(&live, "verdict") {
        Some(pyjson::Json::Str(s)) => s == "conformant",
        _ => false,
    };
    let doc = pyjson::Json::Object(vec![
        (
            "kind".to_string(),
            pyjson::Json::Str("conformance".to_string()),
        ),
        ("report".to_string(), live),
        (
            "issues".to_string(),
            pyjson::Json::Array(
                issues
                    .iter()
                    .map(|s| pyjson::Json::Str(s.clone()))
                    .collect(),
            ),
        ),
    ]);
    emit(doc.dumps_file().as_bytes(), &out)?;
    if issues.is_empty() && ok_verdict {
        Ok(ExitCode::SUCCESS)
    } else {
        Ok(ExitCode::from(1))
    }
}

pub(crate) fn run_conformance(args: &[String]) -> Result<ExitCode, String> {
    let sub = args
        .first()
        .map(|s| s.as_str())
        .ok_or("conformance 后缺子命令")?;
    if sub == "run" {
        return run_conformance_run(&args[1..]);
    }
    if sub == "contract" {
        return run_conformance_contract(&args[1..]);
    }
    if sub == "list" {
        let mut s = String::new();
        for id in contracts::PORTED {
            s.push_str(id);
            s.push('\n');
        }
        emit(s.as_bytes(), &None)?;
        return Ok(ExitCode::SUCCESS);
    }
    if sub != "seal" {
        return Err(format!(
            "conformance 未知子命令：{}（修复指引：run | seal | contract <id> | list）",
            sub
        ));
    }
    let (input, out) = super::parse_in_out(args, "缺 --in（修复指引：给契约裁决行 JSON）")?;
    let text = std::fs::read_to_string(&input)
        .map_err(|e| format!("读 {} 失败：{}", input.display(), e))?;
    let v: serde_json::Value = serde_json::from_str(&text)
        .map_err(|e| format!("{} 不是合法 JSON：{}", input.display(), e))?;

    let rows = parse_rows(&v)?;
    let mismatches = conformance::digest_mismatches(&rows);
    emit(&conformance::seal_bytes(&rows), &out)?;
    for m in &mismatches {
        eprintln!("  [FAIL] {}", m);
    }
    if mismatches.is_empty() {
        Ok(ExitCode::SUCCESS)
    } else {
        Ok(ExitCode::from(1))
    }
}

/// 解析契约裁决行（真源 `run()` 的报告对象亦可直接喂入）。
pub(crate) fn parse_rows(v: &serde_json::Value) -> Result<Vec<conformance::Row>, String> {
    let arr = match v {
        serde_json::Value::Array(a) => a,
        serde_json::Value::Object(o) => o
            .get("contracts")
            .and_then(|c| c.as_array())
            .ok_or("输入对象缺 contracts 数组（修复指引：给契约行数组或真源报告对象）")?,
        _ => return Err("输入必须是契约行数组或含 contracts 的对象".into()),
    };
    let mut rows = Vec::with_capacity(arr.len());
    for (i, item) in arr.iter().enumerate() {
        let o = item
            .as_object()
            .ok_or_else(|| format!("第 {} 行不是对象", i))?;
        let id = o
            .get("id")
            .and_then(|x| x.as_str())
            .ok_or_else(|| format!("第 {} 行缺 id（字符串）", i))?;
        let ok = o
            .get("ok")
            .and_then(|x| x.as_bool())
            .ok_or_else(|| format!("第 {} 行缺 ok（布尔）", i))?;
        rows.push(conformance::Row {
            id: id.to_string(),
            ok,
            detail: o
                .get("detail")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            description: o
                .get("description")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            recorded_digest: o
                .get("digest")
                .and_then(|x| x.as_str())
                .map(|s| s.to_string()),
        });
    }
    Ok(rows)
}
