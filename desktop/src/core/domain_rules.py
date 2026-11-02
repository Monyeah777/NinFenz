"""域包「12 条细分规则」的机读化：把 DOMAIN_SPEC 的 check 文本编译成可消费规则表。

不执行自然语言判定：只抽结构化事实（id/name/definition/check/pitfall/字段名/锚），
并给规则表一个稳定 digest；证据卡可引用该 digest，agent 可据此逐条检查产物。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from core import json_doc

SCHEMA = "nf-domain-rules/1"
_FIELD = re.compile(r"([a-z][a-z0-9_]{2,64})\s*[（(]")


def _field_names(text: str) -> List[str]:
    out: List[str] = []
    for m in _FIELD.finditer(text or ""):
        name = m.group(1)
        if name not in out:
            out.append(name)
    return out


def build_rules(package: str, root: str = ".") -> Dict[str, Any]:
    base = Path(root) / "community" / package
    spec = json_doc.load(base / "outputs" / "DOMAIN_SPEC.json", dict,
                         what="%s/outputs/DOMAIN_SPEC.json" % package)
    rules = []
    for s in spec.get("subdivisions") or []:
        check = str(s.get("check") or "")
        rules.append({"id": str(s.get("id") or ""), "name": str(s.get("name") or ""),
                      "definition": str(s.get("definition") or ""),
                      "check": check, "pitfall": str(s.get("pitfall") or ""),
                      "fields": _field_names(check),
                      "anchor": str(s.get("anchor") or "")})
    body = {"schema": SCHEMA, "package": package, "code": spec.get("code"),
            "content_tier": spec.get("content_tier"), "rules": rules}
    body["rule_digest"] = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    body["machine_fields"] = sum(1 for r in rules if r["fields"])
    return body


def coverage(text: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    """产物对规则表的覆盖：细分名命中 + 字段命中 + **逐规则**判定。"""
    t = text or ""
    rows = rules.get("rules") or []
    per_rule = []
    for r in rows:
        fs = list(dict.fromkeys(r.get("fields") or []))
        name_hit = bool(r.get("name")) and r["name"] in t
        fh = [f for f in fs if f in t]
        per_rule.append({"id": r.get("id"), "name": r.get("name"),
                         "name_hit": name_hit, "fields": len(fs),
                         "fields_hit": len(fh),
                         "ok": name_hit and (not fs or len(fh) == len(fs))})
    name_hits = [r["id"] for r in rows if r.get("name") and r["name"] in t]
    fields = []
    for r in rows:
        fields.extend(r.get("fields") or [])
    uniq = list(dict.fromkeys(fields))
    field_hits = [f for f in uniq if f in t]
    return {"rules": len(rows), "names_hit": len(name_hits),
            "fields": len(uniq), "fields_hit": len(field_hits),
            "rule_ids_hit": name_hits,
            "per_rule": per_rule,
            "rules_ok": sum(1 for x in per_rule if x["ok"])}
