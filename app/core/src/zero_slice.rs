//! zero_slice 导入映射的 Rust 参考实现（对照 app/prototypes/zero_slice）。
//!
//! 只覆盖结构解析/映射/例外，不替代 Android ImportSession；用于先锁语义再进 op/FFI。

mod types_infer;
mod session;

pub use types_infer::*;
pub use session::*;

#[cfg(test)]
mod tests {
    use super::*;

    fn spec() -> Spec {
        Spec { id: "demo".into(), sections: vec![], slots: vec![
            SlotSpec { id: "SLT-01".into(), name: "背景".into(), required: true, max_chars: None },
            SlotSpec { id: "SLT-02".into(), name: "目标".into(), required: true, max_chars: None },
        ]}
    }

    #[test]
    fn headings_become_sections() {
        let doc = parse_markdown("# 简报\n\n## 背景\n\n正文\n\n## 目标\n\n- 一点\n");
        assert_eq!(doc.title, "简报");
        assert_eq!(doc.sections.iter().map(|s| s.title.as_str()).collect::<Vec<_>>(), vec!["背景", "目标"]);
    }

    #[test]
    fn section_blocks_fill_slots() {
        let spec = Spec {
            id: "demo".into(),
            slots: vec![
                SlotSpec { id: "SLT-01".into(), name: "主题句".into(), required: true, max_chars: None },
                SlotSpec { id: "SLT-02".into(), name: "读者设定".into(), required: true, max_chars: None },
            ],
            sections: vec![SectionSpec { id: "SEC-01".into(), title: "开篇".into(), slots: vec!["SLT-01".into(), "SLT-02".into()] }],
        };
        let doc = parse_markdown("# 示例\n\n## 开篇\n\n甲段\n\n乙段\n");
        let report = infer(&spec, &doc);
        assert_eq!(report.mappings.len(), 2);
        assert_eq!(report.mappings[0].from_block, Some(0));
        assert_eq!(report.mappings[1].from_block, Some(1));
        let project = to_project(&doc, &report, None);
        assert_eq!(project["slots"]["SLT-01"], "甲段");
        assert_eq!(project["slots"]["SLT-02"], "乙段");
    }

    #[test]
    fn freeform_single_section_falls_back() {
        let doc = parse_markdown("# 自由稿\n\n雨夜的边境小镇，主角必须在一个时辰内找到落脚点。\n");
        let report = infer(&spec(), &doc);
        assert_eq!(report.mappings.len(), 1);
        assert_eq!(report.mappings[0].to_id, "SLT-01");
        assert_eq!(report.mappings[0].confidence, 0.6);
        assert_eq!(report.coverage, 1.0);
        assert_eq!(report.exceptions.len(), 1);
        assert_eq!(report.exceptions[0].target.as_deref(), Some("SLT-02"));
    }

    #[test]
    fn year_is_not_a_list() {
        let doc = parse_markdown("2026 年计划\n\n1. 第一项\n\n2) 第二项");
        assert_eq!(doc.blocks[0].kind, "paragraph");
        assert_eq!(doc.blocks[1].kind, "list");
        assert_eq!(doc.blocks[2].kind, "list");
    }

    #[test]
    fn tables_and_code_are_blocks() {
        let doc = parse_markdown("|a|b|\n|-|-|\n|1|2|\n\n\u{60}\u{60}\u{60}\nx\n\u{60}\u{60}\u{60}\n");
        assert!(doc.blocks.iter().any(|b| b.kind == "table"));
        assert!(doc.blocks.iter().any(|b| b.kind == "code"));
    }

    #[test]
    fn exact_titles_map() {
        let doc = parse_markdown("# 简\n\n## 背景\n\n甲\n\n## 目标\n\n乙\n");
        let report = infer(&spec(), &doc);
        assert_eq!(report.mappings.len(), 2);
        assert_eq!(report.coverage, 1.0);
        assert!(report.exceptions.is_empty());
    }

    #[test]
    fn low_confidence_kept_as_exception() {
        let doc = parse_markdown("# 简\n\n## 天气\n\n甲\n");
        let report = infer(&spec(), &doc);
        assert!(report.mappings.is_empty());
        assert_eq!(report.exceptions.len(), 3);
        assert_eq!(report.coverage, 0.0);
    }

    #[test]
    fn to_project_reference_shape() {
        let doc = parse_markdown("# 简\n\n## 背景\n\n甲\n");
        let report = infer(&spec(), &doc);
        let project = to_project(&doc, &report, Some("d1"));
        assert_eq!(project["schema"], "nf-project/1");
        assert_eq!(project["slots"]["SLT-01"], "甲");
        assert_eq!(project["draft_id"], "d1");
    }

    #[test]
    fn draft_store_overwrites_same_source() {
        let root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/nf-test-tmp").join(format!("zero_draft_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        let store = DraftStore::new(&root);
        let doc = parse_markdown("# 简\n\n## 背景\n\n甲\n");
        let report = infer(&spec(), &doc);
        let a = store.save("same.md", &doc, &report).unwrap();
        let b = store.save("same.md", &doc, &report).unwrap();
        assert_eq!(a, b);
        assert_eq!(store.list(), vec![a.clone()]);
        assert!(store.load(&a).is_some());
        assert!(store.delete(&a));
        assert!(store.load(&a).is_none());
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn session_transitions_and_reset() {
        let mut session = Session::new();
        let doc = parse_markdown("# 简\n\n## 背景\n\n甲\n");
        session.start(doc).unwrap();
        assert_eq!(session.stage(), Stage::Preview);
        session.infer(&spec()).unwrap();
        assert_eq!(session.stage(), Stage::Mapping);
        session.accept_draft().unwrap();
        assert_eq!(session.stage(), Stage::Draft);
        session.reset(ResetScope::All);
        assert_eq!(session.stage(), Stage::Empty);
        assert!(session.document().is_none());
        assert!(!session.undo());
    }

    #[test]
    fn session_undo_restores_previous_stage() {
        let mut session = Session::new();
        session.start(parse_markdown("# 简\n\n## 背景\n\n甲\n")).unwrap();
        session.infer(&spec()).unwrap();
        assert!(session.undo());
        assert_eq!(session.stage(), Stage::Preview);
        assert!(session.report().is_none());
    }

    #[test]
    fn empty_session_start_rejected() {
        let mut session = Session::new();
        assert!(session.start(Document { title: "空".into(), sections: vec![], blocks: vec![] }).is_err());
    }

    #[test]
    fn freeform_without_spec() {
        let doc = parse_markdown("标题\n\n正文");
        let report = infer(&Spec { id: "free".into(), slots: vec![], sections: vec![] }, &doc);
        assert_eq!(report.mappings[0].to_id, "freeform");
        assert_eq!(report.coverage, 1.0);
    }
}
