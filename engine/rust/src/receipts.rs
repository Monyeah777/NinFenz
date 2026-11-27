//! 协议层回执单根 —— **与 Python 真源 `desktop/src/core/receipts.py::build_scope` 逐字节对账**。
//!
//! 叶载荷 = `{"digest":<文件 sha256>,"id":<仓库相对路径>}`（紧凑无空格、键序 digest→id）；
//! 叶 = `SHA-256(0x00 ‖ 载荷)`；根 = RFC 6962 折叠。产物形态与真源 `write_scope` 落盘一致：
//! `json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"`，以 LF 写出、无 BOM。
//!
//! 只读：本模块**不写盘**，只把字节交回调用方。

use crate::merkle::{self, Hash};
use crate::pyjson::Json;
use std::path::Path;

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_table_matches_python_source() {
        assert_eq!(FIXED.len(), 54, "固定段条数必须与 receipts.py 同步");
        assert_eq!(FIXED[0], "STRATEGY.md");
        assert_eq!(FIXED[53], "desktop/src/core/registry.json");
    }

    #[test]
    fn payload_shape_is_compact_and_sorted() {
        let p = payload_bytes("a.md", "00ff");
        assert_eq!(
            String::from_utf8(p).unwrap(),
            "{\"digest\":\"00ff\",\"id\":\"a.md\"}"
        );
    }

    #[test]
    fn non_ascii_id_is_raw_utf8() {
        let p = payload_bytes("decisions/ADR-0005-新增NET引擎线.md", "ab");
        assert_eq!(
            String::from_utf8(p).unwrap(),
            "{\"digest\":\"ab\",\"id\":\"decisions/ADR-0005-新增NET引擎线.md\"}"
        );
    }
}
