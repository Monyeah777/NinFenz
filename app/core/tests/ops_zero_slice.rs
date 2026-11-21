mod common;

use serde_json::json;
use common::run_ok;

#[test]
fn zero_slice_maps_exact_titles() {
    let out = run_ok("zero-slice", &json!({
        "text": "# 简报\n\n## 背景\n\n甲\n\n## 目标\n\n乙\n",
        "spec": {"id": "demo", "slots": [
            {"id": "SLT-01", "name": "背景", "required": true},
            {"id": "SLT-02", "name": "目标", "required": true}
        ]}
    }));
    assert_eq!(out["coverage"], 100);
    assert_eq!(out["mappings"].as_array().unwrap().len(), 2);
    assert_eq!(out["exceptions"].as_array().unwrap().len(), 0);
}

#[test]
fn zero_slice_keeps_low_confidence_as_exception() {
    let out = run_ok("zero-slice", &json!({
        "text": "# 简\n\n## 天气\n\n甲\n",
        "spec": {"slots": [{"id": "SLT-01", "name": "背景", "required": true}]}
    }));
    assert_eq!(out["mappings"].as_array().unwrap().len(), 0);
    assert_eq!(out["exceptions"].as_array().unwrap().len(), 2);
    assert_eq!(out["coverage"], 0);
}

#[test]
fn zero_slice_freeform_without_spec() {
    let out = run_ok("zero-slice", &json!({"text": "标题\n\n正文"}));
    assert_eq!(out["mappings"][0]["to_id"], "freeform");
    assert_eq!(out["coverage"], 100);
}
