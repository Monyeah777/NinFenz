#!/usr/bin/env python3
"""敏感内容检测（FG-03）：Issue / PR 命中密钥片段、内部路径、未公开漏洞线索 → 打标并提示转私密。

手册 FG-03 的伪解点名两件事：① 建了 sensitive 标签却没有自动检测；② 检测只接在 PR 上，
Issue 侧空白。本脚本同时服务 issue 与 pull_request 事件，规则集中在
scripts/sensitive_patterns.json（样例必须是明显假值），命中后由 workflow 打标签 + 评论提醒。

设计边界（诚实声明）：
- 本脚本只做**检测与建议动作**，不自动删改正文、不自动关闭——敏感内容可能需要保留取证；
- 真正的「转私密」通道是 GitHub Security Advisory / 邮件，workflow 评论里给出入口；
- 输出对密钥片段做遮蔽（只留前 4 字符），避免检测产物本身变成新的泄漏面。

用法：
  python scripts/sensitive_scan.py --payload event.json --json
负例自证：假密钥/假内网路径/假 CVE 的模拟 payload 必须命中；普通正文必须零命中。
"""
import argparse
import json
import re
import sys
from pathlib import Path

RULES_REL = Path("scripts") / "sensitive_patterns.json"


def _utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def load_rules(root="."):
    path = Path(root) / RULES_REL
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = []
    for rule in data.get("rules", []):
        rules.append({
            "id": rule["id"],
            "category": rule.get("category", "other"),
            "why": rule.get("why", ""),
            "regex": re.compile(rule["regex"], re.I if rule.get("ignore_case", True) else 0),
        })
    return rules


def _mask(text, category):
    if category == "secret":
        return text[:4] + "***" if len(text) > 4 else "***"
    return text if len(text) <= 60 else text[:57] + "..."


def _collect(payload):
    """→ 待检测文本列表 [(field, text)]，覆盖 issue 与 PR 两种事件形态。"""
    out = []
    for key in ("issue", "pull_request"):
        obj = payload.get(key) or {}
        if not obj:
            continue
        out.append((key + ".title", obj.get("title") or ""))
        out.append((key + ".body", obj.get("body") or ""))
    if not out:
        for key in ("title", "body"):
            if payload.get(key):
                out.append((key, payload[key] or ""))
    return out


def scan(payload, root="."):
    rules = load_rules(root)
    hits = []
    for field, text in _collect(payload):
        for rule in rules:
            for m in rule["regex"].finditer(text):
                hits.append({
                    "field": field,
                    "category": rule["category"],
                    "rule": rule["id"],
                    "match": _mask(m.group(0), rule["category"]),
                    "why": rule["why"],
                })
    return {"hits": hits, "matched": bool(hits),
            "categories": sorted({h["category"] for h in hits})}


def main(argv=None):
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="Issue/PR 敏感内容检测（打标 + 提示转私密）")
    ap.add_argument("--payload", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--github-output", default=None)
    args = ap.parse_args(argv)
    try:
        with open(args.payload, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError) as exc:
        print("[ERROR] payload 读取失败：%s" % exc)
        return 2
    res = scan(payload, args.root)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write("matched=%s\n" % ("true" if res["matched"] else "false"))
            fh.write("categories=%s\n" % ",".join(res["categories"]))
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("敏感扫描：%d 处命中" % len(res["hits"]))
        for h in res["hits"]:
            print("  [%s] %s -> %s" % (h["category"], h["field"], h["match"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
