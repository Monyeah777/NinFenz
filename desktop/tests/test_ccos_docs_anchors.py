"""docs/ccos/*.md 的**代码锚点**判据：文档必须能指到真实实现，不能只讲概念。

依据（第 38 轮锚点棘轮的延伸）：方法包动作已强制「有锚点或显式声明概念」；
同一规矩适用于**文档**——docs/ccos 是面向读者的能力说明，若整篇没有任何可核的
仓库路径，它只能靠作者记忆维护，半年后必然与代码分叉。

判据：① 每篇至少 1 个**真实存在**的、带仓库目录前缀的路径；
② 这些带前缀的路径不得指向不存在的文件；③ 判据自身不空转（>=10 篇）。

只看**带目录前缀**的 token（desktop/ scripts/ protocol/ results/ docs/ ...）：
裸文件名（items.json 这类）是 CLI 示例占位，不当作仓库路径。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "ccos"
DIRS = ("desktop", "scripts", "protocol", "results", "docs", "packaging", "tui",
        "engine", "tools", ".github")
_DIRS_PATTERN = "|".join(re.escape(d) for d in DIRS)
PREFIXED = re.compile(r"(?<![\w/.-])((?:" + _DIRS_PATTERN + r")/[\w./-]+\*?)")


def _prefixed(text: str) -> list[str]:
    out = []
    for raw in PREFIXED.findall(text):
        rel = raw.strip().rstrip(".,;:)").rstrip("/")
        if not rel or len(rel) > 120 or ".." in rel:
            continue
        if any(ch in rel for ch in "<>*$"):
            continue
        out.append(rel)
    return out


#: 已知生成物前缀（git 不可用时也要能判：快照/归档环境里可能没有可用的 git）
GENERATED_PREFIXES = ("engine/dotnet/dist", "packaging/npm/payload", "site/dist",
                      "node_modules", "dist", ".worktrees")


def _ignored(rel: str) -> bool:
    """构建产物/被忽略路径不算仓库文件（干净快照里必然不存在）。"""
    import shutil
    import subprocess
    if any(rel == p or rel.startswith(p + "/") for p in GENERATED_PREFIXES):
        return True
    git = shutil.which("git")
    if not git:
        return False
    try:
        proc = subprocess.run([git, "-C", str(ROOT), "check-ignore", "-q", rel],
                              timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0

def _exists(rel: str) -> bool:
    return (ROOT / rel).exists() or (ROOT / "desktop" / "src" / rel).exists()


class DocsAnchorTest(unittest.TestCase):
    def test_each_doc_has_a_real_repo_path(self):
        docs = sorted(DOCS.glob("*.md"))
        self.assertGreaterEqual(len(docs), 10, "docs/ccos 文档数异常少")
        bad = [p.name for p in docs
               if not any(_exists(rel) and not _ignored(rel) for rel in _prefixed(
                   p.read_text(encoding="utf-8", errors="replace")))]
        self.assertEqual([], bad, f"这些文档没有任何可核的仓库路径：{bad}")

    def test_prefixed_paths_actually_exist(self):
        broken = []
        for path in sorted(DOCS.glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for rel in _prefixed(text):
                if not _exists(rel) and not _ignored(rel):
                    broken.append(f"{path.name} → {rel}")
        self.assertEqual([], broken[:10], f"文档里指向了不存在的路径：{broken[:10]}")


if __name__ == "__main__":
    unittest.main()
