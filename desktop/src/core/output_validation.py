"""Output / Validation（WP-22）：把产物按 contract + output form 独立校验，失败拒收。

纪律（PR-07 / §13A L6：形态合规 / 可 diff / 失败拒收）：
- **输出独立校验**：不信任 adapter 自述，逐项验 citations（编造=0）、budget、output form
  （md/json/text 的语法/控制字符/占位符/行宽）、contract（`nf-contract/1` 过 schema）；
- **失败拒收**：任何红项 → `OutputRejected`（含修复指引），调用方（Assembly Runtime gate）
  必须停链、不得落交付；
- **可复算**：校验报告 `nf-output-report/1` 只含 digest/指标；同输入同报告逐字节一致；
- **form 登记复用**：form 名与 tier 口径对齐 `protocol/output_forms.json`（T0 散文/T1 良构/
  T2 形状/T3 语义/T4 可复算），不新造一套形态词表。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import agent_adapter as aa

REPORT_SCHEMA = "nf-output-report/1"
CONTRACT_SCHEMA_REL = "protocol/production/contract.schema.json"
GUIDE = "修复指引："
PLACEHOLDERS = ("TODO", "TBD", "<placeholder>", "待补", "FIXME")
CONTROL_EXCEPT = ("\n", "\t")


class OutputRejected(Exception):
    """产物被拒收（消息含修复指引，供 check33 raise 审计）。"""

    def __init__(self, message: str, code: str = "OUTPUT-REJECTED") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _form_of(kind: str) -> str:
    return "json" if kind == "json" else ("file" if kind == "file" else "md")


def _tier(form: str) -> str:
    return "T2" if form == "json" else "T1"


def _control_chars(text: str) -> List[str]:
    bad = []
    for ch in text:
        if ch in CONTROL_EXCEPT:
            continue
        if ord(ch) < 0x20 or ord(ch) == 0x7F:
            bad.append("U+%04X" % ord(ch))
    return bad


def _form_issues(form: str, content: str) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    if form == "json":
        try:
            json.loads(content)
        except ValueError as exc:
            issues.append({"code": "FORM-JSON-INVALID",
                           "message": "JSON 不可解析：%s" % exc,
                           "fix": GUIDE + "输出 kind=json 必须是合法 JSON"})
    else:
        if form == "md" and not any(line.startswith("#") for line in content.splitlines()):
            issues.append({"code": "FORM-MD-NO-HEADING",
                           "message": "Markdown 缺标题（#）",
                           "fix": GUIDE + "md 输出必须有标题结构"})
        for line_no, line in enumerate(content.splitlines(), 1):
            if len(line) > 400:
                issues.append({"code": "FORM-LINE-TOO-LONG",
                               "message": "第 %d 行 >400 字符" % line_no,
                               "fix": GUIDE + "拆行（行宽影响可 diff）"})
                break
    for word in PLACEHOLDERS:
        if word in content:
            issues.append({"code": "FORM-PLACEHOLDER",
                           "message": "含占位符：%s" % word,
                           "fix": GUIDE + "去掉占位符，交付前补全"})
            break
    bad = _control_chars(content)
    if bad:
        issues.append({"code": "FORM-CONTROL-CHARS",
                       "message": "含控制字符：%s" % ",".join(bad[:3]),
                       "fix": GUIDE + "去除控制字符（UTF-8 可读文本）"})
    return issues


def _contract(task: Dict[str, Any], out: Dict[str, Any], content: str) -> Dict[str, Any]:
    slot = str((task.get("slot") or {}).get("id") or "slot:unknown")
    slug = slot.replace("slot:", "").replace("/", "-").replace(":", "-")
    path = str(((out.get("output") or {}).get("path")) or "")
    artifact: Dict[str, Any] = {"kind": "doc", "digest": _sha(content)}
    if path:
        artifact["path"] = path
    return {"schema": "nf-contract/1", "id": "nf:output:" + slug, "version": 1,
            "artifact": artifact,
            "constraints": [
                {"id": "C-001", "rule": "citations ⊆ context_refs（编造引用=0）", "severity": "MUST"},
                {"id": "C-002", "rule": "content ≤ budget.max_tokens×4", "severity": "MUST"},
                {"id": "C-003", "rule": "output form 语法/控制字符/占位符合规", "severity": "MUST"}],
            "acceptance": [{"id": "A-001"}, {"id": "A-002"}], "status": "active"}


def validate(out: Dict[str, Any], task: Dict[str, Any],
             pack: Optional[Dict[str, Any]] = None, root: str = ".") -> Dict[str, Any]:
    """独立校验产物 → `nf-output-report/1`（不抛；accept() 才拒收）。"""
    from core import json_schema
    issues: List[Dict[str, str]] = []
    content = str(((out.get("output") or {}).get("content")) or "")
    kind = str((out.get("output") or {}).get("kind") or "md")
    form = _form_of(kind)
    # 1) adapter 契约（citations/budget/kind/slot/tokens）
    for item in aa.validate_output(out, task, pack):
        issues.append({"code": "ADAPTER-CONTRACT", "message": item,
                       "fix": GUIDE + "按 nf-adapter-output/1 修"})
    # 2) contract（nf-contract/1 schema）
    contract = _contract(task, out, content)
    schema = json.loads((Path(root) / CONTRACT_SCHEMA_REL).read_text(encoding="utf-8"))
    for item in json_schema.json_schema_check(contract, schema)[:3]:
        issues.append({"code": "CONTRACT-INVALID", "message": "contract schema：%s" % item,
                       "fix": GUIDE + "修 nf-contract/1 字段"})
    # 3) output form
    issues += _form_issues(form, content)
    # 4) metrics
    citations = [str(c) for c in out.get("citations") or []]
    allowed = {str((c or {}).get("id")) for c in task.get("context_refs") or []}
    if pack:
        allowed = {str(e.get("id")) for e in pack.get("entries") or []}
    cited_ok = sum(1 for c in citations if c in allowed)
    rate = (cited_ok / len(citations)) if citations else 0.0
    metrics = {"form": form, "tier": _tier(form), "chars": len(content),
               "tokens": int((out.get("usage") or {}).get("tokens") or 0),
               "citations": len(citations), "citation_rate": round(rate, 4),
               "control_chars": len(_control_chars(content)),
               "violations": len(issues)}
    report = {"schema": REPORT_SCHEMA, "ok": not issues, "form": form, "tier": _tier(form),
              "digest": _sha(content), "contract": contract, "issues": issues,
              "metrics": metrics}
    return report


def accept(out: Dict[str, Any], task: Dict[str, Any],
           pack: Optional[Dict[str, Any]] = None, root: str = ".") -> Dict[str, Any]:
    """校验并拒收：有红项 → OutputRejected（含 code/修复指引）；否则返回报告。"""
    report = validate(out, task, pack, root)
    if not report["ok"]:
        first = report["issues"][0]
        raise OutputRejected("产物被拒收：%s（%s；%s）"
                             % (first["code"], first["message"], first["fix"]),
                             code=str(first["code"]))
    return report


def render(report: Dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_report(report: Dict[str, Any], rel: str, root: str = ".") -> Path:
    from core import atomic_write
    path = Path(root) / rel
    atomic_write.write_text(path, render(report))
    return path
