"""治理附件模式（WP-32，G3）：none / observe / require + 生产独立性。

纪律：
- `none`：治理不介入（生产照常，不留观察）；
- `observe`：记录证据是否在场/等级，**绝不阻塞**；
- `require`：证据必须存在、验证 ok、等级 ≥ min_level，否则拒收（exit 2）；
- **独立性**：附件评估是纯函数，不读写生产产物——同输入生产记录/交付包在三模式下逐字节一致
  （判据断言 digest 相等）；治理开关不得改变生产输出；
- 口径诚实：observe 不等于「通过治理」；require 只做证据/receipt 门，不评价内容质量。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = "nf-attachment/1"
REL = "protocol/attachment.json"
LEVELS = ("T0", "T1", "T2", "T3", "T4")
GUIDE = "修复指引："


class AttachmentError(Exception):
    """附件拒绝（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "ATTACHMENT-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise AttachmentError("缺 %s（修复指引：补附件模式登记）" % REL,
                              code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AttachmentError("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise AttachmentError("registry schema 必须 %s" % SCHEMA)
    return doc


def modes(root: str = ".") -> Dict[str, Dict[str, Any]]:
    reg = load_registry(root)
    return {str(m.get("id")): m for m in reg.get("modes") or [] if isinstance(m, dict)}


def _mode_rows_issues(table: Dict[str, Dict[str, Any]]) -> List[str]:
    """模式行：必备三模式齐备、blocking 在场、min_level 合法。"""
    issues: List[str] = []
    for need in ("none", "observe", "require"):
        if need not in table:
            issues.append("缺模式：%s" % need)
    for mid, mode in table.items():
        if "blocking" not in mode:
            issues.append("%s 缺 blocking" % mid)
        if str(mode.get("min_level") or "") and str(mode.get("min_level")) not in LEVELS:
            issues.append("%s min_level 非法：%s" % (mid, mode.get("min_level")))
    return issues


def _require_mode_issues(table: Dict[str, Dict[str, Any]]) -> List[str]:
    """require 模式：必须阻塞且写明 min_level。"""
    issues: List[str] = []
    require = table.get("require") or {}
    if not require.get("blocking"):
        issues.append("require 必须 blocking=true（修复指引：require 不阻塞就失去意义）")
    if not str(require.get("min_level") or ""):
        issues.append("require 必须写 min_level")
    return issues


def _registry_index(reg: Dict[str, Any]) -> tuple[Dict[str, Dict[str, Any]], List[str]]:
    """登记表与模式词表两视图（都源于同一份 registry）。"""
    table = {str(m.get("id")): m for m in reg.get("modes") or []}
    vocab = [str(x) for x in reg.get("mode_vocabulary") or []]
    return table, vocab


def _vocabulary_issues(table: Dict[str, Dict[str, Any]], vocab: List[str]) -> List[str]:
    """modes 与 mode_vocabulary 必须逐项同集。"""
    if sorted(table) != sorted(vocab):
        return ["modes 与 mode_vocabulary 不一致"]
    return []


def _boundary_issues(reg: Dict[str, Any]) -> List[str]:
    """claims_boundary 必须写明不替代适配层/审计包。"""
    boundary = " ".join(str(x) for x in reg.get("claims_boundary") or [])
    if "不替代" not in boundary:
        return ["claims_boundary 必须写明不替代适配层/审计包"]
    return []


def check_registry(root: str = ".") -> List[str]:
    issues: List[str] = []
    reg = load_registry(root)
    table, vocab = _registry_index(reg)
    issues.extend(_vocabulary_issues(table, vocab))
    issues.extend(_mode_rows_issues(table))
    issues.extend(_require_mode_issues(table))
    if not str(reg.get("independence_rule") or "").strip():
        issues.append("缺 independence_rule")
    issues.extend(_boundary_issues(reg))
    return issues


def _observe_observations(present: bool, ok: bool, level: str) -> List[str]:
    """observe 模式：只记录观察，绝不阻塞。"""
    observations: List[str] = []
    if not present:
        observations.append("WARN 证据不在场（observe 不阻塞）")
    elif not ok:
        observations.append("WARN 验证未通过（observe 不阻塞）")
    else:
        observations.append("证据在场且验证通过（level=%s）" % (level or "T0"))
    return observations


def _require_outcome(table: Dict[str, Dict[str, Any]], mode: str, present: bool,
                     ok: bool, level: str) -> tuple[bool, str, List[str]]:
    """require 模式：证据在场 + 验证 ok + 等级 ≥ min_level，否则拒收（exit 2）。"""
    min_level = str(table[mode].get("min_level") or "T1")
    passed = True
    code = ""
    if not present:
        passed, code = False, "ATTACHMENT-MISSING"
    elif not ok:
        passed, code = False, "ATTACHMENT-NOT-VERIFIED"
    elif level not in LEVELS or LEVELS.index(level) < LEVELS.index(min_level):
        passed, code = False, "ATTACHMENT-LEVEL-LOW"
    observations: List[str] = []
    if not passed:
        observations.append("require 未满足：%s（修复指引：附证据并验证到 ≥%s）"
                            % (code, min_level))
    return passed, code, observations


def evaluate(mode: str, evidence: Optional[Dict[str, Any]] = None,
             root: str = ".") -> Dict[str, Any]:
    """评估附件模式 → 判定（纯函数：不读写生产产物）。

    evidence 形如 `{"bundle_present": bool, "verification": {"ok": bool, "level": "T1"}}`。
    返回 {"schema":"nf-attachment-report/1","mode","passed","exit_code","observations",...}。
    """
    table = modes(root)
    if mode not in table:
        raise AttachmentError("未知附件模式：%r（修复指引：none/observe/require）" % mode,
                              code="MODE-UNKNOWN")
    ev = evidence or {}
    present = bool(ev.get("bundle_present"))
    verification = ev.get("verification") or {}
    ok = bool(verification.get("ok"))
    level = str(verification.get("level") or "")
    observations: List[str] = []
    passed = True
    code = ""
    if mode == "none":
        pass
    elif mode == "observe":
        observations = _observe_observations(present, ok, level)
    else:  # require
        passed, code, observations = _require_outcome(table, mode, present, ok, level)
    report = {"schema": "nf-attachment-report/1", "mode": mode,
              "passed": passed, "exit_code": 0 if passed else 2,
              "observations": observations,
              "evidence": {"bundle_present": present, "verification_ok": ok,
                           "level": level},
              "note": "附件评估不改生产产物；observe 不阻塞、require 缺证据即拒"}
    if not passed:
        raise AttachmentError(report["observations"][0], code=code)
    return report


def independence_digest(record: Dict[str, Any]) -> str:
    """生产产物摘要（用于三模式独立性对照；只读记录里的 assembly/output digest）。"""
    import hashlib
    payload = {"assembly": record.get("assembly") or {},
               "output": (record.get("run") or {}).get("output") or {},
               "status": (record.get("run") or {}).get("status")}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()
