#!/usr/bin/env python3
"""TISA —— 增量静态分析缓存（Time-Incremental Static Analysis）。

目标：**没变的测试模块不再重跑**。判据不是"文件清单变了没"（粗），而是**内容寻址**：
对每个测试模块算一枚 key = sha256(测试源码 + 其依赖闭包里每个 core 文件的内容 + 工具版本)。
key 一致 ⇒ 该模块的输入面与上次通过的运行完全相同 ⇒ 可以安全跳过。

为什么不用 mtime：mtime 在 checkout / 复制 / CI 上不可靠；内容摘要跨机器稳定。
为什么不用"全仓树摘要"：那会让改任何一个文件都让全部测试失效（等于没做增量）——按
**反向依赖闭包**取摘要，只让真正受影响的模块失效。

纪律（与 verify_tests 同源）：
- **不做假绿**：只有"上次同一 key 全部通过"才跳过；一旦该模块任一条测试失败/报错，
  本次不写缓存（下次照跑），且不因跳过而降低任何判据。
- **可回退**：`NF_TISA=0` 或 `--jobs` 外不加 `--incremental` 时行为与历史完全一致。
- 缓存位置：`.nf-cache/tisa.json`（gitignored；可整体删除，无副作用）。
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 本脚本会打印中文判定信息：Windows 控制台默认 GBK，必须钉 UTF-8（与其余入口同一纪律）。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")
TESTS_REL = "desktop/tests"
CORE_REL = "desktop/src/core"
CACHE_REL = ".nf-cache/tisa.json"
SCHEMA = "nf-tisa/1"


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _core_imports(text: str) -> set:
    """从测试源码抽它直接引用的 core 模块名（兼容 `from core import X` / `from core.X import ..`）。"""
    out: set = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "core":
                out.update(a.name for a in node.names)
            elif mod.startswith("core."):
                out.add(mod.split(".")[1])
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("core."):
                    out.add(a.name.split(".")[1])
    return out


def _module_imports(path: Path) -> set:
    """core 模块之间的相对/绝对 import（`from . import x` / `from .x import y`）。"""
    out: set = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.module is None:
                out.update(a.name for a in node.names)
            elif node.level and node.module:
                out.add(node.module.split(".")[0])
            elif (node.module or "").startswith("core."):
                out.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("core."):
                    out.add(a.name.split(".")[1])
    return out


def _closure(seeds: set, root: Path) -> dict:
    """从 seeds 出发求 core 模块的传递闭包 → {模块名: 文件 Path}（缺件的名字跳过）。"""
    got: dict = {}
    stack = list(seeds)
    while stack:
        name = stack.pop()
        if name in got:
            continue
        p = root / CORE_REL / ("%s.py" % name)
        if not p.is_file():
            continue
        got[name] = p
        stack.extend(_module_imports(p) - set(got))
    return got


def _tool_version(root: Path) -> str:
    """工具版本面：verify.sh 的版本头 + Python 主版本（版本变了就不能复用旧结论）。"""
    ver = ""
    try:
        head = (root / "verify.sh").read_text(encoding="utf-8", errors="replace")[:2000]
        for line in head.splitlines():
            if "# 版本" in line:
                ver = " ".join(line.split()[:3])
                break
    except OSError:
        pass
    return "%s|py%d.%d" % (ver, sys.version_info[0], sys.version_info[1])


def _file_digest(p: Path, cache: dict) -> str:
    """单个文件的内容摘要（一次 plan 内按路径去重：327 个模块共享同一批 core 文件）。"""
    key = str(p)
    got = cache.get(key)
    if got is None:
        try:
            got = _digest_bytes(p.read_bytes())
        except OSError:
            got = ""
        cache[key] = got
    return got


def module_key(test_path: Path, root: Path = ROOT, version: str = "",
               digest_cache: dict = None) -> str:
    """该测试模块的内容寻址 key（测试源码 + 依赖闭包 + 工具版本）。"""
    cache = {} if digest_cache is None else digest_cache
    h = hashlib.sha256()
    h.update(version.encode("utf-8"))
    h.update(_file_digest(test_path, cache).encode("utf-8"))
    seeds = _core_imports(test_path.read_text(encoding="utf-8", errors="replace"))
    for name, p in sorted(_closure(seeds, root).items()):
        digest = _file_digest(p, cache)
        if not digest:
            return ""
        h.update(name.encode("utf-8"))
        h.update(digest.encode("utf-8"))
    return h.hexdigest()


def module_of(test_id: str) -> str:
    return test_id.split(".")[0]


def modules_of(ids: list) -> dict:
    out: dict = {}
    for tid in ids:
        out.setdefault(module_of(tid), []).append(tid)
    return out


def load(root: Path = ROOT) -> dict:
    p = root / CACHE_REL
    if not p.is_file():
        return {}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        # 可吞：缓存坏件 = 无缓存（下次全跑，绝不假绿）；缓存只是加速面，坏了不影响判据。
        return {}
    return doc if isinstance(doc, dict) and doc.get("schema") == SCHEMA else {}


def save(doc: dict, root: Path = ROOT) -> None:
    from core import atomic_write          # 在仓写盘唯一入口（脚本面同纪律）
    doc["schema"] = SCHEMA
    atomic_write.write_text(root / CACHE_REL,
                            json.dumps(doc, ensure_ascii=False, indent=2,
                                       sort_keys=True) + "\n")
def plan(ids: list, root: Path = ROOT) -> tuple:
    """→ (skip_ids, run_ids, keys_by_module)。

    跳过条件：该模块**所有**测试都在缓存里且上次 passed。key 不同 = 输入面变了 = 照跑。
    """
    cache = load(root).get("modules") or {}
    version = _tool_version(root)
    keys, skip, run = {}, [], []
    digest_cache: dict = {}
    for mod, mod_ids in sorted(modules_of(ids).items()):
        p = root / TESTS_REL / ("%s.py" % mod)
        key = module_key(p, root, version, digest_cache) if p.is_file() else ""
        keys[mod] = key
        hit = cache.get(mod) or {}
        if key and hit.get("key") == key and hit.get("passed") is True:
            skip.extend(mod_ids)
        else:
            run.extend(mod_ids)
    return sorted(skip), sorted(run), keys


def commit(ids_run: list, failed_ids: list, keys: dict, root: Path = ROOT) -> dict:
    """本次跑完后写缓存：按模块记 key + passed（该模块**所有**跑过的测试都没失败）。"""
    doc = load(root)
    doc.setdefault("schema", SCHEMA)
    mods = doc.setdefault("modules", {})
    failed_mods = {module_of(t) for t in failed_ids}
    for mod, mod_ids in modules_of(ids_run).items():
        key = keys.get(mod) or ""
        if not key:
            continue
        if mod in failed_mods:
            mods.pop(mod, None)                 # 失败即失效（下次照跑，绝不留假绿）
            continue
        mods[mod] = {"key": key, "passed": True, "tests": len(mod_ids)}
    save(doc, root)
    return doc


def main(argv: list) -> int:
    ids = []
    for line in sys.stdin.read().splitlines():
        if line.strip():
            ids.append(line.strip())
    skip, run, _k = plan(ids)
    print("TISA: 跳过 %d 条（模块未变）/ 需跑 %d 条" % (len(skip), len(run)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
