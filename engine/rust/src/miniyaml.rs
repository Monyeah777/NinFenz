//! YAML **子集**解析器 + 围栏块提取 —— 复刻真源 `conformance_scan._fence_yaml` 的输入面。
//!
//! **为什么自己写**：真源用 PyYAML（`lazy_yaml` 惰性入口），而本线的依赖纪律不容 Python 运行时。
//! 这与 `engine/dotnet` 的 `MiniYaml.cs` 是同一条路数：**只支持真源用到的那一层，越出子集即
//! fail-closed**（不猜、不近似）。
//!
//! **实测界定子集**（2026-10-03，248 份模块文档的 `machine_contract` 围栏块全量普查）：
//!
//! | 构造 | 用量 |
//! |---|---|
//! | 嵌套映射（缩进驱动） | 全部 |
//! | 裸标量 | 3,428 |
//! | 带引号标量 | 486 |
//! | 行内列表 `[a, b]` | 1,226 |
//! | 块列表 `- item` | 41 |
//! | 多行折叠 `\|`/`>` · 锚点 `&`/`*` · 文档分隔 `---` · 制表符 | **0** |
//!
//! **解析后类型面**（同上普查）：`dict` 1,225 · `list` 1,242 · `str` 3,830 · `NoneType` 5，
//! **零 int/float/bool**。故本模块把裸标量一律当字符串；**若某裸标量在 YAML 1.1 下本应解析成
//! 数字/布尔/null，则直接报错**——宁可让对账在门禁上显形，也不静默给出一个错误的字符串值。

use crate::pyjson::Json;

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = "machine_contract:\n  conformance: \"L2\"\n  schema: \"1\"\n  id: M08\n  name: 季节天气\n  inputs: [通用:M10]\n  events:\n    publish: [weather_state]\n    subscribe: [tick_day]\n  interfaces: []\n  io_types:\n    outputs:\n      region: untyped\n";

    #[test]
    fn parses_real_module_block_shape() {
        let v = parse(SAMPLE).expect("真实样本必须可解析");
        let get = |j: &Json, k: &str| crate::pyval::get(j, k).cloned();
        let mc = get(&v, "machine_contract").unwrap();
        assert_eq!(get(&mc, "id"), Some(Json::Str("M08".into())));
        assert_eq!(get(&mc, "name"), Some(Json::Str("季节天气".into())));
        assert_eq!(
            get(&mc, "inputs"),
            Some(Json::Array(vec![Json::Str("通用:M10".into())]))
        );
        assert_eq!(get(&mc, "interfaces"), Some(Json::Array(vec![])));
        let events = get(&mc, "events").unwrap();
        assert_eq!(
            get(&events, "publish"),
            Some(Json::Array(vec![Json::Str("weather_state".into())]))
        );
        let io = get(&mc, "io_types").unwrap();
        let outs = get(&io, "outputs").unwrap();
        assert_eq!(get(&outs, "region"), Some(Json::Str("untyped".into())));
    }

    #[test]
    fn key_colon_without_space_belongs_to_the_key() {
        // 真源里 `通用:M10: untyped` —— 分隔点是**第一个「冒号+空格」**
        let v = parse("io_types:\n  inputs:\n    通用:M10: untyped\n").unwrap();
        let io = crate::pyval::get(&v, "io_types").unwrap();
        let ins = crate::pyval::get(io, "inputs").unwrap();
        assert_eq!(
            crate::pyval::get(ins, "通用:M10"),
            Some(&Json::Str("untyped".into()))
        );
    }

    #[test]
    fn absent_key_and_empty_value_both_yield_null() {
        // `a:` 后无子块 → null；`b: text` 是字符串
        let v = parse("a:\nb: text\n").unwrap();
        assert_eq!(crate::pyval::get(&v, "a"), Some(&Json::Null));
        assert_eq!(crate::pyval::get(&v, "b"), Some(&Json::Str("text".into())));
    }

    #[test]
    fn empty_flow_collections_are_containers_not_strings() {
        // 真源语料里真的有 `outputs: {}` —— 当成字符串会让边界摘要在该件上漂移
        let v = parse("io_types:\n  outputs: {}\n  inputs: []\n").unwrap();
        let io = crate::pyval::get(&v, "io_types").unwrap();
        assert_eq!(
            crate::pyval::get(io, "outputs"),
            Some(&Json::Object(vec![]))
        );
        assert_eq!(crate::pyval::get(io, "inputs"), Some(&Json::Array(vec![])));
        // 非空流式映射**现已支持**（真源 protocol.yaml 的 `mount_layers:` 需要它——
        // 早先 fail-closed 曾让 111 份 protocol.yaml 整件解析失败）
        let v2 = parse("k: {a: 1, b: x}\n").unwrap();
        assert_eq!(
            crate::pyval::get(&v2, "k"),
            Some(&Json::Object(vec![
                ("a".into(), Json::Int(1)),
                ("b".into(), Json::Str("x".into())),
            ]))
        );
    }

    #[test]
    fn block_list_items_may_be_mappings() {
        // 真源 `tool_face:` 的真形态（M10_节拍推进.md）——曾因「列表项是映射」被我 fail-closed，
        // 导致整个 M10 被丢弃、它发布的 minute_tick 变成"无发布方"。
        let body = "machine_contract:\n  id: 通用:M10\n  tool_face:\n    - purpose: 三轨换算\n      candidates:\n        - repo: https://github.com/arrow-py/arrow\n          ref: 1.3.0\n  events:\n    publish: [minute_tick]\n";
        let v = parse(body).expect("列表项是映射时必须可解析");
        let mc = crate::pyval::get(&v, "machine_contract").unwrap();
        let tf = crate::pyval::get(mc, "tool_face").unwrap();
        let Json::Array(items) = tf else {
            panic!("tool_face 应是列表")
        };
        assert_eq!(items.len(), 1);
        assert_eq!(
            crate::pyval::get(&items[0], "purpose"),
            Some(&Json::Str("三轨换算".into()))
        );
        let cands = crate::pyval::get(&items[0], "candidates").unwrap();
        let Json::Array(cs) = cands else {
            panic!("candidates 应是列表")
        };
        assert_eq!(
            crate::pyval::get(&cs[0], "repo"),
            Some(&Json::Str("https://github.com/arrow-py/arrow".into()))
        );
        // `ref: 1.3.0` 不是合法浮点 ⇒ PyYAML 当字符串
        assert_eq!(
            crate::pyval::get(&cs[0], "ref"),
            Some(&Json::Str("1.3.0".into()))
        );
    }

    #[test]
    fn scalar_types_follow_yaml_1_1() {
        assert_eq!(
            parse("k: 0\n").unwrap(),
            Json::Object(vec![("k".into(), Json::Int(0))])
        );
        assert_eq!(
            parse("k: 12\n").unwrap(),
            Json::Object(vec![("k".into(), Json::Int(12))])
        );
        assert_eq!(
            parse("k: -3\n").unwrap(),
            Json::Object(vec![("k".into(), Json::Int(-3))])
        );
        assert_eq!(
            parse("k: 010\n").unwrap(),
            Json::Object(vec![("k".into(), Json::Int(8))])
        );
        assert_eq!(
            parse("k: 0x1f\n").unwrap(),
            Json::Object(vec![("k".into(), Json::Int(31))])
        );
        assert_eq!(
            parse("k: true\n").unwrap(),
            Json::Object(vec![("k".into(), Json::Bool(true))])
        );
        assert_eq!(
            parse("k: no\n").unwrap(),
            Json::Object(vec![("k".into(), Json::Bool(false))])
        );
        assert_eq!(
            parse("k: ~\n").unwrap(),
            Json::Object(vec![("k".into(), Json::Null)])
        );
        assert_eq!(
            parse("k: 1.5\n").unwrap(),
            Json::Object(vec![("k".into(), Json::Float(1.5))])
        );
        assert_eq!(
            parse("k: untyped\n").unwrap(),
            Json::Object(vec![("k".into(), Json::Str("untyped".into()))])
        );
    }

    #[test]
    fn one_bad_scalar_must_not_sink_the_whole_block() {
        // 实测教训：`tick: 0` 曾让整件 M50 被丢弃，连带它的 publish 消失
        let body = "machine_contract:\n  id: M50\n  world_model:\n    abstract_state:\n      initial:\n        tick: 0\n  events:\n    publish: [minute_tick]\n";
        let v = parse(body).expect("含整数标量的块必须仍可解析");
        let mc = crate::pyval::get(&v, "machine_contract").unwrap();
        let ev = crate::pyval::get(mc, "events").unwrap();
        assert_eq!(
            crate::pyval::get(ev, "publish"),
            Some(&Json::Array(vec![Json::Str("minute_tick".into())]))
        );
    }

    #[test]
    fn out_of_subset_scalars_are_refused() {
        for bad in ["2026-01-01", "1:30"] {
            let body = format!("k: {}\n", bad);
            assert!(parse(&body).is_err(), "`{}` 应被拒绝", bad);
        }
    }

    #[test]
    fn fence_requires_marker_and_yaml_language() {
        let text = "```yaml\nother: 1\n```\n\n```yaml\nmachine_contract:\n  id: M01\n```\n";
        let got = fence_yaml(text, "machine_contract").expect("应命中第二个块");
        assert!(crate::pyval::get(&got, "machine_contract").is_some());
        assert!(fence_yaml("```json\nmachine_contract: x\n```", "machine_contract").is_none());
    }

    #[test]
    fn flow_mapping_is_supported() {
        // 真源 protocol.yaml 的 `mount_layers:` 真形态——早先 fail-closed 让 111 份件全挂
        let body = "mount_layers:\n  P40 行为决策: {default: [AI保险:M01], available: []}\n  P60 长期演变: {default: [AI保险:M02], available: []}\n";
        let v = parse(body).expect("流式映射必须可解析");
        let ml = crate::pyval::get(&v, "mount_layers").unwrap();
        let p40 = crate::pyval::get(ml, "P40 行为决策").unwrap();
        assert_eq!(
            crate::pyval::get(p40, "default"),
            Some(&Json::Array(vec![Json::Str("AI保险:M01".into())]))
        );
        assert_eq!(
            crate::pyval::get(p40, "available"),
            Some(&Json::Array(Vec::new()))
        );
    }

    #[test]
    fn flow_mapping_value_colon_is_content() {
        // `default: [A:B]` —— 值里的冒号后不跟空白，属内容
        let v = parse("m:\n  k: {default: [A:B], n: 1}\n").unwrap();
        let m = crate::pyval::get(&v, "m").unwrap();
        let k = crate::pyval::get(m, "k").unwrap();
        assert_eq!(
            crate::pyval::get(k, "default"),
            Some(&Json::Array(vec![Json::Str("A:B".into())]))
        );
        assert_eq!(crate::pyval::get(k, "n"), Some(&Json::Int(1)));
    }

    #[test]
    fn inline_splitting_respects_nesting() {
        // 嵌套集合里的逗号不得在顶层切分
        let v = parse("k: [[1, 2], [3]]\n").unwrap();
        assert_eq!(
            crate::pyval::get(&v, "k"),
            Some(&Json::Array(vec![
                Json::Array(vec![Json::Int(1), Json::Int(2)]),
                Json::Array(vec![Json::Int(3)]),
            ]))
        );
    }

    #[test]
    fn trailing_comment_after_empty_value_key_is_not_a_value() {
        // 真源 M91/M92 的真形态：`host_consumed:   # 说明` 后跟块列表
        let body = "events:\n  publish:\n    - a\n  host_consumed:   # 终端事件\n    - b\n";
        let v = parse(body).unwrap();
        let ev = crate::pyval::get(&v, "events").unwrap();
        assert_eq!(
            crate::pyval::get(ev, "publish"),
            Some(&Json::Array(vec![Json::Str("a".into())]))
        );
        assert_eq!(
            crate::pyval::get(ev, "host_consumed"),
            Some(&Json::Array(vec![Json::Str("b".into())])),
            "行尾注释不得被当成值"
        );
    }

    #[test]
    fn hash_inside_quotes_is_not_a_comment() {
        let v = parse("k: \"a # b\"\n").unwrap();
        assert_eq!(crate::pyval::get(&v, "k"), Some(&Json::Str("a # b".into())));
    }

    #[test]
    fn duplicate_keys_take_the_last_like_pyyaml() {
        let v = parse("k: a\nk: b\n").unwrap();
        assert_eq!(crate::pyval::get(&v, "k"), Some(&Json::Str("b".into())));
    }

    #[test]
    fn quoted_scalars_lose_their_quotes() {
        let v = parse("a: \"L2\"\nb: 'it''s'\n").unwrap();
        assert_eq!(crate::pyval::get(&v, "a"), Some(&Json::Str("L2".into())));
        assert_eq!(crate::pyval::get(&v, "b"), Some(&Json::Str("it's".into())));
    }
    /// M2 收口的**回归锁**：解析入口对任意畸形输入只许 `Ok/Err`、`Some/None`，**不许 panic**。
    ///
    /// 极简 fuzz（不用 cargo-fuzz：那要额外依赖面/CI 成本）：确定性 LCG 生成 1000 轮噪声，
    /// 一半是纯字节噪声、一半是把 YAML 元字符拼成「像 YAML 但不合法」的结构噪声。
    /// 任何一处 panic（含索引越界、切片越界、expect 裸崩）都会让本用例直接红。
    #[test]
    fn fuzz_malformed_input_never_panics() {
        // 覆盖真语料里出现过的元字符 + 边界字符（NUL / DEL / 反斜杠 / CR）。
        let alphabet: &[u8] = b"-:#[]{}\"'|>&*!%@`,. \t\r\n\\/0129aZ\x00\x7f";
        let mut state: u64 = 0x5eed_1234_abcd_0001;
        let mut next = |n: usize| -> usize {
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            ((state >> 33) as usize) % n.max(1)
        };
        for _round in 0..1000 {
            let len = next(96);
            let mut noise = String::new();
            for _ in 0..len {
                noise.push(alphabet[next(alphabet.len())] as char);
            }
            let _ = parse(&noise);
            let _ = fence_yaml(&noise, "machine_contract");

            let mut structured = String::new();
            for _ in 0..next(6) {
                let indent = " ".repeat(next(5));
                let frag = ["- ", "k: ", "k: [", "]", "{", "}", "\"", "|", ">", "\n"][next(10)];
                structured.push_str(&indent);
                structured.push_str(frag);
                structured.push('\n');
            }
            let _ = parse(&structured);
            let _ = fence_yaml(&structured, "machine_contract");
        }
        // 空输入与纯空白也必须给出确定结果（真源：空文档 → None/Null）。
        assert_eq!(parse("").unwrap(), Json::Null);
        assert!(parse("   \n\t\n").is_ok());
    }
}
