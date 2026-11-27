//! glob 子集 —— 复刻真源所用的 `Path.glob` 形态。
//!
//! **范围纪律**：真源实际用到的只有两种形态（2026-10-03 全仓普查）：
//! `*`（不跨 `/`）与 `**`（跨目录）；另有直路径（无通配符）与 `?`。故本模块只保证这些：
//!
//! | 形态 | 语义 | 与 `Path.glob` |
//! |---|---|---|
//! | `*` | 段内任意字符（不跨 `/`） | 同 |
//! | `?` | 段内单字符 | 同 |
//! | `**` | 跨目录（可为零段） | 同（**仅作独立段时**；真源无「非独立段的 `**`」用例） |
//! | `[...]` | **不支持** → 由调用方回退或显式报错 | 不同 |
//!
//! `Path.glob` 的 `**` 必须是独立段才算递归；本模块沿用真源自己的快路径口径
//! （`layer_model._pattern_to_regex`：「`**` → `.*`，紧随的 `/` 一并吞掉」），
//! 因为那正是仓库内已验证过等价性的那份实现。
//!
//! 隐藏文件**照收**：`Path.glob` 不像 shell 那样跳过点开头项。

use std::cell::RefCell;
use std::path::Path;

mod part1;

pub(crate) use part1::*;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wildcard_detection_matches_truth_source_rule() {
        assert!(has_wildcard("a/*.md"));
        assert!(has_wildcard("a/**/b"));
        assert!(has_wildcard("a/?"));
        assert!(has_wildcard("a/[xy]"));
        assert!(!has_wildcard("docs/layers.md"));
    }

    #[test]
    fn star_does_not_cross_directory_separator() {
        let re = to_regex("protocol/schema/*.json");
        assert!(re.is_match("protocol/schema/asset.schema.json"));
        assert!(!re.is_match("protocol/schema/sub/asset.json"));
    }

    #[test]
    fn double_star_crosses_and_matches_zero_segments() {
        let re = to_regex("a/**/*.md");
        assert!(re.is_match("a/x.md"), "`**` 应可匹配零段");
        assert!(re.is_match("a/b/c/x.md"));
        let re2 = to_regex("external/**/*");
        assert!(re2.is_match("external/x"));
        assert!(re2.is_match("external/a/b"));
    }

    #[test]
    fn fixed_prefix_stops_at_first_wildcard_segment() {
        assert_eq!(
            fixed_prefix("docs/examples/state-front/*.md"),
            "docs/examples/state-front"
        );
        assert_eq!(fixed_prefix("a/**/b/*.md"), "a");
        assert_eq!(fixed_prefix("*.md"), "");
    }

    #[test]
    fn char_class_is_out_of_scope_and_yields_nothing() {
        // 不在承诺范围内的形态必须**空手而归**，不许给出近似结果
        let tmp = crate::testutil::fixture("glob");
        std::fs::write(tmp.join("a.md"), b"x").unwrap();
        assert!(expand(&tmp, "[ab].md").is_empty());
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn expand_finds_files_and_sorts_them() {
        let tmp = crate::testutil::fixture("glob2");
        std::fs::create_dir_all(tmp.join("d/sub")).unwrap();
        std::fs::write(tmp.join("d/b.md"), b"x").unwrap();
        std::fs::write(tmp.join("d/a.md"), b"x").unwrap();
        std::fs::write(tmp.join("d/sub/c.md"), b"x").unwrap();
        assert_eq!(
            expand(&tmp, "d/*.md"),
            vec!["d/a.md".to_string(), "d/b.md".to_string()]
        );
        assert_eq!(
            expand(&tmp, "d/**/*.md"),
            vec![
                "d/a.md".to_string(),
                "d/b.md".to_string(),
                "d/sub/c.md".to_string()
            ]
        );
        assert_eq!(expand(&tmp, "d/a.md"), vec!["d/a.md".to_string()]);
        assert!(expand(&tmp, "d/none.md").is_empty());
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn cache_segment_pruning_skips_unrelated_dirs() {
        // `community/*/assets/*.md` 必须只碰各包的 assets 目录，不得枚举包内其它件
        let tmp = crate::testutil::fixture("glob-prune");
        std::fs::create_dir_all(tmp.join("community/p1/assets")).unwrap();
        std::fs::create_dir_all(tmp.join("community/p1/modules")).unwrap();
        std::fs::create_dir_all(tmp.join("community/p2/assets")).unwrap();
        std::fs::write(tmp.join("community/p1/assets/A.md"), "x").unwrap();
        std::fs::write(tmp.join("community/p1/modules/M.md"), "x").unwrap();
        std::fs::write(tmp.join("community/p2/assets/B.md"), "x").unwrap();
        std::fs::write(tmp.join("community/p2/README.md"), "x").unwrap();

        let mut c = Cache::new();
        assert_eq!(
            c.expand(&tmp, "community/*/assets/*.md"),
            vec!["community/p1/assets/A.md", "community/p2/assets/B.md"]
        );
        // 命中整模式缓存
        assert_eq!(c.expand(&tmp, "community/*/assets/*.md").len(), 2);
        // 单层目录清单已缓存 ⇒ 换个模式不必重列 `community/`
        assert!(c
            .dirs
            .contains_key(&tmp.join("community").to_string_lossy().to_string()));
        assert_eq!(
            c.expand(&tmp, "community/*/modules/*.md"),
            vec!["community/p1/modules/M.md"]
        );
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn cache_prefers_a_cached_subtree_over_a_segment_walk() {
        // 有 `**` 留下的全递归清单时，窄模式只需过滤它（layers 曾有 257→453 ms 的教训）
        let tmp = crate::testutil::fixture("glob-subtree");
        std::fs::create_dir_all(tmp.join("community/p1/assets")).unwrap();
        std::fs::write(tmp.join("community/p1/assets/A.md"), "x").unwrap();
        std::fs::write(tmp.join("community/p1/note.md"), "x").unwrap();
        let mut c = Cache::new();
        let wide = c.expand(&tmp, "community/**/*.md");
        assert_eq!(wide.len(), 2);
        assert!(c.trees.contains_key("community"), "宽模式应留下全递归清单");
        assert!(c.dirs.is_empty(), "走了全递归就不该再列单层目录");
        assert_eq!(
            c.expand(&tmp, "community/*/assets/*.md"),
            vec!["community/p1/assets/A.md"]
        );
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn py_path_str_drops_dot_root_and_uses_platform_separator() {
        assert_eq!(
            py_path_str(Path::new("."), "a/b.md"),
            if cfg!(windows) { "a\\b.md" } else { "a/b.md" }
        );
        let got = py_path_str(Path::new("C:/x/y/"), "a/b.md");
        assert!(
            got.ends_with(if cfg!(windows) {
                "y\\a\\b.md"
            } else {
                "y/a/b.md"
            }),
            "got: {}",
            got
        );
    }
}
