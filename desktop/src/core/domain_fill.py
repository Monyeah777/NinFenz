"""域包补全模板（不代写领域内容，只把「要填什么」变成结构化清单）。

背景：73 个 derived 域包 12 条细分的定义/判据/失效模式仍是段级框架（`shell_ledger` 台账）。
本模块给作者/领域专家一个**待填模板**：从公开机读投影生成 12 条骨架（名称/锚已就位，
定义/判据/失效模式留空），并提供 `check()` 校验填好的模板——不生成内容、不调用模型。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import json_doc

SCHEMA = "nf-domain-fill/1"
SHELL_PHRASES = ("领域细则待作者补全", "领域专属判据待补", "领域专属失效模式待补")


def template(root: str, package: str) -> Dict[str, Any]:
    """按包公开投影生成待填模板（确定性：无时间戳、按 id 排序）。"""
    base = Path(root) / "community" / package
    spec = json_doc.load(base / "outputs" / "DOMAIN_SPEC.json", dict,
                         what="%s/outputs/DOMAIN_SPEC.json" % package)
    rows = []
    for s in spec.get("subdivisions") or []:
        rows.append({
            "id": str(s.get("id") or ""),
            "name": str(s.get("name") or ""),
            "standard_ref": str(s.get("standard_ref") or ""),
            "anchors": s.get("standards") or [],
            # 下面三列**必须由作者/领域专家落笔**（不代写）：
            "definition": "",
            "check": "",
            "pitfall": "",
        })
    return {"schema": SCHEMA, "package": package,
            "code": spec.get("code"), "domain": spec.get("domain"),
            "section": spec.get("section"), "metric_family": spec.get("metric_family"),
            "content_tier": "authored（填写完毕后改）",
            "instruction": ("逐条填写 definition/check/pitfall（领域专属、可判定、可机检）；"
                            "填完用 `nf domain template <包> --check <文件>` 自检，"
                            "再按 docs/domain-packs.md「内容完备度」流程补全与重冻结。"),
            "subdivisions": rows}


def check(doc: Any) -> List[str]:
    """校验填好的模板 → issue 列表（空 = 可进入下一步补全流程）。"""
    issues: List[str] = []
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return ["模板 schema 不匹配（期望 %s）" % SCHEMA]
    subs = doc.get("subdivisions")
    if not isinstance(subs, list) or len(subs) != 12:
        return ["subdivisions 须为 12 条（当前 %s）"
                % (len(subs) if isinstance(subs, list) else "非数组")]
    for i, s in enumerate(subs):
        if not isinstance(s, dict):
            issues.append("subdivisions[%d] 非对象" % i)
            continue
        sid = str(s.get("id") or ("#%d" % i))
        for key in ("definition", "check", "pitfall"):
            val = str(s.get(key) or "").strip()
            if not val:
                issues.append("%s 缺 %s" % (sid, key))
            elif any(t in val for t in SHELL_PHRASES):
                issues.append("%s 的 %s 仍是占位短语" % (sid, key))
    return issues


def write_template(root: str, package: str, out: str) -> str:
    import json
    doc = template(root, package)
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(p)


def check_dir(directory: str):
    """批量校验目录下的待填模板 → (issues, stats)。"""
    import json
    d = Path(directory)
    files = sorted(d.glob("*.json")) if d.is_dir() else []
    issues = []
    ok = 0
    for f in files:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            issues.append("%s 不可读/非 JSON：%s" % (f.name, exc))
            continue
        bad = check(doc)
        if bad:
            issues.extend("%s: %s" % (f.name, i) for i in bad)
        else:
            ok += 1
    stats = {"files": len(files), "ok": ok, "bad": len(files) - ok}
    return issues, stats


def fill_status(directory: str):
    """批量统计模板填写进度 → (stats, per_file)。（不写盘；供 `nf domain shells --fill-dir`）"""
    import json
    d = Path(directory)
    files = sorted(d.glob("*.json")) if d.is_dir() else []
    per = {}
    total = filled = 0
    for f in files:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            per[f.name] = {"total": 12, "filled": 0, "bad": 1}
            total += 12
            continue
        subs = doc.get("subdivisions") if isinstance(doc, dict) else None
        n = len(subs) if isinstance(subs, list) else 0
        got = 0
        for s in subs or []:
            if not isinstance(s, dict):
                continue
            if all(str(s.get(k) or "").strip() and
                   not any(t in str(s.get(k)) for t in SHELL_PHRASES)
                   for k in ("definition", "check", "pitfall")):
                got += 1
        per[f.name] = {"total": n, "filled": got}
        total += n
        filled += got
    stats = {"files": len(files), "subdivisions": total, "filled": filled,
             "percent": round(filled * 100.0 / total, 1) if total else 0.0}
    return stats, per
