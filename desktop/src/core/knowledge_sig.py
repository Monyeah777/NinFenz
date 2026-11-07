"""v2.8.0 波C C1/C2：协议知识签名 + 版本差异检测（41 规划「确定性知识编译」）。

C1 `nf sig`：对 NF 文档（编号方案 01-36 / 协议 / 管线 / 模块）生成结构化签名
    ——知识指纹（标题/编号/版本/章节/引用集/正文哈希），纯标准库、可复现。
C2 `nf diff`：任意两份签名 → 字段级差异 + 兼容判定；verify.sh check25 收编
   「全量 01-36 签名覆盖 + 可复现」门禁（编译期冲突发现，录入时而非提问时）。

纪律：只做新增可计算摘要，不改 01-07/registry/verify 既有契约字段；
      yaml 一律按文本片段解析（无第三方依赖，verify 零依赖红线保持）。
"""
from __future__ import annotations

import hashlib
import json
import os

from core.contract_text import DOC_RANGE, build_signature_text


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_signature(path: str, root: str = ".") -> dict:
    """对单个 NF 文档生成结构化签名（相对 root 的可复现摘要）。"""
    abs_path = os.path.join(root, path)
    with open(abs_path, encoding="utf-8") as fh:
        raw = fh.read()
    return build_signature_text(path, raw)


def _canonical(sig: dict) -> bytes:
    return json.dumps(sig, sort_keys=True, ensure_ascii=False).encode("utf-8")


def signature_digest(sig: dict) -> str:
    return _sha(_canonical(sig).decode("utf-8"))


def discover_docs(root: str = ".") -> list:
    """全量 01-36 根目录方案文档（验收基线：试点 3 + 全量 01-36）。"""
    out = []
    for name in sorted(os.listdir(root)):
        if name.endswith(".md") and DOC_RANGE.match(name):
            out.append(name)
    return out


def scan(root: str = ".") -> dict:
    """生成全量签名集：{count, records:[{digest, sig}]}。"""
    records = []
    for rel in discover_docs(root):
        sig = build_signature(rel, root)
        records.append({"digest": signature_digest(sig), "sig": sig})
    return {"count": len(records), "records": records}


def verify_reproducible(root: str = ".") -> tuple:
    """check25 语义：01-36 全量签名两遍生成逐字节一致（可复现 = 知识指纹稳定）。"""
    issues = []
    first = scan(root)
    second = scan(root)
    if first["count"] == 0:
        issues.append("未发现任何 01-36 编号方案文档")
    if first["count"] != second["count"]:
        issues.append("两遍扫描文件数不一致")
    d1 = {r["sig"]["path"]: r["digest"] for r in first["records"]}
    d2 = {r["sig"]["path"]: r["digest"] for r in second["records"]}
    if d1 != d2:
        for p in sorted(set(d1) | set(d2)):
            if d1.get(p) != d2.get(p):
                issues.append("签名不可复现：%s" % p)
    for r in first["records"]:
        if not r["sig"]["title"]:
            issues.append("缺少标题：%s" % r["sig"]["path"])
    stats = {
        "docs": first["count"],
        "reproducible": int(not issues),
        "digests": sorted(d1.values()),
    }
    return issues, stats


def diff_signatures(a: dict, b: dict) -> dict:
    """C2：任意两签名 → 字段级差异 + 兼容判定（判定规则自含文档化）。"""
    changes = []
    scalar_fields = ("kind", "doc_id", "title", "version", "self_id",
                     "layer", "category", "heading_count",
                     "meta_line_count", "line_count", "body_hash")
    for f in scalar_fields:
        va, vb = a.get(f), b.get(f)
        if va != vb:
            changes.append({"field": f, "from": va, "to": vb, "kind": "字段变更"})
    list_fields = ("headings", "schema_names", "field_paths", "refs")
    for f in list_fields:
        sa, sb = set(a.get(f, [])), set(b.get(f, []))
        for x in sorted(sa - sb):
            changes.append({"field": f, "from": x, "to": None, "kind": "移除"})
        for x in sorted(sb - sa):
            changes.append({"field": f, "from": None, "to": x, "kind": "新增"})
    removed = [
        c for c in changes
        if c["kind"] == "移除" and c["field"] in ("refs", "headings", "field_paths")
    ]
    removed_any = [c for c in changes if c["kind"] == "移除"]
    added_any = [c for c in changes if c["kind"] == "新增"]
    if a.get("doc_id") and b.get("doc_id") and a["doc_id"] != b["doc_id"]:
        verdict = "破坏（文档编号变更）"
    elif removed:
        verdict = "需评审（存在移除项：引用/章节收缩）"
    elif a.get("version") != b.get("version"):
        verdict = "兼容（版本演进）"
    else:
        verdict = "兼容"
    # 43 A3 —— 影响度三档：bump > additive > editorial（protocol/EXTENSION.md 判据表）
    version_bump = a.get("version") != b.get("version")
    if a.get("doc_id") != b.get("doc_id") or removed_any or version_bump:
        impact = "bump"
    elif added_any:
        impact = "additive"
    else:
        impact = "editorial"
    return {"from": a.get("path"), "to": b.get("path"),
            "verdict": verdict, "impact": impact, "changes": changes}
