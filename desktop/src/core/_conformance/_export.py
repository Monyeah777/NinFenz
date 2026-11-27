"""conformance_scan 私有子模块 _export：导出契约 manifest 判据：verify.sh 的 check 定义/调用/可失败路径。

门面 core.conformance_scan 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import os
import re



#: 门禁函数体里「可能红」的字面落点；一个都不含 ⇒ 该 check 不可能失败（判据空转）
_GATE_FAIL_TOKENS = ("err=1", "problems.append", 'no "', "no '")



def _gate_defs(verify_txt: str) -> Dict[str, str]:
    """verify.sh → {checkN 的 N: 函数体原文}（从行首 `checkN(){` 到行首 `}`）。"""
    defs: Dict[str, str] = {}
    cur = ""
    buf: List[str] = []
    for line in verify_txt.splitlines():
        if not cur:
            m = re.match(r"^check(\d+)\(\)\{$", line)
            if m:
                cur, buf = m.group(1), []
            continue
        if line == "}":
            defs[cur] = "\n".join(buf)
            cur = ""
            continue
        buf.append(line)
    return defs



def _gate_calls(verify_txt: str) -> set:
    """主执行体里真被调用的 check 号（只取 `主执行体` 标记之后——注释/表头里提一句不算跑）。"""
    run = verify_txt.split("主执行体", 1)[-1]
    return set(re.findall(r"\bcheck(\d+)\b", run))



def export_manifest_issues(root: str,
 verify_txt: str,
 manifest: Dict[str,
 Any]) -> Tuple[List[str],
 int]:
    """导出契约面 manifest 判据（check29 面）→ (issues, 项数)。

    门禁判据（2026-10-07 强化，原差距：只判 `gate in verify_txt`）：**名子串 ⇒ 真定义 +
    主执行体真调用 + 有可失败路径**。旧口径下，注释里写一句 `check18/22` 就算过；而未定义、
    未调用、或任何分支都不 `no`/`err=1` 的 check 都能被声明为「锁定该导出面」——那样
    「L3 = 经导出门禁锁定」就是一句无从证伪的话。
    """
    issues: List[str] = []
    items = manifest.get("items") or []
    defs = _gate_defs(verify_txt)
    calls = _gate_calls(verify_txt)
    for item in items:
        if not isinstance(item, dict):
            issues.append("export manifest item 非对象")
            continue
        iid = item.get("id")
        if item.get("conformance") != "L3":
            issues.append(f"导出面 {iid}: conformance 应为 L3（导出门禁锁定面）")
        for ev in item.get("evidence") or []:
            if not os.path.isfile(os.path.join(root, ev)):
                issues.append(f"导出面 {iid}: 证据文件缺失 {ev}")
        for gate in item.get("gates") or []:
            gid = str(gate)
            num = gid[5:] if gid.startswith("check") and gid[5:].isdigit() else ""
            if not num or num not in defs:
                issues.append(f"导出面 {iid}: 证据门禁 {gid} 在 verify.sh 无 check 定义"
                              f"（修复指引：只声明真存在的 checkN）")
                continue
            if num not in calls:
                issues.append(f"导出面 {iid}: 证据门禁 {gid} 未在主执行体调用（声明了却不跑）")
                continue
            if not any(tok in defs[num] for tok in _GATE_FAIL_TOKENS):
                issues.append(f"导出面 {iid}: 证据门禁 {gid} 无可失败路径"
                              f"（判据空转：该 check 任何分支都不会红）")
    return issues, len(items)
