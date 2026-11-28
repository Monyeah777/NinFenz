"""core.asset_ledger 私有实现分片 2/2（对外只经 core.asset_ledger 门面导入）：remove_entry 等"""

from __future__ import annotations

import glob
import os

from core import atomic_write
from core import repo_face as _repo_face

from ._part1 import (
    HEADER_MARK,
    LEDGER_FILE,
    SHELF_GLOBS,
    VALID_STATUS,
    VALID_TIER,
    AssetLedgerError,
    _load_for_update,
    _safe_join,
    default_ledger_path,
    load_ledger,
    parse_header,
    save_ledger,
)


def remove_entry(assets_root: str, key: str, ledger_path: str | None = None) -> dict:
    """从台账摘除条目（只删台账不删文件；文件仍带旧头时 verify 报孤儿头，提示手动清理）。"""
    # 读-改-写加锁（2026-10-01）：摘除也走同一把锁，锁内重读（并发 add 不会复活被摘条目）。
    with atomic_write.lock_file(ledger_path or default_ledger_path(assets_root),
                                what="资产台账（nf asset rm）"):
        ledger, target, lp = _load_for_update(assets_root, ledger_path, key)
        ledger["assets"] = [e for e in ledger["assets"] if e.get("key") != key]
        save_ledger(ledger, lp)
    return target


def _iter_md_candidates(ledger_dir: str) -> list:
    """台账目录下候选资产 md（排除 README*——包/库索引手册非内容资产，对齐 check7 口径）。"""
    out = []
    for base, dirs, files in os.walk(ledger_dir):
        dirs[:] = [d for d in dirs if d not in (".git", ".gitee", "__pycache__")
                   and not os.path.islink(os.path.join(base, d))]
        for fn in sorted(files):
            if fn.lower().startswith("readme"):
                continue
            full = os.path.join(base, fn)
            if fn.endswith(".md") and not os.path.islink(full):
                out.append(full)
    return out


def verify_ledger_dir(ledger_dir: str, ledger_path: str | None = None) -> tuple:
    """单台账闭合校验。返回 (issues, stats)。

    stats：assets（在册条目数）/ untracked（目录下无头 md）/ orphans（孤儿文件头）。
    目录无台账 → 不校验（存量未入库由 inventory 提示，不视为事故）。
    """
    lp = ledger_path or default_ledger_path(ledger_dir)
    issues: list[str] = []
    stats = {"assets": 0, "untracked": 0, "orphans": 0}
    if not os.path.isfile(lp):
        return issues, stats
    try:
        ledger = load_ledger(lp)
    except AssetLedgerError as exc:
        return [str(exc)], stats
    entries = ledger["assets"]
    stats["assets"] = len(entries)
    seen_keys = set()
    seen_files = set()
    for e in entries:
        _verify_entry(lp, ledger_dir, e, issues, seen_keys, seen_files)
    # 反向闭合：目录内带头 md 的键必须 ∈ 台账（键无孤儿）
    _scan_orphans(lp, ledger_dir, issues, stats, seen_files)
    return issues, stats


def _verify_entry(lp: str, ledger_dir: str, e: dict, issues: list[str],
                  seen_keys: set, seen_files: set) -> None:
    """台账单条目的正/反向校验（键唯一、文件在场、文件头一致、字段齐全）。"""
    key = str(e.get("key", "") or "")
    frel = str(e.get("file", "") or "").replace("\\", "/")
    if not key:
        issues.append("[%s] 条目缺 key" % lp)
    if key in seen_keys:
        issues.append("[%s] 键重复（键无孤儿前提：键唯一）: %s" % (lp, key))
    seen_keys.add(key)
    if not frel or frel in seen_files:
        issues.append("[%s] 文件重复/为空: %r" % (lp, frel))
        return
    seen_files.add(frel)
    try:
        full = _safe_join(ledger_dir, frel)
    except AssetLedgerError as exc:
        issues.append(f"[{lp}] {exc}")
        return
    if not os.path.isfile(full):
        issues.append("[%s] 在册文件缺失（可发现性断裂）: %s" % (lp, frel))
        return
    with open(full, encoding="utf-8") as f:
        text = f.read()
    _entry_header_issues(lp, e, key, frel, text, issues)
    _entry_field_issues(lp, e, key, issues)


def _entry_header_issues(lp: str, e: dict, key: str, frel: str,
                         text: str, issues: list[str]) -> None:
    """文件头在场且与台账一致（双源核对）。"""
    try:
        header = parse_header(text)
    except AssetLedgerError as exc:
        issues.append("[%s] %s" % (lp, exc))
        return
    if header is None:
        issues.append("[%s] 台账条目缺文件头（双源不一致）: %s" % (lp, frel))
    elif header["key"] != key or header["status"] != e.get("status"):
        issues.append("[%s] 文件头与台账不一致（台账 key=%s status=%s / 头=%s）: %s"
                      % (lp, key, e.get("status"), header, frel))


def _entry_field_issues(lp: str, e: dict, key: str, issues: list[str]) -> None:
    """source / version / status 必填与词表。"""
    if not str(e.get("source") or "").strip():
        issues.append("[%s] 条目缺 source（不可溯源）: %s" % (lp, key))
    if not str(e.get("version") or "").strip():
        issues.append("[%s] 条目缺 version（版本位必填）: %s" % (lp, key))
    if e.get("status") not in VALID_STATUS:
        issues.append("[%s] status 非法: %s" % (lp, e.get("status")))


def _scan_orphans(lp: str, ledger_dir: str, issues: list[str], stats: dict,
                  seen_files: set) -> None:
    """反向闭合：目录内带头 md 的键必须 ∈ 台账（键无孤儿）。"""
    for cand in _iter_md_candidates(ledger_dir):
        rel = os.path.relpath(cand, ledger_dir).replace("\\", "/")
        if rel in seen_files:
            continue
        with open(cand, encoding="utf-8") as f:
            text = f.read()
        if HEADER_MARK not in text:
            stats["untracked"] += 1
            continue
        try:
            header = parse_header(text)
        except AssetLedgerError as exc:
            issues.append("[%s] %s" % (lp, exc))
            continue
        stats["orphans"] += 1
        issues.append("[%s] 孤儿文件头（键不在台账）: %s（key=%s）——nf asset rm 后需手动清理旧头"
                      % (lp, rel, header["key"]))


def _walk_repo(root: str):
    """仓库件遍历：跳过 VCS/缓存 + 被 .gitignore 覆盖的生成物（产出 `(base, dirs, files)`）。

    依据（2026-10-03 实测）：裸 `os.walk(root)` 会把已忽略的生成副本当**第二份台账**读进来——
    npm 暂存面在场时 `verify_root` 报「台账 206 / 托管资产 614」，真实值恰为一半（103 / 307），
    `iter_assets` 亦让每件资产列两遍。面判据收敛到 `core.repo_face`（单一出处）。
    """
    ignored = _repo_face.ignored_paths(root)
    for base, dirs, files in os.walk(root):
        rel = os.path.relpath(base, root).replace(os.sep, "/")
        rel = "" if rel == "." else rel
        dirs[:] = [d for d in dirs
                   if d not in (".git", ".gitee", "__pycache__")
                   and not os.path.islink(os.path.join(base, d))
                   and not _repo_face.is_ignored(("%s/%s" % (rel, d)) if rel else d, ignored)]
        files[:] = [f for f in files if not os.path.islink(os.path.join(base, f))]
        yield base, dirs, files


def verify_shelf_shape(root: str = ".") -> tuple:
    """资产货架**单层不变量**：货架目录下不得含子目录（返回 issues, stats）。

    为什么是硬门而不是提示：三面扫描（`asset_density` / `asset_ledger_projection` /
    `asset_line_baseline`）不递归，子目录里的资产会静默脱离密度、键表投影与行数基线，
    而台账面（`os.walk`）仍看得见——口径分裂且无门禁可见。修复指引：资产平铺为 .md；
    需要分组请用键表（assets/README.md 或资产内条目键）与「一包多文件」表达。
    """
    issues = []
    shelves = 0
    for pattern in SHELF_GLOBS:
        for shelf in sorted(glob.glob(os.path.join(root, pattern))):
            if not os.path.isdir(shelf):
                continue
            shelves += 1
            rel = os.path.relpath(shelf, root).replace("\\", "/")
            subs = sorted(d for d in os.listdir(shelf)
                          if os.path.isdir(os.path.join(shelf, d)))
            if subs:
                issues.append("%s 资产货架含子目录 %s（货架为单层：密度 / 键表投影 / 行数基线"
                              "三面不递归，子目录会静默丢口径；修复指引：资产平铺为 .md，"
                              "分组用键表表达）" % (rel, "、".join(subs)))
    return issues, {"shelves": shelves}


def verify_root(root: str) -> tuple:
    """仓库级扫描：找出全部 provenance.json 台账目录并逐册校验；聚合统计。"""
    issues = []
    stats = {"ledgers": 0, "assets": 0, "untracked": 0, "orphans": 0, "shelves": 0}
    shape_issues, shape_stats = verify_shelf_shape(root)
    issues.extend(shape_issues)
    stats["shelves"] = shape_stats["shelves"]
    for base, dirs, files in _walk_repo(root):
        if LEDGER_FILE in files:
            dir_issues, dir_stats = verify_ledger_dir(base, os.path.join(base, LEDGER_FILE))
            issues.extend(dir_issues)
            stats["ledgers"] += 1
            for k in ("assets", "untracked", "orphans"):
                stats[k] += dir_stats.get(k, 0)
    return issues, stats


def iter_assets(root: str):
    """浏览：逐台账展开为行（台账级 package/tier 与条目字段合并），按目录+文件排序。"""
    rows = []
    for base, dirs, files in _walk_repo(root):
        if LEDGER_FILE not in files:
            continue
        try:
            ledger = load_ledger(os.path.join(base, LEDGER_FILE))
        except AssetLedgerError:  # 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁另行报出（见 AUD-0016）
            continue
        rel_dir = os.path.relpath(base, root).replace("\\", "/")
        for e in ledger["assets"]:
            row = dict(e)
            row["dir"] = rel_dir if rel_dir != "." else "(root)"
            row["package"] = ledger.get("package", "")
            row["tier"] = ledger.get("tier", "")
            rows.append(row)
    rows.sort(key=lambda r: (r["dir"], r["file"], r["key"]))
    return rows


def _row_matches(r: dict, pkg: str, tier: str, status: str) -> bool:
    """单行是否命中 ls 过滤器（pkg/tier/status 全为空即全命中）。"""
    if pkg and r.get("package", "") != pkg:
        return False
    if tier and r.get("tier", "") != tier:
        return False
    if status and r.get("status") != status:
        return False
    return True


def filter_rows(rows: list, pkg: str = "", tier: str = "",
                status: str = "") -> list:
    """ls 过滤器（pkg = 台账 package 字段；tier/status = 台账级/条目级匹配）。"""
    if tier and tier not in VALID_TIER:
        raise AssetLedgerError("tier 过滤器非法：%s" % tier)
    if status and status not in VALID_STATUS:
        raise AssetLedgerError("status 过滤器非法：%s" % status)
    out = []
    for r in rows:
        if _row_matches(r, pkg, tier, status):
            out.append(r)
    return out


def inventory_root(root: str) -> list:
    """库存盘点：返回台账摘要行（目录/package/tier/在册数/未托管数/问题数），按目录排序。"""
    rows = []
    for base, dirs, files in _walk_repo(root):
        if LEDGER_FILE not in files:
            continue
        lp = os.path.join(base, LEDGER_FILE)
        try:
            ledger = load_ledger(lp)
            _, dir_stats = verify_ledger_dir(base, lp)
            rel = os.path.relpath(base, root).replace("\\", "/")
            rows.append({
                "dir": rel if rel != "." else "(root)",
                "package": ledger.get("package", ""),
                "tier": ledger.get("tier", ""),
                "assets": len(ledger["assets"]),
                "untracked": dir_stats.get("untracked", 0),
                "orphans": dir_stats.get("orphans", 0),
            })
        except AssetLedgerError as exc:
            rel = os.path.relpath(base, root).replace("\\", "/")
            rows.append({"dir": rel, "package": "", "tier": "", "assets": -1,
                         "untracked": 0, "orphans": 0, "error": str(exc)})
    rows.sort(key=lambda r: r["dir"])
    return rows
