"""core.asset_density 私有实现分片 1/2（对外只经 core.asset_density 门面导入）：_CENSUS_CACHE 等"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import conformance_scan as csc

#: 引用度普查的内容键缓存：键 = **语料与键集的 sha256**（见 `usage_scan`）。
#: 必要性（实测）：一次普查 = 1499 个键 × 3.5 MB 语料的逐键子串计数 ≈ **2.7 s**；而
#: 「跑全量评分」的路径（`nf score`、回归单测、发布体检 + 覆盖率通道）会在同一进程里
#: 反复走到这里。键取内容哈希（不是路径）→ 内容没变必然同结果，内容一改键就变，
#: 因此不存在「改了文件还读到旧值」的陈旧风险。
_CENSUS_CACHE: Dict[str, Dict[str, int]] = {}


_CENSUS_CACHE_MAX = 64


#: **逐件**计数的内容键缓存（键 = (该件正文 sha256, 键集 sha256)）：`count_keys_additive` 用它把
#: 「改一件就要重扫 3.5 MB」变成「只重算被改的那一件」。存**稀疏**字典（单件里绝大多数键不出现），
#: 于是 2500 件 × ~30 个非零键 ≈ 75k 条，量级完全可控。
_FILE_COUNT_CACHE: Dict[Any, Dict[str, int]] = {}


_FILE_COUNT_CACHE_MAX = 4096


#: `_keys_of` 的**逐件内容键缓存**（键 = (文件名 stem, 正文 sha256)）。依据（实测 2026-09-29）：
#: `usage_scan` 要为 360 份资产件各跑四个正则取键（实测 6.6 ms），而键集只是**该件正文 + 文件名**
#: 的纯函数——改 `04_模块库`、文档、代码这类与资产无关的件时结果必然不变。
_KEYS_OF_CACHE: Dict[Any, List[str]] = {}


_KEYS_OF_CACHE_MAX = 4096


MAX_KEYS = 100_000


MAX_KEY_CHARS = 8 * 1024 * 1024


MAX_ASSET_FILE_BYTES = 16 * 1024 * 1024


#: `usage_scan` 的**语料面**（就是它数的那些件）。指纹走常驻层**逐件摘要**，不再把 3.5 MB 正文
#: 逐件 `encode()` 后重哈希一遍（实测那条 2815 件的哈希环占 `usage_scan` 的三分之一）。
CORPUS_PATTERNS = ("04_模块库/**/*.md", "community/**/*.md", "docs/**/*.md")


def _keys_of(path: Path, text: Optional[str] = None) -> List[str]:
    """文件名令牌 ∪ 正文键声明（`text` 可由调用方传入——避免同一份件被读两遍）。"""
    if text is None:
        try:
            text = csc.read_text_cached(path)
        except OSError:
            return sorted(set(re.findall(r"[A-Z][A-Z0-9_]*", path.stem)))
    ck = (path.stem, hashlib.sha256(text.encode("utf-8")).hexdigest())
    hit = _KEYS_OF_CACHE.get(ck)
    if hit is not None:                       # 键集只是**该件正文 + 文件名**的纯函数（键即内容）
        return hit
    keys = set(re.findall(r"[A-Z][A-Z0-9_]*", path.stem))
    head = text[:6000]
    # 条目键面（2026-09-23 对齐）：除大写下划线键外，仓库里还大量使用**带连字符的条目键**
    # （如域包的 `C01-01` / `A08-07` —— 经 asset_get('<资产键>','<条目键>') 真实可寻址）。
    # 原字符集 `[A-Z0-9_]` 看不见它们 → 密度被系统性低估（AI 品类域包扩面后实测暴露）。
    keys.update(re.findall(r"`([A-Z][A-Z0-9_-]{2,})`", head))
    keys.update(re.findall(r"\"([A-Z][A-Z0-9_-]{2,})\"\s*:", head))
    keys.update(re.findall(r"##\s*([A-Z][A-Z0-9_-]{2,})", head))
    got = sorted(keys)
    if len(got) > MAX_KEYS:
        raise ValueError("%s 的键数 %d 超过上限 %d" % (path, len(got), MAX_KEYS))
    if len(_KEYS_OF_CACHE) >= _KEYS_OF_CACHE_MAX:
        _KEYS_OF_CACHE.clear()
    _KEYS_OF_CACHE[ck] = got
    return got


#: `scan()` / `thickness_scan()` 的全部输入：就是它们枚举的那两条**资产面**
#: （community 各包的 assets/*.md + 官方用户自定义资产）。两条面都很窄，
#: 所以「改文档/代码」不会作废它们的缓存，只有动资产才重算。
ASSET_INPUTS = ("community/*/assets/*.md", "05_资产库/用户自定义/*.md")


def _scan_impl(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    issues: List[str] = []
    rows = []
    patterns = ["community/*/assets/*.md", "05_资产库/用户自定义/*.md"]
    for pat in patterns:
        # 走共享枚举器（`os.scandir` 单遍 + 作用域内子树清单复用）：同一棵 community
        # 过去被 scan / thickness / usage 各自用 Path.glob/rglob 走了一遍。
        for rel in csc.iter_files(root, pat):
            if rel.rsplit("/", 1)[-1] == "README.md":
                continue
            path = Path(root) / rel
            try:
                size = path.stat().st_size
                if size > MAX_ASSET_FILE_BYTES:
                    issues.append("%s 过大（%d > %d 字节）" % (rel, size, MAX_ASSET_FILE_BYTES))
                    continue
                text = csc.read_text_cached(path)
            except OSError as exc:
                issues.append("%s 不可读：%s" % (rel, exc))
                continue
            if not text.strip():
                issues.append("%s 为空档（0 字符）" % rel)
                continue
            try:
                keys = _keys_of(Path(rel), text)
            except ValueError as exc:
                issues.append(str(exc))
                continue
            pkg = rel.split("/")[1] if rel.startswith("community") else "官方"
            rows.append({"package": pkg, "file": rel,
                         "keys": len(keys), "key_list": keys,
                         "chars": len(text)})
    n_files = len(rows)
    n_keys = sum(x["keys"] for x in rows)
    n_unkeyed = sum(1 for x in rows if x["keys"] == 0)
    n_tiny = sum(1 for x in rows if x["chars"] < 200)
    stats = {"files": n_files, "keys": n_keys,
             "unkeyed": n_unkeyed, "tiny": n_tiny,
             "avg_keys_per_file": round(n_keys / max(1, n_files), 2)}
    return issues, stats


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """资产台账面体检（原体见 `_scan_impl`）。派生结果按**输入内容指纹**缓存（键即内容）。"""
    return csc.memo_pair("asset-density", ASSET_INPUTS, _scan_impl, root,
                          code_modules=("core.asset_density",))


#: 键集 → 自动机（上限几份：一次普查只用一份键集）。键集变了自然换机，无需手工失效。
_MATCHERS: Dict[str, "_Matcher"] = {}


_MATCHERS_MAX = 4
