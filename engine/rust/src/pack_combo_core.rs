//! `pack_combo` 的**判决层**：`combine` / `verify_certificate` / `breadth` / 证书校验 / `scan`。
//!
//! 拆分只为可读；口径与真源逐条对应。索引层见 `pack_combo`。

use crate::pack_combo as pc;
use crate::pyjson::Json;
use crate::jsonx::{obj_get, arr_of, str_list, s_of};
use crate::pyval;
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

mod part1;
mod part2;
mod part3;

pub(crate) use part1::*;
pub(crate) use part2::*;
pub(crate) use part3::*;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pack_combo_matches_truth_source() {
        let root = crate::testutil::repo_root();
        let (issues, stats) = scan(&root);
        assert_eq!(issues, &[] as &[&str], "issues 须逐字且同序");
        let want: Json = crate::jsonread::convert(
            &serde_json::from_str::<serde_json::Value>(r#"{"breadth": {"all_legal": true, "failures": [], "packs": 111, "pairs": 6105, "pairs_legal": 6105, "quads": 200, "quads_legal": 200, "quints": 120, "quints_legal": 120, "sexts": 60, "sexts_legal": 60, "triples": 400, "triples_legal": 400}, "declared_certificates": 18}"#).unwrap(),
        )
        .unwrap();
        assert!(
            crate::jsonread::json_eq(&stats, &want),
            "stats 不一致\n  实得 {}\n  期望 {}",
            stats.dumps(),
            want.dumps()
        );
    }
    // <<< GENERATED
}
