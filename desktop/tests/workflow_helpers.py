"""CI workflow 契约测试共用的 YAML 访问 helper（D-005：22 份测试此前各抄一份）。"""
from __future__ import annotations


def on(doc: dict) -> dict:
    value = doc.get("on")
    if value is None:
        value = doc.get(True)
    return value if isinstance(value, dict) else {}


def steps(job: dict) -> list:
    return [s for s in (job.get("steps") or []) if isinstance(s, dict)]


def runs(job: dict) -> str:
    return "\n".join(str(s.get("run") or "") for s in steps(job))
