//! 共享 JSON 访问小工具。
//!
//! obj_get / arr_of / str_list / s_of 此前在 pack_combo / pack_combo_core /
//! output_forms_verify 等模块各写一份（审计规则 D-004）；统一到这里，签名保持不变。

use crate::pyjson::Json;
use crate::pyval;

pub fn obj_get<'a>(v: &'a Json, k: &str) -> Option<&'a Json> {
    match v {
        Json::Object(o) => o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv),
        _ => None,
    }
}

pub fn arr_of(v: Option<&Json>) -> Vec<Json> {
    match v {
        Some(Json::Array(a)) => a.clone(),
        _ => Vec::new(),
    }
}

pub fn str_list(v: Option<&Json>) -> Vec<String> {
    arr_of(v).iter().map(pyval::plain_str).collect()
}

pub fn s_of(v: Option<&Json>) -> String {
    match v {
        None | Some(Json::Null) => String::new(),
        Some(x) => pyval::plain_str(x),
    }
}
