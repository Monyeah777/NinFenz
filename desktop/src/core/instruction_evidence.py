"""规范入口指令的**实测记录**判据（文档可执行性面 · 顶层化目标 GAP-6）。

为什么需要：文档里的入口指令（`bash verify.sh`、`python scripts/nf.py release` …）此前
只有「写着」，没有任何证据表明它**被真跑过、跑出什么结果、什么时候跑的**——读者与下游
无从区分「可执行」与「曾经可执行」。本模块把「指令块挂实测记录」落成判据：

- **声明面**（真源）= `protocol/instruction_evidence.json` 的 `instructions`
  （id / cmd / note / tier / max_age_days），不写死在代码里；
- **证据面** = 同件 `evidence`（由 `--record` 真跑写入：命令 / 退出码 / 时间 / 输出摘要
  / 输出 sha256）；
- **判据**：① 每条声明须有记录（缺 = FAIL）；② 记录须**退出码 0**（非 0 = FAIL）；
  ③ 记录须在 `max_age_days` 内（过期 = FAIL）；④ 记录键必须都是已声明指令（凭空记录 = FAIL）。

纪律：纯标准库；本模块不自己执行命令（执行发生在 `scripts/instruction_evidence.py` 的
`--record` 里），以便「判据只读、实测显式」。
"""
from __future__ import annotations

import datetime as _dt

from core import atomic_write
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from core import json_doc

DECL_REL = "protocol/instruction_evidence.json"
SCHEMA = "nf-instruction-evidence/1"
#: 临近过期提前量（天）：剩余天数 <= 它就发 WARN（不是 FAIL）。
#: 为什么要有（2026-11-07 实测）：release 记录 2026-10-07、窗口 30 天，恰好在 11-06 仍有效、
#: 11-07 一过就 FAIL——**没有任何内容变更，门禁在午夜自己变红**，且与「提交坏了」长得一样。
#: 提前 7 天喊，比午夜突袭好。
WARN_DAYS_BEFORE_EXPIRY = 7

#: 机器绝对路径（Windows 盘符 / macOS / Linux 家目录）——证据件进公开仓，**不得**带作者机器路径。
_MACHINE_PATH = re.compile(r"(?:[A-Za-z]:[\\/][^\s\"'）)】]*)|(?:/(?:Users|home)/[^\s\"'）)】]*)")


def redact_paths(text: str) -> str:
    """把输出摘要里的机器绝对路径换成 `<path>`（泄漏面收口；只影响人读摘要，不动哈希）。"""
    return _MACHINE_PATH.sub("<path>", text or "")


def load(root: str = ".") -> Tuple[Dict[str, Any], List[str]]:
    """读声明+证据件 → (doc, issues)；缺失/不可解析/字段不全一律 fail-closed。"""
    p = Path(root) / DECL_REL
    if not p.is_file():
        return {}, ["缺指令实测记录件 %s（修复指引：新建并声明入口指令，再跑 "
                    "python scripts/instruction_evidence.py --record）" % DECL_REL]
    try:
        doc = json_doc.load(p, dict, what=DECL_REL)
    except ValueError as exc:
        return {}, ["%s 不是合法 JSON：%s（修复指引：修好 JSON 语法）" % (DECL_REL, exc)]
    issues: List[str] = []
    if doc.get("schema") != SCHEMA:
        issues.append("%s schema 不匹配（期望 %s）（修复指引：改为声明件当前形态）"
                      % (DECL_REL, SCHEMA))
    if not isinstance(doc.get("instructions"), list) or not doc["instructions"]:
        issues.append("%s 缺 instructions 声明（修复指引：至少声明一条入口指令）" % DECL_REL)
    return doc, issues


def _age_days(stamp: str, today: _dt.date) -> int:
    try:
        d = _dt.date.fromisoformat(str(stamp)[:10])
    except ValueError:
        return 10 ** 6                       # 时间戳不可解析 → 视作无限旧（判 FAIL）
    return (today - d).days


def _warn_window(max_age: int) -> int:
    """提前量：取 7 天与窗口一半的较小者（短窗口不被常量吞掉；刚录完的不吵）。"""
    return min(WARN_DAYS_BEFORE_EXPIRY, max(1, max_age // 2))


def _record_issues(iid: str, item: Dict[str, Any], rec: Any,
                   today: _dt.date) -> Tuple[List[str], str]:
    """单条声明的记录面：策略词表/记录在场/退出码/新鲜度 → (issues, warn)。"""
    issues: List[str] = []
    warn = ""
    policy = str(item.get("evidence_policy") or "green")
    if policy not in ("green", "recorded"):
        issues.append("指令 %s 的 evidence_policy 非法：%s（修复指引：只许 green / recorded）"
                      % (iid, policy))
    if not isinstance(rec, dict):
        issues.append("指令 %s（%s）无实测记录（修复指引：python scripts/"
                      "instruction_evidence.py --record）" % (iid, item.get("cmd")))
        return issues, warn
    if int(rec.get("exit_code", 1)) != 0 and policy != "recorded":
        issues.append("指令 %s 实测退出码 %s（修复指引：先修到 0 再 --record）"
                      % (iid, rec.get("exit_code")))
    max_age = int(item.get("max_age_days", 30) or 30)
    age = _age_days(str(rec.get("ran_at") or ""), today)
    if age > max_age:
        issues.append("指令 %s 的实测记录已过期（%d 天 > 上限 %d 天）（修复指引："
                      "python scripts/instruction_evidence.py --record --only %s）"
                      % (iid, age, max_age, iid))
    elif max_age - age <= _warn_window(max_age):
        left = max_age - age
        warn = (f"指令 {iid} 的实测记录 {left} 天后过期（{age}/{max_age} 天，"
                f"上限 {max_age}）（修复指引：趁早 --record --only {iid}，"
                "别等它半夜变红）")
    return issues, warn


def _scan_item(item: Any, ev: Dict[str, Any],
               today: _dt.date) -> Tuple[List[str], str]:
    """单条声明 → (issues, warn)；缺 id 直接报。"""
    iid = str((item or {}).get("id") or "")
    if not iid:
        return ["%s 有声明项缺 id（修复指引：补齐 id/cmd/note）" % DECL_REL], ""
    return _record_issues(iid, item, ev.get(iid), today)


def _decl_scan_issues(decl: List[Any], ev: Dict[str, Any],
                      today: _dt.date) -> Tuple[List[str], List[str]]:
    """全部声明逐条体检 → (issues, warns)。"""
    issues: List[str] = []
    warns: List[str] = []
    for item in decl:
        item_issues, warn = _scan_item(item, ev, today)
        issues.extend(item_issues)
        if warn:
            warns.append(warn)
    return issues, warns


def _undeclared_issues(ev: Dict[str, Any], known: set) -> List[str]:
    """凭空记录（无对应声明）逐条报。"""
    return ["记录 %s 无对应声明（修复指引：要么在 %s 声明该指令，要么删掉记录）"
            % (iid, DECL_REL) for iid in sorted(set(ev) - known)]


def _recorded_policy_count(decl: List[Any]) -> int:
    """evidence_policy=recorded 的声明数。"""
    return sum(1 for i in decl
               if str((i or {}).get("evidence_policy") or "") == "recorded")


def scan(root: str = ".", today: _dt.date | None = None
         ) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """→ (issues, warns, stats)：缺记录/非零退出/过期/凭空记录 = FAIL。

    例外：`evidence_policy: "recorded"` 的指令只要求「真跑记录存在 + 新鲜」——它们与判据表
    互为不动点（见声明件 note）：`verify` / `release` 要绿必须判据表全绿，而判据表里就要求
    它们绿。这类入口的绿由 CI 跨平台 workflow 与发布流程另判，不在这里自证。
    """
    doc, issues = load(root)
    warns: List[str] = []
    if not doc or issues:
        return issues, warns, {"declared": 0, "recorded": 0}
    today = today or _dt.date.today()  # noqa: DTZ011 - 本地日历日期是有意语义（UTC 会在跨零点给出错误「今天」）
    decl = doc.get("instructions") or []
    ev = doc.get("evidence") or {}
    decl_issues, decl_warns = _decl_scan_issues(decl, ev, today)
    issues.extend(decl_issues)
    warns.extend(decl_warns)
    known = {str((i or {}).get("id") or "") for i in decl}
    issues.extend(_undeclared_issues(ev, known))
    stats = {"declared": len(known), "recorded": len(set(ev) & known)}
    stats["recorded_policy"] = _recorded_policy_count(decl)
    return issues, warns, stats


def _should_run(item: Dict[str, Any], only: str, iid: str) -> bool:
    """本次 --record 是否跑该指令（all / fast / 具体 id）。"""
    if not only:
        return True
    if only in ("all", iid):
        return True
    return only == "fast" and item.get("tier") == "fast"


def _run_item(item: Dict[str, Any], iid: str, ev: Dict[str, Any], runner,
              today: _dt.date) -> None:
    """真跑一条指令并把证据写进 ev。"""
    cmd = str(item.get("cmd") or "")
    code, out = runner(cmd)
    ev[iid] = {"cmd": cmd, "exit_code": int(code), "ran_at": today.isoformat(),
               "output_tail": redact_paths(
                   "\n".join(out.strip().splitlines()[-3:]))[:400],
               "output_sha256": hashlib.sha256(out.encode("utf-8", "replace")).hexdigest()}


def _policies(doc: Dict[str, Any]) -> Dict[str, str]:
    """指令 id → evidence_policy（缺省 green）。"""
    return {str((i or {}).get("id") or ""): str((i or {}).get("evidence_policy") or "green")
            for i in doc.get("instructions") or []}


def _bad_ids(ev: Dict[str, Any], pol: Dict[str, str]) -> List[str]:
    """汇总口径与 scan 一致：`evidence_policy: recorded` 的入口（不动点例外）非零退出不算 bad。"""
    return [k for k, v in ev.items() if int((v or {}).get("exit_code", 1)) != 0
            and pol.get(k, "green") != "recorded"]


def record(root: str = ".", only: str = "", runner=None,
           today: _dt.date | None = None) -> Tuple[List[str], Dict[str, Any]]:
    """真跑声明指令并写回证据 → (bad_ids, doc)。

    `runner(cmd) -> (exit_code, output)` 由调用方注入（CLI 里是 subprocess），便于单测注入
    假执行器；`only` 可为 `all` / `fast` / 具体 id。
    """
    doc, issues = load(root)
    if not doc or issues:
        return issues, doc
    today = today or _dt.date.today()  # noqa: DTZ011 - 本地日历日期是有意语义（UTC 会在跨零点给出错误「今天」）
    ev = doc.setdefault("evidence", {})
    for item in doc.get("instructions") or []:
        iid = str((item or {}).get("id") or "")
        if not iid:
            continue
        if not _should_run(item, only, iid):
            continue
        _run_item(item, iid, ev, runner, today)
    p = Path(root) / DECL_REL
    atomic_write.write_text(p, json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return _bad_ids(ev, _policies(doc)), doc
