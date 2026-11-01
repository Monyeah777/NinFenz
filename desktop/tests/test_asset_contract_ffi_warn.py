#!/usr/bin/env python3
"""F3（VULN-02）· `engine-rust-ffi` 契约面的注入自证（真源侧）。

判据是**声明驱动**的（`protocol/asset_contracts.json` 的 `engine-rust-ffi.warn_rules`）：
- ① 每个 `unsafe` 前 3 行内必须有 `SAFETY:` 注释；
- ② `from_raw_parts` 前必须有 null 检查（`is_null`）；
- ③ `#[no_mangle]` 导出面不得 panic / unwrap / expect / assert。

本测试做两件事：
1. **注入**：构造三类违规都踩的 `lib.rs` → 必须各报一条 WARN；再补齐 → 必须清零；
2. **清零状态**：真语料当前告警面必须为空（它是 WARN 面，不参与 issues/FAIL，但
   靠沉默过关会掩盖存量——故用断言把它钉住）。

Rust 侧同一批规则的同构自证见 `engine/rust/src/asset_contract.rs` 的
`ffi_warn_rules_fire_and_clear`（两侧断言同一批文案，防止口径漂移）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import asset_contract as ac  # noqa: E402

DECL = ROOT / "protocol" / "asset_contracts.json"


def _ffi_spec() -> dict:
    """从**真源声明**取 engine-rust-ffi 面（不复制一份规则，防两套口径）。"""
    doc = json.loads(DECL.read_text(encoding="utf-8"))
    for spec in doc.get("code") or []:
        if spec.get("id") == "engine-rust-ffi":
            return spec
    raise AssertionError("protocol/asset_contracts.json 缺 engine-rust-ffi 面")


BAD = r"""pub unsafe fn raw(p: *const u8, len: usize) -> u8 {
    let s = std::slice::from_raw_parts(p, len);
    s[0]
}
#[no_mangle]
pub extern "C" fn boom() -> u32 { panic!() }
"""

GOOD = r"""// SAFETY: 调用方保证 p 有效；本块只读而不写。
pub unsafe fn raw(p: *const u8, len: usize) -> u8 {
    if p.is_null() { return 0; }
    let s = std::slice::from_raw_parts(p, len);
    s[0]
}
#[no_mangle]
pub extern "C" fn ok() -> u32 { ABI_VERSION }
"""


class FfiContractWarnTest(unittest.TestCase):
    def _write(self, text: str) -> str:
        tmp = tempfile.mkdtemp(prefix="nf-ffi-warn-")
        # 路径须落在真源声明的 glob（engine/rust/ffi/src/**/*.rs）内，否则 resolve 命中 0 件。
        p = Path(tmp) / "engine" / "rust" / "ffi" / "src" / "lib.rs"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return tmp

    def test_injected_violations_are_warned_then_cleared(self):
        spec = _ffi_spec()
        warns = ac._code_warns(self._write(BAD), spec)
        self.assertEqual(3, len(warns), f"三类违规应各报一条：{warns}")
        self.assertTrue(any("SAFETY:" in w for w in warns), "缺 SAFETY 注释应被抓")
        self.assertTrue(any("from_raw_parts" in w for w in warns), "缺空指针检查应被抓")
        self.assertTrue(any("panic!" in w for w in warns), "导出面 panic 应被抓")
        cleared = ac._code_warns(self._write(GOOD), spec)
        self.assertEqual([], cleared, f"补齐后 WARN 面应清零：{cleared}")

    def test_real_corpus_warn_face_is_clean(self):
        # WARN 面**不进** issues（不 FAIL），但必须可见：真语料当前应为零债。
        issues, warns, _stats = ac.scan(str(ROOT))
        self.assertEqual([], issues, "真语料 issues 应为空（WARN 面不得影响 FAIL 判定）")
        self.assertEqual([], warns, f"真语料 FFI 告警面应已清零：{warns}")


if __name__ == "__main__":
    unittest.main()
