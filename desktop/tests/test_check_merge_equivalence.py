#!/usr/bin/env python3
"""步骤5「合并同类项」等价性证明：参数化引擎 vs 旧判据（独立参照实现 + 变异夹具）。

覆盖范围（实测可无损合并的那一组）：check1 / check3 / check4 / check5 / check6 ——
它们的判定形状同为「声明清单 × 文件系统」（在场 / 关键词在场），旧实现是五段各写一遍的
bash 循环。旧 check 一旦有**独有**判定（如 check20 的模块文档必填项、check10 的 EXT
溯源 + 版本锚点），就不进本组。

证明方式（两层）：
1. **引擎 ≡ 参照实现**：把适配器里的声明表解析出来，喂给本文件独立实现的参照判定
   （不复用 verify.sh 的引擎代码），逐条比对 [FAIL] 消息集合；
2. **变异必红**：删件 / 抽词 后双方都必须报出同一条消息——否则这条对账是空转。

文案约束：旧失败文案**不含**"修复指引"，本测试也不强求——文案是受棘轮保护的资产
（ADR-0002 / gate_labels 逐字抽取），合并只许改组织方式、不许改字。
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import posix_shell as psh  # noqa: E402

VERIFY = ROOT / "verify.sh"
BASH = psh.find_posix_shell()
CHECKS = (1, 3, 4, 5, 6)
DECL_KINDS = ("file", "dir", "token", "all")

#: 每个 check 的变异夹具：至少一条「让旧判据红」的输入（删件 / 抽词）。
MUTATIONS = {
    1: [("delete", "04_模块库/通用类/M50_调度器.md", ""), ("delete", "LICENSE", "")],
    3: [("drop", "01_核心协议.md", "三正交分离"), ("drop", "01_核心协议.md", "M80")],
    4: [("drop", "04_模块库/通用类/M23_可见性边界.md", "fail"), ("delete", "06_Agent执行协议.md", "")],
    5: [("drop", "04_模块库/通用类/M80_输出质检门.md", "pass:"), ("drop", "06_Agent执行协议.md", "最小可读")],
    6: [("drop", "README.md", "07_官方核心出厂与社区预设导航"), ("delete", "05_资产库/README.md", "")],
}


def _brace_block(lines, start):
    depth = 0
    for j in range(start, len(lines)):
        depth += lines[j].count("{") - lines[j].count("}")
        if depth == 0 and j > start:
            return "\n".join(lines[start:j + 1])
    raise AssertionError("括号未闭合：%s" % lines[start])


def adapter(check_num):
    lines = VERIFY.read_text(encoding="utf-8").split("\n")
    return _brace_block(lines, lines.index("check%d(){" % check_num))


def engine_src():
    lines = VERIFY.read_text(encoding="utf-8").split("\n")
    return _brace_block(lines, lines.index("_decl_check(){"))


def decls_of(check_num):
    """从适配器 heredoc 解析声明表 → [(kind, path, token, message)]。"""
    out = []
    for line in adapter(check_num).split("\n"):
        parts = line.split("\t")
        if len(parts) == 4 and parts[0] in DECL_KINDS:
            out.append((parts[0], parts[1], "" if parts[2] == "-" else parts[2], parts[3]))
    return out


def reference(decls, tree):
    """独立参照实现（不复用 verify.sh 的 _decl_check）：→ 缺失消息列表。"""
    miss = []
    for kind, rel, token, msg in decls:
        path = Path(tree) / rel
        if kind == "file":
            ok = path.is_file()
        elif kind == "dir":
            ok = path.is_dir()
        elif kind == "token":
            ok = path.is_file() and token in path.read_text(encoding="utf-8")
        else:
            ok = path.is_file() and all(t in path.read_text(encoding="utf-8")
                                        for t in token.split("|"))
        if not ok:
            miss.append(msg)
    return miss


def run_adapter(check_num, tree):
    script = (
        "set -u\n"
        "PASS=0;FAIL=0;WARN=0\n"
        "ok(){ PASS=$((PASS+1)); printf '  [PASS] %s\n' \"$1\"; }\n"
        "no(){ FAIL=$((FAIL+1)); printf '  [FAIL] %s\n' \"$1\"; }\n"
        "wn(){ WARN=$((WARN+1)); printf '  [WARN] %s\n' \"$1\"; }\n"
        + engine_src() + "\n" + adapter(check_num) + "\n"
        + "check%d\n" % check_num
    )
    proc = subprocess.run([BASH, "-c", script], cwd=str(tree), capture_output=True,
                          text=True, encoding="utf-8")
    got = []
    for line in proc.stdout.split("\n"):
        if line.startswith("  [FAIL] "):
            got.append(line[len("  [FAIL] "):])
    return got


def build_tree(paths):
    tmp = tempfile.mkdtemp()
    for rel in sorted(set(paths)):
        src = ROOT / rel
        if not src.exists():
            continue
        tgt = Path(tmp) / rel
        tgt.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            tgt.mkdir(parents=True, exist_ok=True)
        else:
            shutil.copy2(src, tgt)
    return tmp


def mutate(tree, kind, rel, token=""):
    path = Path(tree) / rel
    if kind == "delete":
        path.unlink()
        return
    text = path.read_text(encoding="utf-8")
    # 用 replace 全量抽词：同一关键词在正文里常有多次出现（如 M80 既是模块名又是引用），
    # 只删第一处会让夹具「看起来改了、其实还命中」——变异必须真的让它不命中。
    path.write_text(text.replace(token, ""), encoding="utf-8", newline="\n")


@unittest.skipUnless(BASH, "没有 bash：合并判据的等价性证明无法跑")
class MergeEquivalenceTest(unittest.TestCase):
    def _compare(self, check_num, tag, mutate_kind=None, rel="", token=""):
        decls = decls_of(check_num)
        self.assertTrue(decls, "check%d 适配器里没有声明表" % check_num)
        tree = build_tree([d[1] for d in decls])
        try:
            if mutate_kind:
                mutate(tree, mutate_kind, rel, token)
            want = reference(decls, tree)
            got = run_adapter(check_num, tree)
            self.assertEqual(want, got, "check%d %s：引擎与参照实现不一致" % (check_num, tag))
            return want
        finally:
            shutil.rmtree(tree, ignore_errors=True)

    def test_clean_tree_has_no_findings(self):
        for num in CHECKS:
            self.assertEqual([], self._compare(num, "干净树"))

    def test_mutations_are_red_on_both_sides(self):
        for num in CHECKS:
            for i, mut in enumerate(MUTATIONS[num]):
                got = self._compare(num, "变异例%d" % i, mut[0], mut[1], mut[2])
                self.assertTrue(got, "check%d 变异例%d 没红" % (num, i))

    def test_messages_are_verbatim_from_source(self):
        decls = decls_of(3)
        self.assertIn(("token", "01_核心协议.md", "三正交分离", "01 §5 缺不变式: 三正交分离"),
                      decls)


if __name__ == "__main__":
    unittest.main()
