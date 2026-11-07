"""跨用例隔离的**静态**判据：不许把桩打在「模块导入时抓到的 core 模块」上。

为什么只钉这一个面（2026-11-05 血账）：同一根因在四轮里犯了四次——
常驻层会在代码变化时 reload core.*，于是「导入时抓到的模块对象」可能已经过时；
桩打在旧对象上，被测代码用的是新对象 → 桩不生效 → 判据假绿或假红。
四次都在原子写面上（_replace / write_text / write_bytes），故本判据先钉死这个面：
打桩 atomic_write 的落盘面时，目标必须是运行时取的模块（_live("core.atomic_write")），
不能是「from core import atomic_write as aw」这种模块级别名。

其余模块别名打桩不在此列（多数打常量，风险面不同）；若哪天在 reload 面上出事，
往 ATOMIC_ATTRS 加规则即可——判据本身有变异自证，不会静默放过。
"""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "desktop" / "tests"

#: 原子写落盘面：这几个属性被打桩时必须是运行时模块
ATOMIC_ATTRS = frozenset({"_replace", "write_text", "write_bytes", "write_json"})

#: 已复核豁免（file -> 理由）。空表是目标：豁免必须逐条写清为什么打桩面是安全的。
REVIEWED_EXEMPT: dict = {}


def _module_scope_core_aliases(tree: ast.AST) -> set:
    """模块级 from core import X [as Y] 的别名集合。"""
    out = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("core"):
            for alias in node.names:
                out.add(alias.asname or alias.name)
    return out


def _is_mock_patch_object(call: ast.Call) -> bool:
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr == "object"):
        return False
    inner = func.value
    return (isinstance(inner, ast.Attribute) and inner.attr == "patch"
            and isinstance(inner.value, ast.Name) and inner.value.id == "mock")


def fragile_patch_sites(source: str) -> list:
    """源码 -> [(lineno, alias, attr)]：打在模块级别名上的原子写落盘面桩。"""
    tree = ast.parse(source)
    aliases = _module_scope_core_aliases(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_mock_patch_object(node):
            continue
        if len(node.args) < 2:
            continue
        target, attr = node.args[0], node.args[1]
        if (isinstance(target, ast.Name) and target.id in aliases
                and isinstance(attr, ast.Constant) and attr.value in ATOMIC_ATTRS):
            out.append((node.lineno, target.id, str(attr.value)))
    return out


class TestMutationSelfCheck(unittest.TestCase):
    """判据自身的变异自证：该红的红、该绿的不许误报（否则判据是摆设）。"""

    def test_flags_module_alias_patch(self):
        src = ("from unittest import mock\n"
               "from core import atomic_write as aw\n"
               "def f():\n"
               "    with mock.patch.object(aw, \"_replace\", side_effect=OSError(\"x\")):\n"
               "        pass\n")
        self.assertEqual([(4, "aw", "_replace")], fragile_patch_sites(src))

    def test_accepts_live_runtime_target(self):
        src = ("from unittest import mock\n"
               "from core import atomic_write as aw\n"
               "def f():\n"
               "    with mock.patch.object(_live(\"core.atomic_write\"), \"_replace\"):\n"
               "        pass\n")
        self.assertEqual([], fragile_patch_sites(src))

    def test_accepts_function_local_import(self):
        src = ("from unittest import mock\n"
               "def f():\n"
               "    from core import atomic_write as aw\n"
               "    with mock.patch.object(aw, \"_replace\"):\n"
               "        pass\n")
        self.assertEqual([], fragile_patch_sites(src), "函数内导入是运行时取，风险面不同")

    def test_accepts_other_attributes(self):
        src = ("from unittest import mock\n"
               "from core import agent_density as ad\n"
               "def f():\n"
               "    with mock.patch.object(ad, \"MAX_BLOB_TEXT\", 1):\n"
               "        pass\n")
        self.assertEqual([], fragile_patch_sites(src))


class TestRepoIsolationPatterns(unittest.TestCase):
    def test_no_fragile_atomic_write_patches(self):
        bad = []
        for path in sorted(TESTS.glob("test*.py")):
            if path.name in REVIEWED_EXEMPT:
                continue
            try:
                hits = fragile_patch_sites(path.read_text(encoding="utf-8",
                                                           errors="replace"))
            except SyntaxError as exc:
                bad.append(f"{path.name}: 无法解析（{exc}）")
                continue
            bad.extend(f"{path.name}:{lineno} 打在别名 {alias} 的 {attr} 上"
                       for lineno, alias, attr in hits)
        self.assertEqual([], bad,
                         "打桩必须打在运行时模块上（修复指引：改用 _live 取当前模块 / "
                         "_no_replace()；理由见本文件 docstring）")

    def test_exemptions_carry_reasons(self):
        for name, reason in REVIEWED_EXEMPT.items():
            self.assertTrue((TESTS / name).is_file(), f"豁免表指向不存在的文件：{name}")
            self.assertTrue(str(reason).strip(), f"豁免必须写理由：{name}")


if __name__ == "__main__":
    unittest.main()
