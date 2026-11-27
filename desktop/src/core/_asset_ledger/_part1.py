"""core.asset_ledger 私有实现分片 1/2（对外只经 core.asset_ledger 门面导入）： 等"""

from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import dataclass

from core import atomic_write, paths

LEDGER_SCHEMA_VERSION = "1"


LEDGER_FILE = "provenance.json"


#: 资产货架目录（**单层不变量**，2026-09-20 作者裁决收口）：密度体检 / 键表投影 / 行数基线
#: 三面均以**非递归** glob 取件（`community/*/assets/*.md`、`05_资产库/用户自定义/*.md`），
#: 而本台账面走 `os.walk`（递归）——货架一旦出现子目录，文件会「台账可见、三面不可见」
#: （静默丢口径，外部实证见 results/audit/docs_audit-52-external-inputs.md §三.①）。
#: 故把单层写成可机检不变量：子目录即 FAIL，分组请用键表 / 一包多文件表达。
SHELF_GLOBS = (os.path.join("community", "*", "assets"),
               os.path.join("05_资产库", "用户自定义"))


STATUS_ACTIVE = "active"


STATUS_DEPRECATED = "deprecated"


STATUS_RETIRED = "retired"


VALID_STATUS = (STATUS_ACTIVE, STATUS_DEPRECATED, STATUS_RETIRED)


VALID_TIER = ("official", "community", "experimental")


HEADER_MARK = "nf-asset"


_HEADER_RE = re.compile(
    r'<!--\s*nf-asset:\s*key="([^"]+)"\s+version="([^"]+)"\s+status="([^"]+)"\s*-->')


class AssetLedgerError(ValueError):
    """台账操作拒绝原因（CLI 层据此友好提示，退出码 2）。"""


def _today() -> str:
    return datetime.date.today().isoformat()  # noqa: DTZ011 - 本地日历日期是有意语义（UTC 会在跨零点给出错误「今天」）


def blank_ledger(package: str = "", tier: str = "official", **meta) -> dict:
    """空白台账骨架。tier 缺省 official（官方资产集为默认货架）。"""
    if tier not in VALID_TIER:
        raise AssetLedgerError("tier 非法：%s（应为 %s）" % (tier, "/".join(VALID_TIER)))
    ledger = {"schema_version": LEDGER_SCHEMA_VERSION, "tier": tier, "assets": []}
    if package:
        ledger["package"] = package
    for k, v in meta.items():
        if v not in (None, ""):
            ledger[k] = v
    return ledger


def default_ledger_path(assets_root: str) -> str:
    return os.path.join(assets_root, LEDGER_FILE)


def load_ledger(ledger_path: str) -> dict:
    """读取台账；缺失或结构非法抛 AssetLedgerError（防静默覆盖/误写）。"""
    if not os.path.isfile(ledger_path):
        raise AssetLedgerError("台账不存在：%s（先 nf asset add 建档）" % ledger_path)
    with open(ledger_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        raise AssetLedgerError("台账结构非法：%s（缺 assets[]）" % ledger_path)
    if data.get("schema_version") != LEDGER_SCHEMA_VERSION:
        raise AssetLedgerError(
            "台账 schema_version=%r 不识别（当前 %s）：%s"
            % (data.get("schema_version"), LEDGER_SCHEMA_VERSION, ledger_path))
    return data


def save_ledger(ledger: dict, ledger_path: str) -> None:
    """写盘（UTF-8、缩进 2、ensure_ascii=False）；原子替换（并发读者不见半截台账）。"""
    atomic_write.write_text(ledger_path,
                            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")


@dataclass(frozen=True)
class EntryOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    module: str = ''
    version: str = '1.0'
    status: str = STATUS_ACTIVE
    added: str | None = None


def _require_entry_fields(key, file_rel, source, version, status) -> None:
    """条目必填字段校验（源头拦截，CLI/测试共用）；不合法即抛 AssetLedgerError。"""
    if not key or not str(key).strip():
        raise AssetLedgerError("溯源键 key 不能为空——请先填溯源键再入库")
    if not file_rel or not str(file_rel).strip():
        raise AssetLedgerError("file 不能为空——请先填相对文件路径再入库")
    if not source or not str(source).strip():
        raise AssetLedgerError("source（溯源说明）不能为空——每资产必须可溯源")
    if not version or not str(version).strip():
        raise AssetLedgerError("version 不能为空——资产版本位必填")
    if status not in VALID_STATUS:
        raise AssetLedgerError("status 非法：%s（应为 %s）" % (status, "/".join(VALID_STATUS)))


def make_entry(file_rel: str, key: str, source: str, opts: EntryOptions | None = None) -> dict:
    """构造条目并做字段级校验（源头拦截，CLI/测试共用）。"""

    opts = opts if opts is not None else EntryOptions()
    module = opts.module
    version = opts.version
    status = opts.status
    added = opts.added
    _require_entry_fields(key, file_rel, source, version, status)
    entry = {"file": str(file_rel), "key": str(key), "source": str(source),
             "version": str(version), "status": status}
    if module:
        entry["module"] = str(module)
    entry["added"] = added or _today()
    return entry


def _guard_duplicates(ledger: dict, key: str, file_rel: str) -> None:
    """键唯一 + 文件唯一（**写前**与**锁内重读后**各查一次：并发窗口可能刚被别人写进去）。"""
    for e in ledger.get("assets") or []:
        if e.get("key") == key:
            raise AssetLedgerError("台账已托管该键：%s（先 nf asset rm / restore）" % key)
        if e.get("file") == file_rel.replace("\\", "/"):
            raise AssetLedgerError("台账已托管该文件：%s" % file_rel)


def _guard_tier(ledger: dict, tier) -> None:
    """一册一货架：已建档台账的 tier 不得与本次冲突。"""
    if tier is not None and ledger.get("tier") and ledger.get("tier") != tier:
        raise AssetLedgerError("台账已属 tier=%s，与本次 tier=%s 冲突（一册一货架）"
                               % (ledger.get("tier"), tier))


def _safe_join(assets_root: str, file_rel: str) -> str:
    """防路径逃逸：拒绝绝对路径与 .. 段；返回根内绝对路径。

    判据收敛到 `core.paths.validate_path`（单一真相源——同一套包含性判据不再各写一份）。
    """
    try:
        return paths.validate_path(assets_root, file_rel)
    except paths.PathEscapeError as exc:
        raise AssetLedgerError("file 不合规：%s（修复指引：file 须是资产根内的相对路径）"
                               % exc) from None


def render_header(entry: dict) -> str:
    return '<!-- %s: key="%s" version="%s" status="%s" -->\n' % (
        HEADER_MARK, entry["key"], entry["version"], entry["status"])


def parse_header(text: str):
    """解析 nf-asset 头；无头返回 None，有头但不可解析抛错（防半截头混过）。"""
    if HEADER_MARK not in text:
        return None
    m = _HEADER_RE.search(text)
    if not m:
        raise AssetLedgerError("发现 %s 头但格式不可解析（应 key/version/status 齐备）" % HEADER_MARK)
    return {"key": m.group(1), "version": m.group(2), "status": m.group(3)}


@dataclass(frozen=True)
class AssetOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    module: str = ''
    version: str = '1.0'
    status: str = STATUS_ACTIVE
    tier: str | None = None
    package: str = ''
    added: str | None = None
    ledger_path: str | None = None


def _initial_ledger(lp: str, package, tier) -> dict:
    """已有台账 → 读入（tier 非空时校验并落级）；没有 → 空白台账。"""
    if not os.path.isfile(lp):
        return blank_ledger(package=package, tier=tier or "official")
    ledger = load_ledger(lp)
    if tier is not None:
        _guard_tier(ledger, tier)
        ledger["tier"] = tier
    return ledger


def _append_locked(lp: str, package, tier, key: str, file_rel: str, entry: dict) -> None:
    """台账读-改-写加锁：锁内重读复查（键/文件唯一 + tier），并发窗口不丢条目。"""
    with atomic_write.lock_file(lp, what="资产台账（nf asset add）"):
        fresh = load_ledger(lp) if os.path.isfile(lp) else \
            blank_ledger(package=package, tier=tier or "official")
        _guard_tier(fresh, tier)
        _guard_duplicates(fresh, key, file_rel)
        if tier:
            fresh["tier"] = tier
        fresh["assets"].append(entry)
        save_ledger(fresh, lp)


def add_asset(
    assets_root: str,
    file_rel: str,
    key: str,
    source: str,
    opts: AssetOptions | None = None,
) -> dict:
    """入库：资产文件头部写 nf-asset 头 + 台账 append 条目。

    幂等判定 = 同键/同文件已托管 → 拒绝（键唯一 + 文件唯一）。tier 在首次建档时落台账级。
    """

    opts = opts if opts is not None else AssetOptions()
    module = opts.module
    version = opts.version
    status = opts.status
    tier = opts.tier
    package = opts.package
    added = opts.added
    ledger_path = opts.ledger_path
    full = _safe_join(assets_root, file_rel)
    if not os.path.isfile(full):
        raise AssetLedgerError("资产文件不存在：%s" % full)
    lp = ledger_path or default_ledger_path(assets_root)
    ledger = _initial_ledger(lp, package, tier)
    _guard_duplicates(ledger, key, file_rel)
    with open(full, encoding="utf-8") as f:
        text = f.read()
    existing = parse_header(text)
    if existing is not None:
        raise AssetLedgerError(
            "资产文件已带 %s 头（key=%s）——文件级唯一，禁止双托管"
            % (HEADER_MARK, existing.get("key")))
    entry = make_entry(
        file_rel.replace('\\', '/'),
        key,
        source,
        opts=EntryOptions(module=module, version=version, status=status, added=added),
    )
    atomic_write.write_text(full, render_header(entry) + text)   # 资产件也原子落盘
    # 台账读-改-写加锁（2026-10-01）：与 registry 同形——原子写只保证「读者不见半截」，
    # 并发 add 会**丢条目**（同形探针实测：两个 RMW 写者最终只剩一条）。锁内**重读 + 复查**
    # （键/文件唯一 + tier 冲突），把并发窗口里刚写进去的那条如实并进来或如实拒掉。
    _append_locked(lp, package, tier, key, file_rel, entry)
    return entry


def _load_for_update(assets_root: str, ledger_path: str | None, key: str):
    lp = ledger_path or default_ledger_path(assets_root)
    ledger = load_ledger(lp)
    for e in ledger["assets"]:
        if e.get("key") == key:
            return ledger, e, lp
    raise AssetLedgerError("台账无该键：%s（nf asset inventory 查看在册键）" % key)


def _set_status_locked(assets_root: str, ledger: dict, target: dict, lp: str,
                       status: str) -> dict:
    """锁内执行状态流转（调用方已持锁）——拆出来只为让持锁范围一眼可见。"""
    if target["status"] == status:
        return target
    target["status"] = status
    full = _safe_join(assets_root, target["file"])
    if os.path.isfile(full):
        with open(full, encoding="utf-8") as f:
            text = f.read()
        if parse_header(text) is not None:
            text = _HEADER_RE.sub(
                '<!-- %s: key="%s" version="%s" status="%s" -->'
                % (HEADER_MARK, target["key"], target["version"], target["status"]),
                text, count=1)
            atomic_write.write_text(full, text)
    save_ledger(ledger, lp)
    return target


def set_status(assets_root: str, key: str, status: str, ledger_path: str | None = None) -> dict:
    """状态流转（active/deprecated/retired）；同步改写资产文件头 status 位（双源一致）。"""
    if status not in VALID_STATUS:
        raise AssetLedgerError("status 非法：%s" % status)
    # 读-改-写加锁（2026-10-01）：与 `add_asset` 同一台账，锁内**重读**再改（并发窗口不丢更新）。
    with atomic_write.lock_file(ledger_path or default_ledger_path(assets_root),
                                what="资产台账（nf asset 状态流转）"):
        ledger, target, lp = _load_for_update(assets_root, ledger_path, key)
        return _set_status_locked(assets_root, ledger, target, lp, status)
