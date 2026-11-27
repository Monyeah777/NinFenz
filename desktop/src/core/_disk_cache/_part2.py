"""core.disk_cache 私有实现分片 2/2（对外只经 core.disk_cache 门面导入）：_DISABLED、_DEFER 等"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core import json_doc

from ._part1 import (
    _CODE_FP,
    _KEEP,
    _PRUNE_COUNT,
    _ROOT,
    ENFORCE_EVERY,
    ENV_DIR,
    ENV_OFF,
    KEEP,
    PRUNE_EVERY_BIG,
    PRUNE_EVERY_SMALL,
    _adopt_fallback,
    _probe_writable,
    _repo_tag,
    _root_key,
    _user_cache_base,
    max_total,
)

_DISABLED = False


#: **延迟写盘**模式（`defer_begin` 起、`defer_flush` 止）：`store()` 只入队不碰盘。
#: 依据（实测 2026-09-29）：一次新内容状态里落盘合计 14–17 ms（守护口径的差值实测 20–80 ms），
#: 而写盘**纯写**、结果只供**别的进程**（冷进程 / 守护重启）用 ⇒ 完全可以挪到「回包之后」再付：
#: 客户端拿到响应就走，守护在这之后把队列落盘。fail-closed：中途崩了就丢这批缓存（缓存不是事实，
#: 丢了只是下次重算），**不影响任何判定**。
_DEFER: Optional[list] = None


_STORE_TICKS = 0


def count_files() -> int:
    """当前缓存根下的 `.json` 文件总数（只扫两层：<tag>/<key>.json）。"""
    total = 0
    try:
        for tag_dir in root_dir().iterdir():
            if tag_dir.is_dir():
                total += sum(1 for _ in tag_dir.glob("*.json"))
    # 缓存根不可读＝按 0 计（这是诊断/容量面，不参与任何判定）
    except OSError:
        return 0
    return total


def enforce_bounds(limit: int | None = None) -> int:
    """把总量压到上限内（按 mtime 从旧到新删），返回删掉的份数。

    边界：任何异常都吞（缓存不是事实，删不动只是多占空间，不得影响命令结果）。
    """
    cap = max_total() if limit is None else int(limit)
    removed = 0
    try:
        entries = []
        for tag_dir in root_dir().iterdir():
            if not tag_dir.is_dir():
                continue
            for f in tag_dir.glob("*.json"):
                try:
                    entries.append((f.stat().st_mtime, f))
                except OSError:  # 枚举与 stat 之间消失的条目＝当作不存在（并发写者的正常竞态）
                    continue
        if len(entries) <= cap:
            return 0
        entries.sort(key=lambda t: t[0])
        for _mtime, f in entries[: len(entries) - cap]:
            try:
                f.unlink()
                removed += 1
            except OSError:  # 单份删不掉（被占用）＝跳过它，下一轮再试（不影响已删数量）
                continue
    # 整体枚举失败＝尽力而为（缓存不是事实；返回已删数量供观测）
    except OSError:
        return removed
    return removed


def defer_begin() -> None:
    """进入延迟写盘模式（守护在**处理请求前**调用）。"""
    global _DEFER
    _DEFER = []


def deferring() -> bool:
    return _DEFER is not None


def defer_drop() -> None:
    """丢弃队列并退出延迟模式（异常路径用；缓存非事实，丢了只会重算）。"""
    global _DEFER
    _DEFER = None


def defer_flush() -> int:
    """把队列落盘并退出延迟模式（守护在**回包之后**调用）→ 写了几条。"""
    global _DEFER
    pending, _DEFER = _DEFER, None
    n = 0
    for tag, ckey, value, keep in pending or ():
        store(tag, ckey, value, keep)
        n += 1
    return n


def enabled() -> bool:
    return not os.environ.get(ENV_OFF) and not _DISABLED


def _resolve_root() -> Path:
    """缓存根裁决（C1）：NF_CACHE_DIR → 显式 NF_HOME → 用户级（按仓分段）→ 仓内回退。"""
    global _DISABLED
    key = _root_key()
    hit = _ROOT.get("root")
    if hit is not None and _ROOT.get("key") == key:
        return hit
    _DISABLED = False        # 环境变了：重新裁决（上一次的禁用结论只对它那一组环境成立）
    explicit = os.environ.get(ENV_DIR)
    home = os.environ.get("NARRATIVE_FORGE_HOME")
    if explicit:
        root = Path(explicit).expanduser()
    elif home:
        # 测试/便携隔离：显式 NF_HOME 保持旧口径（<NF_HOME>/cache）
        root = Path(home).expanduser() / "cache"
    else:
        root = _user_cache_base() / _repo_tag()
    if _probe_writable(root):
        _ROOT["root"], _ROOT["key"] = root, key
        return root
    fallback = (Path.cwd() / ".nf-cache").resolve()
    if _adopt_fallback(fallback):
        print(f"WARN: 用户缓存目录不可写（{root}），判据缓存回退仓内 {fallback}："
              "该目录可能被仓库内容影响，只应作降级运行", file=sys.stderr)
        _ROOT["root"], _ROOT["key"] = fallback, key
        return fallback
    # 两处都不可用：关闭缓存（读=未命中、写=失败），绝不回落到可疑位置
    _DISABLED = True
    print(f"WARN: 没有可写的判据缓存目录（用户级 {root} 与仓内 {fallback} 均不可用）："
          "本次运行**禁用缓存**", file=sys.stderr)
    _ROOT["root"], _ROOT["key"] = root, key
    return root


def root_dir() -> Path:
    """缓存根（C1）：默认用户级、按被审仓库分段；见 `_resolve_root`。"""
    return _resolve_root()


def _reset_root_state() -> None:
    """测试隔离：清缓存根裁决与禁用标记（生产调用方不应使用）。"""
    global _DISABLED
    _ROOT.clear()
    _DISABLED = False


def dir_for(tag: str) -> Path:
    return root_dir() / str(tag)


def _path(tag: str, ckey: str) -> Path:
    return dir_for(tag) / ("%s.json" % ckey)


#: 写失败观测（2026-10-10 审计 N7，P2）：缓存写不进是**降级**（读者重算即可），不该静默到
#: 无法判别。此前 store 用固定名 p.name+".tmp" 手工写（4 进程 × 200 同键写实测 800 次全返回、
#: 读者 55.5% FileNotFoundError）且 except 全吞。现在原子写 + 计数 + 最近原因。
STORE_FAILURES = 0


LAST_STORE_ERROR = ""


def store_failures() -> Dict[str, Any]:
    """写失败观测面 → {failures, last_error}（供 daemon stats / doctor 报出）。"""
    return {"failures": STORE_FAILURES, "last_error": LAST_STORE_ERROR}


def load(tag: str, ckey: str,
         validate: Optional[Callable[[Any], bool]] = None) -> Any:
    """读回缓存值；**任何不可信**一律返回 None（宁可重算，不可错答）。"""
    if not enabled():
        return None
    try:
        got = json_doc.load(_path(tag, ckey), None, what=ckey)
    except Exception:                                  # noqa: BLE001 - 缺件/半截/不可读
        return None  # best-effort 显式忽略（不可读/不可用属预期，由上层门禁另行报出）
    if validate is not None:
        try:
            if not validate(got):
                return None
        except Exception:                              # noqa: BLE001 - 校验器自己炸也算不可信
            return None  # best-effort 显式忽略（不可读/不可用属预期，由上层门禁另行报出）
    return got


def store(tag: str, ckey: str, value: Any, keep: Optional[int] = None) -> bool:
    """写盘（尽力而为）：原子替换 + 有界裁剪；失败静默。

    `keep` 给「每份文件一条」的大集合标签用（如 AST 事实 250 条）；小集合标签沿用 `KEEP`。
    裁剪一律**按批**：大集合每 `PRUNE_EVERY_BIG` 次、小集合每 `PRUNE_EVERY_SMALL` 次写入裁一次
    （每次都裁的代价实测占 `store` 的一半，见 `PRUNE_EVERY_SMALL` 的说明）。
    """
    global STORE_FAILURES, LAST_STORE_ERROR, _STORE_TICKS
    if not enabled():
        return False
    if _DEFER is not None:                  # 延迟模式：只入队（守护回包之后再落盘，见 `defer_flush`）
        _DEFER.append((tag, ckey, value, keep))
        return True
    try:
        d = dir_for(tag)
        d.mkdir(parents=True, exist_ok=True)
        p = _path(tag, ckey)
        # 并发安全（审计 N7）：固定名 `.tmp` 会被同键并发写互踩；统一走 atomic_write
        # （mkstemp 唯一临时名 + fsync + os.replace + 瞬时错短重试），与全仓落盘面同一出处。
        from core import atomic_write
        atomic_write.write_text(p, json.dumps(value, ensure_ascii=False, sort_keys=True))
        limit = int(keep if keep is not None else _KEEP.get(tag, KEEP))
        n = _PRUNE_COUNT.get(tag, 0) + 1
        every = PRUNE_EVERY_BIG if limit > 64 else PRUNE_EVERY_SMALL
        if n >= every:
            _PRUNE_COUNT[tag] = 0
            prune(tag, limit)
        else:
            _PRUNE_COUNT[tag] = n
        _STORE_TICKS += 1
        if _STORE_TICKS % ENFORCE_EVERY == 0:
            enforce_bounds()
        return True
    except Exception as exc:                           # noqa: BLE001 - 写不进不该让命令失败，但**要可观测**
        STORE_FAILURES += 1
        LAST_STORE_ERROR = "%s: %s" % (tag, exc)
        return False


def prune(tag: str, keep: int = KEEP) -> None:
    """只留最近 `keep` 份（按 mtime）。"""
    try:
        d = dir_for(tag)
        entries = sorted(d.glob("*.json"), key=lambda q: q.stat().st_mtime, reverse=True)
        for old in entries[keep:]:
            old.unlink()
    except Exception:                                  # noqa: BLE001 - 裁剪失败不影响结果
        return  # best-effort 显式忽略（不可读/不可用属预期，由上层门禁另行报出）


def reset_code_fingerprint(root: Optional[str] = None) -> None:
    """清掉代码面指纹记忆（守护判定「代码已换版」后调用；不给 root 则全清）。"""
    if root is None:
        _CODE_FP.clear()
        return
    _CODE_FP.pop(os.path.normcase(os.path.abspath(str(root))), None)


# : 仓库内模块的**导入图**（懒建、按 (根, 模块) 记忆）：模块名 → (文件相对路径, 依赖, 是否含动态导入
# )。
# : 只用来**划定代码面的范围**（谁真的依赖谁的代码），不参与任何判定；解析不出/含动态导入 → 退回整块
# 。
_CORE_DIR = ("desktop", "src", "core")
