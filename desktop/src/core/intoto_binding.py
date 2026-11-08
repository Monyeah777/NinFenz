"""in-toto Statement v1 与协议层回执的绑定判据。"""
from __future__ import annotations

import re
from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def check_statement(st: dict[str, Any], rec: dict[str, Any], issues: list[str]) -> None:
    """校验 Statement 头、subject/digest 与 predicate 均和回执逐项同源。"""
    entries = _list(rec.get("entries"))
    subjects = _list(st.get("subject"))
    want_subjects = [(str(e.get("path") or ""), str(e.get("digest") or "")) for e in entries]
    got_subjects = [
        (str(s.get("name") or ""), str(_dict(s.get("digest")).get("sha256") or ""))
        for s in subjects
    ]
    if got_subjects != want_subjects:
        issues.append("in-toto subject 与协议层回执不一致：须按下标逐项匹配 path + sha256"
                      "（修复指引：subject 顺序、名称或摘要不得漂移）")
    for name, digest in got_subjects:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            issues.append(f"in-toto subject 缺合规 sha256：{name}"
                          "（修复指引：回执 digest 须 64 位小写十六进制）")
    if st.get("_type") != "https://in-toto.io/Statement/v1":
        issues.append("in-toto Statement 类型头不合法（修复指引：_type 须为 Statement/v1）")
    predicate_type = str(st.get("predicateType") or "")
    if not re.fullmatch(r"https://[^\s]+", predicate_type):
        issues.append("in-toto predicateType 须为 HTTPS URI")
    predicate = st.get("predicate")
    if not isinstance(predicate, dict):
        issues.append("in-toto predicate 必须是对象")
        return
    if predicate.get("count") != len(subjects):
        issues.append("in-toto predicate.count 与 subject 数不一致")
    if predicate.get("root") != rec.get("root"):
        issues.append("in-toto predicate.root 与协议层回执不一致")
    if predicate.get("algorithm") != rec.get("algorithm"):
        issues.append("in-toto predicate.algorithm 与协议层回执不一致")
    if predicate.get("scope") != rec.get("scope"):
        issues.append("in-toto predicate.scope 与协议层回执不一致")
