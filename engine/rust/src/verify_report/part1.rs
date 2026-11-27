use super::*;

pub(crate) const REPORT_REL: &str = "protocol/verification_report.json";

pub(crate) const SCHEMA: &str = "nf-verify-report/1";

pub(crate) struct Spec {
    pub id: &'static str,
    pub name: &'static str,
    pub module: &'static str,
    pub entry: &'static str,
}

impl Spec {
    pub fn source(&self) -> String {
        format!("{}.{}", self.module, self.entry)
    }
}

/// 真源 `SPECS` 逐字（次序即报告 items 的次序）。
pub(crate) const SPECS: [Spec; 31] = [
    Spec {
        id: "purity",
        name: "架构纯度体检（R1-R7 + 分层阶梯 L1-L4）",
        module: "purity_scan",
        entry: "scan",
    },
    Spec {
        id: "schema",
        name: "协议层 IDL schema 门禁",
        module: "schema_lint",
        entry: "scan",
    },
    Spec {
        id: "conformance",
        name: "社区领域包 conformance 分级",
        module: "conformance_scan",
        entry: "scan",
    },
    Spec {
        id: "contract",
        name: "机读契约面（官方核心 13 件 id/标题一致）",
        module: "machine_contract",
        entry: "scan",
    },
    Spec {
        id: "knowledge",
        name: "双源知识层（权威分层/顺序/时效/巡检）",
        module: "knowledge",
        entry: "scan",
    },
    Spec {
        id: "rating",
        name: "馆藏内容分级声明",
        module: "rating_gate",
        entry: "scan",
    },
    Spec {
        id: "rating_decided",
        name: "馆藏分级是否真被定级（Z3：显式 unrated 不算已定级）",
        module: "rating_gate",
        entry: "decided",
    },
    Spec {
        id: "license",
        name: "许可证门",
        module: "license_gate",
        entry: "scan",
    },
    Spec {
        id: "intake",
        name: "投稿闸门三方一致",
        module: "intake",
        entry: "scan",
    },
    Spec {
        id: "payload",
        name: "事件载荷注册表",
        module: "payload_registry",
        entry: "scan",
    },
    Spec {
        id: "doc_markers",
        name: "文档 marker 卫生",
        module: "doc_hygiene",
        entry: "check_markers",
    },
    Spec {
        id: "assets_ledger",
        name: "资产 ledger 投影一致",
        module: "asset_ledger_projection",
        entry: "verify",
    },
    Spec {
        id: "instruction",
        name: "指令档步骤审计",
        module: "instruction_step_audit",
        entry: "scan",
    },
    Spec {
        id: "baseline",
        name: "基线自描述一致（verify 版本 / check 数）",
        module: "quality_baseline",
        entry: "scan",
    },
    Spec {
        id: "library",
        name: "图书馆 frontmatter + 投影一致",
        module: "library",
        entry: "verify",
    },
    Spec {
        id: "library_projection",
        name: "图书馆 INDEX/ALIAS 实时一致",
        module: "library",
        entry: "check_projection",
    },
    Spec {
        id: "receipts",
        name: "馆藏回执折叠到根",
        module: "receipts",
        entry: "verify_wrapped",
    },
    Spec {
        id: "conformance_report",
        name: "一致性报告（已提交 == 实时重算）",
        module: "conformance_report",
        entry: "verify_committed",
    },
    Spec {
        id: "audit",
        name: "审计件被审对象 digest",
        module: "audit",
        entry: "scan",
    },
    Spec {
        id: "self_stats",
        name: "自述数字 == 实算（README/llms 生成区）",
        module: "repo_stats",
        entry: "check_strict",
    },
    Spec {
        id: "code_metrics",
        name: "代码规模/复杂度上限（棘轮冻结）",
        module: "code_metrics",
        entry: "scan",
    },
    Spec {
        id: "redos",
        name: "正则失控回溯（形态 + 增长律；Y3 接线）",
        module: "redos_scan",
        entry: "scan",
    },
    Spec {
        id: "key_naming",
        name: "资产键命名规范（形态 + 声明词表）",
        module: "key_naming",
        entry: "scan",
    },
    Spec {
        id: "instruction_evidence",
        name: "规范入口指令实测记录（新鲜 + 退出码 0）",
        module: "instruction_evidence",
        entry: "scan",
    },
    Spec {
        id: "coupling",
        name: "模块级耦合（Martin 包度量 / SDP / 环 · 只许收敛）",
        module: "coupling_metrics",
        entry: "scan",
    },
    Spec {
        id: "perf_budget",
        name: "性能预算（中位耗时 ≤ 预算 + 记录新鲜）",
        module: "perf_budget",
        entry: "scan",
    },
    Spec {
        id: "drill_fidelity",
        name: "演练保真度（执行演练 + 回合级回放 = 100%）",
        module: "drill_fidelity",
        entry: "scan",
    },
    Spec {
        id: "judgement_coverage",
        name: "判据接线覆盖（暴露 scan() 的判据必须有消费者或例外登记）",
        module: "judgement_coverage",
        entry: "scan",
    },
    Spec {
        id: "workflow_policy",
        name: "工作流供应链策略（actions 钉 40 位 SHA + 显式最小 permissions）",
        module: "workflow_policy",
        entry: "scan",
    },
    Spec {
        id: "asset_contract",
        name: "数字资产契约（数据/代码/脚本三面：格式+字段完整性+防篡改+AST 规范+脚本 I/O 对齐）",
        module: "asset_contract",
        entry: "scan",
    },
    Spec {
        id: "role_coordinates",
        name: "职能坐标（ADR-0006：核内逐件 / 规则不漂 / verify 只读）",
        module: "role_model",
        entry: "scan",
    },
];

/// 未移植判据的喂入结果（`--results` 的一条）。
#[derive(Clone)]
pub(crate) struct Supplied {
    pub issues: Vec<String>,
    pub warns: Vec<String>,
    pub stats: Json,
    /// 覆盖派生出的 status（仅真源的 `error` 路径需要——它也是非空 issues）。
    pub status: Option<String>,
}

impl Default for Supplied {
    fn default() -> Self {
        Self {
            issues: Vec::new(),
            warns: Vec::new(),
            stats: empty_obj(),
            status: None,
        }
    }
}

/// 一条判据的归一结果。
pub(crate) struct Called {
    pub(crate) status: String,
    pub(crate) issues: Vec<String>,
    pub(crate) warns: Vec<String>,
    pub(crate) stats: Json,
}

pub(crate) fn empty_obj() -> Json {
    Json::Object(Vec::new())
}

pub(crate) fn status_of(issues: &[String], warns: &[String]) -> String {
    if !issues.is_empty() {
        "fail".to_string()
    } else if !warns.is_empty() {
        "warn".to_string()
    } else {
        "pass".to_string()
    }
}

/// 本线**已自主算出**的判据；未移植的返回 `None`（由 `--results` 喂入）。
/// 本线**已自主算出**的判据；未移植的返回 \`None\`（由 \`--results\` 喂入）。
pub(crate) fn native(spec: &Spec, root: &Path) -> Option<Called> {
    match spec.id {
        "schema" | "doc_markers" | "baseline" | "code_metrics" | "conformance_report" => {
            native_a(spec.id, root)
        }
        "purity" | "receipts" | "drill_fidelity" | "conformance" => native_b(spec.id, root),
        "knowledge" | "contract" | "license" | "coupling" | "judgement_coverage" | "audit"
        | "workflow_policy" | "rating_decided" | "rating" => native_c(spec.id, root),
        "library" | "library_projection" | "key_naming" | "intake" | "payload"
        | "assets_ledger" | "instruction" | "self_stats" => native_d(spec.id, root),
        _ => None,
    }
}

/// 本线自算（第一组）：schema / doc_markers / baseline / code_metrics / conformance_report。
pub(crate) fn native_a(id: &str, root: &Path) -> Option<Called> {
    match id {
        "schema" => {
            let (issues, stats) = crate::schema_lint::scan(root);
            Some(Called {
                status: status_of(&issues, &[]),
                issues,
                warns: Vec::new(),
                stats: stats.to_json(),
            })
        }
        // 形态 `list`：真源直接返回 issues 列表
        "doc_markers" => {
            let issues = crate::doc_hygiene::check_markers(root);
            Some(Called {
                status: status_of(&issues, &[]),
                issues,
                warns: Vec::new(),
                stats: empty_obj(),
            })
        }
        "baseline" => {
            let (issues, stats) = baseline::scan(root);
            let stats = match stats {
                Some(s) => Json::Object(vec![
                    ("verify_version".to_string(), Json::Str(s.verify_version)),
                    ("checks".to_string(), Json::Int(s.checks)),
                ]),
                None => empty_obj(),
            };
            Some(Called {
                status: status_of(&issues, &[]),
                issues,
                warns: Vec::new(),
                stats,
            })
        }
        // 裁定（2026-10-14）：`asset_contract` **退出本线原生面**——数字资产契约新增了
        // YAML/TOML 解析、包自述双向对账、Frictionless 导出与可移植 schema 校验，Rust 侧无 YAML 解析
        // 依赖且语义面已超出「只读快线」的移植收益；按增量法由真源 `--results` 喂入（同 check40 的
        // 「范围外」先例）。见 docs/asset_contract.md。
        "code_metrics" => {
            let (issues, warns, stats) = crate::code_metrics::scan(root);
            Some(Called {
                status: status_of(&issues, &warns),
                issues,
                warns,
                stats,
            })
        }
        "conformance_report" => {
            let (issues, stats) = crate::conformance::verify_committed(root);
            Some(Called {
                status: status_of(&issues, &[]),
                issues,
                warns: Vec::new(),
                stats,
            })
        }
        _ => None,
    }
}

/// 本线自算（第二组）：purity / receipts / drill_fidelity / conformance。
pub(crate) fn native_b(id: &str, root: &Path) -> Option<Called> {
    match id {
        "purity" => {
            let (issues, stats) = crate::purity::scan(root);
            Some(Called {
                status: status_of(&issues, &[]),
                issues,
                warns: Vec::new(),
                stats,
            })
        }
        "receipts" => {
            // 真源 `_call` 对这条有**前置在场检查**：文件不在 → 直接记 fail 并给修复指引
            if !root
                .join(crate::receipts_verify::LIBRARY_RECEIPTS_REL)
                .is_file()
            {
                Some(Called {
                    status: "fail".to_string(),
                    issues: vec![format!(
                        "缺 {}（修复指引：nf library receipts --write）",
                        crate::receipts_verify::LIBRARY_RECEIPTS_REL
                    )],
                    warns: Vec::new(),
                    stats: crate::pyjson::Json::Object(Vec::new()),
                })
            } else {
                let (issues, stats) = crate::receipts_verify::verify(root);
                Some(Called {
                    status: status_of(&issues, &[]),
                    issues,
                    warns: Vec::new(),
                    stats,
                })
            }
        }
        "drill_fidelity" => {
            let (issues, warns, stats) = crate::drill_fidelity::scan(root);
            Some(Called {
                status: status_of(&issues, &warns),
                issues,
                warns,
                stats,
            })
        }
        "conformance" => {
            let c = crate::conformance_scan::scan(root);
            Some(Called {
                status: status_of(&c.issues, &[]),
                issues: c.issues,
                warns: Vec::new(),
                stats: c.stats,
            })
        }
        _ => None,
    }
}
