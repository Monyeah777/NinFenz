"""core.asset_density 私有实现分片 2/2（对外只经 core.asset_density 门面导入）：MAX_BLOB_TEXT 等"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import conformance_scan as csc
from core import disk_cache
from core import import_graph as _ig

from ._part1 import (
    _CENSUS_CACHE,
    _CENSUS_CACHE_MAX,
    _FILE_COUNT_CACHE,
    _FILE_COUNT_CACHE_MAX,
    _MATCHERS,
    _MATCHERS_MAX,
    ASSET_INPUTS,
    CORPUS_PATTERNS,
    MAX_ASSET_FILE_BYTES,
    MAX_KEY_CHARS,
    MAX_KEYS,
    _keys_of,
)

MAX_BLOB_TEXT = 64 * 1024 * 1024


MAX_MATCHER_NODES = 1_000_000


class _Matcher:
    """键集固定时的 **Aho–Corasick** 自动机：**建一次，多份文本复用**。

    2026-09-29 实测（一个真事故）：上一版把自动机**逐件各建一次**（921 件）——建机成本
    ≈2 ms × 921 ≈ **2.0 s**，比「拼成一整条一次扫完」（0.3 s）**慢 6 倍**。自动机只由**键集**
    决定，所以按键集缓存复用：逐件扫描就只剩 O(该件长度)，而逐件结果又能按内容缓存。
    """

    __slots__ = ("_goto", "_out", "_fail", "keys")

    def __init__(self, keys):
        from collections import deque
        self.keys = [str(k) for k in keys]
        key_chars = sum(len(k) for k in self.keys)
        if len(self.keys) > MAX_KEYS or key_chars > MAX_KEY_CHARS:
            raise ValueError("键集超限（%d 键 / %d 字符）" % (len(self.keys), key_chars))
        goto: List[Dict[str, int]] = [{}]
        out: List[List[str]] = [[]]
        fail: List[int] = [0]
        for k in self.keys:
            node = 0
            for ch in k:
                nxt = goto[node].get(ch)
                if nxt is None:
                    if len(goto) >= MAX_MATCHER_NODES:
                        raise ValueError("自动机节点数超过上限 %d" % MAX_MATCHER_NODES)
                    nxt = len(goto)
                    goto.append({})
                    out.append([])
                    fail.append(0)
                    goto[node][ch] = nxt
                node = nxt
            out[node].append(k)
        queue = deque(goto[0].values())
        while queue:
            node = queue.popleft()
            for ch, nxt in goto[node].items():
                f = fail[node]
                while f and ch not in goto[f]:
                    f = fail[f]
                fail[nxt] = goto[f].get(ch, 0)
                out[nxt] = out[nxt] + out[fail[nxt]]   # 输出沿失败链传播（互相包含的键都算）
                queue.append(nxt)
        self._goto, self._out, self._fail = goto, out, fail

    def counts(self, blob: str) -> Dict[str, int]:
        """一遍扫过 `blob`：按键盘下每次出现的位置，再**按键做非重叠贪心计数**
        （`pos > 上次命中结束位置` 才计数）——`str.count` 的左优先非重叠语义就是这样。"""
        _goto, _out, _fail = self._goto, self._out, self._fail
        positions: Dict[str, List[int]] = {}
        node = 0
        for i, ch in enumerate(blob):
            while node and ch not in _goto[node]:
                node = _fail[node]
            node = _goto[node].get(ch, 0)
            for k in _out[node]:
                positions.setdefault(k, []).append(i - len(k) + 1)
        counts: Dict[str, int] = {}
        for k in self.keys:
            n, last_end = 0, -1
            for pos in positions.get(k, ()):            # 位置天然升序
                if pos > last_end:
                    n += 1
                    last_end = pos + len(k) - 1
            counts[k] = n
        return counts


def _matcher(keys) -> Optional["_Matcher"]:
    """按**键集内容**取自动机；空键 / 单键不值得建机（参考实现更快也更好懂）→ None。"""
    str_keys = [str(k) for k in keys]
    if "" in str_keys or len(str_keys) < 2:
        return None
    key = hashlib.sha256("\x01".join(sorted(str_keys)).encode("utf-8")).hexdigest()
    got = _MATCHERS.get(key)
    if got is None:
        if len(_MATCHERS) >= _MATCHERS_MAX:
            _MATCHERS.clear()
        got = _Matcher(str_keys)
        _MATCHERS[key] = got
    return got


def count_keys(blob: str, keys) -> Dict[str, int]:
    """数每个键在 `blob` 里的出现次数——**与 `str.count` 逐字节同语义**（非重叠、互相包含都算）。

    为什么不用一行 `{k: blob.count(k) for k in keys}`：那是「1499 个键 × 3.5 MB 语料」= **5.2 GB**
    的字符扫描，实测 **3.11 s**（profile 里单笔最大，且每个新内容状态都要重付一遍）。走自动机后
    同一批数字只要 ~0.3 s。等价性由 `test_asset_density.KeyCountEquivalenceTest` 守着
    （随机串 400 例 + 重叠/嵌套/空键边界 + 真语料逐键比对）。
    """
    if len(blob) > MAX_BLOB_TEXT:
        raise ValueError("待计数文本过大（%d > %d 字符）" % (len(blob), MAX_BLOB_TEXT))
    str_keys = [str(k) for k in keys]
    if len(str_keys) > MAX_KEYS or sum(map(len, str_keys)) > MAX_KEY_CHARS:
        raise ValueError("键集超过计数上限（修复指引：缩小资产键集或拆分资产文件）")
    matcher = _matcher(str_keys)
    if matcher is None:
        return {k: blob.count(k) for k in str_keys}
    return matcher.counts(blob)


def _check_keys_limit(keys) -> List[str]:
    """键集上限校验（键数 + 字符数）→ 字符串键列表；超限即抛。"""
    keys = [str(k) for k in keys]
    if len(keys) > MAX_KEYS or sum(map(len, keys)) > MAX_KEY_CHARS:
        raise ValueError("键集超过计数上限（修复指引：缩小资产键集或拆分资产文件）")
    return keys


def _cached_counts(text: str, keys: List[str], matcher, keys_key: str, dg: str) -> Dict[str, int]:
    """单件计数（按键集+件摘要缓存；无自动机时退回 str.count）→ 稀疏计数表。"""
    ck = (dg, keys_key)
    per = _FILE_COUNT_CACHE.get(ck)
    if per is None:
        per = matcher.counts(text) if matcher is not None \
            else {k: text.count(k) for k in keys}
        sparse = {k: n for k, n in per.items() if n}      # 稀疏：单件里绝大多数键一次都不出现
        if len(_FILE_COUNT_CACHE) >= _FILE_COUNT_CACHE_MAX:
            _FILE_COUNT_CACHE.clear()
        _FILE_COUNT_CACHE[ck] = sparse
        per = sparse
    return per


def count_keys_additive(texts, keys, digests=None) -> Dict[str, int]:
    """**逐件计数再相加**（等价于把语料用 `"\\n"` 连起来数一次），但**逐件**结果可缓存。

    为什么两者等价（可证）：连接语料用的是 `"\\n"` 分隔，而**任何键都不可能含换行**（资产 id 是
    字母数字 + 分隔符）。于是「跨件匹配」只可能出现在包含该分隔符的位置——而那样的匹配不存在
    ⇒ 逐件计数之和与「拼成一整条再数」**逐键相同**。这条等价性由
    `test_asset_density.KeyCountEquivalenceTest` 在**真语料**上断言（并在合成语料上加负例）。

    为什么不直接数整条：逐件结果可以按**文件内容**缓存（键即内容）——一次真编辑只会让**被改的那一件**
    重算（守护里尤其明显：常驻层已经按路径给出新正文，这里按正文命中），而整条 blob 的指纹一变
    就要把 3.5 MB 重扫一遍。

    fail-closed：键里只要出现换行（当前不可能），就退回整条拼接计数——正确性优先于省算。

    `digests`（可选，与 `texts` 一一对应）让调用方交出**已经算过的内容摘要**（常驻层逐件摘要），
    省掉这里再 `sha256(text.encode())` 一遍——一次新内容状态里那是 2815 次编码 + 哈希（实测 ~5 ms）。
    摘要口径与这里现算的完全一致（同一 payload 语义，见 `conformance_scan._payload_digest`）。
    """
    keys = _check_keys_limit(keys)
    if any("\n" in k for k in keys):
        return count_keys("\n".join(texts), keys)
    keys_key = hashlib.sha256("\x01".join(sorted(keys)).encode("utf-8")).hexdigest()
    matcher = _matcher(keys)                        # 自动机按**键集**复用（别逐件重建，实测慢 6 倍）
    totals = {k: 0 for k in keys}
    for idx, text in enumerate(texts):
        if len(text) > MAX_BLOB_TEXT:
            raise ValueError("单件文本过大（%d > %d 字符）" % (len(text), MAX_BLOB_TEXT))
        dg = digests[idx] if digests is not None else \
            hashlib.sha256(text.encode("utf-8")).hexdigest()
        for k, n in _cached_counts(text, keys, matcher, keys_key, dg).items():
            totals[k] += n
    return totals


def _usage_keys(root: str) -> Dict[str, str]:
    """资产键集（键 → 首个出处）：跳过 README、超大件与不可读件。"""
    keys: Dict[str, str] = {}
    for pat in ("community/*/assets/*.md", "05_资产库/用户自定义/*.md"):
        for rel in csc.iter_files(root, pat):
            if rel.rsplit("/", 1)[-1] == "README.md":
                continue
            path = Path(root) / rel
            try:
                if path.stat().st_size > MAX_ASSET_FILE_BYTES:
                    continue
            except OSError:
                # 不可读件由对应门禁另行报告；本统计不重复吞成零值。
                continue
            # 路径必须锚在 `root` 上：`Path(rel)` 是按 **CWD** 解析的，读不到时 `_keys_of`
            # 的自带兜底会**静默降级**成「仅文件名令牌」（实测同树上 键 8→4 / 引用 24→12 且不报 issu
            # e）。
            try:
                for k in _keys_of(path):
                    keys.setdefault(k, rel)
            except (OSError, ValueError):
                continue
    return keys


def _census_hash(keys: Dict[str, str], fp: str) -> str:
    """普查内容键：语料面指纹 + 排序键集（键先算，命中时不读正文）。"""
    h = hashlib.sha256()
    h.update(fp.encode("utf-8"))
    h.update(b"\x00")
    for k in sorted(keys):
        h.update(k.encode("utf-8"))
        h.update(b"\x01")
    return h.hexdigest()


def _corpus_texts(root: str, digest_map) -> Tuple[List[str], List[str]]:
    """未命中缓存时读语料 → (正文列表, 逐件摘要 hex 列表)。"""
    corpus: List[str] = []
    digests: List[str] = []
    for rel in (r for pat in CORPUS_PATTERNS for r in csc.iter_files(root, pat)):
        try:
            corpus.append(csc.read_text_cached(Path(root) / rel))
        except OSError:  # 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁另行报出（见 AUD-0016）
            continue
        dg = (digest_map or {}).get(rel)
        if dg is None:                     # 面指纹是**复用**来的（手里没摘要）→ 现取
            dg = csc._payload_digest(root, rel)
        digests.append(dg.hex())
    return corpus, digests


def usage_scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """资产引用度体检：每个资产键在 04/community/docs 全语料中被引用次数。

    FAIL 面留空（纯统计）：zero_usage 为「注册了但全语料无引用」的键清单，
    供作者裁决（低信息键候选），不自动删。
    """
    keys = _usage_keys(root)
    # 内容键：**语料面指纹**（常驻层逐件摘要，不读正文）＋ 键集。口径与旧实现一致（同一批件、
    # 同一 payload 语义），但不再把 3.5 MB 正文逐件 `encode()` + 重哈希——而且键能**先算**，
    # 于是命中时**根本不必把 2815 份语料读成列表**（旧实现是「先全读、再查表」）。
    # 面指纹与**逐件摘要**一次拿到：未命中时 `face_digests` 已经把 2815 份语料的摘要算齐，
    # 下面 `count_keys_additive` 的逐件缓存键直接复用它们——过去同一批摘要算了两遍（实测 ~5.6 ms）。
    fp, digest_map = csc.face_digests(root, CORPUS_PATTERNS)
    ckey = _census_hash(keys, fp)
    # 落盘键另叠**代码面 + 运行时**（见 core.disk_cache）：改了普查算法必然换键，
    # 不靠"记得手工 bump 版本标签"。
    dkey = disk_cache.key("census", ckey, root=root,
                               code_scope=_ig.code_scope_fingerprint(root, ("core.asset_density",)))
    counts = _CENSUS_CACHE.get(ckey)
    if counts is None:
        counts = disk_cache.load("census", dkey,
                                 validate=lambda d: isinstance(d, dict)
                                 and set(d) == set(keys))
    if counts is None:
        # 语义 = 逐键 `str.count`（非重叠、含互相包含）——已实测：bytes 版更慢；单遍 alternation 在
        # 「两键于同一位置重叠」（如 AB/BC 于 ABC）时会漏计。现在走 `count_keys_additive`
        # （逐件 Aho–Corasick + 非重叠贪心，再相加；与「拼成一整条再数」逐键等价，见其 docstring），
        # 于是**逐件**结果能按文件内容缓存：真编辑只让被改的那一件重算。实测整条 3.11 s → ~0.2 s，
        # 且改一件之后再算只需那一件的钱。
        corpus, digests = _corpus_texts(root, digest_map)
        counts = count_keys_additive(corpus, keys, digests=digests)
        disk_cache.store("census", dkey, counts)
    if ckey not in _CENSUS_CACHE:
        if len(_CENSUS_CACHE) >= _CENSUS_CACHE_MAX:
            _CENSUS_CACHE.clear()
        _CENSUS_CACHE[ckey] = counts
    zero = sorted(k for k, n in counts.items() if n == 0)
    stats = {"assets": len(keys), "zero_usage": len(zero),
             "used": len(keys) - len(zero),
             "total_refs": sum(counts.values()),
             "zero_keys": zero}
    return [], stats


def _row_metrics(text: str, keys) -> Tuple[int, int, bool]:
    """单件厚度度量：小节数 / 表格行数 / 低信息档判定。"""
    import re as _re

    lines = text.splitlines()
    sections = sum(1 for ln in lines if _re.match(r"^#{1,3}\s", ln))
    tables = sum(1 for ln in lines if ln.lstrip().startswith("|"))
    low = len(text) < 200 or (not keys and sections == 0)
    return sections, tables, low


def _thickness_row(root: str, rel: str) -> Optional[Dict[str, Any]]:
    """单件厚度行；README/超大件/不可读/空件/键集超限 → None（跳过）。"""
    if rel.rsplit("/", 1)[-1] == "README.md":
        return None
    try:
        path = Path(root) / rel
        if path.stat().st_size > MAX_ASSET_FILE_BYTES:
            return None
        text = csc.read_text_cached(path)
    except OSError:  # 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁另行报出（见 AUD-0016）
        return None
    if not text.strip():
        return None
    try:
        keys = _keys_of(Path(rel), text)
    except ValueError:
        # 键集超限已由 scan 的面级问题报告；厚度统计跳过该件。
        return None
    sections, tables, low = _row_metrics(text, keys)
    pkg = rel.split("/")[1] if rel.startswith("community") else "官方"
    return {"package": pkg, "file": rel, "chars": len(text),
            "keys": len(keys), "sections": sections,
            "tables": tables, "low_info": low}


def _thickness_impl(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """真算（未命中缓存时走这里）。"""
    rows = []
    for pat in ("community/*/assets/*.md", "05_资产库/用户自定义/*.md"):
        for rel in csc.iter_files(root, pat):
            row = _thickness_row(root, rel)
            if row is not None:
                rows.append(row)
    low_files = sorted(x["file"] for x in rows if x["low_info"])
    stats = {"files": len(rows),
             "low_info": len(low_files), "low_files": low_files,
             "avg_chars": round(sum(x["chars"] for x in rows) / max(1, len(rows))),
             "avg_sections": round(sum(x["sections"] for x in rows) / max(1, len(rows)))}
    return [], stats


def thickness_scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """资产语义厚度（计数升半语义）：每档 字符/键/小节/表格行 与 low 判定。

    low = 空/过短(<200字) 或 无键且无小节（低信息档候选）；只报告不删（issues 空）。
    派生结果按**输入内容指纹**缓存（输入面与 `scan()` 同：两条资产面）——纯函数，键即内容。
    """
    return csc.memo_pair("asset-thickness", ASSET_INPUTS, _thickness_impl, root,
                          code_modules=("core.asset_density",))
