"""严格 ISO-8601 日期/时间解析（stdlib-only，单一出处）。

为什么单独成件：`as_of` / `allowlist_expiry` / `eval_harness` 等此前用**字符串字典序**
比较时间（`"2026-1-2" < "2026-10-01"` 之类的格式变体会误判）；本模块把「解析 + 归一 + 校验」
收成一处，避免各模块各写一版宽窄不同的口径。

口径：
- 日期 → `YYYY-MM-DD`（`date.fromisoformat` 严格零填充）；
- 时间 → ISO-8601，`Z` 归一为 `+00:00`；无时区按 UTC；有偏移先换算到 UTC；
- 非法/缺失一律返回 `None`（调用方决定 fail-closed 文案）。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional


def parse_date(value: object) -> Optional[date]:
    """严格日期（只认 `YYYY-MM-DD` 这类 `date.fromisoformat` 接受的形态）。"""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        # 非法日期返回 None，由调用方生成 fail-closed 诊断。
        return None


def parse_instant(value: object) -> Optional[datetime]:
    """日期或时间 → 带 UTC 时区的 `datetime`；非法/缺失 → None。"""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    day = parse_date(text)
    if day is not None:
        return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        got = datetime.fromisoformat(text)
    except ValueError:
        # 非法时间返回 None，由调用方生成 fail-closed 诊断。
        return None
    if got.tzinfo is None:
        got = got.replace(tzinfo=timezone.utc)
    return got.astimezone(timezone.utc)


def is_iso_date(value: object) -> bool:
    return parse_date(value) is not None


def is_iso_instant(value: object) -> bool:
    return parse_instant(value) is not None


__all__ = ["is_iso_date", "is_iso_instant", "parse_date", "parse_instant"]
