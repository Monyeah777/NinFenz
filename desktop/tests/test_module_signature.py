"""模块边界签名（F14：解析面为 0 不得空过）。"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import module_signature as ms  # noqa: E402

_FENCE = """# 模块 %s · 测试

```yaml
machine_contract:
  id: %s
  category: 测试
  layer: L1
  inputs: []
  outputs: []
  events: []
  interfaces: []
  io_types: []
```
"""




def _write_module(root: Path, mid: str) -> None:
    d = root / "04_模块库" / "测试类"
    d.mkdir(parents=True, exist_ok=True)
    (d / ("%s_测试.md" % mid)).write_text(_FENCE % (mid, mid), encoding="utf-8")


class ModuleSignatureEmptyTest(unittest.TestCase):
    def test_missing_baseline_is_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            issues, _w, _s = ms.verify(tmp)
        self.assertTrue(any("缺模块边界基线" in i for i in issues), issues)

    def test_zero_signatures_is_not_a_silent_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "protocol").mkdir()
            (d / "protocol" / "module_signatures.json").write_text(
                '{"schema": "nf-module-signatures/1", "modules": {"M00": {"digest": "x"}}}',
                encoding="utf-8")
            # 没有任何模块文档 → 解析面 0 条
            issues, warns, stats = ms.verify(tmp)
        self.assertTrue(any("0 模块" in i for i in issues), issues)
        self.assertEqual(0, stats.get("modules"))

    def test_drift_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            _write_module(d, "M00")
            ms.write(tmp)
            _write_module(d, "M00")   # 同内容 → 无漂移
            self.assertEqual([], ms.verify(tmp)[0])
            (d / "04_模块库" / "测试类" / "M00_测试.md").write_text(
                _FENCE.replace("layer: L1", "layer: L2") % ("M00", "M00"),
                encoding="utf-8")
            issues, _w, _s = ms.verify(tmp)
        self.assertTrue(any("边界漂移" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
