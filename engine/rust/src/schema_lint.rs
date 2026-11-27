//! 协议件子集校验（`schema_lint` / check28）—— 与真源 `desktop/src/core/schema_lint.py` 对账。
//!
//! 真源是**自实现的 JSON-Schema 子集校验器**：`SUBSET_ALLOWED_KEYS` 之外的关字一律 FAIL
//! （防止「校验器声称子集却静默忽略语义」的假绿），再用它校五张面——模块契约围栏 /
//! registry 投影 / 管线声明 / community 协议声明 / 资产台账。
//!
//! **未移植的近似（如实标注）**：真源在读取/解析失败时把**底层异常文本**拼进 issue；
//! 本线的错误措辞是自拟的。正常仓库上不会走到这两条分支（真源当前 0 issues）。
//! 真源的 `_csc.yaml is None`（PyYAML 缺席）分支在本线不存在——`miniyaml` 恒在场。

use crate::jsonread;
use crate::miniyaml;
use crate::pyfloat;
use crate::pyjson::Json;
use crate::pyval::{get, plain_str, py_repr, py_str};
use std::path::Path;

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::jsonread;

    fn j(v: serde_json::Value) -> Json {
        jsonread::convert(&v).unwrap()
    }

    #[test]
    fn object_required_and_additional_properties() {
        let schema = j(serde_json::json!({
            "type": "object",
            "required": ["a"],
            "properties": {"a": {"type": "string"}},
            "additionalProperties": false
        }));
        let inst = j(serde_json::json!({"a": "x", "b": 1}));
        let got = subset_validate(&inst, &schema, "p");
        assert_eq!(got.len(), 1);
        assert!(got[0].contains("未知字段 b"), "{:?}", got);
        // 缺必填
        let got2 = subset_validate(&j(serde_json::json!({"b": 1})), &schema, "p");
        assert!(
            got2.iter().any(|m| m.contains("缺必填字段 a")),
            "{:?}",
            got2
        );
    }

    #[test]
    fn type_names_match_python_type_dunder_name() {
        let schema = j(serde_json::json!({"type": "object"}));
        for (v, want) in [
            (serde_json::json!([1]), "list"),
            (serde_json::json!("s"), "str"),
            (serde_json::json!(1), "int"),
            (serde_json::json!(1.5), "float"),
            (serde_json::json!(true), "bool"),
            (serde_json::json!(null), "NoneType"),
        ] {
            let got = subset_validate(&j(v), &schema, "p");
            assert_eq!(got.len(), 1);
            assert!(
                got[0].ends_with(want),
                "期望 {} 收尾，实得 {:?}",
                want,
                got[0]
            );
        }
    }

    #[test]
    fn bool_is_not_integer_like_python() {
        // Python: isinstance(True, int) 为真，故真源显式排 bool
        let schema = j(serde_json::json!({"type": "integer"}));
        let got = subset_validate(&j(serde_json::json!(true)), &schema, "p");
        assert_eq!(got.len(), 1);
        assert!(got[0].contains("实为 bool"), "{:?}", got);
    }

    #[test]
    fn enum_and_pattern_messages_use_python_repr() {
        let schema = j(serde_json::json!({"type": "string", "enum": ["a", "b"]}));
        let got = subset_validate(&j(serde_json::json!("z")), &schema, "p");
        assert_eq!(got.len(), 1);
        // Python: 值 'z' 不在枚举 ['a', 'b']
        assert!(got[0].contains("值 'z' 不在枚举 ['a', 'b']"), "{:?}", got);
    }

    #[test]
    fn enum_is_type_independent_and_bool_is_not_number() {
        // 2026-10-10 审计 Y4：enum 此前只在 string 分支里判 ⇒ boolean/number 静默放行。
        let schema = j(serde_json::json!({"type": "boolean", "enum": [true]}));
        let got = subset_validate(&j(serde_json::json!(false)), &schema, "p");
        assert_eq!(got.len(), 1, "boolean enum 必须判违例：{:?}", got);
        assert!(got[0].contains("不在枚举"), "{:?}", got);
        // 严格相等：False 不能冒充 0 / True 不能冒充 1；数字之间 1 == 1.0
        assert!(json_equal(
            &j(serde_json::json!(true)),
            &j(serde_json::json!(true))
        ));
        assert!(!json_equal(
            &j(serde_json::json!(true)),
            &j(serde_json::json!(1))
        ));
        assert!(!json_equal(
            &j(serde_json::json!(false)),
            &j(serde_json::json!(0))
        ));
        assert!(json_equal(
            &j(serde_json::json!(1)),
            &j(serde_json::json!(1.0))
        ));
        // 无 type 时 enum 违例不得被吞掉（真源这一支此前 return []）
        let s2 = j(serde_json::json!({"enum": ["a"]}));
        let g2 = subset_validate(&j(serde_json::json!("b")), &s2, "p");
        assert_eq!(g2.len(), 1, "无 type 也要报 enum：{:?}", g2);
    }

    #[test]
    fn subset_key_violations_flags_unimplemented_keywords() {
        let schema = j(serde_json::json!({"type": "object", "oneOf": [{"type": "string"}]}));
        let got = subset_key_violations(&schema, "s");
        assert_eq!(got.len(), 1);
        assert!(got[0].contains("oneOf"), "{:?}", got);
    }

    #[test]
    fn unsupported_type_is_reported_not_silently_ignored() {
        let schema = j(serde_json::json!({"type": "null"}));
        let got = subset_validate(&j(serde_json::json!(1)), &schema, "p");
        assert_eq!(got.len(), 1);
        assert!(got[0].contains("校验器不支持的 type"), "{:?}", got);
    }
}
